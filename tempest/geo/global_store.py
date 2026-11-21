"""Readers for the G-stage stores (docs/global/README.md data notes). Every reader runs tempest.geo.holdout.check.

    from tempest.geo import global_store as gs
    pts = gs.points()                          # lat, lon, ilat, ilon, igra of the 7,483 store points
    m = gs.month("2020-01")                    # decoded floats: u v t r z (days, 13, P), surface (days, P), valid_time
    prof, rh2m = gs.profiles(m, pts, idx)      # 44-height profiles (u, v, T, RH) like the regional stores
    x = gs.extra("2020-01")                    # w fg10 blh cape tcc tp
    h = gs.hres("202001")                      # WeatherBench2 HRES u v t q z (100 forecasts, 13, P) + u10 v10 t2m sp

Store levels run 1000 -> 50 hPa (bottom up). RH is clipped to 0-100 % (the store holds -21 to 186 %).
"""
import os

import numpy as np

from tempest.geo import holdout

STORE = "data/raw/era5_global"
EXTRA = "data/raw/era5_global_extra"
HRES = "data/raw/wb2_hres_global"
G = 9.80665
LAST_YEAR = 2025


def _code(d, default=None):
    """{name: (scale, offset)} from a file's `code` array ("name scale offset"), else the default table."""
    if "code" in d:
        return {s.split()[0]: (float(s.split()[1]), float(s.split()[2])) for s in np.asarray(d["code"]).astype(str)}
    return default


def _decode(d, code, skip=()):
    out = {}
    for k in d.files if hasattr(d, "files") else d:
        x = d[k]
        if k in code and k not in skip:
            s, o = code[k]
            out[k] = x.astype(np.float32) * np.float32(s) + np.float32(o)
        elif k != "code":
            out[k] = x
    return out


def points(store=STORE):
    with np.load(os.path.join(store, "points.npz")) as d:
        p = {k: d[k] for k in ("lat", "lon", "ilat", "ilon", "igra")}
    holdout.check(p["lat"], p["lon"], what="store points")
    return p


def months(first=1991, last=LAST_YEAR, store=STORE):
    """Month names (YYYY-MM) present in the store within [first, last]; never past 2025."""
    last = min(last, LAST_YEAR)
    names = sorted(f[:7] for f in os.listdir(store) if len(f) == 11 and f.endswith(".npz") and f[4] == "-")
    return [m for m in names if first <= int(m[:4]) <= last]


def month(name, store=STORE):
    from tempest.ingest.fetch_global import CODE
    with np.load(os.path.join(store, f"{name}.npz")) as d:
        out = _decode(d, CODE)
    holdout.check(times=out["valid_time"], what=f"store month {name}")
    out["r"] = np.clip(out["r"], 0, 100)
    return out


def extra(name, store=EXTRA):
    with np.load(os.path.join(store, f"{name}.npz")) as d:
        out = _decode(d, _code(d))
    holdout.check(times=out["valid_time"], what=f"extra month {name}")
    return out


def hres(name, store=HRES):
    """name YYYYMM. q is specific humidity (kg/kg)."""
    with np.load(os.path.join(store, f"{name}.npz")) as d:
        out = _decode(d, _code(d))
    holdout.check(times=out["valid"], what=f"HRES month {name}")
    return out


def profiles(m, pts, idx=None, t=None, oro_m=None):
    """Decoded month -> ({u, v, T, RH} (days, P', 44), rh2m (days, P')) for store points idx (all if None) and days t.
    oro_m: surface height (m) per selected point; default from tempest.geo.statics."""
    from tempest.profiles.to_heights import profiles_from_levels
    idx = np.arange(len(pts["lat"])) if idx is None else np.asarray(idx)
    t = slice(None) if t is None else t
    if oro_m is None:
        from tempest.geo.statics import statics
        oro_m = statics(pts["lat"][idx], pts["lon"][idx])["oro_m"]
    lev = {k: np.moveaxis(m[k][t][..., idx], 1, -1) for k in ("z", "u", "v", "t", "r")}       # (days, P', 13)
    sfc = {k: m[k][t][..., idx] for k in ("u10", "v10", "u100", "v100", "t2m", "d2m")}
    zs = np.broadcast_to(np.asarray(oro_m, np.float32) * G, sfc["t2m"].shape)
    return profiles_from_levels(lev["z"], lev["u"], lev["v"], lev["t"], lev["r"], zs, **sfc)


def q_to_rh(q, t, p_hpa):
    """Specific humidity (kg/kg), temperature (K), pressure (hPa) -> RH over liquid water (%), clipped 0-100."""
    e = q * p_hpa / (0.622 + 0.378 * q)
    es = 6.112 * np.exp(17.67 * (t - 273.15) / (t - 29.65))
    return np.clip(100.0 * e / es, 0, 100)
