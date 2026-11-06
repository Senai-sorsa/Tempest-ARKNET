"""Boundary-layer fill from ARCO-ERA5 (Google Cloud) instead of the Copernicus CDS: the same 8 pressure levels, the same box, written as <yyyymm>.nc.

    python -m tempest.ingest.arco_fill --months 202401 202402 --out data/raw/era5_cds [--workers 16] [--source gs|https]

Meant to run INSIDE Google's network (a free Colab notebook, see notebooks/arco_fill_colab.md): ARCO stores one global hour per chunk (85-120 MB per
variable, all 37 levels), so the machine that runs this reads about 0.5 GB per hour from the bucket, but only the small box (31-34 N, 108-101 W, 8 levels,
u v t r z) is written, about 25 MB per month. Run from a home connection it would move ~370 GB per month: do not.
ARCO has specific humidity, not relative humidity; RH is derived with the IFS mixed-phase formulas (IFS documentation Part IV, 7.2.1) as ERA5 does.
Months already present in --out (as .nc or .grib) are skipped, so a session that dies resumes. to_heights reads the .nc files like the CDS grib files.
"""
import argparse
import os

import numpy as np
import xarray as xr

URL = "ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
LEVELS = [975, 950, 900, 875, 825, 800, 775, 750]
LAT, LON = (34.0, 31.0), (252.0, 259.0)          # N to S as in the CDS files; longitudes 0-360
VARS = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t", "geopotential": "z", "specific_humidity": "q"}
T0, TICE = 273.16, 250.16
EPS = 287.0597 / 461.5250


def _es(t, a3, a4):
    return 611.21 * np.exp(a3 * (t - T0) / (t - a4))


def rh_from_q(q, t, p_pa):
    """Relative humidity in % from specific humidity, temperature (K) and pressure (Pa), ERA5/IFS mixed-phase saturation (water above 0 C, ice below -23 C)."""
    e = p_pa * q / (EPS + (1 - EPS) * q)
    alpha = np.clip(((t - TICE) / (T0 - TICE)) ** 2, 0, 1)
    alpha = np.where(t >= T0, 1.0, np.where(t <= TICE, 0.0, alpha))
    es = alpha * _es(t, 17.502, 32.19) + (1 - alpha) * _es(t, 22.587, -0.7)
    return np.clip(100 * e / es, 0, 100)


def open_arco(source="gs"):
    if source == "gs":
        import gcsfs  # noqa: F401  (Colab has it)
        m = __import__("fsspec").get_mapper("gs://gcp-public-data-arco-era5/" + URL, token="anon")
    else:
        m = __import__("fsspec").get_mapper("https://storage.googleapis.com/gcp-public-data-arco-era5/" + URL)
    return xr.open_zarr(m, consolidated=True, chunks=None)   # chunks={"time": 1} here builds dask arrays for all 273 variables: 5.9 GB before any read


def month(ds, yyyymm, workers):
    import dask
    t0 = np.datetime64(f"{yyyymm[:4]}-{yyyymm[4:]}-01")
    t1 = (t0.astype("datetime64[M]") + 1).astype("datetime64[h]")
    sub = ds[list(VARS)].sel(time=slice(t0, t1 - np.timedelta64(1, "h")), level=LEVELS, latitude=slice(*LAT), longitude=slice(*LON)).chunk({"time": 1})
    with dask.config.set(scheduler="threads", num_workers=workers):
        sub = sub.load()
    sub = sub.rename(VARS).rename(level="isobaricInhPa")
    p = sub.isobaricInhPa.astype(float) * 100.0
    out = xr.Dataset({"u": sub.u, "v": sub.v, "t": sub.t, "z": sub.z, "r": xr.apply_ufunc(rh_from_q, sub.q, sub.t, p)})
    return out.transpose("time", "isobaricInhPa", "latitude", "longitude").astype("float32")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--months", nargs="+", required=True, help="yyyymm ...")
    ap.add_argument("--out", default="data/raw/era5_cds")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--source", choices=["gs", "https"], default="gs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ds = open_arco(a.source)
    for ym in a.months:
        if any(os.path.exists(os.path.join(a.out, ym + e)) for e in (".nc", ".grib")):
            print(ym, "present, skipped", flush=True)
            continue
        tmp = os.path.join(a.out, ym + ".nc.part")
        month(ds, ym, a.workers).to_netcdf(tmp)
        os.replace(tmp, os.path.join(a.out, ym + ".nc"))
        print(ym, "written", flush=True)


if __name__ == "__main__":
    main()
