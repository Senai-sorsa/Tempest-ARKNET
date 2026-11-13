"""New_Plan 13 AV6 (a), variation of G1-5 (b3_g15_spread_replay.py, FAIL: the tracker sat at its 1.5 cap, so the gain looked like a fixed widening):
one FIXED widening factor per site for 10 m wind speed, no tracking. Same data as G1-5: WB2 IFS ENS 50 members (00Z every ~8 days), grid point nearest
TCS / MAF, valid 00 UTC vs ASOS, leads 1-7 d pooled. Factor f per site = the value on the grid 1.00, 1.05, ..., 3.00 with the lowest mean fair CRPS over
valid dates 2016-01-01..2022-12-31 (members -> mean + f (member - mean)); scored 2023-01-01..2024-12-31. Intervals: block bootstrap on the per-case CRPS
change with 21-day blocks of the valid day (AU-4 default).

Rule (set before any result; written 2026-11-13 05:58, from the AV6 row of New_Plan 13):
  PASS: in BOTH wind cells (TCS, MAF) the 90 % coverage error |cov(5-95 % of members) - 0.90| falls AND mean CRPS is not worse than raw by more than 0.0009.
  KILL: the row's kill test (the tool's output already within 0.03 of 0.90) belongs to part (b); for (a) it is read on the raw ensemble: KILL if raw
        coverage is within 0.03 of 0.90 in both cells (nothing to fix).
  Otherwise MISS (record; section 13 standing note).
  Part (b) (the tool's forecast-mode output) is NOT run here: the HRES archive that mode F reads (data/raw/wb2_hres_v2) ends 2022-12, so there is no
  tool output for 2023-24 on disk. Stated before the run.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b11_av6_fixed_widen.py
Result: docs/results/logs/kit_b11_av6_fixed_widen.log
"""
import glob

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K
from b3_g15_spread_replay import SITES, ens_crps
from bias_backtest import obs_series

FIT = ("2016-01-01", "2022-12-31")
SCORE = ("2023-01-01", "2024-12-31")
GRID = np.round(np.arange(1.0, 3.0001, 0.05), 2)
BLOCK = 21


def widen(e, f):
    mu = e.mean(1, keepdims=True)
    return mu + f * (e - mu)


def best_factor(e, y):
    """Grid factor with the lowest mean fair CRPS on (e, y)."""
    s = [ens_crps(widen(e, f), y).mean() for f in GRID]
    return float(GRID[int(np.argmin(s))])


def coverr(e, y):
    return abs(float(np.mean((y >= np.percentile(e, 5, 1)) & (y <= np.percentile(e, 95, 1)))) - 0.90)


def judge(cells):
    """cells[site] = (crps raw, crps widened, coverr raw, coverr widened) -> verdict."""
    if all(x[2] <= 0.03 for x in cells.values()):
        return "KILL (raw coverage already within 0.03 of 0.90)"
    ok = all(x[3] < x[2] and x[1] - x[0] <= 0.0009 for x in cells.values())
    return "PASS" if ok else "MISS (record)"


def main():
    files = sorted(glob.glob(K.REPO + "/data/raw/wb2_ifs_ens/*_00z.nc"))
    lines = [f"AV6 (a): fixed 10 m wind widening per site, fit {FIT[0]}..{FIT[1]} (CRPS-best on grid {GRID[0]}-{GRID[-1]}), scored {SCORE[0]}..{SCORE[1]}; "
             f"WB2 IFS ENS 50 members vs ASOS 00 UTC, leads 1-7 d pooled; {BLOCK}-day blocks"]
    cells = {}
    for st, (lat, lon) in SITES.items():
        obs = obs_series(st)
        ds = xr.open_mfdataset(files, combine="by_coords")[["u10", "v10"]].sel(latitude=lat, longitude=lon % 360, method="nearest").load()
        ens_all = np.hypot(ds.u10, ds.v10)
        E, Y, V = [], [], []
        for li, td in enumerate(ds.prediction_timedelta.values):
            e = ens_all.isel(prediction_timedelta=li).transpose("time", "number").values.astype(float)
            valid = pd.DatetimeIndex(ds.time.values) + pd.Timedelta(td)
            y = obs["ws"].reindex(valid).to_numpy()
            ok = np.isfinite(y) & np.isfinite(e).all(1)
            E.append(e[ok]), Y.append(y[ok]), V.append(valid[ok])
        e, y, v = np.concatenate(E), np.concatenate(Y), pd.DatetimeIndex(np.concatenate([x.values for x in V]))
        assert v.max() < pd.Timestamp("2026-01-01"), "no 2026 data here"  # Dec 2024 starts reach Jan 2025 at long leads; not scored
        fit, sc = (v >= FIT[0]) & (v <= FIT[1] + " 23:59"), (v >= SCORE[0]) & (v <= SCORE[1] + " 23:59")
        f = best_factor(e[fit], y[fit])
        c0, c1 = ens_crps(e[sc], y[sc]), ens_crps(widen(e[sc], f), y[sc])
        dm, lo, hi = K.block_boot(c1 - c0, list((v[sc].normalize() - pd.Timestamp(SCORE[0])).days // BLOCK), draws=2000)
        cells[st] = (c0.mean(), c1.mean(), coverr(e[sc], y[sc]), coverr(widen(e[sc], f), y[sc]))
        lines.append(f"  {st} ws: factor {f:.2f} (fit {fit.sum()} cases); scored {sc.sum()} cases: CRPS {c0.mean():.4f} -> {c1.mean():.4f}, change {dm:+.4f} "
                     f"[{lo:+.4f}, {hi:+.4f}]; 90 % coverage error {cells[st][2]:.3f} -> {cells[st][3]:.3f}")
    lines.append("Verdict: " + judge(cells))
    K.report("b11_av6_fixed_widen", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    truth = rng.normal(0, 2, 400)
    e = rng.normal(0, 1, (400, 50))                                      # members twice too narrow around a mean of 0
    assert 1.6 <= best_factor(e, truth) <= 2.4
    assert coverr(widen(e, 2.0), truth) < coverr(e, truth)
    assert judge({"A": (1.0, 0.99, 0.2, 0.05), "B": (1.0, 1.0005, 0.2, 0.1)}) == "PASS"
    assert judge({"A": (1.0, 0.99, 0.2, 0.05), "B": (1.0, 1.002, 0.2, 0.1)}).startswith("MISS")
    assert judge({"A": (1.0, 0.99, 0.02, 0.05), "B": (1.0, 1.0, 0.01, 0.1)}).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
