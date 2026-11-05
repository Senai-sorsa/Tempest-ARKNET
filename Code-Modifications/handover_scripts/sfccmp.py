"""Balloon launch surface vs ERA5 grid surface at 00Z, per year: is the gap stable and linear (fixable by a+b*ERA5)?"""
import numpy as np, pandas as pd, xarray as xr
from tempest.calibrate.station import STATIONS, ELEV, nearest_point, read_igra
ds = xr.open_zarr("data/pilot/profiles80.zarr"); T = pd.DatetimeIndex(ds.time.values)
for sid, (la, lo) in STATIONS.items():
    t, _, sfc = read_igra(f"data/raw/igra/{sid}-drvd.txt.zip", 1991, 2025)
    m = (t.hour == 0) & t.isin(T) & np.isfinite(sfc).all(1); t, sfc = t[m], sfc[m]
    p = nearest_point(ds, la, lo); b = ds[["t2m", "rh2m", "sp"]].isel(point=p).sel(time=t).load()
    z = float(ds.z_sfc.values[p])
    d = pd.DataFrame({"year": t.year, "dT": sfc[:, 0] - b.t2m.values, "dRH": sfc[:, 2] - b.rh2m.values,
                      "obsRH": sfc[:, 2], "eraRH": b.rh2m.values})
    fit, test = d[d.year <= 2020], d[d.year >= 2024]
    bb, aa = np.polyfit(fit.eraRH, fit.obsRH, 1)
    print(sid, f"grid z {z:.0f} m vs launch {ELEV[sid]:.0f} m; rh fit obs = {aa:.1f} + {bb:.2f} era")
    for nm, x in (("raw", test.eraRH), ("lin", aa + bb * test.eraRH)):
        print(f"  2024-25 {nm}: rh2m bias {np.mean(x - test.obsRH):+.1f}, mae {np.mean(abs(x - test.obsRH)):.1f}, corr {np.corrcoef(x, test.obsRH)[0,1]:.2f}")
    g = d.groupby("year")[["dT", "dRH"]].mean().round(1)
    print("  per-year mean gap (balloon - ERA5), every 3rd year:", g.iloc[::3].to_dict("index"))
