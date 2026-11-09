"""M1: how much of the wind profile of a given hour is still there h hours later (the NASA Shuttle "wind in-persistence" idea), height by height, from the ERA5 lag-correlation table that the coherence step uses
(`models/coherence_lagcorr.npz`, key `rho` (4 seasons, 13 lags 0..12 h, 176 columns = u, v, T, RH at 44 heights), anomalies against the month x hour climatology, fit years 2005-2022).

    from tempest_weather_v2.persistence import load_table, wind_persistence, persistence_sd_factor
    tab = load_table("models/coherence_lagcorr.npz")
    r = wind_persistence(tab, season=2, lag_h=3.0, heights_m=[10, 500, 2000])      # correlation of the wind anomaly with itself 3 h later (JJA), per height
    k = persistence_sd_factor(r)                                                    # sd of the change as a fraction of the anomaly sd: sqrt(2 (1 - r))

Reading (ERA5, DJF-SON, mean of u and v): 10 m 0.94-0.97 at 1 h, 0.76-0.87 at 3 h, 0.59-0.71 at 6 h, 0.39-0.47 at 12 h; 2 km 0.98-0.99 / 0.90-0.94 / 0.80-0.85 / 0.62-0.69; 10 km 0.99-1.00 / 0.96-0.97 / 0.90-0.93 / 0.77-0.82. Summer (JJA) decorrelates fastest near the ground.
Caveat: ERA5 (0.25 deg, smoothed) cannot contain the small-scale features that the Shuttle balloon pairs showed to be gone within 90 minutes (features shorter than about 1.3 km), so these numbers
are an UPPER bound on persistence of the fine structure; use them for the large-scale part (and compare with the observation-age weights in `obs.py`, own-station time scale about 6 h).
"""
import numpy as np

__all__ = ["load_table", "wind_persistence", "persistence_sd_factor"]


def load_table(path):
    z = np.load(path)
    return np.asarray(z["rho"], float)


def season_of(month):
    """Month (1-12) -> season index used by the table: 0 DJF, 1 MAM, 2 JJA, 3 SON."""
    return ((int(month) % 12) // 3)


def wind_persistence(table, season, lag_h, heights_m, model_heights=None):
    """Correlation of the wind anomaly (mean of the u and v columns) with itself `lag_h` hours later, at `heights_m`. lag_h is interpolated linearly between the whole hours of the table (0 .. 12);
    beyond 12 h the last value is held (a lower bound on the decay would need more data)."""
    if model_heights is None:
        from tempest_weather import _core
        model_heights = _core.HEIGHTS
    nh = len(model_heights)
    t = np.asarray(table, float)[int(season)]                                        # (lags, 176)
    lag = float(np.clip(lag_h, 0.0, t.shape[0] - 1))
    l0 = int(np.floor(lag))
    l1 = min(l0 + 1, t.shape[0] - 1)
    w = lag - l0
    col = lambda c: t[l0, c] * (1 - w) + t[l1, c] * w
    prof = 0.5 * (col(np.arange(nh)) + col(nh + np.arange(nh)))
    return np.interp(np.asarray(heights_m, float), np.asarray(model_heights, float), prof)


def persistence_sd_factor(rho):
    """sd of the change of a standardised anomaly over the lag, sqrt(2 (1 - rho)): 0 = unchanged, 1.41 = independent."""
    return np.sqrt(2.0 * np.clip(1.0 - np.asarray(rho, float), 0.0, 2.0))
