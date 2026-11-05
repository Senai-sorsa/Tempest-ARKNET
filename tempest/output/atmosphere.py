"""One call from a place and time to a coupled atmosphere (the "mode 4 / climate" path of the tool, inside the pilot box).

    python -m tempest.output.atmosphere --lat 32.99 --lon -106.97 --when "2027-06-16 15:00" --n 1024 --out out_dir

Steps, all on whole samples:
  1. features from place, date and solar time; the climate indices come from the latest records for dates they cover, and from the joint ridge
     forecast (ingest.index_forecast) for dates ahead (beyond 12 months the 12-month draw is used);
  2. generator samples (m = 199 per group) drawn with one index draw per sample, then the range calibration;
  3. vertical wind from the w-head, given each sampled atmosphere;
  4. 10 m peak gust parameters (gust model, wind-only variant) from each sample's own 10 m wind;
  5. 24 h soak history from the diurnal library (training years only), matched to each sample's launch t2m;
  6. output.coupled writes atmosphere_samples.npz / atmosphere_coupling.npz / atmosphere_coupling.toml.
Not filled (stay NaN, listed in the metadata): w_sigma, w_turb (thermals need sensible heat flux, ASK_LATER 5). Gust parameters exist only at 10 m
(the other near-ground heights stay NaN: no gust profile law has been fitted). Times are UTC unless the string carries an offset; a naive time is local
SOLAR time at the longitude (no timezone database is used here).
"""
import argparse
import os

import numpy as np
import pandas as pd
import torch
import xarray as xr

from tempest.calibrate import spread
from tempest.generator import features as feat
from tempest.generator import sample as sample_mod
from tempest.generator.sample import Sampler
from tempest.generator.train import load_npz
from tempest.gust import model as gm
from tempest.ingest import index_forecast, indices
from tempest.output import blend, coupled, soak
from tempest.output.whead import head_inputs
from tempest.profiles.to_heights import HEIGHTS

M_CAL = 199
BOX = dict(lat=(31.0, 34.0), lon=(-108.0, -101.0))


def solar_time(when, lon):
    """-> (UTC timestamp, solar hour). Aware strings are taken as given; naive ones are local solar time."""
    t = pd.Timestamp(when)
    if t.tzinfo is None:
        return t - pd.Timedelta(hours=lon / 15.0), t.hour + t.minute / 60
    t_utc = t.tz_convert("UTC").tz_localize(None)
    return t_utc, (t_utc.hour + t_utc.minute / 60 + lon / 15.0) % 24


class Atmosphere:
    def __init__(self, model, calib, data, head=None, gust="models/gust_model.npz", surface="data/pilot/surface_hourly.zarr",
                 profiles="data/pilot/profiles80.zarr", indices_root="data/raw/indices", lib_years=(1991, 2023), device="cpu"):
        self.sampler = Sampler(torch.load(model, map_location="cpu", weights_only=True), device=device)
        self.cal = spread.load(calib, model)
        load_npz(data)  # activates the dataset's feature list and humidity target
        self.head = Sampler(torch.load(head, map_location="cpu", weights_only=True), device=device) if head else None
        g = np.load(gust) if gust else None
        self.gust = dict(theta=g["wind_theta"], phi=g["wind_phi"]) if g is not None else None
        ds = xr.open_zarr(profiles)
        self.pt_lat, self.pt_lon, self.pt_elev = ds.lat.values, ds.lon.values, ds.z_sfc.values
        self.surface = xr.open_zarr(surface) if surface else None
        self.lib = soak.Library(self.surface, *lib_years) if self.surface is not None else None
        self.table = indices.load(indices_root)
        self.gm_table = indices.gmst_table(indices_root) if "gmst" in feat.FEATURES else None

    def drivers(self, t_utc, n, rng):
        """(n, 4) oni, wwv, qbo30, qbo50 draws for the month of t_utc."""
        month = t_utc.to_period("M").to_timestamp()
        known = self.table.dropna(subset=["oni", "qbo30", "qbo50", "wwv"])
        if month <= known.index[-1]:
            row = known.loc[month, ["oni", "wwv", "qbo30", "qbo50"]].to_numpy(float)
            return np.tile(row, (n, 1)), "observed"
        horizon = int(min(12, (month.year - known.index[-1].year) * 12 + month.month - known.index[-1].month))
        d = index_forecast.draw(known, known.index[-1], horizon, n, rng)  # columns in indices.COLS order: oni, qbo30, qbo50, wwv
        return d[:, [0, 3, 1, 2]], f"ridge forecast, {horizon} months ahead"

    def sample(self, lat, lon, when, n=1024, seed=0, tau_hours=6.0):
        box = dict(lat=(float(self.pt_lat.min()), float(self.pt_lat.max())), lon=(float(self.pt_lon.min()), float(self.pt_lon.max())))      # the grid defines the trained area
        if not (box["lat"][0] <= lat <= box["lat"][1] and box["lon"][0] <= lon <= box["lon"][1]):
            raise ValueError(f"({lat}, {lon}) is outside the trained area {box}")
        rng = np.random.default_rng(seed)
        torch.manual_seed(seed)
        t_utc, sh = solar_time(when, lon)
        if not 6.0 <= sh <= 21.0:
            raise ValueError(f"solar time {sh:.1f} h is outside the trained 06-21 h window")
        p = int(np.argmin((self.pt_lat - lat) ** 2 + (self.pt_lon - lon) ** 2))      # nearest point, reported
        pts, wts = blend.bilinear(self.pt_lat, self.pt_lon, lat, lon)                 # F-6: bilinear over the four surrounding points
        elev = float(np.dot(wts, self.pt_elev[pts]))                                  # the site (bilinear grid elevation)
        groups = int(np.ceil(n / M_CAL))
        total = groups * M_CAL
        row_pt = np.repeat(np.repeat(pts, blend.allocate(wts, groups, rng)), M_CAL)    # every range-map block comes from one point, blocks allocated by the weights
        elev_row = self.pt_elev[row_pt].astype(float)
        drv, drv_note = self.drivers(t_utc, total, rng)
        doy = t_utc.dayofyear
        extras_kw = {}
        if "gmst" in feat.FEATURES:
            extras_kw = indices.feature_extras(feat.FEATURES, self.table, self.gm_table, pd.DatetimeIndex([t_utc]))
            extras_kw = {k: np.repeat(v, total) for k, v in extras_kw.items()}
        cond = feat.features(self.pt_lat[row_pt], self.pt_lon[row_pt], elev_row, elev_row, doy, sh, t_utc.year, drv[:, 0], drv[:, 1], drv[:, 2], drv[:, 3], **extras_kw)
        phys = spread.apply(self.cal, self.sampler.profiles(cond).reshape(groups, M_CAL, -1)).reshape(total, -1)[:n]
        cond = cond[:n]
        extras = {}
        notes = ["indices: " + drv_note]
        if self.head is not None:
            extras["w"] = self.head(head_inputs(cond, phys)).astype(np.float32)
        phys = sample_mod.to_site(phys, elev_row[:n], elev)                              # temperature, pressure, humidity to the site (the w head above saw grid-elevation inputs)
        if self.gust is not None:
            u10, v10 = phys[:, 0], phys[:, len(HEIGHTS)]
            X = gm.design(np.hypot(u10, v10), np.full(n, doy), np.full(n, gm.utc_hour(t_utc)), station=np.full(n, gm.station_flag(lat, lon)))   # fitted with UTC hour and the nearer ASOS site
            mu, beta = gm.params(self.gust, X)
            gmu, gbeta = np.full((n, 5), np.nan, np.float32), np.full((n, 5), np.nan, np.float32)
            gmu[:, 0], gbeta[:, 0] = mu, beta
            extras["gust_mu"], extras["gust_beta"] = gmu, gbeta
            notes.append("gust parameters at 10 m only")
        if self.lib is not None:
            hist = self.lib.draw(p, t_utc.round("h"), phys[:, 176], rng)
            extras["soak_t2m"], extras["soak_ssrd"], extras["soak_wind10"] = (h.astype(np.float32) for h in hist)
            extras["T_soak"] = soak.t_soak(hist[0], tau_hours).astype(np.float32)
            notes.append(f"T_soak tau = {tau_hours:g} h (a setting)")
        arrays, meta = coupled.build(phys, elev, np.column_stack([drv[:n], np.full(n, t_utc.year)]),
                                     query=dict(lat=lat, lon=lon, when=str(when), valid_utc=str(t_utc), solar_hour=sh, grid_point=p, n=n, seed=seed), extras=extras)
        meta["notes"] = notes
        return arrays, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--when", required=True)
    ap.add_argument("--n", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="models/generator_80_p2f.pt")
    ap.add_argument("--calib", default="models/generator_80_p2f.calib2021.npz")
    ap.add_argument("--data", default="data/train/pilot80_dpd.npz")
    ap.add_argument("--head", default="models/whead.pt")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    atm = Atmosphere(a.model, a.calib, a.data, head=a.head if os.path.exists(a.head) else None)
    arrays, meta = atm.sample(a.lat, a.lon, a.when, a.n, a.seed)
    paths = coupled.write(a.out, arrays, meta)
    print(paths, meta["notes"], "placeholders:", meta["placeholders"])


if __name__ == "__main__":
    main()
