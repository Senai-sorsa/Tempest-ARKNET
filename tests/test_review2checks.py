"""External review 2checks: fixes that are cheap to pin down."""
import numpy as np
import pytest

from tempest.forecast import router, scenarios
from tempest.generator import features as feat
from tempest.generator import sample as S
from tempest.generator import train as T
from tempest.generator import sample as thermo


def test_router_rejects_bad_settings():
    with pytest.raises(ValueError):
        router.ramp(5, 10, 10)
    with pytest.raises(ValueError):
        router.mode(3, dict(f_days=0.0, p0_days=1.0))                       # boundaries out of order
    with pytest.raises(ValueError):
        router.mix(np.random.default_rng(0), np.zeros((4, 2)), np.zeros((5, 2)), 0.5)
    with pytest.raises(ValueError):
        router.mix(np.random.default_rng(0), np.zeros((4, 2)), np.zeros((4, 2)), 1.5)


def test_scenario_weights_validated_and_uniform_weights_equal_unweighted():
    x = np.random.default_rng(0).normal(size=200)
    s = {"a": x}
    for bad in (np.full(200, np.nan), -np.ones(200), np.zeros(200), np.ones(5)):
        with pytest.raises(ValueError):
            scenarios.scenarios(s, lambda d: d["a"], weights=bad)
    a = scenarios.scenarios(s, lambda d: d["a"])
    b = scenarios.scenarios(s, lambda d: d["a"], weights=np.ones(200))
    assert [r["index"] for r in a] == [r["index"] for r in b] or max(abs(r["outcome"] - q["outcome"]) for r, q in zip(a, b)) < 0.15


def test_wrong_feature_order_is_refused():
    class Fake(S.Sampler):
        def __init__(self, names):
            self.rh_target, self.cond_names = "rh", names
    ok = Fake(list(feat.BASE_FEATURES))
    ok._activate()
    shuffled = list(feat.BASE_FEATURES)
    shuffled[0], shuffled[1] = shuffled[1], shuffled[0]
    with pytest.raises(ValueError):
        Fake(shuffled)._activate()
    with pytest.raises(ValueError):
        Fake(list(feat.BASE_FEATURES) + ["gmst"])._activate()
    feat.set_active(feat.BASE_FEATURES)


def test_block_split_uses_true_calendar_and_keeps_support():
    names = list(feat.BASE_FEATURES)
    n_years = list(range(1991, 2001))
    year, doy = [], []
    for y in n_years:
        d = np.arange(1, 367 if y % 4 == 0 else 366)
        year += [y] * len(d)
        doy += list(d)
    year, doy = np.array(year), np.array(doy)
    cond = np.zeros((len(year), len(names)), np.float32)
    a = 2 * np.pi * doy / 365.25
    cond[:, names.index("doy_sin")], cond[:, names.index("doy_cos")] = np.sin(a), np.cos(a)
    tr, va = T.split(year, cond, names, dict(val_block_frac=0.1))
    assert (tr & va).sum() == 0 and va.sum() > 0 and tr.sum() > va.sum()
    for y in n_years:
        assert (tr & (year == y)).sum() > 100


def test_dpd_roundtrip_over_the_domain():
    t = np.array([200.0, 230.0, 260.0, 290.0, 320.0])
    for rh in (0.5, 1.0, 10.0, 50.0, 99.0, 100.0):
        back = thermo.rh_from_dpd(t, thermo.dpd_from_rh(t, np.full_like(t, rh)))
        assert np.allclose(back, rh, atol=1e-3), (rh, back)


def test_order_statistic_interval_of_m199_holds_99_percent():
    """Review 2.7: the min-max range of 199 exchangeable draws contains a new draw with probability (m-1)/(m+1) = 0.99, not ~1."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200000, 199))
    y = rng.normal(size=200000)
    cov = ((y > x.min(1)) & (y < x.max(1))).mean()
    assert abs(cov - 0.99) < 0.001
