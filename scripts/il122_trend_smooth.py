"""IL-122 follow-up (V1 finding): the tool's climate-mode temperature is +2.4 K in January 2025 and -1.9 K in December 2025 against ERA5 of the same years, which looks like noisy month-by-month trend slopes extrapolated to
the end of the data. Backtest of trend shapes on ERA5 t2m at the pilot box, fit 1991-2015, test 2016-2025: per-(month, hour) cell slopes (as il122_trend.py) against ONE slope for all cells, and a slope with a smooth annual cycle (constant + sin + cos of the month).

    .venv/Scripts/python -W ignore scripts/il122_trend_smooth.py
"""
import os

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t = z["time"].values
    yr = t.astype("datetime64[Y]").astype(int) + 1970
    mo = t.astype("datetime64[M]").astype(int) % 12
    hr = (t.astype("datetime64[h]") - t.astype("datetime64[D]")).astype(int)
    cell = mo * 24 + hr
    x = z["t2m"].mean("point").compute().values.astype(np.float64)
    fit, test = (yr >= 1991) & (yr <= 2015), (yr >= 2016) & (yr <= 2025)
    y0 = yr - 2003.0
    cells = np.unique(cell)
    base = {c: x[fit & (cell == c)].mean() for c in cells}
    res = x - np.array([base.get(c, np.nan) for c in cell])
    ok_fit = fit & np.isfinite(res)
    ang = 2 * np.pi * (mo + 0.5) / 12.0
    preds = {}
    # (a) no trend
    preds["plain mean"] = np.zeros_like(x)
    # (b) per-cell slope
    sl = np.zeros_like(x)
    for c in cells:
        m = ok_fit & (cell == c)
        if m.sum() > 40:
            s = np.polyfit(y0[m], res[m], 1)[0]
            sl[cell == c] = s
    preds["per-cell slope (today's kind)"] = sl * y0
    # (c) one slope
    s1 = (y0[ok_fit] * res[ok_fit]).sum() / (y0[ok_fit] ** 2).sum()
    preds["one slope for all cells"] = s1 * y0
    # (d) slope with a smooth annual cycle
    A = np.stack([y0, y0 * np.sin(ang), y0 * np.cos(ang)], 1)
    coef = np.linalg.lstsq(A[ok_fit], res[ok_fit], rcond=None)[0]
    preds["slope = const + annual harmonic"] = A @ coef
    print(f"one slope {s1 * 10:+.2f} K/decade; harmonic slope const {coef[0] * 10:+.2f}, sin {coef[1] * 10:+.2f}, cos {coef[2] * 10:+.2f} K/decade")
    ok = test & np.isfinite(res)
    mse0 = np.mean(res[ok] ** 2)
    for name, p in preds.items():
        e = res[ok] - p[ok]
        by_m = [np.mean(e[mo[ok] == k]) for k in range(12)]
        print(f"  {name:36} bias {e.mean():+.3f}  RMSE {np.sqrt(np.mean(e ** 2)):.3f}  skill vs plain {1 - np.mean(e ** 2) / mse0:+.4f}  bias by month 1..12: {' '.join(f'{b:+.1f}' for b in by_m)}")
    print("  (the per-month bias spread is the thing to look at: today's per-cell slopes vs a smooth slope)")


if __name__ == "__main__":
    main()
