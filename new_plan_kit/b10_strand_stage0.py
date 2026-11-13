"""New_Plan 14.5 STRAND stage 0 (CPU, no training): does the hour-to-hour link matter for a launch-window question in climate mode?
Real probability that 10 m wind stays under a limit for 3 hours in a row, against the same from independent draws (each hour drawn on its own
from the same climate pool = the product of the three per-hour probabilities). ERA5 hourly box store data/pilot/profiles80.zarr, 1991-2020
only (no 2026 data), every point, cells = point x calendar month x start hour (window start, start+1, start+2 all kept and consecutive).

Rule (set before any result; written 2026-11-13 03:38, from the plan's stage 0 text):
  per limit L in (5, 8, 10) m/s, d = mean over cells of |P_real - P_indep|, only cells with 0.05 <= P_indep <= 0.95 (where a launch
  decision is open). STOP (STRAND dropped for climate mode) if d < 0.02 at every limit; otherwise GO to stage 1.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b10_strand_stage0.py
Result: docs/results/logs/kit_b10_strand_stage0.log
"""
import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

LIMITS = (5.0, 8.0, 10.0)
YEARS = ("1991", "2020")


def window_probs(w, ok3, month, hour, L):
    """w (T, P) wind; ok3 (T,) window start valid -> per (month, hour, point): P_real, P_indep, n. Marginals from the same window starts."""
    b = w < L
    run = b[:-2] & b[1:-1] & b[2:]
    rows = []
    for m in range(1, 13):
        for h in np.unique(hour[:-2][ok3]):
            k = np.flatnonzero(ok3 & (month[:-2] == m) & (hour[:-2] == h))
            if len(k) < 30:
                continue
            p_ind = b[k].mean(0) * b[k + 1].mean(0) * b[k + 2].mean(0)
            rows.append((m, h, run[k].mean(0), p_ind, len(k)))
    return rows


def judge(d):
    return "STOP (under 0.02 at every limit; STRAND dropped for climate mode)" if all(v < 0.02 for v in d.values()) else "GO to stage 1"


def main():
    ds = xr.open_zarr("data/pilot/profiles80.zarr").sel(time=slice(*YEARS))
    t = pd.DatetimeIndex(ds.time.values)
    assert t.year.max() <= 2020, "no data after 2020 here"
    w = np.hypot(ds.u10.values, ds.v10.values).T.astype(np.float32)          # (T, P)
    gap = np.diff(t.values).astype("timedelta64[h]").astype(int)
    ok3 = (gap[:-1] == 1) & (gap[1:] == 1)
    lines = [f"STRAND stage 0: 10 m wind under L for 3 h in a row, real vs independent hours; {YEARS[0]}-{YEARS[1]}, {w.shape[1]} points, "
             f"{ok3.sum():,} window starts, start hours {sorted(set(t.hour[:-2][ok3]))}"]
    d = {}
    for L in LIMITS:
        r = window_probs(w, ok3, t.month.values, t.hour.values, L)
        pr, pi = np.concatenate([x[2] for x in r]), np.concatenate([x[3] for x in r])
        k = (pi >= 0.05) & (pi <= 0.95)
        diff = pr[k] - pi[k]
        d[L] = float(np.abs(diff).mean())
        lines.append(f"  L {L:>4.0f} m/s: {k.sum():,} open cells; P_real mean {pr[k].mean():.3f}, P_indep {pi[k].mean():.3f}; mean |diff| {d[L]:.4f}, "
                     f"mean diff {diff.mean():+.4f}, p90 |diff| {np.quantile(np.abs(diff), 0.9):.4f}, max {np.abs(diff).max():.4f}")
    lines.append("Verdict: " + judge(d))
    K.report("b10_strand_stage0", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n, hour = 24 * 400, np.tile(np.arange(24), 400)
    month = np.repeat(pd.date_range("2001-01-01", periods=400).month.values, 24)
    ok = np.ones(n - 2, bool)
    ind = rng.uniform(0, 10, (n, 1))                                         # independent hours: P_real ~ P_indep
    x = np.repeat(rng.uniform(0, 10, (n // 3 + 1, 1)), 3, 0)[:n]           # same value 3 h running: P_real >> P_indep
    for w, big in ((ind, False), (x, True)):
        r = window_probs(w, ok, month, hour, 5.0)
        dd = np.mean([abs(a[2] - a[3]).mean() for a in r])
        assert (dd > 0.1) == big, dd
    assert judge({5: 0.01, 8: 0.019}).startswith("STOP") and judge({5: 0.01, 8: 0.03}).startswith("GO")


_selfcheck()
if __name__ == "__main__":
    main()
