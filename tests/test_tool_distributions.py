"""Tool distribution types and coupling: round trips, selection rule, empirical table, copula limits."""
import numpy as np
import pytest

from tempest_weather import coupling, distributions as D
from tempest_weather.distributions import base


def test_normal_ppf_inverse_and_cdf():
    q = np.array([0.001, 0.05, 0.5, 0.95, 0.999])
    z = base.norm_ppf(q)
    assert np.allclose(base.norm_cdf(z), q, atol=1e-8) and abs(base.norm_ppf(0.5)) < 1e-9


@pytest.mark.parametrize("name,params,draw", [
    ("normal", dict(mean=3.0, std=2.0), lambda r, n: r.normal(3, 2, n)),
    ("lognormal", dict(mu=1.0, sigma=0.4), lambda r, n: r.lognormal(1.0, 0.4, n)),
    ("gumbel", dict(loc=5.0, scale=1.5), lambda r, n: r.gumbel(5.0, 1.5, n)),
    ("weibull", dict(shape=2.2, scale=6.0), lambda r, n: 6.0 * r.weibull(2.2, n)),
    ("beta", dict(a=2.0, b=3.0), lambda r, n: r.beta(2.0, 3.0, n))])
def test_fit_recovers_parameters_and_ppf_inverts_cdf(name, params, draw):
    r = np.random.default_rng(0)
    cls = D.REGISTRY[name]
    p = cls.fit(draw(r, 60000))
    for k, v in params.items():
        assert abs(p[k] - v) < 0.06 * abs(v) + 0.03, (name, k, p[k], v)
    q = np.linspace(0.01, 0.99, 50)
    assert np.allclose(cls.cdf(cls.ppf(q, p), p), q, atol=2e-3)


def test_selection_rule_by_support_and_fallback_to_empirical():
    r = np.random.default_rng(1)
    assert D.describe(r.beta(4, 2, 5000), True)["type"] == "beta"
    assert D.describe(6.0 * r.weibull(2.0, 5000), True)["type"] in ("weibull", "lognormal")
    assert D.describe(r.normal(280, 3, 5000), True)["type"] == "normal"
    two_lumps = np.r_[r.normal(0, 1, 3000), r.normal(12, 1, 3000)]
    d = D.describe(two_lumps, True)
    assert d["type"] == "empirical" and "no standard type" in d["note"]
    assert D.describe(r.normal(0, 1, 500), False)["type"] == "empirical"
    assert D.describe(np.full(10, 3.0), True)["type"] == "constant"


def test_empirical_table_rebuilds_the_quantiles():
    r = np.random.default_rng(2)
    x = r.gumbel(5, 2, 20000)
    spec = D.describe(x, False)
    dist = D.build(spec)
    q = np.array([0.005, 0.1, 0.5, 0.9, 0.995])
    assert np.allclose(dist.ppf(q), np.quantile(x, q), rtol=0.03, atol=0.15)
    s = dist.sample(20000, np.random.default_rng(3))
    assert abs(s.mean() - x.mean()) < 0.1 and s.min() >= x.min() - 1e-9 and s.max() <= x.max() + 1e-9


def _joint(n=20000, seed=0):
    r = np.random.default_rng(seed)
    z = r.multivariate_normal([0, 0], [[1, 0.7], [0.7, 1]], n)
    return np.stack([5 + 2 * z[:, 0], np.exp(0.3 * z[:, 1])], 1)


def test_whole_sample_returns_whole_rows_and_stratifies():
    t = _joint(2000)
    c = coupling.make("whole_sample", ["a", "b"], t, key=t[:, 0])
    idx, rows = c.draw(500, np.random.default_rng(0))
    assert np.array_equal(rows, t[idx])
    idx, rows = c.draw(100, np.random.default_rng(1), stratified=True)
    assert len(np.unique(np.digitize(t[idx, 0], np.quantile(t[:, 0], np.linspace(0, 1, 11)[1:-1])))) == 10   # every tenth of the key is hit


def test_gaussian_copula_keeps_marginals_and_rank_correlation_but_not_everything():
    t = _joint()
    marg = [D.describe(t[:, j], False) for j in range(2)]
    c = coupling.make("gaussian_copula", ["a", "b"], t, marginals=marg)
    _, rows = c.draw(30000, np.random.default_rng(0))
    for j in range(2):
        assert np.allclose(np.quantile(rows[:, j], [0.05, 0.5, 0.95]), np.quantile(t[:, j], [0.05, 0.5, 0.95]), rtol=0.03)
    rank = lambda x: np.argsort(np.argsort(x))
    r_in = np.corrcoef(rank(t[:, 0]), rank(t[:, 1]))[0, 1]
    r_out = np.corrcoef(rank(rows[:, 0]), rank(rows[:, 1]))[0, 1]
    assert abs(r_in - r_out) < 0.03
    with pytest.raises(ValueError):
        coupling.make("nonsense", ["a"], t)
    with pytest.raises(ValueError):
        coupling.make("gaussian_copula", ["a", "b"], t)
