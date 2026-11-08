"""Distribution fits and the three coupling methods."""
import numpy as np
import pytest

from tempest_weather_v2 import stats as S


def test_fit_best_picks_sensible_families_and_reports_tail_quality():
    rng = np.random.default_rng(0)
    n = S.fit_best(rng.normal(20, 3, 2000))
    assert n["type"] == "normal" and n["fit_ok"] and abs(n["params"]["mu"] - 20) < 0.3 and n["quantiles"][0.5] == pytest.approx(20, abs=0.3)
    w = S.fit_best(rng.weibull(2.0, 3000) * 6.0)
    assert w["type"] in ("weibull", "gamma", "lognormal", "beta") and w["fit_ok"]
    g = S.fit_best(rng.gumbel(5, 2, 3000))
    assert g["type"] in ("gumbel", "normal", "weibull", "beta", "lognormal") and g["ks"] < 0.05
    c = S.fit_best(np.full(100, 3.0))
    assert c["type"] is None and not c["fit_ok"] and c["quantiles"][0.5] == 3.0
    bimodal = np.concatenate([rng.normal(0, 1, 1000), rng.normal(12, 1, 1000)])
    mix = S.fit_best(bimodal, families=["normal", "gumbel"])
    assert not mix["fit_ok"]                                              # a bimodal sample passes no bell-shaped family's tail check; the empirical table is still there
    assert len(mix["quantiles"]) == len(S.QUANTILES)
    only = S.fit_best(rng.normal(size=500), families=["gumbel"])
    assert only["type"] == "gumbel"


def make_t_data(nu, n=6000, rho=0.7, seed=1):
    rng = np.random.default_rng(seed)
    L = np.linalg.cholesky(np.array([[1, rho, 0.3], [rho, 1, 0.3], [0.3, 0.3, 1.0]]))
    z = rng.standard_normal((n, 3)) @ L.T
    return z / np.sqrt(rng.chisquare(nu, (n, 1)) / nu) if nu else z


def joint_exceedance(x, q=0.99):
    t = np.quantile(x, q, axis=0)
    return float(((x[:, 0] > t[0]) & (x[:, 1] > t[1])).mean())


def test_whole_sample_resamples_real_rows_and_gaussian_copula_keeps_marginals_and_correlation():
    x = make_t_data(0)
    ws = S.Coupled(x, ["a", "b", "c"], "whole_sample")
    d = ws.draw(500)
    rows = {tuple(r) for r in x.round(9)}
    assert all(tuple(r.round(9)) in rows for r in d)                       # exact atmospheres only
    gc = S.Coupled(x, ["a", "b", "c"], "gaussian_copula")
    d = gc.draw(20000, seed=3)
    assert np.allclose(np.median(d, 0), np.median(x, 0), atol=0.05) and np.allclose(d.std(0), x.std(0), rtol=0.08)
    assert abs(np.corrcoef(d[:, 0], d[:, 1])[0, 1] - np.corrcoef(x[:, 0], x[:, 1])[0, 1]) < 0.04
    assert np.array_equal(gc.draw(10, seed=4), gc.draw(10, seed=4))


def test_t_copula_fits_low_nu_for_heavy_tails_and_keeps_joint_extremes_better():
    heavy = make_t_data(3)
    t_c = S.Coupled(heavy, ["a", "b", "c"], "t_copula")
    g_c = S.Coupled(heavy, ["a", "b", "c"], "gaussian_copula")
    assert t_c.nu <= 8
    truth = joint_exceedance(heavy)
    te = joint_exceedance(t_c.draw(60000, seed=5))
    ge = joint_exceedance(g_c.draw(60000, seed=5))
    assert abs(te - truth) < abs(ge - truth)                               # the Gaussian copula underestimates the joint tail
    assert S.Coupled(make_t_data(0), ["a", "b", "c"], "t_copula").nu >= 20     # gaussian data: nu comes out large


def test_conditioning_gaussian_and_exact_student_t():
    x = make_t_data(5)
    for method in ("gaussian_copula", "t_copula"):
        c = S.Coupled(x, ["a", "b", "c"], method)
        hi = float(np.quantile(x[:, 0], 0.95))
        cond = c.condition({"a": hi})
        d = cond.draw(8000, seed=2)
        assert np.allclose(d[:, 0], hi) and d[:, 1].mean() > c.draw(8000, seed=2)[:, 1].mean() + 0.3      # positively correlated column follows
        assert c._cond is None                                                                      # the original is unchanged
        assert "conditioned-on-1-values" in cond.flags
    t = S.Coupled(x, ["a", "b", "c"], "t_copula").condition({"a": 1.0, "b": 0.5})
    assert t._cond[0] == "t" and t._cond[5] == pytest.approx(S.Coupled(x, ["a", "b", "c"], "t_copula").nu + 2)      # nu' = nu + d_obs
    ws = S.Coupled(x, ["a", "b", "c"], "whole_sample").condition({"a": 1.0})
    assert abs(ws.draw(3000, seed=1)[:, 0].mean() - 1.0) < 0.3
    with pytest.raises(KeyError):
        S.Coupled(x, ["a", "b", "c"], "t_copula").condition({"zzz": 1})


def test_adjust_flags_spec_and_method_validation():
    x = make_t_data(0)
    c = S.Coupled(x, ["a", "b", "c"], "gaussian_copula")
    a = c.adjust(shift=[2.0, 0, 0], scale=[1.5, 1, 1])
    assert "adjusted-uncalibrated" in a.flags and "adjusted-uncalibrated" not in c.flags
    d0, d1 = c.draw(8000, seed=1), a.draw(8000, seed=1)
    assert d1[:, 0].mean() == pytest.approx(d0[:, 0].mean() + 2.0, abs=0.15) and d1[:, 0].std() == pytest.approx(1.5 * d0[:, 0].std(), rel=0.05)
    sp = S.Coupled(x, ["a", "b", "c"], "t_copula").spec()
    assert sp["method"] == "t_copula" and "nu" in sp and len(sp["eigenvalues"]) == 3 and len(sp["marginals"]["a"]["quantiles"]) == len(x)
    with pytest.raises(ValueError, match="method must be one of"):
        S.Coupled(x, ["a", "b", "c"], "vine")
