"""AU-16 (New_Plan 15.3): the 3-month-lagged ONI is drawn jointly with the target month's ONI, and taken as observed when known at the origin."""
import numpy as np
import pandas as pd

from tempest.ingest import index_forecast as fc
from tempest.ingest import indices


def _table(n=480, seed=0):
    rng = np.random.default_rng(seed)
    oni = np.zeros(n)
    for i in range(1, n):
        oni[i] = 0.9 * oni[i - 1] + rng.normal(0, 0.25)
    t = np.arange(n)
    return pd.DataFrame(dict(oni=oni, qbo30=10 * np.sin(2 * np.pi * t / 28) + rng.normal(0, 1, n), qbo50=8 * np.sin(2 * np.pi * t / 28 + 0.5) + rng.normal(0, 1, n),
                             wwv=0.5 * oni + rng.normal(0, 0.2, n)), index=pd.date_range("1980-01-01", periods=n, freq="MS"))[indices.COLS]


def test_lag_draw_keeps_the_hindcast_error_correlation_at_h6():
    tab = _table()
    pos, h = 300, 6
    oni = fc.draw(tab, tab.index[pos], h, 20000, np.random.default_rng(1))[:, 0]
    lag = fc.draw_lag(tab, tab.index[pos], h, 3, oni, np.random.default_rng(2))
    o = tab["oni"].to_numpy()
    org = np.arange(fc.LAGS, pos - h + 1)                 # observed: errors of the persistence-like AR(1) forecast at h and h - 3 over past origins
    e6, e3 = o[org + h] - 0.9 ** h * o[org], o[org + h - 3] - 0.9 ** (h - 3) * o[org]
    assert abs(np.corrcoef(oni, lag)[0, 1] - np.corrcoef(e6, e3)[0, 1]) < 0.1
    assert np.corrcoef(oni, lag)[0, 1] > 0.3


def test_lag_month_already_observed_is_used_as_is():
    tab = _table()
    oni = fc.draw(tab, tab.index[300], 2, 50, np.random.default_rng(1))[:, 0]
    lag = fc.draw_lag(tab, tab.index[300], 2, 3, oni, np.random.default_rng(2))
    assert np.all(lag == tab["oni"].iloc[299])
