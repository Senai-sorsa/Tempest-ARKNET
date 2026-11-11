"""N2 full run (New_Plan 10.4): Mode F rows at the 7,483 world points, same format as data/modeF_v2/<year>.npz (fields used by the trainer:
year, valid, lead_days, lead_hours, lat, lon, z_sfc (m), doy, hres (n, 4, 44), obs (n, 4, 44)).
Forecast = world HRES store data/raw/wb2_hres_global (13 pressure levels + u10 / v10 / t2m), turned into 44 heights by the shipped
modeF.forecast_profiles with the shipped boundary-layer tables (models/modeF_bl.npz), as the box rows. Truth = world ERA5 store
data/raw/era5_global through profiles.to_heights.profiles_from_levels, as the box truth store. Leads beyond 7.5 d are dropped (the trainer drops them too).
The stores have no orography: ground height per point = ERA5 geopotential interpolated in ln p to the surface pressure, median over the first year built.
`--points` points drawn per HRES record (one valid time and lead). IGRA holdouts are already out of the store. Never 2026.
    PYTHONPATH=. .venv/Scripts/python -W ignore -u scripts/il6_build_world.py --years 2016-2020 --points 150
    smoke: ... --years 2016 --months 1 --points 5 --out data/modeF_world_smoke
Writes <out>/<year>.npz; a year already written is skipped (resumable).
"""
import argparse
import os

import numpy as np
import pandas as pd
import xarray as xr

from tempest.forecast import modeF
from tempest.profiles.to_heights import profiles_from_levels

G = 9.80665
HRES, ERA5 = "data/raw/wb2_hres_global", "data/raw/era5_global"


def decode(f, name, code=None):
    """int16 store field -> float32 physical value (codes 'name scale offset'; the ERA5 month files keep theirs in points.npz)."""
    s, o = {c.split()[0]: c.split()[1:] for c in (f["code"] if code is None else code)}[name]
    return f[name].astype(np.float32) * np.float32(s) + np.float32(o)


def ground_geopotential(z, lev_hpa, sp):
    """z (..., L) geopotential on levels lev_hpa (L,), sp (...) Pa -> (...) geopotential at the surface, linear in ln p (extrapolated below the lowest level)."""
    o = np.argsort(lev_hpa)
    lp = np.log(np.asarray(lev_hpa, float)[o] * 100.0)
    z = z[..., o]
    k = np.clip(np.searchsorted(lp, np.log(sp)), 1, len(lp) - 1)
    z0, z1 = np.take_along_axis(z, (k - 1)[..., None], -1)[..., 0], np.take_along_axis(z, k[..., None], -1)[..., 0]
    w = (np.log(sp) - lp[k - 1]) / (lp[k] - lp[k - 1])
    return z0 + w * (z1 - z0)


def era5_months(months):
    """ERA5 monthly files covering `months` ('YYYY-MM') -> dict field -> concatenated array, plus 'valid_time'."""
    parts = [np.load(f"{ERA5}/{m}.npz") for m in months if os.path.exists(f"{ERA5}/{m}.npz")]
    code = np.load(f"{ERA5}/points.npz")["code"]
    out = {n: np.concatenate([decode(p, n, code) for p in parts]) for n in ("u", "v", "t", "r", "z", "u10", "v10", "u100", "v100", "t2m", "d2m", "sp")}
    out["valid_time"] = np.concatenate([p["valid_time"] for p in parts])
    out["level"] = parts[0]["pressure_level"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2016-2020")
    ap.add_argument("--points", type=int, default=150)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--max-lead-h", type=int, default=180)
    ap.add_argument("--out", default="data/modeF_world")
    ap.add_argument("--bl", default="models/modeF_bl.npz")
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-")) if "-" in a.years else (int(a.years),) * 2
    assert y1 < 2026, "never 2026"
    os.makedirs(a.out, exist_ok=True)
    bl = dict(np.load(a.bl)) if os.path.exists(a.bl) else None
    pts = np.load(f"{HRES}/points.npz")
    plat, plon = pts["lat"].astype(np.float32), pts["lon"].astype(np.float32)
    zs_path = f"{a.out}/z_sfc.npy"
    if os.path.exists(zs_path):
        zsg = np.load(zs_path)
    else:
        e = era5_months([f"{y0}-{m:02d}" for m in range(1, 13)])
        zsg = np.median(ground_geopotential(np.moveaxis(e["z"], 1, -1), e["level"], e["sp"]), 0).astype(np.float32)   # (P,) geopotential
        np.save(zs_path, zsg)
    print(f"ground height: median {np.median(zsg) / G:.0f} m, max {zsg.max() / G:.0f} m, {len(zsg)} points; boundary tables {'shipped' if bl else 'default'}", flush=True)
    for year in range(y0, y1 + 1):
        dst = f"{a.out}/{year}.npz"
        if os.path.exists(dst):
            print(f"{year}: exists, skipped", flush=True)
            continue
        rows = []
        for mo in range(1, a.months + 1):
            f = np.load(f"{HRES}/{year}{mo:02d}.npz")
            keep = np.flatnonzero(f["lead_h"] <= a.max_lead_h)
            nxt = pd.Timestamp(year, mo, 1) + pd.offsets.MonthBegin(1)
            e = era5_months([f"{year}-{mo:02d}", nxt.strftime("%Y-%m")])
            ti = pd.Index(e["valid_time"]).get_indexer(f["valid"][keep])
            keep, ti = keep[ti >= 0], ti[ti >= 0]
            rng = np.random.default_rng(year * 100 + mo)
            P = len(plat)
            rec = np.repeat(keep, a.points)
            tix = np.repeat(ti, a.points)
            pt = np.concatenate([rng.choice(P, a.points, replace=False) for _ in keep])
            lev = f["level"]
            hx = {n: decode(f, n) for n in ("u", "v", "t", "q", "z")}
            sx = {n: decode(f, n) for n in ("u10", "v10", "t2m")}
            n = len(rec)
            # fake (time, lead, level, lat, lon) grid of size (n, 1, 13, 1, 1) so the shipped forecast_profiles runs unchanged
            h = xr.Dataset({k: (("time", "lead", "level", "lat", "lon"), v[rec, :, pt][:, None, :, None, None]) for k, v in hx.items()}
                           | {k: (("time", "lead", "lat", "lon"), v[rec, pt][:, None, None, None]) for k, v in sx.items()}, coords={"level": lev})
            z0 = np.zeros(n, int)
            hp = modeF.forecast_profiles(h, np.arange(n), z0, z0, z0, zsg[pt].astype(float), bl)
            lapse, dpd_low, _ = modeF.boundary_inputs(h, np.arange(n), z0, z0, z0, zsg[pt].astype(float))
            g3 = lambda k: e[k][tix, :, pt]
            g2 = lambda k: e[k][tix, pt]
            tp, _ = profiles_from_levels(g3("z"), g3("u"), g3("v"), g3("t"), g3("r"), zsg[pt], g2("u10"), g2("v10"), g2("u100"), g2("v100"), g2("t2m"), g2("d2m"))
            hres = np.stack([hp[v] for v in modeF.PROFILE], 1).astype(np.float32)
            obs = np.stack([tp[v] for v in modeF.PROFILE], 1).astype(np.float32)
            ok = np.isfinite(hres).all((1, 2)) & np.isfinite(obs).all((1, 2))
            vv = f["valid"][rec]
            lh = f["lead_h"][rec]
            assert (vv.astype("datetime64[Y]").astype(int) + 1970 < 2026).all()
            out = dict(year=np.full(n, year), valid=vv, lead_days=(lh / 24.0).astype(np.float32), lead_hours=lh, start_hour=f["start"][rec].astype("datetime64[h]").astype(np.int64) % 24,
                       valid_utc_hour=vv.astype("datetime64[h]").astype(np.int64) % 24, lat=plat[pt], lon=plon[pt], z_sfc=(zsg[pt] / G).astype(np.float32),
                       doy=pd.DatetimeIndex(vv).dayofyear.to_numpy(), hres=hres, obs=obs, lapse_low=lapse.astype(np.float32), dpd_low=dpd_low.astype(np.float32))
            rows.append({k: v[ok] for k, v in out.items()})
            print(f"{year}-{mo:02d}: {len(keep)} records, {ok.sum():,} / {n:,} rows finite", flush=True)
        d = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}
        np.savez(dst + ".tmp.npz", **d)
        os.replace(dst + ".tmp.npz", dst)
        print(f"{year}: {len(d['obs']):,} rows -> {dst}", flush=True)


def _selfcheck():
    lev = np.array([50, 100, 200, 500, 850, 1000.0])
    zz = 8000.0 * G * np.log(101325.0 / (lev * 100.0))          # isothermal atmosphere: z linear in ln p
    for sp in (101325.0, 85000.0, 103000.0):
        assert abs(ground_geopotential(zz[None], lev, np.array([sp]))[0] - 8000.0 * G * np.log(101325.0 / sp)) < 1e-6 * G * 8000


_selfcheck()
if __name__ == "__main__":
    main()
