"""F-10: would a trajectory-aware first guess help mode P? Compare, on 00Z/12Z soundings of 2024-25, the MAE of ERA5 as ONE value against the balloon for
(a) the launch point and launch hour (what mode P uses), (b) the balloon's own path: it rises 5 m/s, is carried by the ERA5 wind of the launch profile, and ERA5 is read at the grid point
and (linearly interpolated) hour it passes at each height. If (b) is not clearly better than (a) the retrain is not worth doing.
    PYTHONPATH=. python scripts/f10_check.py"""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station
from tempest.profiles.to_heights import HEIGHTS, PROFILE

RISE = 5.0                      # m/s
ds = xr.open_zarr("data/pilot/profiles80.zarr")
lat, lon, step = ds.lat.values, ds.lon.values, 0.25
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]
res = {k: [] for k in ("a", "b")}
truth_all = []
for sid, (slat, slon) in station.STATIONS.items():
    t, prof, _ = station.read_igra(f"data/raw/igra/{sid}-drvd.txt.zip", 2024, 2025)
    ok = np.isfinite(prof).all((1, 2))
    t, prof = t[ok], prof[ok]
    box = np.flatnonzero((np.abs(lat - slat) <= 1.0) & (np.abs(lon - slon) <= 1.0))
    t0, t1 = t.min() - pd.Timedelta(hours=1), t.max() + pd.Timedelta(hours=4)
    sub = ds.sel(time=slice(t0, t1)).isel(point=box)
    E = np.stack([sub[v].values for v in PROFILE], 0)                                  # (4, npt, nt, 44)
    times = pd.DatetimeIndex(sub.time.values)
    pl, pn = lat[box], lon[box]
    for s_i, ts in enumerate(t):
        i0 = times.get_loc(ts) if ts in times else None
        if i0 is None:
            continue
        p0 = int(np.argmin((pl - slat) ** 2 + (pn - slon) ** 2))
        a = E[:, p0, i0, :]                                                              # launch point, launch hour
        u0, v0 = a[0], a[1]
        dt = np.diff(np.r_[0.0, HEIGHTS.astype(float)]) / RISE                          # s between levels
        x = np.cumsum(u0 * dt)                                                           # m east of the launch
        y = np.cumsum(v0 * dt)
        la = slat + y / 111000.0
        lo = slon + x / (111000.0 * np.cos(np.radians(slat)))
        tsec = np.cumsum(dt)
        b = np.empty_like(a)
        for j in range(44):
            pj = int(np.argmin((pl - la[j]) ** 2 + ((pn - lo[j]) * np.cos(np.radians(slat))) ** 2))
            fh = tsec[j] / 3600.0
            k0 = i0 + int(np.floor(fh))
            w = fh - np.floor(fh)
            k1 = min(k0 + 1, E.shape[2] - 1)
            for v in range(4):
                b[v, j] = (1 - w) * E[v, pj, k0, j] + w * E[v, pj, k1, j]
        res["a"].append(a)
        res["b"].append(b)
        truth_all.append(prof[s_i])
A, B, Y = (np.array(res["a"]), np.array(res["b"]), np.array(truth_all))
print(f"{len(Y)} soundings 2024-25")
rows = []
for v, name in enumerate(PROFILE):
    for lo_, hi_ in BANDS:
        s = (HEIGHTS >= lo_) & (HEIGHTS < hi_)
        ea, eb = np.abs(A[:, v][:, s] - Y[:, v][:, s]).mean(), np.abs(B[:, v][:, s] - Y[:, v][:, s]).mean()
        ga = np.abs(A[:, v][:, s] - Y[:, v][:, s]).mean(1)
        gb = np.abs(B[:, v][:, s] - Y[:, v][:, s]).mean(1)
        d = gb - ga
        rows.append(dict(var=name, band=f"{lo_ / 1000:g}-{min(hi_, 18000) / 1000:g} km", mae_launch=ea, mae_path=eb, change_pct=100 * (eb - ea) / ea, se_pct=100 * d.std() / np.sqrt(len(d)) / ea))
t = pd.DataFrame(rows)
print(t.round(3).to_string(index=False))
t.to_csv("models/f10_check.csv", index=False)
