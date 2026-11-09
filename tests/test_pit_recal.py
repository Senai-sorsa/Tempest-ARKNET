"""PIT recalibration: repairs a biased and over-narrow forecast in the middle of the distribution, leaves a calibrated one alone."""
import numpy as np

from tempest.calibrate import pit_recal as PR


def _data(n, m, d, bias, width, seed):
    rng = np.random.default_rng(seed)
    mu = rng.normal(0, 1, (n, 1, d))
    y = mu[:, 0] + rng.normal(0, 1, (n, d))
    x = mu + bias + width * rng.normal(0, 1, (n, m, d))
    return x, y


def _tv(x, y):
    pit = PR.pit_values(x, y, np.random.default_rng(1))
    h = np.stack([((pit * 10).astype(int).clip(0, 9) == b).mean() for b in range(10)])
    return 0.5 * np.abs(h - 0.1).sum()


def test_repairs_bias_and_width_on_new_data():
    groups = np.zeros(4, int)
    xc, yc = _data(4000, 99, 4, 0.4, 0.6, 0)
    t = PR.fit(xc, yc, groups)
    xt, yt = _data(4000, 99, 4, 0.4, 0.6, 5)
    assert _tv(xt, yt) > 0.15 and _tv(PR.apply(t, xt), yt) < 0.07


def test_calibrated_forecast_is_left_alone():
    groups = np.zeros(4, int)
    xc, yc = _data(4000, 99, 4, 0.0, 1.0, 2)
    t = PR.fit(xc, yc, groups)
    xt, yt = _data(2000, 99, 4, 0.0, 1.0, 3)
    assert abs(_tv(PR.apply(t, xt), yt) - _tv(xt, yt)) < 0.02
    assert np.all(np.diff(PR.apply(t, xt, keep_order=False), axis=1) >= -1e-9)   # keep_order=False: still sorted (the pre-IL-140 contract)
