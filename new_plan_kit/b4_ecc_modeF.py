"""New_Plan 10.2 O5: ECC ordering in forecast mode. Order the members across heights by the IFS ensemble's own joint ranks (ECC) instead of the
Schaake template of real HRES error profiles (what mode F does now). Same design as scripts/m4_ecc_test.py (marginals fixed at the ensemble's own
sorted members, only the joint order differs, so per-height CRPS cannot change), on the plan's test years: IFS ENS 00z starts 2023-24 (the files end
2024-12; 2025 has none), every lead 1-7 d, `--points` grid points per start and lead, truth = ERA5 profile store. Schaake pool = mode F rows 2016-20.
Seed = the point and Schaake-pool draw.
Checks (pre-set, New_Plan 10.2; the two last made concrete here):
  variogram score (p 0.5, standardised columns) ECC better than Schaake by >= 1 % at EVERY lead 1-7, start-block interval excluding 0;
  shear rate within 10 % of Schaake: share of member layers (consecutive wind columns above 50 m) with vector shear > 10 m/s per km;
  IL-128 inflation check: 99th percentile of member layer shear, ECC / Schaake <= 1.2 (the IL-128 threshold).
PASS: all three, both seeds. Else keep Schaake.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b4_ecc_modeF.py --seed 0     # then --seed 1
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b4_ecc_modeF.py --points 3 --months 1
Result: docs/results/logs/kit_b4_ecc_modeF.log
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K
from m4_ecc_test import K as NM, G, HEIGHTS, ranks, variogram_score

SHEAR = 0.01        # 10 m/s per km
LEADS = tuple(range(1, 8))


def layer_shear(x, cols, hgt):
    """x (members, columns); the wind columns (u var 0, v var 1) at heights hgt -> (members, layers) vector shear in 1/s between consecutive wind heights."""
    hs = sorted({hgt[i] for i, c in enumerate(cols) if c // 44 in (0, 1)})
    u = {hgt[i]: x[:, i] for i, c in enumerate(cols) if c // 44 == 0}
    v = {hgt[i]: x[:, i] for i, c in enumerate(cols) if c // 44 == 1}
    hs = [h for h in hs if h in u and h in v]
    out = [np.hypot(u[b] - u[a], v[b] - v[a]) / (b - a) for a, b in zip(hs, hs[1:]) if b > a]
    return np.stack(out, 1) if out else np.zeros((x.shape[0], 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--months", type=int, default=24, help="ENS monthly files used (first year onward)")
    ap.add_argument("--years", default="2023,2024", help="ENS years; 2022 = the M4 check year (reproduction only, not a test year)")
    a = ap.parse_args()
    K.ram_gate(3.0)
    rng = np.random.default_rng(a.seed)
    H = np.asarray(HEIGHTS, float)
    tr = {k: np.concatenate([np.load(os.path.join(K.REPO, "data", "modeF", f"{y}.npz"))[k] for y in range(2016, 2021)]) for k in ("obs", "hres", "lead_days")}
    res_tr = (tr["obs"] - tr["hres"]).reshape(len(tr["obs"]), -1)
    z = xr.open_zarr(os.path.join(K.REPO, "data", "pilot", "profiles.zarr"))
    zlat, zlon, zsfc = z.lat.values, z.lon.values, z.z_sfc.values
    have = pd.DatetimeIndex(z.time.values)
    files = sorted(f for y in map(int, a.years.split(",")) for f in glob.glob(os.path.join(K.REPO, "data", "raw", "wb2_ifs_ens", f"{y}*_00z.nc")))[:a.months]
    rows, shear = [], {m: [] for m in ("ECC", "Schaake")}
    for f in files:
        ds = xr.open_dataset(f)
        ld = ds.prediction_timedelta.values.astype("timedelta64[D]").astype(int)
        for it, t0 in enumerate(pd.DatetimeIndex(ds.time.values)):
            assert t0.year < 2026
            for lead in LEADS:
                if lead not in ld:
                    continue
                li = int(np.flatnonzero(ld == lead)[0])
                valid = t0 + pd.Timedelta(days=lead)
                if valid not in have or valid.year >= 2026:
                    continue
                pts = rng.choice(len(zlat), a.points, replace=False)
                tru = {v: z[v].isel(point=pts).sel(time=valid).values for v in ("u", "v", "T")}
                pool_idx = rng.choice(np.flatnonzero(tr["lead_days"] == lead), NM, replace=False) if (tr["lead_days"] == lead).sum() >= NM else None
                if pool_idx is None:      # mode F rows carry leads 1/3/5/7 only: take the nearest stored lead's error profiles
                    near = min(set(np.unique(tr["lead_days"]).astype(int)), key=lambda q: abs(q - lead))
                    pool_idx = rng.choice(np.flatnonzero(tr["lead_days"] == near), NM, replace=False)
                for j, p in enumerate(pts):
                    la = int(np.argmin(np.abs(ds.latitude.values - zlat[p])))
                    lo = int(np.argmin(np.abs(ds.longitude.values - (zlon[p] % 360))))
                    cols, hgt = [0, 44], [10.0, 10.0]
                    mem, y = [ds["u10"].values[it, :, li, la, lo], ds["v10"].values[it, :, li, la, lo]], [tru["u"][j, 0], tru["v"][j, 0]]
                    zs = float(zsfc[p])
                    zs = zs / G if zs > 20000 else zs
                    for lv in range(len(ds.level)):
                        agl = float(np.median(ds["z"].values[it, :, li, lv, la, lo])) / G - zs
                        if agl < 50:
                            continue
                        h = int(np.argmin(np.abs(H - agl)))
                        for var, name, tk in ((0, "u", "u"), (1, "v", "v"), (2, "t", "T")):
                            cols.append(var * 44 + h)
                            hgt.append(float(H[h]))
                            mem.append(ds[name].values[it, :, li, lv, la, lo])
                            y.append(tru[tk][j, h])
                    cols, mem, y = np.array(cols), np.stack(mem, 1).astype(float), np.array(y, float)
                    if not (np.isfinite(mem).all() and np.isfinite(y).all()):
                        continue
                    srt = np.sort(mem, 0)
                    sd = np.maximum(res_tr[:, cols].std(0), 1e-6)
                    sch = np.take_along_axis(srt, ranks(res_tr[pool_idx][:, cols]), 0)
                    for meth, xs in (("ECC", mem), ("Schaake", sch)):
                        rows.append((meth, lead, str(t0.date()), int(p), float(variogram_score((xs / sd)[None], (y / sd)[None])[0])))
                        shear[meth].append(layer_shear(xs, cols, hgt).ravel())
        ds.close()
    t = pd.DataFrame(rows, columns=["method", "lead", "start", "point", "vs"])
    lines = [f"O5 ECC vs Schaake in forecast mode: seed {a.seed}, {t.start.nunique()} IFS ENS starts {a.years.replace(",", "-")}, {len(t) // 2} rows (start x lead x point), {a.points} points per start and lead"]
    if t.empty:
        K.report("b4_ecc_modeF", lines + ["no rows"])
        return
    piv = t.pivot_table(index=["start", "lead", "point"], columns="method", values="vs")
    ok_vs = True
    for lead in LEADS:
        sel = piv[piv.index.get_level_values("lead") == lead]
        if sel.empty:
            ok_vs = False
            lines.append(f"  lead {lead}: no rows")
            continue
        dd = (sel["ECC"] - sel["Schaake"]).groupby(level="start").mean()
        dm, dlo, dhi = K.block_boot(dd.to_numpy(), list(dd.index), draws=1000)
        rel = 100 * dd.mean() / sel["Schaake"].mean()
        ok = rel <= -1.0 and dhi < 0
        ok_vs &= bool(ok)
        lines.append(f"  lead {lead}: variogram Schaake {sel['Schaake'].mean():.4f}  ECC {sel['ECC'].mean():.4f}  ECC minus Schaake {dm:+.4f} ({rel:+.1f} %) [{dlo:+.4f}, {dhi:+.4f}]  {'ok' if ok else 'fail'}")
    sh = {m: np.concatenate(v) for m, v in shear.items()}
    rate = {m: float((x > SHEAR).mean()) for m, x in sh.items()}
    p99 = {m: float(np.percentile(x, 99)) for m, x in sh.items()}
    ok_rate = abs(rate["ECC"] / max(rate["Schaake"], 1e-9) - 1.0) <= 0.10
    ok_p99 = p99["ECC"] / max(p99["Schaake"], 1e-9) <= 1.2
    lines.append(f"  shear rate (> 10 m/s per km): ECC {rate['ECC']:.4f}  Schaake {rate['Schaake']:.4f}  ratio {rate['ECC'] / max(rate['Schaake'], 1e-9):.3f}  {'ok' if ok_rate else 'fail'} (within 10 %)")
    lines.append(f"  IL-128 check, 99th percentile shear: ECC {1000 * p99['ECC']:.2f}  Schaake {1000 * p99['Schaake']:.2f} m/s per km  ratio {p99['ECC'] / max(p99['Schaake'], 1e-9):.3f}  {'ok' if ok_p99 else 'fail'} (<= 1.2)")
    lines.append("Rule (pre-set): variogram >= 1 % better at every lead 1-7 with interval excluding 0, shear rate within 10 %, IL-128 ratio <= 1.2; both seeds.")
    lines.append("Seed verdict: " + ("PASS (needs the other seed)" if ok_vs and ok_rate and ok_p99 else "FAIL -> keep Schaake"))
    K.report("b4_ecc_modeF", lines)


def _selfcheck():
    x = np.array([[0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 2.0]])     # u10, v10, u@1000, v@1000
    s = layer_shear(x, [0, 44, 5, 49], [10.0, 10.0, 1010.0, 1010.0])
    assert s.shape == (2, 1) and abs(s[0, 0] - 0.001) < 1e-12 and abs(s[1, 0] - 0.002) < 1e-12


_selfcheck()
if __name__ == "__main__":
    main()
