"""ERA5 profiles at our 44 heights from a local store (the pilot profiles zarr built by tempest.profiles.to_heights).

    store = open_store(path)                         # needs xarray + zarr (optional dependencies; a clear message if missing)
    e = profile(store, lat, lon, t_utc)              # dict: u, v, T, RH (44,), t2m, sp, rh2m, elev, point, time

The path can also come from the environment variable TEMPEST_ERA5_STORE. Only hours the store keeps (UTC 12-23 and 00-04) exist; others raise LookupError.
Online access to the Earthmover store for machines without a local copy is not implemented yet (PHASE5_TOOL.md, 5.4).
"""
import os

import numpy as np

ENV = "TEMPEST_ERA5_STORE"


def default_path():
    p = os.environ.get(ENV)
    return p if p and os.path.exists(p) else None


def open_store(path):
    try:
        import xarray as xr
    except ImportError as e:
        raise ImportError("past dates from a local ERA5 store need `pip install xarray zarr` (optional dependencies)") from e
    return xr.open_zarr(path)


def profile(store, lat, lon, t_utc):
    t = np.datetime64(np.datetime64(t_utc, "h"))
    times = store.time.values
    i = np.searchsorted(times, t)
    if i >= len(times) or times[i] != t:
        raise LookupError(f"the ERA5 store has no {str(t)[:13]} UTC (it keeps UTC hours 12-23 and 00-04 and ends {str(times[-1])[:10]})")
    p = int(np.argmin((store.lat.values - lat) ** 2 + (store.lon.values - lon) ** 2))
    d = store.isel(point=p, time=int(i))
    out = {k: np.asarray(d[k].values, float) for k in ("u", "v", "T", "RH")}
    out.update({k: float(d[k].values) for k in ("t2m", "sp", "rh2m")})
    out.update(elev=float(d["z_sfc"].values), point=p, time=str(t))
    if not all(np.isfinite(out[k]).all() for k in ("u", "v", "T", "RH")):
        raise LookupError("the ERA5 profile has missing levels at that time and place")
    return out
