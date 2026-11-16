"""WD6 data pull: ERA5 hourly u10 v10 u100 v100 blh ssrd at the five WFIP1 sodar sites (nearest 0.25 deg point), 2011-06-01 to 2012-10-31, from Earthmover's public icechunk store.
Site positions are approximate (town / site area, no coordinates on disk): ERA5 is 0.25 deg, so a few km do not matter. Output data/kit/wd6_era5_points.nc (small). Resumable: skips if present.
    .venv/Scripts/python scripts/wd6_era5_points.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.ingest.fetch_earthmover import open_store  # noqa: E402

SITES = {"brady": (31.14, -99.33), "cleburne": (32.35, -97.43), "colorado_city": (32.39, -100.87), "jayton": (33.25, -100.57), "ozona": (30.71, -101.20)}
VARS = {"single/temporal": ["u10", "v10", "u100", "v100", "blh", "ssrd"]}
OUT = os.path.join(REPO, "data", "kit", "wd6_era5_points.nc")


def main():
    if os.path.exists(OUT):
        print("present:", OUT)
        return
    store = open_store()
    parts = []
    for g, names in VARS.items():
        ds = xr.open_zarr(store, group=g, zarr_format=3, chunks={})[names].sel(valid_time=slice("2011-06-01", "2012-10-31"))
        for s, (la, lo) in SITES.items():
            p = ds.sel(latitude=la, longitude=lo % 360, method="nearest").load()
            parts.append(p.expand_dims(site=[s]).drop_vars(["latitude", "longitude"], errors="ignore"))
            print(s, "ok", dict(p.sizes), flush=True)
    xr.concat(parts, "site").to_netcdf(OUT + ".part")
    os.replace(OUT + ".part", OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
