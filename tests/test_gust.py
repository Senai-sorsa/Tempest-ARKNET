"""Gust module: recovers known parameters, samples never fall below the sustained wind."""
import numpy as np

from tempest.gust import model as gm


def _synthetic(n=40000, seed=0):
    rng = np.random.default_rng(seed)
    ws = rng.gamma(4.0, 1.5, n)
    doy, hour = rng.integers(1, 366, n), rng.uniform(0, 24, n)
    mu, beta = 1.0 + 1.2 * ws, np.exp(-0.2 + 0.05 * ws)
    g = mu - beta * np.log(-np.log(rng.random(n)))
    return gm.design(ws, doy, hour), g, (mu, beta)


def test_fit_recovers_gumbel_parameters():
    X, g, (mu, beta) = _synthetic()
    mod = gm.fit(X, g, l2=0.1)
    muh, bh = gm.params(mod, X)
    assert np.abs(muh - mu).mean() < 0.15 and np.abs(bh - beta).mean() < 0.15


def test_samples_cover_the_truth_and_are_not_negative():
    X, g, _ = _synthetic(20000, seed=1)
    mod = gm.fit(X, g, l2=0.1)
    s = gm.sample(mod, X[:3000], 199, np.random.default_rng(2))
    assert (s >= 0).all() and s.shape == (3000, 199)
    inside = (g[:3000] >= s.min(1)) & (g[:3000] <= s.max(1))
    assert abs(inside.mean() - 0.99) < 0.01


def test_design_columns():
    d = gm.design(np.ones(5), np.arange(5), np.full(5, 12.0))
    assert d.shape == (5, 7)
    d2 = gm.design(np.ones(5), np.arange(5), np.full(5, 12.0), fg=np.full(5, 3.0), station=np.zeros(5))
    assert d2.shape == (5, 10)
