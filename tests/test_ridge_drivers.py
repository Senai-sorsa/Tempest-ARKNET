"""F-13: ridge-forecast drivers fill the driver columns only."""
import numpy as np
import pandas as pd

from tempest.generator.features import FEATURES, drivers
from tempest.scoring import ridge_drivers


def test_fill_changes_only_driver_columns():
    idx = pd.date_range("1980-01-01", "2023-12-01", freq="MS")
    rng = np.random.default_rng(0)
    n = len(idx)
    tab = pd.DataFrame(dict(oni=np.sin(np.arange(n) / 20) + rng.normal(0, .1, n), qbo30=np.sin(np.arange(n) * 2 * np.pi / 28),
                            qbo50=np.cos(np.arange(n) * 2 * np.pi / 28), wwv=1e13 * np.sin(np.arange(n) / 30)), index=idx)
    cond = np.zeros((2, len(FEATURES)), np.float32)
    cond[:, FEATURES.index("doy_sin")], cond[:, FEATURES.index("doy_cos")] = np.sin(2 * np.pi * 180 / 365.25), np.cos(2 * np.pi * 180 / 365.25)
    rep = np.repeat(cond, 5, 0).copy()
    before = rep.copy()
    out = ridge_drivers.fill(rep, cond, np.array([2020, 2020]), 5, 6, rng, table=tab)
    dc = [FEATURES.index(k) for k in drivers()]
    other = [j for j in range(len(FEATURES)) if j not in dc]
    assert np.array_equal(out[:, other], before[:, other])
    assert np.isfinite(out[:, dc]).all() and out[:, dc].std() > 0
