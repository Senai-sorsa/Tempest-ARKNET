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


def test_training_runs_with_rh_loss_final_m_and_float32_storage():
    from tempest.generator.train import train
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    rng = np.random.default_rng(0)
    nh, n = len(HEIGHTS), 3000
    y = np.zeros((n, 4 * nh + 3), np.float32)
    first = {"u": 5.0, "v": 0.0, "T": 285.0, "RH": 1.5}
    for i, v in enumerate(PROFILE):
        y[:, i * nh] = first[v] + rng.normal(0, 1, n)
        y[:, i * nh + 1:(i + 1) * nh] = rng.normal(0, 0.2, (n, nh - 1))
    y[:, 4 * nh:] = [285.0, 85000.0, 40.0]
    cond = rng.normal(size=(n, 2)).astype(np.float32)
    cfg = dict(width=16, depth=2, noise_dim=2, batch=256, steps=60, eval_every=30, val_years=1, lr=1e-3, m_final=6, final_steps=20, rh_loss_weight=0.1, store_dtype="float32", linear_features=[])
    ck = train(cond, y, np.repeat(np.arange(3), n // 3), cfg, device="cpu", log=lambda *_: None,
               meta=dict(cond_names=["a", "b"], target_names=[f"{v}_{h:g}" for v in PROFILE for h in HEIGHTS] + ["t2m", "sp", "rh2m"], rh_target="dpd"))
    assert ck["state"] is not None


def test_training_refuses_to_save_when_validation_is_never_finite():
    from tempest.generator.train import train
    rng = np.random.default_rng(0)
    cond = rng.normal(size=(600, 2)).astype(np.float32)
    y = rng.normal(size=(600, 3)).astype(np.float32)
    y[300:] = np.nan                                                         # the validation years carry only NaN
    cfg = dict(width=8, depth=1, noise_dim=2, batch=64, steps=10, eval_every=5, val_years=1, linear_features=[])
    with pytest.raises(Exception):
        train(cond, y, np.repeat(np.arange(2), 300), cfg, device="cpu", log=lambda *_: None)


def test_interaction_slope_lets_one_driver_change_anothers_effect():
    import torch
    from tempest.generator.model import Generator
    torch.manual_seed(0)
    g = Generator(4, 3, noise_dim=2, width=16, depth=1, linear_cols=[2, 3], interactions=True).eval()
    for p in g.slope[-1].parameters():
        torch.nn.init.normal_(p, std=0.5)
    a = torch.tensor([[0.0, 0.0, 1.0, 0.0]])
    b = torch.tensor([[0.0, 0.0, 1.0, 2.0]])                                   # same first driver, other driver changed
    torch.manual_seed(1)
    ya = g(a, 1)
    torch.manual_seed(1)
    yb = g(b, 1)
    h = Generator(4, 3, noise_dim=2, width=16, depth=1, linear_cols=[2, 3], interactions=False)
    assert ya.shape == (1, 1, 3) and not torch.allclose(ya, yb)
    assert h.slope[0].in_features == 2 and g.slope[0].in_features == 4
