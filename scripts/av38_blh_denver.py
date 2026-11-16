"""AV38 data pull: ERA5 hourly blh at the Denver cell (39.75 N, 255.25 E = -104.75; covers DEN, APA and balloon 72469 within 0.125 deg), 2016-2023, Earthmover public store.
Output data/kit/av38_blh_denver.nc (resumable).   .venv/Scripts/python scripts/av38_blh_denver.py"""
import os
import sys

import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.ingest.fetch_earthmover import open_store  # noqa: E402

OUT = os.path.join(REPO, "data", "kit", "av38_blh_denver.nc")
if os.path.exists(OUT):
    print("present:", OUT)
else:
    ds = xr.open_zarr(open_store(), group="single/temporal", zarr_format=3, chunks={})[["blh"]].sel(valid_time=slice("2016-01-01", "2023-12-31"))
    p = ds.sel(latitude=39.75, longitude=255.25, method="nearest").load()
    print(dict(p.sizes), float(p.latitude), float(p.longitude))
    p.to_netcdf(OUT + ".part")
    os.replace(OUT + ".part", OUT)
    print("wrote", OUT)
