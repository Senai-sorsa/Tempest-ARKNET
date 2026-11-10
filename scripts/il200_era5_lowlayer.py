"""IL-200 step 2 (CPU): the ERA5 TRAINING TRUTH's low-layer shear at the balloon stations, for comparison with scripts/il200_lowlayer_shear.py (tool vs balloons).
Same layers (neighbour heights 10-2500 m), same stations (EPZ, MAF nearest profile point), same hours (00Z + 12Z of 2021-2022, a random 160 per station-hour group), m/s per km p50 / p99.
If ERA5 is already as sharp as the tool at 100-300 m, the excess comes from the data (ERA5 vs real soundings); if ERA5 is as smooth as the balloons, a later stage of the tool introduces it.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il200_era5_lowlayer.py [--out docs/results/logs/il200_era5_lowlayer.log]"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.calibrate import shear_map   # noqa: E402

ST = {"EPZ": (31.8728, -106.6981), "MAF": (31.9425, -102.2019)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/logs/il200_era5_lowlayer.log")
    ap.add_argument("--per-group", type=int, default=160)
    a = ap.parse_args()
    d = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    lat, lon = d.lat.values, d.lon.values
    t = pd.DatetimeIndex(d.time.values)
    rng = np.random.default_rng(0)
    H = d.height.values.astype(float)
    S = []
    for name, (la, lo) in ST.items():
        p = int(np.argmin((lat - la) ** 2 + ((lon - lo) * np.cos(np.radians(la))) ** 2))
        for hh in (0, 12):
            idx = np.flatnonzero((t.year >= 2021) & (t.year <= 2022) & (t.hour == hh))
            idx = np.sort(rng.choice(idx, min(a.per_group, len(idx)), replace=False))
            u = d.u.isel(point=p, time=idx).values
            v = d.v.isel(point=p, time=idx).values
            uv = np.stack([u, v], 1)
            S.append(shear_map.shears(uv.astype(np.float64))[1])
    s = np.concatenate(S, 0)
    lines = [f"IL-200 step 2: ERA5 training truth, same layers, EPZ + MAF, 00Z + 12Z 2021-22, {s.shape[0]} profiles (m/s per km)", "  layer (m)         ERA5 p50   ERA5 p99"]
    for k in range(12):
        lines.append(f"  {H[k]:6.0f}-{H[k + 1]:5.0f}    {np.median(s[:, k]):8.1f}   {np.quantile(s[:, k], .99):8.1f}")
    for l in lines:
        print(l)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
