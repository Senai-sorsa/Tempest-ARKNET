"""The variables a caller can ask for, by name, evaluated on a set of whole atmospheres.

    surface:   t2m (K)  t2m_c (degC)  sp (Pa)  rh2m (%)  rh2m_frac (0-1)  rho_sfc (kg/m3)  gust10 (m/s)
    at height: u@z v@z T@z RH@z p@z rho@z a@z w@z wind_speed@z wind_dir@z   (z = metres above ground, 10-18000; linear between the 44 heights)
    layers:    shear@z1-z2 (m/s per km, size of the wind-vector change over the layer)   mean_wind@z1-z2 (m/s)
    summary:   flight_score (see ranking.py; higher is worse)
`wind_dir` is the direction the wind blows FROM, in degrees clockwise from north. `evaluate` returns plain arrays, one value per atmosphere.
"""
import re

import numpy as np

from tempest_weather._core import HEIGHTS

UNITS = dict(t2m="K", t2m_c="degC", sp="Pa", rh2m="%", rh2m_frac="0-1", rho_sfc="kg/m3", gust10="m/s", flight_score="score (higher = worse)")
AT = dict(u="m/s", v="m/s", T="K", RH="%", p="Pa", rho="kg/m3", a="m/s", w="m/s", wind_speed="m/s", wind_dir="deg")
SIMPLE = ("t2m", "t2m_c", "sp", "rh2m", "rh2m_frac", "rho_sfc", "gust10", "flight_score")
_AT = re.compile(r"^(u|v|T|RH|p|rho|a|w|wind_speed|wind_dir)@(\d+(?:\.\d+)?)$")
_LAYER = re.compile(r"^(shear|mean_wind)@(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")


def valid_names():
    return sorted(SIMPLE) + [f"{k}@<z>" for k in AT] + ["shear@<z1>-<z2>", "mean_wind@<z1>-<z2>"]


def units_of(name):
    if name in UNITS:
        return UNITS[name]
    m = _AT.match(name)
    if m:
        return AT[m.group(1)]
    m = _LAYER.match(name)
    return "m/s per km" if m and m.group(1) == "shear" else "m/s" if m else ""


def _at(profile, z):
    if not 10.0 <= z <= 18000.0:
        raise ValueError(f"height {z} m is outside 10-18000 m above ground")
    return np.stack([np.interp(z, HEIGHTS, row) for row in profile]) if profile.ndim == 2 else None


def evaluate(atm, names, rng=None, score_fn=None):
    """atm: dict of arrays with the sample first (u, v, T, RH, p, rho, a, w (optional), t2m, sp, rh2m, gust_mu / gust_beta (optional)).
    -> dict name -> (n,) array. Raises ValueError naming the valid names for an unknown one."""
    rng = rng or np.random.default_rng()
    out = {}
    for name in names:
        if name == "t2m":
            v = atm["t2m"]
        elif name == "t2m_c":
            v = atm["t2m"] - 273.15
        elif name in ("sp", "rh2m"):
            v = atm[name]
        elif name == "rh2m_frac":
            v = np.clip(atm["rh2m"], 0, 100) / 100.0
        elif name == "rho_sfc":
            v = atm["rho"][:, 0]
        elif name == "gust10":
            if atm.get("gust_mu") is None:
                raise ValueError("gust10 needs the gust model (assets/model.npz has none)")
            u = np.clip(rng.random(len(atm["t2m"])), 1e-12, 1 - 1e-12)
            v = np.maximum(atm["gust_mu"] - atm["gust_beta"] * np.log(-np.log(u)), 0.0)
        elif name == "flight_score":
            from tempest_weather import ranking
            v = (score_fn or ranking.flight_score)(atm)
        elif _AT.match(name):
            kind, z = _AT.match(name).group(1), float(_AT.match(name).group(2))
            if kind in ("wind_speed", "wind_dir"):
                u, w_ = _at(atm["u"], z), _at(atm["v"], z)
                v = np.hypot(u, w_) if kind == "wind_speed" else np.degrees(np.arctan2(-u, -w_)) % 360.0
            else:
                if kind == "w" and atm.get("w") is None:
                    raise ValueError("w@z needs the vertical-wind head (assets/model.npz has none)")
                v = _at(atm[kind], z)
        elif _LAYER.match(name):
            kind, z1, z2 = _LAYER.match(name).group(1), float(_LAYER.match(name).group(2)), float(_LAYER.match(name).group(3))
            if not (10.0 <= z1 < z2 <= 18000.0):
                raise ValueError(f"layer {z1}-{z2} m must satisfy 10 <= z1 < z2 <= 18000")
            if kind == "shear":
                v = np.hypot(_at(atm["u"], z2) - _at(atm["u"], z1), _at(atm["v"], z2) - _at(atm["v"], z1)) / (z2 - z1) * 1000.0
            else:
                zs = np.linspace(z1, z2, 25)
                v = np.mean([np.hypot(_at(atm["u"], z), _at(atm["v"], z)) for z in zs], axis=0)
        else:
            raise ValueError(f"unknown variable {name!r}; valid: {', '.join(valid_names())}")
        out[name] = np.asarray(v, float)
    return out
