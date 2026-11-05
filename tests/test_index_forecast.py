"""Index forecast: uses only data known at the origin, near-persistence at 1 month, widens with the horizon."""
import numpy as np
import pandas as pd

from tempest.ingest import index_forecast as fc
from tempest.ingest import indices


def _table(n=480, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1980-01-01", periods=n, freq="MS")
    oni = np.zeros(n)
    for i in range(1, n):
        oni[i] = 0.9 * oni[i - 1] + rng.normal(0, 0.25)  # persistent, ENSO-like
    t = pd.DataFrame(dict(oni=oni, qbo30=10 * np.sin(2 * np.pi * np.arange(n) / 28) + rng.normal(0, 1, n),
                          qbo50=8 * np.sin(2 * np.pi * np.arange(n) / 28 + 0.5) + rng.normal(0, 1, n),
                          wwv=0.5 * oni + rng.normal(0, 0.2, n)), index=idx)
    return t[indices.COLS]


def test_one_month_ahead_follows_the_last_value_and_spread_grows():
    tab = _table()
    rng = np.random.default_rng(1)
    origin = tab.index[300]
    d1, d12 = fc.draw(tab, origin, 1, 4000, rng), fc.draw(tab, origin, 12, 4000, rng)
    last = tab["oni"].iloc[300]
    assert abs(d1[:, 0].mean() - last) < 0.45
    assert d12[:, 0].std() > d1[:, 0].std()
    assert d1.shape == (4000, 4)


def test_future_data_is_not_used():
    tab = _table()
    tab2 = tab.copy()
    tab2.iloc[301:] += 100.0                                   # wreck everything after the origin
    origin = tab.index[300]
    a = fc.fit(tab, origin, 3)
    b = fc.fit(tab2, origin, 3)
    assert np.allclose(a["beta"], b["beta"]) and np.allclose(a["cov"], b["cov"])


def test_joint_draws_keep_the_correlation_between_indices():
    tab = _table()
    d = fc.draw(tab, tab.index[300], 2, 20000, np.random.default_rng(3))
    r_hist = np.corrcoef(tab["oni"].to_numpy()[2:], tab["wwv"].to_numpy()[2:])[0, 1]
    r_draw = np.corrcoef(d[:, indices.COLS.index("oni")], d[:, indices.COLS.index("wwv")])[0, 1]
    assert r_draw > 0.3 and r_hist > 0.3
