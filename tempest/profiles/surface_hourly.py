"""Hourly surface fields for every grid point, all 24 hours, from the raw Earthmover pulls (PHASED_PLAN 3.1, 3.3, 3.4).

    python -m tempest.profiles.surface_hourly [--raw data/raw/era5_em] [--profiles data/pilot/profiles80.zarr]
                                              [--out data/pilot/surface_hourly.zarr]

Variables: t2m (K), u10, v10 (m/s), fg10 (m/s, gust), blh (m), ssrd (W/m2, solar radiation reaching the ground),
ssr (W/m2, net solar), slhf (W/m2, latent heat flux, upward negative as ERA5 stores it). Accumulated ERA5 fields
(ssrd, ssr, slhf) are J/m2 over the hour ending at the stamp; they are divided by 3600 here.
Dims (point, time) with the same point order as the profile store (13 x 29 grid, lat 34 -> 31, lon -108 -> -101),
so row i of one is the same place as row i of the other. Finished files are skipped.
"""
import argparse
import os
import shutil

import numpy as np
import xarray as xr

VARS = ["t2m", "u10", "v10", "fg10", "blh", "ssrd", "ssr", "slhf"]
ACCUM = {"ssrd", "ssr", "slhf"}


def build(raw, profiles, out):
    pts = xr.open_zarr(profiles)
    arrs = []
    for v in VARS:
        ds = xr.open_zarr(os.path.join(raw, f"{v}.zarr"), zarr_format=3)
        da = ds[v].stack(point=("latitude", "longitude")).transpose("point", "valid_time")
        lat, lon = da.latitude.values, da.longitude.values
        lon = np.where(lon > 180, lon - 360, lon)
        if not (np.allclose(lat, pts.lat.values) and np.allclose(lon, pts.lon.values)):
            raise SystemExit(f"{v}: grid points differ from the profile store")
        if v in ACCUM:
            da = da / 3600.0
        arrs.append(da.reset_index("point", drop=True).drop_vars(["latitude", "longitude", "lsm", "z_sfc"], errors="ignore").rename(valid_time="time").to_dataset(name=v))
    ds = xr.merge(arrs).chunk({"point": 377, "time": 8760})
    for c in ds.variables.values():
        c.encoding = {}
    part = out + ".part"
    shutil.rmtree(part, ignore_errors=True)
    ds.to_zarr(part, mode="w")
    os.rename(part, out)
    return ds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw/era5_em")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--out", default="data/pilot/surface_hourly.zarr")
    a = ap.parse_args()
    if os.path.exists(a.out):
        print(f"{a.out} exists, skipping")
        return
    ds = build(a.raw, a.profiles, a.out)
    print(f"wrote {a.out}: {dict(ds.sizes)}")


if __name__ == "__main__":
    main()
