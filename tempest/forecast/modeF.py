"""Mode F (IL-73): an archived forecast turned into a distribution of the 44-height profile.

HRES pressure-level fields on the pilot box (WeatherBench2, data/raw/wb2_hres, 00 UTC starts, leads 1/3/5/7 days) are converted to the same u, v, T, RH profile
on 44 heights as the ERA5 store (tempest.profiles.to_heights.profiles_from_levels). Not in the archive and therefore approximated, the same way everywhere:
wind at 100 m = 1.4 x wind at 10 m (neutral log law, z0 about 0.1 m), 2 m dew point from the RH of the lowest level above ground, RH from specific humidity with the
IFS mixed-phase formula (tempest.ingest.arco_fill.rh_from_q). A residual network (same engression machinery as mode P) learns truth - forecast profile from the
forecast profile itself, the lead time, the day of year and the place; a range map fitted on a later year makes the 99 % range hold.
"""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.ingest.arco_fill import rh_from_q
from tempest.profiles.to_heights import HEIGHTS, PROFILE, profiles_from_levels

NV, NH = len(PROFILE), len(HEIGHTS)
D = NV * NH
NS_DAY = 86_400_000_000_000
COND_NAMES = ["lat", "lon", "z_sfc", "doy_sin", "doy_cos", "lead_days"] + [f"hres_{i}" for i in range(D)]


def _td_from_rh(t, rh):
    tc = t - 273.15
    rh = np.clip(rh, 1.0, 100.0) / 100.0
    g = np.log(rh) + 17.625 * tc / (243.04 + tc)
    return 243.04 * g / (17.625 - g) + 273.15


def forecast_profiles(h, case, lead, la, lo, z_sfc):
    """HRES dataset h, index arrays case, lead (position in prediction_timedelta), la, lo (grid indices), z_sfc (n,) surface GEOPOTENTIAL (m2/s2) -> dict of (n, 44) profiles."""
    g = lambda name: h[name].values[case, lead, :, la, lo] if h[name].ndim == 5 else h[name].values[case, lead, la, lo]
    lev = h.level.values.astype(float)
    t, u, v, q, z = g("t"), g("u"), g("v"), g("q"), g("z")
    r = rh_from_q(q, t, lev[None, :] * 100.0)
    u10, v10, t2m = g("u10"), g("v10"), g("t2m")
    agl = z / 9.80665 - (z_sfc / 9.80665)[:, None]
    low = np.where(agl > 0, agl, np.inf).argmin(1)
    r_low = r[np.arange(len(r)), low]
    d2m = _td_from_rh(t2m, r_low)
    prof, _ = profiles_from_levels(z, u, v, t, r, z_sfc, u10, v10, 1.4 * u10, 1.4 * v10, t2m, d2m)
    return prof


def load_year(year, ds, hres_dir="data/raw/wb2_hres", n_points=60, seed=0):
    """-> dict(year, valid (n,), lead_days (n,), lat, lon, z_sfc (n,), doy (n,), hres (n, 4, 44), obs (n, 4, 44)) for rows complete in both.
    `ds` is the opened ERA5 height-profile store (profiles80.zarr); n_points random grid points are drawn per forecast and lead."""
    h = xr.open_dataset(f"{hres_dir}/{year}.nc")
    leads = (h.prediction_timedelta.values // NS_DAY).astype(int)
    init = h.time.values
    valid = init[:, None] + leads[None, :].astype("timedelta64[D]")
    vt = np.unique(valid.ravel())
    tidx = ds.get_index("time").get_indexer(vt)
    if (tidx < 0).any():
        keep = tidx >= 0
        vt, tidx = vt[keep], tidx[keep]
    truth = {v: ds[v].isel(time=tidx).values for v in PROFILE}                 # (377, nT, 44)
    pl, pn = ds.lat.values, ds.lon.values
    la_all = np.round((h.latitude.values[None, :] - pl[:, None]), 3) == 0
    lo_all = np.round((h.longitude.values[None, :] - 360.0 - pn[:, None]), 3) == 0
    pt_la, pt_lo = la_all.argmax(1), lo_all.argmax(1)                          # grid index of each store point
    zs = ds.z_sfc.values.astype(float)
    rng = np.random.default_rng(seed + year)
    case, lead, pt = [], [], []
    for c in range(len(init)):
        for j in range(len(leads)):
            if np.isin(valid[c, j], vt):
                p = rng.choice(len(pl), n_points, replace=False)
                case += [c] * n_points
                lead += [j] * n_points
                pt += list(p)
    case, lead, pt = np.array(case), np.array(lead), np.array(pt)
    hp = forecast_profiles(h, case, lead, pt_la[pt], pt_lo[pt], zs[pt] * 9.80665)   # the store keeps z_sfc in metres, the converter wants geopotential
    ti = np.searchsorted(vt, valid[case, lead])
    obs = np.stack([truth[v][pt, ti] for v in PROFILE], 1)                    # (n, 4, 44)
    hres = np.stack([hp[v] for v in PROFILE], 1)
    ok = np.isfinite(obs).all((1, 2)) & np.isfinite(hres).all((1, 2))
    doy = pd.DatetimeIndex(valid[case, lead]).dayofyear.to_numpy()
    out = dict(year=np.full(len(case), year), valid=valid[case, lead], lead_days=leads[lead], lat=pl[pt], lon=pn[pt], z_sfc=zs[pt], doy=doy, hres=hres.astype(np.float32),
               obs=obs.astype(np.float32), init_day=pd.DatetimeIndex(init[case]).dayofyear.to_numpy())
    return {k: v[ok] for k, v in out.items()}


def cond_matrix(d, coarse=1):
    """Network inputs: place, season, lead, and the forecast profile (every `coarse`-th height of each variable: fewer columns, less overfitting)."""
    a = 2 * np.pi * d["doy"] / 365.25
    head = np.stack([d["lat"], d["lon"], d["z_sfc"] / 1e4, np.sin(a), np.cos(a), d["lead_days"] / 7.0], 1).astype(np.float32)
    return np.concatenate([head, d["hres"][:, :, ::coarse].reshape(len(head), -1).astype(np.float32)], 1)


def residual(d):
    return (d["obs"] - d["hres"]).reshape(len(d["obs"]), D).astype(np.float32)


def to_physical(hres_flat, res):
    """forecast profile (n, 176) + residual samples (n, m, 176) -> profile samples with RH held to 0-100 %."""
    x = hres_flat[:, None, :] + res
    i = PROFILE.index("RH") * NH
    x[..., i:i + NH] = np.clip(x[..., i:i + NH], 0, 100)
    return x
