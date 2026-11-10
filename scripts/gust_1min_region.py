"""IL-183 (2026-11-10): a region's PHYSICAL gust law from ASOS one-minute data, the W8d recipe of scripts/gust_1min.py for any stations (no METAR join: the 2-minute wind of the one-minute
file is the measured wind). Physical gust = highest 5-second peak in the 10 minutes up to the :53 report minute; model wind = ERA5 10 m wind of the station's grid point from a raw hourly
store (u10.zarr, v10.zarr). Two Gumbel laws (location / log-scale linear in 1, min(ws,20), min(ws,20)^2/10, season, UTC hour, station = 0: one pooled law for the region), fitted <= 2020,
validated 2021-23 against the physical gust (CRPS, 90 % coverage, median factor) next to the BUILT-IN NM/TX laws applied here (station flag 0 and 1), plus a cross-station check
(fit on the first station only, score the others). Writes the npz that `export_tool --gust-phys` reads (model_*, measured_*, caps as the built-in laws, station 0).
    PYTHONPATH=. python -W ignore scripts/gust_1min_region.py --stations DEN:39.8466,-104.6562 APA:39.5701,-104.8493 --onemin data/raw/asos1min_denver
                                                              --era5 data/raw/era5_em_denver_full --out models/gust_phys_den.npz"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_1min import physical_hourly   # noqa: E402
from gust_measured_fit import feats, fit_gumbel   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402


def era5_wind(era5_dir, lat, lon, times):
    u = xr.open_zarr(os.path.join(era5_dir, "u10.zarr"))["u10"]
    v = xr.open_zarr(os.path.join(era5_dir, "v10.zarr"))["v10"]
    glon = np.where(u.longitude.values > 180, u.longitude.values - 360, u.longitude.values)
    i, j = int(np.abs(u.latitude.values - lat).argmin()), int(np.abs(glon - lon).argmin())
    t = pd.DatetimeIndex(u.valid_time.values)
    ix = t.get_indexer(times)
    ok = ix >= 0
    ws = np.full(len(times), np.nan)
    uu, vv = u.isel(latitude=i, longitude=j).values, v.isel(latitude=i, longitude=j).values
    ws[ok] = np.hypot(uu[ix[ok]], vv[ix[ok]])
    return ws


def score(name, x, g, w):
    out = []
    for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 40), (2, 40)):
        b = (w >= lo) & (w < hi)
        if b.sum() < 30:
            continue
        c = crps_ensemble(x[b][..., None], g[b][:, None])[:, 0].mean()
        cv = coverage90(x[b][..., None], g[b][:, None], 0.9)[:, 0].mean()
        out.append(f"{lo}-{hi}: {c:.2f}/{cv:.2f}/{np.median(np.median(x[b], 1) / w[b]):.2f} ({np.median(g[b] / w[b]):.2f})")
    print(f"  {name:58s} " + "  ".join(out), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", nargs="+", required=True, help="ID:lat,lon (one-minute files <onemin>/<ID>_<year>.csv)")
    ap.add_argument("--onemin", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for spec in a.stations:
        sid, ll = spec.split(":")
        lat, lon = map(float, ll.split(","))
        files = sorted(glob.glob(os.path.join(a.onemin, f"{sid}_*.csv")))
        h = pd.concat([physical_hourly(f) for f in files])
        h = h[~h.index.duplicated()]
        h["ws_era"] = era5_wind(a.era5, lat, lon, h.index)
        h["sid"] = sid
        rows.append(h)
        print(f"{sid}: {len(h)} routine hours from {len(files)} files", flush=True)
    m = pd.concat(rows)
    m = m[(m.ws1 >= 2.0) & (m.gphys >= m.ws1) & np.isfinite(m.ws_era)]
    t = pd.DatetimeIndex(m.index)
    doy, hr, yr = t.dayofyear.to_numpy(), (t.hour + t.minute / 60).to_numpy(), t.year.to_numpy()
    wo, g, era, sid = m.ws1.values, m.gphys.values, m.ws_era.values, m.sid.values
    st = np.zeros(len(m))
    fit, val = yr <= 2020, (yr >= 2021) & (yr <= 2023)
    print(f"joined: {len(m)} hours, fit <= 2020 {int(fit.sum())}, validation 2021-23 {int(val.sum())}; median physical gust factor {np.median(g / wo):.2f}", flush=True)
    Xm, Xe = feats(wo, doy, hr, st, "add2")[1], feats(era, doy, hr, st, "add2")[1]
    lm, le = fit_gumbel(Xm[fit], g[fit]), fit_gumbel(Xe[fit], g[fit])
    rng = np.random.default_rng(0)
    L = -np.log(-np.log(rng.random((int(val.sum()), 199)).clip(1e-12, 1 - 1e-12)))
    wv, gv = wo[val], g[val]
    dr = lambda mu, beta: np.maximum(mu[:, None] + beta[:, None] * L, wv[:, None])
    print("\nvalidation 2021-23, truth = PHYSICAL gust: CRPS / cov90 / median factor (observed) by band of the measured wind", flush=True)
    for flag in (0.0, 1.0):
        score(f"built-in NM/TX law, measured wind, station {flag:.0f}", dr(*api._gust_physical(api.GUST_PHYS_MEASURED, api.GUST_MEASURED_WS_CAP, wv, doy[val], hr[val], flag)), gv, wv)
    score("REGION law, measured wind", dr(Xm[val] @ lm[0], np.exp(np.clip(Xm[val] @ lm[1], -6, 4))), gv, wv)
    for flag in (0.0, 1.0):
        score(f"built-in NM/TX law, ERA5 wind, station {flag:.0f}", dr(*api._gust_physical(api.GUST_PHYS_MODEL, api.GUST_PHYS_MODEL_CAP, era[val], doy[val], hr[val], flag)), gv, wv)
    score("REGION law, ERA5 wind", dr(Xe[val] @ le[0], np.exp(np.clip(Xe[val] @ le[1], -6, 4))), gv, wv)
    first = a.stations[0].split(":")[0]
    if len(a.stations) > 1:
        f1 = fit & (sid == first)
        le1 = fit_gumbel(Xe[f1], g[f1])
        o = val & (sid != first)
        L2 = -np.log(-np.log(rng.random((int(o.sum()), 199)).clip(1e-12, 1 - 1e-12)))
        x = np.maximum((Xe[o] @ le1[0])[:, None] + np.exp(np.clip(Xe[o] @ le1[1], -6, 4))[:, None] * L2, wo[o][:, None])
        print(f"\ncross-station: ERA5-wind law fitted on {first} only, scored on the other station(s) 2021-23", flush=True)
        score(f"law from {first}, other station(s)", x, g[o], wo[o])
    np.savez(a.out, model_theta=le[0], model_phi=le[1], model_cap=api.GUST_PHYS_MODEL_CAP, measured_theta=lm[0], measured_phi=lm[1], measured_cap=api.GUST_MEASURED_WS_CAP, station=0.0,
             stations=np.array(a.stations), fit_years="<= 2020")
    print("\nwrote", a.out, "\n  model theta", np.round(le[0], 5).tolist(), "\n  measured theta", np.round(lm[0], 5).tolist(), flush=True)


if __name__ == "__main__":
    main()
