"""IL-6a: how good are the archived IFS HRES forecasts (data/raw/wb2_hres) over the pilot box, against ERA5, by lead time, compared with climatology?

    PYTHONPATH=. python scripts/il6_skill.py [--levels 850 500 250] [--out csv]

For every start (00 UTC, 92 per year, 2016-2022) and lead (1, 3, 5, 7 days): HRES pressure-level u, v, T on the 13 x 29 box grid vs ERA5 at the valid time (raw
Earthmover store). Climatology = ERA5 mean at 00 UTC within +-7 days of the same day of year in 1991-2015 (before any forecast year). Reports per variable x level x lead:
RMSE of the forecast, RMSE of climatology, MSE skill score (1 - MSE_f / MSE_c), bias. Mean over the grid and all cases.
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

ap = argparse.ArgumentParser()
ap.add_argument("--levels", type=int, nargs="+", default=[850, 500, 250])
ap.add_argument("--out", default="models/il6_skill.csv")
a = ap.parse_args()
VARS = [("u", "u"), ("v", "v"), ("t", "t")]
era = {v: xr.open_zarr(f"data/raw/era5_em80/{n}.zarr")[n].sel(pressure_level=a.levels) for v, n in VARS}
hres = xr.concat([xr.open_dataset(f"data/raw/wb2_hres/{y}.nc") for y in range(2016, 2023)], "time").sel(level=a.levels)
vt = era["u"].valid_time.values
day00 = np.flatnonzero((vt.astype("datetime64[h]").astype(int) % 24 == 0) & (vt < np.datetime64("2016-01-01")) & (vt >= np.datetime64("1991-01-01")))
clim_t = vt[day00]
doy = pd.DatetimeIndex(clim_t).dayofyear.to_numpy()
clim_vals = {v: era[v].isel(valid_time=day00).values.astype(np.float32) for v in era}          # (T, L, 13, 29)
print("climatology sample", clim_vals["u"].shape, flush=True)
rows = []
leads = hres.prediction_timedelta.values
for li, lead in enumerate(leads):
    days = int(lead / np.timedelta64(1, "D")) if lead.dtype.kind == "m" else int(lead // 86_400_000_000_000)
    valid = hres.time.values + np.timedelta64(days, "D")
    ok = np.isin(valid, vt)
    idx = np.searchsorted(vt, valid[ok])
    d_valid = pd.DatetimeIndex(valid[ok]).dayofyear.to_numpy()
    for v, n in VARS:
        truth = era[v].isel(valid_time=idx).values                                               # (N, L, 13, 29)
        fc = hres[v].isel(time=np.flatnonzero(ok), prediction_timedelta=li).values               # (N, L, 13, 29) levels sorted as selected
        fc = fc[:, np.argsort(np.argsort(a.levels))] if False else fc
        clim = np.stack([clim_vals[v][np.abs(((doy - dd + 183) % 366) - 183) <= 7].mean(0) for dd in d_valid])
        for k, lev in enumerate(a.levels):
            hk = int(np.flatnonzero(hres.level.values == lev)[0]) if False else list(hres.level.values).index(lev)
            e_f = fc[:, hk] - truth[:, k]
            e_c = clim[:, k] - truth[:, k]
            rows.append(dict(var=n, level=lev, lead_days=days, rmse_fc=float(np.sqrt((e_f ** 2).mean())), rmse_clim=float(np.sqrt((e_c ** 2).mean())),
                             skill=float(1 - (e_f ** 2).mean() / (e_c ** 2).mean()), bias_fc=float(e_f.mean())))
    print("lead", days, "done", flush=True)
t = pd.DataFrame(rows)
t.to_csv(a.out, index=False)
with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
    print(t.pivot_table(index=["var", "level"], columns="lead_days", values="skill").to_string())
    print(t.pivot_table(index=["var", "level"], columns="lead_days", values="rmse_fc").to_string())
