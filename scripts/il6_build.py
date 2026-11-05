"""IL-73 / F-9 step 1: assemble the mode F training rows (HRES profile vs ERA5 profile) per year into data/modeF/<year>.npz. CPU only; resumable.
    PYTHONPATH=. python scripts/il6_build.py [--points 60] [--refit-bl]
First pass uses the neutral log law and a constant dew point; with --refit-bl the boundary-layer tables (u100 / u10 per lapse-rate bin, 2 m dew point from the lowest
level) are fitted on the 2016-2020 rows (models/modeF_bl.npz) and every year is rebuilt with them (review item F-9).
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
ap.add_argument("--refit-bl", action="store_true")
a = ap.parse_args()
ds = xr.open_zarr("data/pilot/profiles80.zarr")
bl = None
if a.refit_bl:
    rows = {}
    for y in range(2016, 2021):
        d = np.load(f"data/modeF/{y}.npz")
        for k in ("obs", "lapse_low", "dpd_low"):
            rows.setdefault(k, []).append(d[k])
    rows = {k: np.concatenate(v) for k, v in rows.items()}
    bl = modeF.fit_boundary_layer(rows)
    np.savez("models/modeF_bl.npz", **bl)
    print("boundary-layer tables:", {k: np.round(v, 3).tolist() for k, v in bl.items()}, flush=True)
for y in range(a.first, a.last + 1):
    out = f"data/modeF/{y}.npz"
    if os.path.exists(out) and not a.refit_bl:
        print(y, "present", flush=True)
        continue
    t0 = time.time()
    d = modeF.load_year(y, ds, n_points=a.points, bl=bl)
    np.savez(out + ".part.npz", **{k: v for k, v in d.items()})
    os.replace(out + ".part.npz", out)
    print(y, len(d["obs"]), "rows", f"{time.time() - t0:.0f}s", flush=True)
