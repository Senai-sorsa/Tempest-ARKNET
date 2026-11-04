"""Conditioning inputs for the generator. The same function builds them for training and for queries."""
import numpy as np

FEATURES = ["lat", "lon", "elev_site", "elev_grid", "doy_sin", "doy_cos", "hour_sin", "hour_cos",
            "year", "oni", "wwv", "qbo30", "qbo50"]


def features(lat, lon, elev_site, elev_grid, doy, solar_hour, year, oni, wwv, qbo30, qbo50) -> np.ndarray:
    """All arguments broadcast to N rows -> (N, len(FEATURES)) float32. Drivers are drawn per sample by the caller.
    shortcut: ERA5 training rows have elev_site == elev_grid, so the model never saw them differ; pass
    elev_site = elev_grid at query time until training uses station-corrected targets (phase 6)."""
    a = 2 * np.pi * np.asarray(doy, float) / 365.25
    h = 2 * np.pi * np.asarray(solar_hour, float) / 24.0
    cols = [lat, lon, elev_site, elev_grid, np.sin(a), np.cos(a), np.sin(h), np.cos(h),
            year, oni, wwv, qbo30, qbo50]
    return np.stack(np.broadcast_arrays(*[np.asarray(c, float) for c in cols]), axis=-1).astype(np.float32)
