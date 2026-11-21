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


LAPSE_BINS = np.array([0.0, 4.0, 7.0, 9.0])       # K/km between 2 m and the lowest level above ground: inversion | stable | neutral | unstable | super-adiabatic
DEFAULT_BL = dict(ratio=np.full(len(LAPSE_BINS) + 1, 1.4), dpd_a=0.0, dpd_b=1.0)   # u100 / u10 per bin; dewpoint depression at 2 m = a + b x depression at the lowest level


def boundary_inputs(h, case, lead, la, lo, z_sfc):
    """Quantities of the lowest level above ground used by the boundary-layer approximations: (lapse K/km 2 m -> level, dewpoint depression K at that level)."""
    g = lambda name: h[name].values[case, lead, :, la, lo] if h[name].ndim == 5 else h[name].values[case, lead, la, lo]
    lev = h.level.values.astype(float)
    t, q, z, t2m = g("t"), g("q"), g("z"), g("t2m")
    agl = z / 9.80665 - (z_sfc / 9.80665)[:, None]
    low = np.where(agl > 0, agl, np.inf).argmin(1)
    ar = np.arange(len(t))
    t_low, agl_low = t[ar, low], agl[ar, low]
    r_low = np.clip(rh_from_q(q[ar, low], t_low, lev[low] * 100.0), 1.0, 100.0)
    lapse = (t2m - t_low) / np.maximum(agl_low / 1000.0, 0.05)
    return lapse, t_low - _td_from_rh(t_low, r_low), low


def forecast_profiles(h, case, lead, la, lo, z_sfc, bl=None):
    """HRES dataset h, index arrays case, lead (position in prediction_timedelta), la, lo (grid indices), z_sfc (n,) surface GEOPOTENTIAL (m2/s2) -> dict of (n, 44) profiles.
    bl: boundary-layer tables (dict ratio, dpd_a, dpd_b; see fit_boundary_layer) for wind at 100 m and the 2 m dew point; default = neutral log law and constant dew point."""
    bl = bl or DEFAULT_BL
    g = lambda name: h[name].values[case, lead, :, la, lo] if h[name].ndim == 5 else h[name].values[case, lead, la, lo]
    lev = h.level.values.astype(float)
    t, u, v, q, z = g("t"), g("u"), g("v"), g("q"), g("z")
    r = rh_from_q(q, t, lev[None, :] * 100.0)
    u10, v10, t2m = g("u10"), g("v10"), g("t2m")
    lapse, dpd_low, _ = boundary_inputs(h, case, lead, la, lo, z_sfc)
    ratio = np.asarray(bl["ratio"])[np.digitize(lapse, LAPSE_BINS)]
    d2m = t2m - np.clip(bl["dpd_a"] + bl["dpd_b"] * dpd_low, 0.0, 60.0)
    prof, _ = profiles_from_levels(z, u, v, t, r, z_sfc, u10, v10, ratio * u10, ratio * v10, t2m, d2m)
    return prof


def load_year(year, ds, hres_dir="data/raw/wb2_hres", n_points=60, seed=0, bl=None):
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
    lo_all = np.round((h.longitude.values[None, :] - pn[:, None] + 180.0) % 360.0 - 180.0, 3) == 0
    assert la_all.any(1).all() and lo_all.any(1).all(), "a store point has no matching HRES grid latitude / longitude (argmax would silently pick index 0)"
    assert (la_all.sum(1) == 1).all() and (lo_all.sum(1) == 1).all(), "duplicate HRES grid matches"
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
    hp = forecast_profiles(h, case, lead, pt_la[pt], pt_lo[pt], zs[pt] * 9.80665, bl)   # the store keeps z_sfc in metres, the converter wants geopotential
    lapse, dpd_low, _ = boundary_inputs(h, case, lead, pt_la[pt], pt_lo[pt], zs[pt] * 9.80665)
    ti = np.searchsorted(vt, valid[case, lead])
    obs = np.stack([truth[v][pt, ti] for v in PROFILE], 1)                    # (n, 4, 44)
    hres = np.stack([hp[v] for v in PROFILE], 1)
    ok = np.isfinite(obs).all((1, 2)) & np.isfinite(hres).all((1, 2))
    doy = pd.DatetimeIndex(valid[case, lead]).dayofyear.to_numpy()
    out = dict(year=np.full(len(case), year), valid=valid[case, lead], lead_days=leads[lead], lat=pl[pt], lon=pn[pt], z_sfc=zs[pt], doy=doy, hres=hres.astype(np.float32),
               obs=obs.astype(np.float32), init_day=pd.DatetimeIndex(init[case]).dayofyear.to_numpy(), lapse_low=lapse.astype(np.float32), dpd_low=dpd_low.astype(np.float32))
    return {k: v[ok] for k, v in out.items()}


def load_year_v2(year, ds, hres_dir="data/raw/wb2_hres_v2", n_points=16, seed=0, bl=None, starts=("00z", "12z")):
    """F-V2 (2026-11-10): rows like load_year from the 00Z + 12Z refetch (monthly files `<yyyymm>_<start>.nc`, prediction_timedelta in HOURS, valid 00 / 12 / 18 UTC).
    Extra fields: lead_hours, start_hour (0 / 12 UTC), valid_utc_hour; lead_days becomes lead_hours / 24 (fractional). Valid times the ERA5 store lacks are dropped.
    n_points grid points are drawn per forecast and lead (30 leads per start, so 16 points give about as many rows per year as the old 60 x 4 leads x 2)."""
    import os
    parts = []
    for mo in range(1, 13):
        for st in starts:
            f = f"{hres_dir}/{year}{mo:02d}_{st}.nc"
            if not os.path.exists(f):
                continue
            h = xr.open_dataset(f)
            init = h.time.values
            td = h.prediction_timedelta.values.astype("timedelta64[h]")
            valid = init[:, None] + td[None, :]
            vt = np.unique(valid.ravel())
            tidx = ds.get_index("time").get_indexer(vt)
            vt = vt[tidx >= 0]
            tidx = tidx[tidx >= 0]
            if not len(vt):
                continue
            truth = {v: ds[v].isel(time=tidx).values for v in PROFILE}
            pl, pn = ds.lat.values, ds.lon.values
            la_all = np.round((h.latitude.values[None, :] - pl[:, None]), 3) == 0
            lo_all = np.round((h.longitude.values[None, :] - pn[:, None] + 180.0) % 360.0 - 180.0, 3) == 0
            assert la_all.any(1).all() and lo_all.any(1).all(), "a store point has no matching HRES grid latitude / longitude"
            assert (la_all.sum(1) == 1).all() and (lo_all.sum(1) == 1).all(), "duplicate HRES grid matches"
            pt_la, pt_lo = la_all.argmax(1), lo_all.argmax(1)
            zs = ds.z_sfc.values.astype(float)
            rng = np.random.default_rng(seed + year * 100 + mo * 2 + (st == "12z"))
            ok_v = np.isin(valid, vt)
            cc, jj = np.nonzero(ok_v)
            case = np.repeat(cc, n_points)
            lead = np.repeat(jj, n_points)
            pt = np.concatenate([rng.choice(len(pl), n_points, replace=False) for _ in range(len(cc))]) if len(cc) else np.zeros(0, int)
            if not len(case):
                continue
            hp = forecast_profiles(h, case, lead, pt_la[pt], pt_lo[pt], zs[pt] * 9.80665, bl)
            lapse, dpd_low, _ = boundary_inputs(h, case, lead, pt_la[pt], pt_lo[pt], zs[pt] * 9.80665)
            ti = np.searchsorted(vt, valid[case, lead])
            obs = np.stack([truth[v][pt, ti] for v in PROFILE], 1)
            hres = np.stack([hp[v] for v in PROFILE], 1)
            ok = np.isfinite(obs).all((1, 2)) & np.isfinite(hres).all((1, 2))
            vv = valid[case, lead]
            lh = td[lead].astype(int)
            out = dict(year=np.full(len(case), year), valid=vv, lead_days=(lh / 24.0).astype(np.float32), lead_hours=lh, start_hour=np.full(len(case), 12 if st == "12z" else 0),
                       valid_utc_hour=(vv.astype("datetime64[h]").astype(np.int64) % 24), lat=pl[pt], lon=pn[pt], z_sfc=zs[pt], doy=pd.DatetimeIndex(vv).dayofyear.to_numpy(),
                       hres=hres.astype(np.float32), obs=obs.astype(np.float32), init_day=pd.DatetimeIndex(init[case]).dayofyear.to_numpy(), lapse_low=lapse.astype(np.float32),
                       dpd_low=dpd_low.astype(np.float32))
            parts.append({k: v[ok] for k, v in out.items()})
            h.close()
    if not parts:
        raise FileNotFoundError(f"no {hres_dir}/{year}MM_<start>.nc files with valid times in the ERA5 store")
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def lead_bin(lead_days):
    """F-V2: the tested lead (1, 3, 5, 7 days) each lead belongs to: < 2 d -> 1, 2-4 -> 3, 4-6 -> 5, 6-7.5 -> 7, beyond 7.5 d -> 0 (not used). Whole-day leads 1 / 3 / 5 / 7 map to themselves."""
    x = np.asarray(lead_days, float)
    return np.where(x < 2.0, 1, np.where(x < 4.0, 3, np.where(x < 6.0, 5, np.where(x <= 7.5, 7, 0)))).astype(int)


def solar_hour(d):
    """Mean solar hour of each row's valid time (UTC hour + lon / 15)."""
    return (np.asarray(d["valid_utc_hour"], float) + np.asarray(d["lon"], float) / 15.0) % 24.0


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


def fit_boundary_layer(rows):
    """Tables for the two boundary-layer approximations from training rows (dict from load_year, concatenated): median |wind 100 m| / |wind 10 m| of the ERA5 truth per
    lapse-rate bin, and a straight line from the forecast's dewpoint depression at the lowest level to the truth's at 10 m (the 2 m value in all but name)."""
    obs = rows["obs"]
    w10, w100 = np.hypot(obs[:, 0, 0], obs[:, 1, 0]), np.hypot(obs[:, 0, 2], obs[:, 1, 2])
    ok = w10 > 1.0
    b = np.digitize(rows["lapse_low"], LAPSE_BINS)
    ratio = np.array([np.median((w100 / np.maximum(w10, 1e-6))[ok & (b == k)]) if (ok & (b == k)).sum() > 100 else 1.4 for k in range(len(LAPSE_BINS) + 1)])
    td = _td_from_rh(obs[:, 2, 0], obs[:, 3, 0])
    dpd_true = np.clip(obs[:, 2, 0] - td, 0, 60)
    x = rows["dpd_low"]
    good = np.isfinite(x) & np.isfinite(dpd_true) & (x < 60)
    bb, aa = np.polyfit(x[good], dpd_true[good], 1)
    return dict(ratio=ratio, dpd_a=float(aa), dpd_b=float(bb))
