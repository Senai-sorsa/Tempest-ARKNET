"""New_Plan WD2 (test): real-calm quantile map, leave-one-station-out. CPU, no training, nothing in the tool changes.
Stations with one-minute data: ELP MAF TCS only (ALM LRU PEQ files are empty), so the 6-station rule of New_Plan WD2 is replaced by the 3-station rule below.
Map: per cell (UTC hour block 0-5 / 6-11 / 12-17 / 18-23 x warm Apr-Sep / cool Oct-Mar) ERA5 10 m speed below the cell's 25th percentile (ERA5 fit sample) is mapped by
quantile to the ASOS 2-min speed (:00 minute) of the same cell; speeds above are unchanged. Fit on the two OTHER stations 2016-2020, test on the left-out station 2021-2023
(hourly :00 minutes, all hours). Baseline arm = raw ERA5 speed at the nearest grid point.
Rule (set 2026-11-16 before running):
  PASS: |P(speed < 3 m/s) arm - station| at most half of the baseline's at 2 of 3 stations, AND mean absolute speed error (the CRPS of a point forecast) not worse than baseline by
        more than 0.5 % at any station.
  KILL: |P(speed < 3 m/s) error| not reduced at 2 of 3 stations.   Otherwise MISS.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b58_wd2_calm_loso.py
Result: docs/results/logs/kit_b58_wd2_calm_loso.log
"""
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K
import b57_wd2_calm_step0 as B

NAME = "b58_wd2_calm_loso"
STNS = ("ELP", "MAF", "TCS")


def cell(t):
    return (np.asarray(t.hour) // 6) * 2 + ((np.asarray(t.month) >= 4) & (np.asarray(t.month) <= 9))


def qmap(e, ef, af, thr_q=0.25):
    """quantile-map speeds e below the thr_q quantile of ef to the same-rank quantile of af; others unchanged."""
    ef = np.sort(ef)
    p = np.searchsorted(ef, e, side="left") / len(ef)
    return np.where(e < np.quantile(ef, thr_q), np.quantile(af, np.clip(p, 0, 1)), e)


def judge(res):
    """res = {st: (err base, err arm, mae base, mae arm)} -> verdict."""
    half = sum(a <= 0.5 * b for b, a, _, _ in res.values())
    red = sum(a < b for b, a, _, _ in res.values())
    mae_ok = all(ma <= mb * 1.005 for _, _, mb, ma in res.values())
    if half >= 2 and mae_ok:
        return "PASS"
    return "KILL" if red < 2 else "MISS"


def load(st, years):
    B.YEARS = years
    B.HOURS = tuple(range(24))
    a = B.asos_hours(st)
    u = xr.open_zarr(os.path.join(K.REPO, "data", "raw", "era5_em", "u10.zarr"))["u10"]
    v = xr.open_zarr(os.path.join(K.REPO, "data", "raw", "era5_em", "v10.zarr"))["v10"]
    la, lo = B.SITES[st]
    sel = dict(latitude=la, longitude=lo % 360, method="nearest")
    e = np.hypot(u.sel(**sel).sel(valid_time=a.index).values, v.sel(**sel).sel(valid_time=a.index).values)
    ok = np.isfinite(e)
    return a.index[ok], a["s"].values[ok], e[ok]


def main():
    K.ram_gate(4.0)
    fit = {s: load(s, range(2016, 2021)) for s in STNS}
    test = {s: load(s, range(2021, 2024)) for s in STNS}
    lines = ["WD2 LOSO real-calm map: P(speed < 3 m/s) error and mean abs speed error vs the left-out station, 2021-23"]
    res = {}
    for st in STNS:
        t, y, e = test[st]
        c = cell(t)
        out = e.copy()
        for k in np.unique(c):
            ef = np.concatenate([fit[s][2][cell(fit[s][0]) == k] for s in STNS if s != st])
            af = np.concatenate([fit[s][1][cell(fit[s][0]) == k] for s in STNS if s != st])
            m = c == k
            out[m] = qmap(e[m], ef, af)
        po = (y < 3).mean()
        res[st] = (abs((e < 3).mean() - po), abs((out < 3).mean() - po), np.abs(e - y).mean(), np.abs(out - y).mean())
        b, a, mb, ma = res[st]
        lines.append(f"  {st}: n {len(y)}; P(<3) obs {po:.3f} base {(e < 3).mean():.3f} arm {(out < 3).mean():.3f}; err base {b:.3f} arm {a:.3f}; MAE base {mb:.3f} arm {ma:.3f} ({100 * (ma / mb - 1):+.2f} %)")
    lines.append("Rule (set 2026-11-16): PASS if arm error <= half of base at 2 of 3 stations and MAE not worse by > 0.5 % anywhere; KILL if error not reduced at 2 of 3.")
    lines.append("Result: " + judge(res))
    K.report(NAME, lines)


def _selfcheck():
    r = np.random.default_rng(0)
    ef, af = r.gamma(4, 1, 5000), r.gamma(3, 1, 5000) * 0.8
    o = qmap(ef, ef, af)
    assert (o <= np.quantile(ef, .25)).sum() > 0 and np.all(o[ef >= np.quantile(ef, .25)] == ef[ef >= np.quantile(ef, .25)])
    assert judge({"a": (.2, .05, 1, 1), "b": (.2, .05, 1, 1), "c": (.2, .2, 1, 1)}) == "PASS"
    assert judge({"a": (.2, .3, 1, 1), "b": (.2, .3, 1, 1), "c": (.2, .1, 1, 1)}) == "KILL"


_selfcheck()
if __name__ == "__main__":
    main()
