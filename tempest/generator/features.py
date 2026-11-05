"""Conditioning inputs for the generator. The same function builds them for training and for queries.

FEATURES is the ACTIVE list of input columns. By default it is the original 13. A dataset built with
`--features p2` carries its own list in `cond_names` (year replaced by gmst, plus the ONI hinges and a lagged ONI);
tempest.generator.train.load_npz switches FEATURES to it in place, so every module that imports FEATURES follows.
"""
import numpy as np

BASE_FEATURES = ["lat", "lon", "elev_site", "elev_grid", "doy_sin", "doy_cos", "hour_sin", "hour_cos",
                 "year", "oni", "wwv", "qbo30", "qbo50"]
P2_FEATURES = [k for k in BASE_FEATURES if k != "year"] + ["gmst", "oni_pos", "oni_neg", "oni_lag3"]
FEATURES = list(BASE_FEATURES)  # active list; mutated in place by set_active
# columns that come from the climate state: drawn together from one earlier row when the future drivers are unknown
DRIVER_NAMES = ["oni", "wwv", "qbo30", "qbo50", "oni_pos", "oni_neg", "oni_lag3"]


def set_active(names) -> None:
    """Make `names` the active feature columns (in place, so `from ... import FEATURES` users see it)."""
    names = [str(n) for n in names]
    if names != FEATURES:
        FEATURES[:] = names


def drivers() -> list[str]:
    """Active columns that are climate-state drivers (copied together when drivers are drawn)."""
    return [k for k in DRIVER_NAMES if k in FEATURES]


def features(lat, lon, elev_site, elev_grid, doy, solar_hour, year, oni, wwv, qbo30, qbo50, gmst=None, oni_lag3=None) -> np.ndarray:
    """All arguments broadcast to N rows -> (N, len(FEATURES)) float32. Drivers are drawn per sample by the caller.
    gmst and oni_lag3 are only needed when the active list asks for them.
    shortcut: ERA5 training rows have elev_site == elev_grid, so the model never saw them differ; pass
    elev_site = elev_grid at query time until training uses station-corrected targets (phase 6)."""
    a = 2 * np.pi * np.asarray(doy, float) / 365.25
    h = 2 * np.pi * np.asarray(solar_hour, float) / 24.0
    cols = dict(lat=lat, lon=lon, elev_site=elev_site, elev_grid=elev_grid, doy_sin=np.sin(a), doy_cos=np.cos(a),
                hour_sin=np.sin(h), hour_cos=np.cos(h), year=year, oni=oni, wwv=wwv, qbo30=qbo30, qbo50=qbo50,
                oni_pos=np.maximum(np.asarray(oni, float), 0), oni_neg=np.minimum(np.asarray(oni, float), 0))
    if gmst is not None:
        cols["gmst"] = gmst
    if oni_lag3 is not None:
        cols["oni_lag3"] = oni_lag3
    missing = [k for k in FEATURES if k not in cols]
    if missing:
        raise ValueError(f"features {missing} are active but were not given (pass gmst= / oni_lag3=)")
    return np.stack(np.broadcast_arrays(*[np.asarray(cols[k], float) for k in FEATURES]), axis=-1).astype(np.float32)
