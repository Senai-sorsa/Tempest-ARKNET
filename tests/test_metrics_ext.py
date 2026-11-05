"""Shape metrics on synthetic data where the right answer is known."""
import numpy as np

from tempest.profiles.to_heights import HEIGHTS
from tempest.scoring import metrics_ext as M

NH = len(HEIGHTS)


def _calibrated(n=3000, m=99, d=5, seed=0, width=1.0, bias=0.0):
    rng = np.random.default_rng(seed)
    mu = rng.normal(0, 1, (n, d))
    y = mu + rng.normal(0, 1, (n, d))
    x = mu[:, None] + bias + width * rng.normal(0, 1, (n, m, d))
    return x, y


def test_pit_flat_when_calibrated_and_u_shaped_when_narrow():
    x, y = _calibrated()
    assert M.pit_tv(M.pit_values(x, y)).max() < 0.03
    xn, yn = _calibrated(width=0.5)
    assert M.pit_tv(M.pit_values(xn, yn)).min() > 0.15
    x, y = _calibrated(m=199)
    cov = M.coverage_levels(M.pit_values(x, y))
    assert np.allclose(cov[2], 0.5, atol=0.03) and np.allclose(cov[-1], 0.99, atol=0.01)


def test_moments_detect_skew():
    rng = np.random.default_rng(1)
    mu = rng.normal(0, 1, (4000, 1))
    y = mu + rng.gamma(2.0, 1.0, (4000, 1))                      # skewed outcomes
    x = mu[:, None] + rng.normal(0, 1.4, (4000, 60, 1)) + 2.0   # symmetric samples
    sk = M.standardized_moments(x, y)[0]
    assert sk[0] > 0.5 and abs(sk[1]) < 0.2


def test_tail_and_event_conditional():
    x, y = _calibrated(n=6000)
    clim = y.copy()
    ex = M.tail_exceedance(x, y, clim)
    assert np.allclose(ex[1], 0.01, atol=0.004) and np.allclose(ex[4], 0.01, atol=0.004)
    inside, ideal, n = M.event_conditional_coverage(x, y, clim)
    assert (n > 30).all() and abs(np.nanmean(inside) - np.nanmean(ideal)) < 0.12
    xn = x * 0.5 + x.mean(1, keepdims=True) * 0.5                   # too narrow: misses the extremes more than the ideal
    inside_n, ideal_n, _ = M.event_conditional_coverage(xn, y, clim)
    assert np.nanmean(inside_n) < np.nanmean(inside) - 0.05


def test_vertical_corr_error_and_shear_distance():
    rng = np.random.default_rng(2)
    n, m = 800, 40
    smooth = np.cumsum(rng.normal(0, 1, (n, m + 1, NH)), -1)
    base = np.zeros((n, 1, NH))
    y = (smooth[:, 0] - smooth[:, 0].mean(1, keepdims=True))
    x = base + (smooth[:, 1:] - smooth[:, 1:].mean(2, keepdims=True))
    cols = np.arange(NH)
    assert M.vertical_corr_error(x, y, cols) < 0.1
    xj = x + rng.normal(0, 3, x.shape)                            # jagged samples: wrong vertical coherence
    assert M.vertical_corr_error(xj, y, cols) > M.vertical_corr_error(x, y, cols) + 0.05
    full = lambda a: np.concatenate([a, a, a, a], -1)
    ks_same, _ = M.shear_distance(full(x), full(y)[:, :4 * NH])
    ks_jag, _ = M.shear_distance(full(xj), full(y)[:, :4 * NH])
    assert ks_jag > ks_same


def test_drift_and_brier_and_direction():
    u = np.full((2, 4 * NH), 10.0)
    u[:, NH:] = 0.0                                               # u = 10 m/s east, v = 0
    d = M.drift_proxy(u)
    h3 = HEIGHTS[HEIGHTS <= 3000]
    assert np.allclose(d[0, 0, 0], 10.0 * (h3[-1] - h3[0]) / 10.0, rtol=0.05) and abs(d[0, 0, 1]) < 1e-6
    x, y = _calibrated(d=3)
    bss, bs, base = M.brier_skill(x, y, [0, 1, 2], 1.0)
    assert bss > 0.1 and 0 < base < 1
    xu = np.zeros((50, 9, NH)); xv = np.ones((50, 9, NH)) * 5.0    # median wind from the south (v = 5 -> north)
    X = np.concatenate([xu, xv], -1); Y = np.concatenate([np.zeros((50, NH)), np.ones((50, NH)) * 5.0], -1)
    assert M.direction_error(X, Y, np.arange(NH), np.arange(NH, 2 * NH)) < 1.0


def test_group_functions():
    x, y = _calibrated(n=600)
    g = np.repeat(np.arange(3), 200)
    b = M.bias_by_group(x, y, g)
    s = M.spread_skill(x, y, g)
    assert set(b) == {0, 1, 2} and all(np.all(np.abs(v) < 0.3) for v in b.values()) and all(0.5 < v.mean() < 1.3 for v in s.values())
