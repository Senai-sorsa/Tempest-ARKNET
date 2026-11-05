"""Near-term ensembles -> profiles on our 44 heights above ground (PHASE4_FORECAST.md 4.7 / TOOL_PLAN mode 2 conversion).

    from tempest.nearterm import ensemble
    doc = ensemble.read_logged("data/ops/raw/midland/ecmwf_ifs025/20261105_00z.json.gz")
    prof = ensemble.to_profiles(doc)          # dict of arrays (members, hours, 44) for u, v, T (K), RH (%) + surface (members, hours)

Input is an Open-Meteo ensemble response (the daily logger's files, tempest.ops.logger): per member, hourly temperature (deg C),
relative humidity, wind speed (m/s) and direction (deg, from which the wind blows), geopotential height (m) on 13 pressure levels,
plus 2 m temperature, 2 m humidity (not served for WeatherNext 2), surface pressure (hPa) and 10 m wind. Levels at or below the ground
(pressure within 5 hPa of the surface pressure, or higher) are dropped; the 2 m and 10 m values anchor the lowest part of the profile
(as profiles.to_heights does for ERA5, except there is no 100 m anchor here). This is plain interpolation with no correction of any kind.
"""
import gzip
import json

import numpy as np

from tempest.profiles.to_heights import G0, HEIGHTS, geometric_height, interp_columns, liquid_rh  # noqa: F401 (liquid_rh: ERA5 humidity is converted elsewhere)

LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]


def read_logged(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _members(h, var):
    """-> (M, T) array of one variable over all members (control first); None if the variable is absent or all null."""
    keys = [k for k in h if k == var or (k.startswith(var + "_member") and k[len(var) + 7:].isdigit())]
    if not keys:
        return None
    keys.sort(key=lambda k: (k != var, k))
    a = np.array([[np.nan if x is None else x for x in h[k]] for k in keys], np.float64)
    return None if np.isnan(a).all() else a


def _uv(speed, direction):
    r = np.deg2rad(direction)
    return -speed * np.sin(r), -speed * np.cos(r)


def to_profiles(doc, elevation=None):
    """Open-Meteo ensemble response -> dict(time, u, v, T, RH (M, T, 44); t2m, sp, rh2m (M, T)). `elevation` (m above sea level) defaults to the response's."""
    h = doc["hourly"]
    elev = float(doc.get("elevation", 0.0) if elevation is None else elevation)
    get = lambda var: _members(h, var)
    t2m, sp, ws10, wd10 = (get(v) for v in ("temperature_2m", "surface_pressure", "wind_speed_10m", "wind_direction_10m"))
    rh2m = get("relative_humidity_2m")
    M, T = t2m.shape
    t2m = t2m + 273.15
    sp = sp * 100.0
    lev = lambda base: np.stack([get(f"{base}_{p}hPa") for p in LEVELS], -1)          # (M, T, L)
    temp, rh, ws, wd, gh = (lev(b) for b in ("temperature", "relative_humidity", "wind_speed", "wind_direction", "geopotential_height"))
    temp = temp + 273.15
    u, v = _uv(ws, wd)
    u10, v10 = _uv(ws10, wd10)
    agl = geometric_height(gh * G0) - elev                                            # metres above the site
    above = (np.array(LEVELS)[None, None, :] * 100.0 < sp[..., None] - 500.0) & (agl > 0)
    agl = np.where(above, agl, np.nan)
    shape = agl.shape[:-1] + (1,)
    hw = np.concatenate([np.full(shape, 10.0), agl], -1)
    ht = np.concatenate([np.full(shape, 2.0), agl], -1)
    rh_anchor = rh2m if rh2m is not None else np.where(np.isfinite(rh[..., :1].squeeze(-1)), np.clip(rh[..., 0], 0, 100), np.nan)
    out = dict(
        time=np.array(h["time"], dtype="datetime64[m]"),
        u=interp_columns(hw, np.concatenate([u10[..., None], u], -1), HEIGHTS, 100),
        v=interp_columns(hw, np.concatenate([v10[..., None], v], -1), HEIGHTS, 100),
        T=interp_columns(ht, np.concatenate([t2m[..., None], temp], -1), HEIGHTS),
        RH=interp_columns(ht, np.concatenate([np.clip(rh_anchor, 0, 100)[..., None], np.clip(rh, 0, 100)], -1), HEIGHTS),
        t2m=t2m.astype(np.float32), sp=sp.astype(np.float32),
        rh2m=(np.clip(rh2m, 0, 100) if rh2m is not None else np.clip(rh_anchor, 0, 100)).astype(np.float32),
        elevation=elev, rh2m_is_model=rh2m is not None)
    return out
