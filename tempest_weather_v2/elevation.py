"""Ground elevation at a point (launch site), from free public elevation services, with a cache and an offline fallback.

    e = lookup(32.99, -106.97)            # -> Elevation(m=1401.3, ft=4597.4, source="usgs-3dep", resolution_m=..., note="")
    e.m, e.ft, e.source

Order tried (source="auto"):
  1. USGS Elevation Point Query Service (3DEP, bare earth, ~1-10 m in the US; no key)       epqs.nationalmap.gov/v1/json
  2. Open Topo Data, dataset ned10m (USGS NED 1/3 arc-second, ~10 m, US; no key;
     public limits 1 call/s, 1000 calls/day)                                                 api.opentopodata.org/v1/ned10m
  3. Open-Meteo Elevation API (Copernicus GLO-90, 90 m, worldwide; no key, non-commercial)   api.open-meteo.com/v1/elevation
  4. a bundled offline DEM (assets/dem.npz: lat, lon, elev arrays), bilinear                 if installed
If every step fails, lookup() raises ElevationUnavailable; the caller then uses the model grid elevation and flags it.

Notes
* Only the standard library is used for the network calls (urllib), so the tool stays numpy-only.
* Results are cached per point (rounded to 1e-5 deg, ~1 m) in a JSON file in the user cache folder, so a site costs one call ever.
* verify=True also asks a second service and flags a disagreement above `tol_m` (default 15 m): a cheap check against a bad point.
* Copernicus GLO-90 is a surface model (includes buildings / trees); USGS 3DEP and NED are bare earth. For an open pad the difference is small.
* Heights are orthometric (above the geoid, i.e. "above sea level" as maps, RASAero, and OpenRocket use).
"""
import os
import time
import urllib.parse
from dataclasses import dataclass, asdict

import numpy as np

from tempest_weather_v2 import _files, _net

FT = 3.28084
UA = "tempest-weather elevation lookup"
NODATA = -1000.0           # anything below this is treated as "no data" (USGS returns -1000000 outside coverage)

_DEM_CACHE = {}            # path -> (lat_asc, lon_asc, elev_array) cached in memory so np.load runs once per file


class ElevationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Elevation:
    m: float
    source: str
    resolution_m: float
    note: str = ""

    @property
    def ft(self):
        return self.m * FT

    def __str__(self):
        return f"{self.ft:,.0f} ft ({self.m:,.1f} m), {self.source}" + (f"; {self.note}" if self.note else "")


# ---------------------------------------------------------------- services (each: (lat, lon, timeout) -> metres, raises on failure)

def _get_json(url, timeout, service=None):
    """Through the shared network layer: timeouts, retries, rate limit per service, strict offline mode (N1-N3)."""
    return _net.fetch_json(url, service=service, timeout=timeout, headers={"Accept": "application/json"}, retries=1)


def _valid(x):
    if x is None:
        raise ValueError("no data at this point")
    try:
        x = float(x)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric elevation response: {x!r}") from exc
    if not np.isfinite(x) or x < NODATA:
        raise ValueError("no data at this point")
    return x


def usgs_3dep(lat, lon, timeout=6.0):
    q = urllib.parse.urlencode(dict(x=lon, y=lat, wkid=4326, units="Meters", includeDate="false"))
    d = _get_json(f"https://epqs.nationalmap.gov/v1/json?{q}", timeout, "usgs-epqs")
    return _valid(d.get("value"))


def opentopodata_ned10m(lat, lon, timeout=6.0):
    d = _get_json(f"https://api.opentopodata.org/v1/ned10m?locations={lat:.6f},{lon:.6f}", timeout, "opentopodata")
    if d.get("status") != "OK":
        raise ValueError(d.get("error", "status not OK"))
    return _valid(d["results"][0]["elevation"])


def open_meteo_glo90(lat, lon, timeout=6.0):
    d = _get_json(f"https://api.open-meteo.com/v1/elevation?latitude={lat:.6f}&longitude={lon:.6f}", timeout, "open-meteo")
    return _valid(d["elevation"][0])


SERVICES = {                         # name -> (function, nominal resolution in m, rough coverage test)
    "usgs-3dep": (usgs_3dep, 10.0, lambda lat, lon: 24 <= lat <= 50 and -125 <= lon <= -66),
    "opentopodata-ned10m": (opentopodata_ned10m, 10.0, lambda lat, lon: 24 <= lat <= 50 and -125 <= lon <= -66),
    "open-meteo-glo90": (open_meteo_glo90, 90.0, lambda lat, lon: -90 <= lat <= 90),
}


# ---------------------------------------------------------------- offline DEM

def _load_dem(path):
    abspath = os.path.abspath(path)
    mtime = os.path.getmtime(abspath)
    cached = _DEM_CACHE.get(abspath)
    if cached is not None and cached[0] == mtime:
        return cached[1], cached[2], cached[3]
    with np.load(abspath) as z:
        la = z["lat"].astype(float)
        lo = z["lon"].astype(float)
        el = z["elev"].astype(float)
    if la[0] > la[-1]:
        la, el = la[::-1], el[::-1]
    _DEM_CACHE[abspath] = (mtime, la, lo, el)
    return la, lo, el


def offline(lat, lon, path):
    """Bilinear elevation from a regular lat/lon grid stored as npz (lat ascending or descending, lon ascending, elev [lat, lon])."""
    la, lo, el = _load_dem(path)
    if not (la[0] <= lat <= la[-1] and lo[0] <= lon <= lo[-1]):
        raise ValueError("point outside the offline DEM")
    i = int(np.clip(np.searchsorted(la, lat) - 1, 0, len(la) - 2))
    j = int(np.clip(np.searchsorted(lo, lon) - 1, 0, len(lo) - 2))
    fy = (lat - la[i]) / (la[i + 1] - la[i])
    fx = (lon - lo[j]) / (lo[j + 1] - lo[j])
    v = (
        el[i, j] * (1 - fy) * (1 - fx)
        + el[i + 1, j] * fy * (1 - fx)
        + el[i, j + 1] * (1 - fy) * fx
        + el[i + 1, j + 1] * fy * fx
    )
    res = abs(la[1] - la[0]) * 111_000.0
    return _valid(v), res


# ---------------------------------------------------------------- cache

def _cache_path():
    return os.path.join(_files.cache_dir(), "elevation.json")


def _key(lat, lon):
    return f"{lat:.5f},{lon:.5f}"


def _cache_read():
    return _files.read_json(_cache_path(), {}) or {}          # a corrupt cache file is removed and read as empty


def _cache_write(c):
    try:
        with _files.file_lock(_cache_path()):
            merged = _cache_read()                              # another process may have added points meanwhile
            merged.update(c)
            _files.atomic_json(_cache_path(), merged)
    except (OSError, TimeoutError):
        pass                                                    # a cache that cannot be written is not an error


# ---------------------------------------------------------------- public

def lookup(lat, lon, source="auto", timeout=6.0, cache=True, verify=False, tol_m=15.0, offline_dem=None, verbose=False):
    """Ground elevation at (lat, lon) -> Elevation. source: "auto", a name in SERVICES, or "offline"."""
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"({lat}, {lon}) is not a valid latitude/longitude")
    k = _key(lat, lon)
    c = _cache_read() if cache else {}
    if cache and k in c and source in ("auto", c[k]["source"]):
        return Elevation(**c[k])

    names = (
        [n for n, (_, _, cover) in SERVICES.items() if cover(lat, lon)]
        if source == "auto"
        else ([] if source == "offline" else [source])
    )
    errors, got = [], []
    for n in names:
        fn, res, _ = SERVICES[n]
        t0 = time.time()
        try:
            got.append(Elevation(m=round(fn(lat, lon, timeout), 2), source=n, resolution_m=res))
            if verbose:
                print(f"elevation: {n} {got[-1].m:.1f} m in {time.time() - t0:.2f} s")
            if not verify or len(got) == 2:
                break
        except Exception as e:                      # network, HTTP, parsing or no-data: try the next one
            errors.append(f"{n}: {type(e).__name__}: {e}")
    if not got and source in ("auto", "offline") and (offline_dem or os.environ.get("TEMPEST_DEM")):
        try:
            v, res = offline(lat, lon, offline_dem or os.environ["TEMPEST_DEM"])
            got.append(Elevation(m=round(v, 2), source="offline-dem", resolution_m=round(res)))
        except Exception as e:
            errors.append(f"offline-dem: {e}")
    if not got:
        raise ElevationUnavailable(
            "no elevation source answered: " + "; ".join(errors)
            if errors
            else "no elevation source covers this point"
        )

    best = got[0]
    if len(got) == 2 and abs(got[0].m - got[1].m) > tol_m:
        best = Elevation(
            best.m,
            best.source,
            best.resolution_m,
            note=f"{got[1].source} says {got[1].m:.0f} m ({got[0].m - got[1].m:+.0f} m): check the coordinates",
        )
    if cache and not best.note:
        c[k] = asdict(best)
        _cache_write(c)
    return best

