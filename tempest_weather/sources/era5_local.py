"""ERA5 profiles at our 44 heights from a local store (the pilot profiles zarr built by tempest.profiles.to_heights).

    store = open_store(path)                         # needs xarray + zarr (optional dependencies; a clear message if missing)
    e = profile(store, lat, lon, t_utc)              # dict: u, v, T, RH (44,), t2m, sp, rh2m, elev, point, time

The path can also come from the environment variable TEMPEST_ERA5_STORE. Only hours the store keeps (UTC 12-23 and 00-04) exist; others raise LookupError.
A24 (2026-11-10, all hours): the path may list SEVERAL stores separated by os.pathsep (";" on Windows), e.g. the day store and the night store (UTC 05-11,
data/pilot/profiles80_night.zarr); they are joined along time (sorted, the first store wins a duplicated hour). One path behaves as before.
Online access to the Earthmover store for machines without a local copy is not implemented yet (PHASE5_TOOL.md, 5.4).
"""
import os

import numpy as np

ENV = "TEMPEST_ERA5_STORE"


def _paths(p):
    return [q for q in str(p).split(os.pathsep) if q]


def default_path():
    p = os.environ.get(ENV)
    return p if p and _paths(p) and all(os.path.exists(q) for q in _paths(p)) else None


def open_store(path):
    try:
        import xarray as xr
    except ImportError as e:
        raise ImportError("past dates from a local ERA5 store need `pip install xarray zarr` (optional dependencies)") from e
    paths = _paths(path)
    if len(paths) == 1:
        return xr.open_zarr(paths[0])
    ds = xr.concat([xr.open_zarr(q) for q in paths], dim="time", data_vars="minimal", coords="minimal", compat="override", join="override")
    _, first = np.unique(ds.time.values, return_index=True)                 # sorted unique hours; np.unique keeps the first occurrence
    return ds.isel(time=np.sort(first)).sortby("time")


def profile(store, lat, lon, t_utc):
    t = np.datetime64(np.datetime64(t_utc, "h"))
    times = store.time.values
    i = np.searchsorted(times, t)
    if i >= len(times) or times[i] != t:
        raise LookupError(f"the ERA5 store has no {str(t)[:13]} UTC (it keeps UTC hours {sorted(set((times[-2000:].astype('datetime64[h]').astype(int) % 24).tolist()))} and ends {str(times[-1])[:10]}; the night hours UTC 05-11 need the night store, see the module note)")
    p = int(np.argmin((store.lat.values - lat) ** 2 + (store.lon.values - lon) ** 2))
    d = store.isel(point=p, time=int(i))
    out = {k: np.asarray(d[k].values, float) for k in ("u", "v", "T", "RH")}
    out.update({k: float(d[k].values) for k in ("t2m", "sp", "rh2m")})
    out.update(elev=float(d["z_sfc"].values), point=p, time=str(t))
    if not all(np.isfinite(out[k]).all() for k in ("u", "v", "T", "RH")):
        raise LookupError("the ERA5 profile has missing levels at that time and place")
    return out
