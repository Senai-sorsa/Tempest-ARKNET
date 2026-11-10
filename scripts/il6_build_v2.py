"""F-V2 (2026-11-10): mode F training rows from the 00Z + 12Z HRES refetch (data/raw/wb2_hres_v2, valid 00 / 12 / 18 UTC, leads 6-240 h) against the ERA5 profiles
(data/pilot/profiles80.zarr), with the shipped boundary-layer tables (models/modeF_bl.npz). Writes data/modeF_v2/<year>.npz; resumable. CPU only.
The old rows (data/modeF, 00Z starts, whole-day leads) are untouched.
    PYTHONPATH=. python scripts/il6_build_v2.py [--first 2016] [--last 2022] [--points 16] [--hres-dir data/raw/wb2_hres_v2] [--store data/pilot/profiles80.zarr] [--out-dir data/modeF_v2]"""
import argparse
import os
import time

import numpy as np
import xarray as xr

from tempest.forecast import modeF

ap = argparse.ArgumentParser()
ap.add_argument("--first", type=int, default=2016)
ap.add_argument("--last", type=int, default=2022)
ap.add_argument("--points", type=int, default=16)
ap.add_argument("--hres-dir", default="data/raw/wb2_hres_v2")
ap.add_argument("--store", default="data/pilot/profiles80.zarr")
ap.add_argument("--out-dir", default="data/modeF_v2")
ap.add_argument("--bl", default="models/modeF_bl.npz")
a = ap.parse_args()
os.makedirs(a.out_dir, exist_ok=True)
ds = xr.open_zarr(a.store)
bl = dict(np.load(a.bl)) if a.bl and os.path.exists(a.bl) else None
print("boundary-layer tables:", a.bl if bl else "default (neutral law)", flush=True)
for y in range(a.first, a.last + 1):
    out = f"{a.out_dir}/{y}.npz"
    if os.path.exists(out):
        print(y, "present", flush=True)
        continue
    t0 = time.time()
    d = modeF.load_year_v2(y, ds, hres_dir=a.hres_dir, n_points=a.points, bl=bl)
    np.savez(out + ".part.npz", **d)
    os.replace(out + ".part.npz", out)
    vh = np.bincount(d["valid_utc_hour"], minlength=24)
    print(y, f"{len(d['obs']):,} rows", f"{time.time() - t0:.0f}s", "valid UTC hours", {h: int(n) for h, n in enumerate(vh) if n}, f"leads {d['lead_hours'].min()}-{d['lead_hours'].max()} h", flush=True)
