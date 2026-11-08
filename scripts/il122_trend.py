"""L16 / IL-122: does a warming-trend term beat a plain climatology when the tool is asked for years after the fit? Backtest on the pilot box with ERA5 t2m and u10 (box mean of the 377 points, stored hours only).

    .venv/Scripts/python -W ignore scripts/il122_trend.py

Fit window 1991-2015, test 2016-2025. Predictors per (calendar month, stored hour of day): (a) plain mean of 1991-2015; (b) the mean plus a linear trend in year fitted on 1991-2015 and extrapolated; (c) the mean of the last 15 fit years (2001-2015);
(d) trend shrunk to half. Score: mean error (bias) and RMSE of the predicted hourly value, and the bias of the yearly mean, in the test years. Skill = 1 - MSE / MSE(a).
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
    for var in ("t2m", "u10"):
        x = z[var].mean("point").compute().values.astype(np.float64)
        fit, test = (yr >= 1991) & (yr <= 2015), (yr >= 2016) & (yr <= 2025)
        pa = np.full(len(x), np.nan)
        pb, pc, pd_ = pa.copy(), pa.copy(), pa.copy()
        for c in np.unique(cell):
            m = cell == c
            f = m & fit
            if f.sum() < 40:
                continue
            slope, icpt = np.polyfit(yr[f] - 2003.0, x[f], 1)
            base = x[f].mean()
            last = m & (yr >= 2001) & (yr <= 2015)
            tt = m & test
            pa[tt] = base
            pb[tt] = icpt + slope * (yr[tt] - 2003.0)
            pc[tt] = x[last].mean()
            pd_[tt] = base + 0.5 * (icpt + slope * (yr[tt] - 2003.0) - base)
        ok = test & np.isfinite(pa)
        print(f"\n{var}: test hours {int(ok.sum())}, fit {int(fit.sum())}")
        mse_a = np.mean((x[ok] - pa[ok]) ** 2)
        for name, p in (("plain mean 1991-2015", pa), ("mean + linear trend (extrapolated)", pb), ("last 15 fit years 2001-2015", pc), ("mean + half the trend", pd_)):
            e = x[ok] - p[ok]
            ybias = [np.mean(e[yr[ok] == y]) for y in range(2016, 2026)]
            print(f"  {name:36} bias {e.mean():+.3f}   RMSE {np.sqrt(np.mean(e ** 2)):.3f}   skill vs plain {1 - np.mean(e ** 2) / mse_a:+.4f}   yearly-mean bias 2016..2025: {' '.join(f'{b:+.2f}' for b in ybias)}")


if __name__ == "__main__":
    main()
