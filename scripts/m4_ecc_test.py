"""M4: ensemble copula coupling (ECC) for forecast mode. Is the dependence structure of the IFS ensemble members better than the Schaake template of real forecast-error
profiles that mode F uses now?
Planned design (mode F marginals + ECC order) is impossible with the data on disk: mode F rows start every 4 days from 1 January (odd days of the year), the WeatherBench2 IFS ENS
runs every 8 days from 8 January (even days), so no mode F row has an ensemble run. This version keeps the question and holds the MARGINALS fixed at the ensemble's own:
for each start (IFS ENS 2022, 00z, 50 members), lead (1 / 3 / 5 / 7 d) and a sample of grid points, the members' values in each column are sorted; only the joint order differs:
  ECC        the members' own joint order (the raw ensemble),
  Schaake    ranks of 50 real HRES error profiles of the same lead (mode F training rows 2016-20; what il6_modeF.py does),
  random     independent columns (the floor).
Columns: u, v at 10 m and u, v, T at the pressure levels more than 50 m above ground (mapped to the nearest model height with the members' median geopotential). Truth: the ERA5
profile store (data/pilot/profiles.zarr, same 377 grid points) at the valid time. Scores: energy score of the standardised columns, variogram score (p = 0.5); paired bootstrap over
starts for ECC minus Schaake. 2022 is outside every fitting step used here (the error pool is 2016-20); no development-window use.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/m4_ecc_test.py [--points 60]
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.profiles.to_heights import HEIGHTS   # noqa: E402
from tempest.scoring.score import variogram_score   # noqa: E402

K, G = 50, 9.80665


def energy(x, y):
    a = np.linalg.norm(x - y[:, None], axis=-1).mean(1)
    b = np.linalg.norm(x[:, :, None] - x[:, None], axis=-1).mean((1, 2))
    return a - 0.5 * b


def ranks(a):
    return np.argsort(np.argsort(a, 0, kind="stable"), 0, kind="stable")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=int, default=60)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    tr = {k: np.concatenate([np.load(os.path.join(REPO, "data", "modeF", f"{y}.npz"))[k] for y in range(2016, 2021)]) for k in ("obs", "hres", "lead_days")}
    res_tr = (tr["obs"] - tr["hres"]).reshape(len(tr["obs"]), -1)                  # (rows, 4 x 44): u, v, T, RH error profiles
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    zlat, zlon, zsfc = z.lat.values, z.lon.values, z.z_sfc.values
    have = pd.DatetimeIndex(z.time.values)
    H = np.asarray(HEIGHTS, float)
    out = []
    for f in sorted(glob.glob(os.path.join(REPO, "data", "raw", "wb2_ifs_ens", "2022*_00z.nc"))):
        ds = xr.open_dataset(f)
        for it, t0 in enumerate(pd.DatetimeIndex(ds.time.values)):
            for lead in (1, 3, 5, 7):
                li = int(np.flatnonzero(ds.prediction_timedelta.values.astype("timedelta64[D]").astype(int) == lead)[0])
                valid = t0 + pd.Timedelta(days=lead)
                if valid not in have:
                    continue
                pts = rng.choice(len(zlat), a.points, replace=False)
                tru = {v: z[v].isel(point=pts).sel(time=valid).values for v in ("u", "v", "T")}
                pool_idx = rng.choice(np.flatnonzero(tr["lead_days"] == lead), K, replace=False)
                for j, p in enumerate(pts):
                    la = int(np.argmin(np.abs(ds.latitude.values - zlat[p])))
                    lo = int(np.argmin(np.abs(ds.longitude.values - (zlon[p] % 360))))
                    cols, mem, y = [0, 44], [ds["u10"].values[it, :, li, la, lo], ds["v10"].values[it, :, li, la, lo]], [tru["u"][j, 0], tru["v"][j, 0]]
                    zs = float(zsfc[p])
                    zs = zs / G if zs > 20000 else zs                                 # the store keeps metres; guard in case it is geopotential
                    for lv in range(len(ds.level)):
                        agl = float(np.median(ds["z"].values[it, :, li, lv, la, lo])) / G - zs
                        if agl < 50:
                            continue
                        h = int(np.argmin(np.abs(H - agl)))
                        for var, name, tk in ((0, "u", "u"), (1, "v", "v"), (2, "t", "T")):
                            cols.append(var * 44 + h)
                            mem.append(ds[name].values[it, :, li, lv, la, lo])
                            y.append(tru[tk][j, h])
                    cols, mem, y = np.array(cols), np.stack(mem, 1).astype(float), np.array(y, float)
                    if not (np.isfinite(mem).all() and np.isfinite(y).all()):
                        continue
                    srt = np.sort(mem, 0)
                    sd = np.maximum(res_tr[:, cols].std(0), 1e-6)
                    r_sch = ranks(res_tr[pool_idx][:, cols])
                    r_rnd = np.stack([rng.permutation(K) for _ in cols], 1)
                    for meth, xs in (("ECC (IFS members)", mem), ("Schaake (error profiles)", np.take_along_axis(srt, r_sch, 0)), ("random (independent)", np.take_along_axis(srt, r_rnd, 0))):
                        es = energy((xs / sd)[None], (y / sd)[None])[0]
                        vs = float(variogram_score((xs / sd)[None], (y / sd)[None])[0])
                        out.append((meth, lead, t0, p, len(cols), es, vs))
    t = pd.DataFrame(out, columns=["method", "lead", "start", "point", "ncol", "es", "vs"])
    print(f"{t.start.nunique()} IFS ENS starts in 2022, {len(t) // 3} rows (start x lead x point); columns per row median {int(t.ncol.median())}")
    print("\nmean energy score / variogram score (standardised columns; lower is better)")
    print(t.groupby(["lead", "method"])[["es", "vs"]].mean().unstack("method").round(4).to_string())
    print("\nECC minus Schaake, bootstrap over starts (95 % interval; negative = ECC better):")
    piv = t.pivot_table(index=["start", "lead", "point"], columns="method", values=["es", "vs"])
    for lead in (1, 3, 5, 7, None):
        sel = piv if lead is None else piv[piv.index.get_level_values("lead") == lead]
        for sc in ("es", "vs"):
            dd = (sel[(sc, "ECC (IFS members)")] - sel[(sc, "Schaake (error profiles)")]).groupby(level="start").mean()
            bs = [dd.sample(len(dd), replace=True, random_state=b).mean() for b in range(1000)]
            rel = 100 * dd.mean() / sel[(sc, "Schaake (error profiles)")].mean()
            print(f"  lead {('all' if lead is None else lead)!s:>3} {sc}: {dd.mean():+.4f} ({rel:+.1f} %)  [{np.percentile(bs, 2.5):+.4f}, {np.percentile(bs, 97.5):+.4f}]")


if __name__ == "__main__":
    main()
