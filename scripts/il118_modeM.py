"""L15 / IL-118 + IL-120: does the IFS extended-range forecast (weekly means, ens mean) carry skill for the pilot box beyond week 2? Skill by lead.

    .venv/Scripts/python -W ignore scripts/il118_modeM.py

Data: data/raw/wb2_ifs_extended/pilot/{fc,rf}: forecasts (730 starts 2016-2022, 41 leads) and the matching reforecast (10 hindcast years per start) at 8 pressure levels, box mean over the 4 x 7 points. Lead k = the 168 h window
[start + k d - 12 h, start + (k+7) d - 12 h) (confirmed note in AUTOPILOT IL-118). Truth: ERA5 box-mean hourly t2m and u10 (data/pilot/profiles.zarr, 377 points) averaged over the same window.
Anomalies: forecast anomaly = forecast - mean of the reforecast over its hindcast years at the same lead; truth anomaly = ERA5 window mean - mean of the ERA5 window means of the SAME hindcast years (same calendar window).
Predictors: T at 850 hPa for t2m, u at 850 hPa for u10. The fit (one slope per lead) uses starts <= 2019, the skill is on starts >= 2020 (2020-2022). Skill = 1 - MSE / MSE(climatological anomaly 0), plus the correlation.
Seasons are pooled. Output: a table by lead; also writes data/il118_modeM.csv.
"""
import glob
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEADS = [0, 3, 7, 10, 14, 17, 21, 24, 28, 31, 33]
VARS = [("t2m", "t", 850), ("u10", "u", 850)]


def era5_series():
    """Daily box-mean series. The profile store keeps only 17 hours a day (00-04 and 12-23 UTC, the solar window), so a 'daily value' is the mean of the stored hours in [d - 12 h, d + 12 h) for centre date d;
    the same hours enter the target and its climatology, so the anomalies are consistent."""
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t = z["time"].values
    cd = (t + np.timedelta64(12, "h")).astype("datetime64[D]")
    days, inv = np.unique(cd, return_inverse=True)
    assert (np.diff(days).astype(int) == 1).all(), "gaps in the daily series"
    cnt = np.bincount(inv)
    out = {}
    for v in ("t2m", "u10"):
        a = z[v].mean("point").compute().values.astype(np.float64)
        out[v] = np.bincount(inv, weights=a) / cnt
    return days[0], out


def window_mean(daily, d0, start, k):
    """Mean of the daily values with centre dates start + k ... start + k + 6 days (nan outside the series)."""
    i0 = int((start.astype("datetime64[D]") - d0) / np.timedelta64(1, "D")) + k
    if i0 < 0 or i0 + 7 > len(daily):
        return np.nan
    return float(np.mean(daily[i0:i0 + 7]))


def load(kind):
    fs = sorted(glob.glob(os.path.join(REPO, "data", "raw", "wb2_ifs_extended", "pilot", kind, "*.nc")))
    return [xr.open_dataset(f) for f in fs]


def main():
    t0, cum = era5_series()
    fcs, rfs = load("fc"), load("rf")
    rows = []
    for var, fv, lev in VARS:
        for k in LEADS:
            fa, ta, yr = [], [], []
            for fc, rf in zip(fcs, rfs):
                li = int(np.argmin(np.abs(fc["level"].values - lev)))
                f_all = fc[fv].isel(level=li, prediction_timedelta=k).mean(("latitude", "longitude")).values          # (starts,)
                r_all = rf[fv].isel(level=li, prediction_timedelta=k).mean(("latitude", "longitude")).values          # (forecast_time, hindcast_year)
                starts = fc["time"].values
                hind = rf["time"].values                                                                         # (forecast_time, hindcast_year) hindcast start dates
                for i, s in enumerate(starts):
                    if i >= len(r_all):
                        continue
                    clim_f = np.nanmean(r_all[i])
                    tr = window_mean(cum[var], t0, s, k)
                    tclim = np.nanmean([window_mean(cum[var], t0, h, k) for h in hind[i]])
                    if np.isfinite(tr) and np.isfinite(tclim) and np.isfinite(f_all[i]) and np.isfinite(clim_f):
                        fa.append(f_all[i] - clim_f)
                        ta.append(tr - tclim)
                        yr.append(int(str(s)[:4]))
            fa, ta, yr = np.array(fa), np.array(ta), np.array(yr)
            fit, test = yr <= 2019, yr >= 2020
            b = float((fa[fit] * ta[fit]).sum() / max((fa[fit] ** 2).sum(), 1e-12))
            pred = b * fa[test]
            mse0 = float(np.mean(ta[test] ** 2))
            skill = 1.0 - float(np.mean((ta[test] - pred) ** 2)) / mse0
            r = float(np.corrcoef(fa[test], ta[test])[0, 1])
            # block bootstrap over test starts (weeks are autocorrelated: blocks of 4)
            rng = np.random.default_rng(0)
            n = test.sum()
            bs = []
            tt, pp = ta[test], pred
            for _ in range(300):
                idx = np.concatenate([np.arange(s, min(s + 4, n)) for s in rng.integers(0, n, n // 4 + 1)])[:n]
                bs.append(1.0 - np.mean((tt[idx] - pp[idx]) ** 2) / np.mean(tt[idx] ** 2))
            rows.append((var, k, int(fit.sum()), int(test.sum()), b, r, skill, np.percentile(bs, 5), np.percentile(bs, 95)))
            print(f"{var:4} lead {k:2d} d  fit n {fit.sum():3d} test n {test.sum():3d}  slope {b:+.2f}  r {r:+.2f}  MSE skill {skill:+.3f} (90 % block-bootstrap {np.percentile(bs, 5):+.3f} .. {np.percentile(bs, 95):+.3f})", flush=True)
    with open(os.path.join(REPO, "data", "il118_modeM.csv"), "w", encoding="utf-8") as f:
        f.write("var,lead_day,n_fit,n_test,slope,corr,mse_skill,skill_p5,skill_p95\n")
        for r in rows:
            f.write(",".join(str(round(x, 4)) if isinstance(x, float) else str(x) for x in r) + "\n")


if __name__ == "__main__":
    sys.exit(main())
