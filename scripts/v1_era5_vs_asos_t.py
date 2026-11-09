"""V1 follow-up: is the warm bias of the tool's climate mode (+1.5 C at TCS / MAF against ASOS) already in the ERA5 profile store it is trained on?  ERA5 t2m at the nearest grid point, moved to the station height with 6.5 K/km,
against ASOS temperature at the same hours, by month, 2021-2025 (stored hours only). Also prints the tool-minus-ERA5 and ERA5-minus-ASOS parts.
"""
import csv
import os
from datetime import datetime, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = {"TCS": (33.2369, -107.2672, 1479.0), "MAF": (31.9425, -102.2019, 872.0)}


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t = z["time"].values
    yr = t.astype("datetime64[Y]").astype(int) + 1970
    sel = (yr >= 2021) & (yr <= 2025)
    ts = t[sel]
    for name, (lat, lon, el) in ST.items():
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        zs = float(z.z_sfc.values[i])
        e = z["t2m"].isel(point=i).values[sel] - 273.15 + 0.0065 * (zs - el)
        era = {np.datetime64(x, "h"): v for x, v in zip(ts, e)}
        diffs = {m: [] for m in range(1, 13)}
        for y in range(2021, 2026):
            with open(os.path.join(REPO, "data", "raw", "asos", name, f"{y}.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        tt = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
                        tf = float(r["tmpf"])
                    except (ValueError, KeyError):
                        continue
                    key = np.datetime64(tt.replace(minute=0).strftime("%Y-%m-%dT%H"), "h") + (np.timedelta64(1, "h") if tt.minute >= 30 else np.timedelta64(0, "h"))
                    if key in era:
                        diffs[tt.month].append(era[key] - (tf - 32.0) / 1.8)
        print(f"{name}: grid point {z.lat.values[i]:.2f},{z.lon.values[i]:.2f} z_sfc {zs:.0f} m vs station {el:.0f} m")
        print("  ERA5 (lapse-moved) minus ASOS, mean by month:", " ".join(f"{m}:{np.mean(v):+.1f}" for m, v in diffs.items() if v), f"| all {np.mean(np.concatenate([v for v in diffs.values() if v])):+.2f} C, n {sum(len(v) for v in diffs.values())}")


if __name__ == "__main__":
    main()
