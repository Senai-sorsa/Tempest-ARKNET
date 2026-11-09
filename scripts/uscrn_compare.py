"""Independent ground-level wind: NOAA USCRN station Las Cruces 20 N (NM, 32.61 N 106.74 W, Jornada basin, 39 km from the Spaceport America pad, NOT an airport, wind at 1.5 m, 5-minute data 2019-2025).
Hourly means (12 five-minute values, good-flag only) compared with (a) the ASOS speed at Truth or Consequences (the airport the tool was tuned on), (b) the raw ERA5 10 m speed at the nearest grid point, (c) the tool's own climate-mode 10 m median for that month and hour.
Answers: how different is the basin's ground wind from the airport's, and how does ERA5 relate to it?    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/uscrn_compare.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402


def read_uscrn(y):
    out = {}
    with open(os.path.join(REPO, "data", "raw", "isd", f"CRNS_LC20N_{y}.txt")) as f:
        for line in f:
            p = line.split()
            if len(p) < 23:
                continue
            try:
                w, flag = float(p[21]), p[22]
            except ValueError:
                continue
            if flag != "0" or w < 0 or w > 60:
                continue
            t = datetime.strptime(p[1] + p[2], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            h = (t - timedelta(minutes=1)).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)     # the value is the 5-min period ending at t: assign to the hour ending at ceil(t)
            out.setdefault(h, []).append(w)
    return {h: float(np.mean(v)) for h, v in out.items() if len(v) >= 10}


def main():
    jr = {}
    for y in range(2019, 2026):
        jr.update(read_uscrn(y))
    print(f"USCRN Las Cruces 20 N: {len(jr)} complete hours 2019-2025, mean 1.5 m speed {np.mean(list(jr.values())):.2f} m/s")
    asos = gw.load_asos("TCS", range(2019, 2026))
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    lat, lon = 32.61, -106.74
    i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
    print(f"nearest ERA5 point {z.lat.values[i]:.2f},{z.lon.values[i]:.2f}")
    t_all = z["time"].values
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
    hs = [h for h in sorted(jr) if h in asos and tt.get(np.datetime64(h.replace(tzinfo=None), "h")) is not None and 12 <= h.hour <= 23 or (h in asos and h.hour <= 4 and tt.get(np.datetime64(h.replace(tzinfo=None), "h")) is not None and h in jr)]
    hs = sorted(set(hs))
    ks = np.array([tt[np.datetime64(h.replace(tzinfo=None), "h")] for h in hs])
    o = np.argsort(ks)
    hs = [hs[j] for j in o]
    ks = ks[o]
    sl = slice(ks.min(), ks.max() + 1)
    u10 = z["u10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
    v10 = z["v10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
    e = np.hypot(u10, v10)
    J = np.array([jr[h] for h in hs])
    A = np.array([np.hypot(*asos[h]) for h in hs])
    print(f"{len(hs)} common hours (stored ERA5 hours). Mean speeds: USCRN 1.5 m {J.mean():.2f}, ASOS TCS 10 m {A.mean():.2f}, ERA5 10 m {e.mean():.2f} m/s")
    print(f"correlation of hourly speed: USCRN vs ASOS TCS {np.corrcoef(J, A)[0, 1]:.2f}; USCRN vs ERA5 {np.corrcoef(J, e)[0, 1]:.2f}; ASOS TCS vs ERA5 {np.corrcoef(A, e)[0, 1]:.2f}")
    # 1.5 m -> 10 m with the log law, z0 = 0.03 m: factor ln(10/z0)/ln(1.5/z0)
    f = np.log(10 / 0.03) / np.log(1.5 / 0.03)
    print(f"USCRN scaled to 10 m (log law z0 0.03 m, factor {f:.2f}): mean {J.mean() * f:.2f} m/s; MAE of ERA5 10 m against it {np.abs(e - J * f).mean():.2f}; against ASOS TCS {np.abs(e - A).mean():.2f}")
    by_hour = {}
    for h, a, j, ee in zip(hs, A, J, e):
        by_hour.setdefault((h.hour - 7) % 24, []).append((a, j * f, ee))
    print("by local solar-ish hour (UTC-7): ASOS TCS / USCRN scaled to 10 m / ERA5 10 m")
    for hh in sorted(by_hour):
        v = np.array(by_hour[hh])
        if len(v) > 100:
            print(f"  {hh:02d}h  {v[:, 0].mean():.2f} / {v[:, 1].mean():.2f} / {v[:, 2].mean():.2f}  (n {len(v)})")


if __name__ == "__main__":
    main()
