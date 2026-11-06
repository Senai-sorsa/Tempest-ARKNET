"""Lead-time forecast history for the pilot box from WeatherBench2 (IFS HRES, Google Cloud), for calibrating forecast modes F / F2 (improvement loop IL-6).

    python -m tempest.ingest.wb2_fetch --out data/raw/wb2_hres [--first 2016] [--last 2022] [--every-days 4] [--leads 24 72 120 168] [--workers 16]

WeatherBench2 stores one forecast (init time, lead, all 13 levels, whole globe) per chunk, about 30 MB per variable, so run this INSIDE Google's network
(a free Colab notebook, notebooks/wb2_colab.md) and keep only the box 31-34 N, 108-101 W; the output is a few MB per year. Reading it from a home connection
would move about 200 GB. Output: <out>/<year>.nc with u, v, t, q, z (init, lead, level, lat, lon) and u10, v10, t2m, sp (init, lead, lat, lon). Years already present are skipped.
Initial times: 00 UTC on every `--every-days`-th day (a spread over the seasons, 320 starts for 2016-2022 at 4), leads in hours (HRES has 6-hourly leads up to 240 h).
"""
import argparse
import os

import numpy as np
import xarray as xr

URL = "weatherbench2/datasets/hres/2016-2022-0012-1440x721.zarr"
from tempest import region as _region  # noqa: E402

_R = _region.load()
LAT, LON = (_R.lat_south, _R.lat_north), _R.era5_lon360      # the box comes from configs/region.toml (HRES latitudes ascend; longitudes 0-360)
UPPER = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t", "specific_humidity": "q", "geopotential": "z"}
SURF = {"10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10", "2m_temperature": "t2m", "surface_pressure": "sp"}


def open_hres(source="https"):
    import fsspec
    m = fsspec.get_mapper(("gs://" if source == "gs" else "https://storage.googleapis.com/") + URL, **({"token": "anon"} if source == "gs" else {}))
    return xr.open_zarr(m, consolidated=True)


def year(ds, y, every_days, leads, workers):
    import dask
    t = ds.time.values
    sel = t[(t.astype("datetime64[Y]").astype(int) + 1970 == y) & (t.astype("datetime64[h]").astype(int) % 24 == 0)]
    sel = sel[:: every_days]
    box = dict(latitude=slice(*LAT), longitude=slice(*LON))
    lead_td = [np.timedelta64(h, "h") for h in leads] if ds.prediction_timedelta.dtype.kind == "m" else list(leads)   # this store keeps leads as integer hours
    sub = ds[list(UPPER) + list(SURF)].sel(time=sel, prediction_timedelta=lead_td, **box)
    with dask.config.set(scheduler="threads", num_workers=workers):
        sub = sub.load()
    sub = sub.rename({**UPPER, **SURF})
    return sub.astype("float32")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/wb2_hres")
    ap.add_argument("--first", type=int, default=2016)
    ap.add_argument("--last", type=int, default=2022)
    ap.add_argument("--every-days", type=int, default=4)
    ap.add_argument("--leads", type=int, nargs="+", default=[24, 72, 120, 168])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--source", choices=["gs", "https"], default="gs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ds = open_hres(a.source)
    for y in range(a.first, a.last + 1):
        path = os.path.join(a.out, f"{y}.nc")
        if os.path.exists(path):
            print(y, "present, skipped", flush=True)
            continue
        year(ds, y, a.every_days, a.leads, a.workers).to_netcdf(path + ".part")
        os.replace(path + ".part", path)
        print(y, "written", flush=True)


if __name__ == "__main__":
    main()
