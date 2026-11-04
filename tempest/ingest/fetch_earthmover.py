"""Download the pilot-box ERA5 (13 pressure levels + surface) from Earthmover's public icechunk store.

    python -m tempest.ingest.fetch_earthmover [--out data/raw/era5_em] [--years N] [--first 1991] [--last 2025-12-31]

One variable at a time to data/raw/era5_em/<var>.zarr. Finished variables are skipped, so rerunning resumes.
Box 31-34 N, 108-101 W (store longitude is 0-360). Time starts on the store's time-chunk boundary just before
1991 (late 1990), so no chunk is read twice; to_heights trims to 1991-2025.
"""
import argparse
import os
import shutil
import time

import dask
import icechunk as ic
import numpy as np
import xarray as xr

PRESSURE = ["u", "v", "t", "r", "z"]
SINGLE = ["u10", "v10", "u100", "v100", "t2m", "d2m", "sp"]
LAT, LON = (34.0, 31.0), (252.0, 259.0)
START, END = np.datetime64("1991-01-01T00"), np.datetime64("2025-12-31T23")


def open_store():
    s = ic.s3_storage(bucket="earthmover-icechunk-era5", prefix="icechunkV2", region="us-east-1", anonymous=True)
    repo = ic.Repository.open(storage=s, config=ic.RepositoryConfig(max_concurrent_requests=16))
    return repo.readonly_session("main").store


def subset(ds, years=None, start=START, end=END):
    ds = ds.sel(latitude=slice(*LAT), longitude=slice(*LON))
    tc = ds["u10" if "u10" in ds else "u"].encoding["chunks"][0]
    t = ds.valid_time.values
    i0 = (int(np.searchsorted(t, start)) // tc) * tc
    i1 = int(np.searchsorted(t, end, side="right"))
    if years:
        i1 = min(i1, i0 + years * tc)
    ds = ds.isel(valid_time=slice(i0, i1)).drop_vars(["sdor", "slor"], errors="ignore")
    return ds.chunk({"valid_time": tc, "latitude": -1, "longitude": -1}), tc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/era5_em")
    ap.add_argument("--years", type=int, help="only the first N time chunks (for a quick test)")
    ap.add_argument("--first", type=int, default=1991, help="first year (the store starts 1940; indices from 1980)")
    ap.add_argument("--last", default="2025-12-31", help="last day, YYYY-MM-DD")
    a = ap.parse_args()
    start, end = np.datetime64(f"{a.first}-01-01T00"), np.datetime64(f"{a.last}T23")
    os.makedirs(a.out, exist_ok=True)
    store = open_store()
    groups = {"pressure/temporal": PRESSURE, "single/temporal": SINGLE}
    with dask.config.set(scheduler="threads", num_workers=16):
        for group, names in groups.items():
            ds, tc = subset(xr.open_zarr(store, group=group, zarr_format=3, chunks={}), a.years, start, end)
            for v in names:
                dst = os.path.join(a.out, f"{v}.zarr")
                if os.path.exists(dst):
                    print(f"{v}: done already, skipping", flush=True)
                    continue
                part, t0 = dst + ".part", time.time()
                shutil.rmtree(part, ignore_errors=True)
                da = ds[[v]]
                if "pressure_level" in da.dims:
                    da = da.chunk({"pressure_level": 1})
                for c in da.variables.values():
                    c.encoding = {}
                da.to_zarr(part, mode="w", zarr_format=3)
                os.rename(part, dst)
                print(f"{v}: {dict(da.sizes)} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
