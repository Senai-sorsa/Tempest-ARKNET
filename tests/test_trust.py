"""Trust layer: w = 1 is the identity, w = 0 gives the climatology quantiles in the model's rank order."""
import numpy as np

from tempest.calibrate import trust


def _data(n=6, m=50, d=179, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, m, d)).astype(np.float32) * 2 + 10
    q = np.sort(rng.normal(size=(n, m, d)).astype(np.float32) * 3 + 11, axis=1)
    return x, q


def test_w_one_is_identity():
    x, q = _data()
    out = trust.apply(np.ones(x.shape[-1], np.float32), x, q)
    assert np.array_equal(out, x)


def test_w_zero_gives_climatology_in_model_rank_order():
    x, q = _data()
    out = trust.apply(np.zeros(x.shape[-1], np.float32), x, q)
    cols = [0, 5, 100]  # no RH column among these (RH clipping would act on 0-100 anyway; values here stay in range)
    for c in cols:
        assert np.allclose(np.sort(out[..., c], 1), q[..., c], atol=1e-4)  # same set of values as the quantiles
        assert np.array_equal(np.argsort(out[..., c], 1), np.argsort(x[..., c], 1))  # same rank order as the model


def test_partial_weight_is_between_and_keeps_rank_order():
    x, q = _data()
    w = np.full(x.shape[-1], 0.5, np.float32)
    out = trust.apply(w, x, q)
    assert np.array_equal(np.argsort(out[..., 3], 1), np.argsort(x[..., 3], 1))  # rank order kept
    rank = np.argsort(np.argsort(x[..., 3], 1), 1)
    expect = 0.5 * x[..., 3] + 0.5 * np.take_along_axis(q[..., 3], rank, 1)
    assert np.allclose(out[..., 3], expect, atol=1e-4)


def test_crps_sorted_matches_reference_crps():
    from tempest.scoring.score import crps_ensemble
    x, _ = _data(n=4, m=30, d=7)
    y = np.random.default_rng(3).normal(size=(4, 7)).astype(np.float32) + 10
    assert np.allclose(trust.crps_sorted(np.sort(x, 1), y), crps_ensemble(x, y), atol=1e-4)


def test_clim_pool_quantiles_and_fallback():
    rng = np.random.default_rng(0)
    n, d = 400, 179
    year = np.repeat(np.arange(2000, 2020), 20)
    keys = np.tile(np.array([1, 2]), 200)
    target = rng.normal(size=(n, d)).astype(np.float32) * 5 + 10
    p = trust.ClimPool(keys, year, target, (2010, 2019), m=20)
    q = p.quantiles(np.array([1, 2, 1]))
    assert q.shape == (3, 20, d) and (np.diff(q, axis=1) >= -1e-6).all() and np.array_equal(q[0], q[2])
    # a key absent from the window but present earlier falls back to all years
    keys2 = keys.copy()
    keys2[year >= 2010] = 2
    p2 = trust.ClimPool(keys2, year, target, (2010, 2019), m=20)
    assert p2.quantiles(np.array([1])).shape == (1, 20, d)
