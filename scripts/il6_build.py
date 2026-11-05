"""IL-73 step 1: assemble the mode F training rows (HRES profile vs ERA5 profile) per year into data/modeF/<year>.npz. CPU only; resumable.
    PYTHONPATH=. python scripts/il6_build.py [--points 60]
"""
import argparse
import os
import time

import numpy as np
import xarray as xr

from tempest.forecast import modeF

ap = argparse.ArgumentParser()
ap.add_argument("--points", type=int, default=60)
ap.add_argument("--first", type=int, default=2016)
ap.add_argument("--last", type=int, default=2022)
a = ap.parse_args()
ds = xr.open_zarr("data/pilot/profiles80.zarr")
for y in range(a.first, a.last + 1):
    out = f"data/modeF/{y}.npz"
    if os.path.exists(out):
        print(y, "present", flush=True)
        continue
    t0 = time.time()
    d = modeF.load_year(y, ds, n_points=a.points)
    np.savez(out + ".part.npz", **{k: v for k, v in d.items()})
    os.replace(out + ".part.npz", out)
    print(y, len(d["obs"]), "rows", f"{time.time() - t0:.0f}s", flush=True)
