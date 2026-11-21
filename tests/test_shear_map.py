"""Shear-space map: matches the target tail, leaves ordinary layers and the large-scale winds alone, keeps the shape of the input otherwise."""
import numpy as np

from tempest.calibrate import shear_map as SM

NH = SM.NH


def _profiles(n, m, scale, seed):
    rng = np.random.default_rng(seed)
    base = np.cumsum(rng.normal(0, 0.15, (n, m, 2, NH)), -1)                   # smooth large-scale wind
    rough = rng.standard_t(3, (n, m, 2, NH)) * scale * 0.3                      # heavy-tailed small-scale part
    uv = base + rough
    x = np.zeros((n, m, 4 * NH + 3), np.float32)
    x[..., :2 * NH] = uv.reshape(n, m, 2 * NH)
    return x


def test_fit_matches_tail_and_keeps_large_scale():
    x = _profiles(300, 30, 1.0, 0)
    truth = _profiles(300, 1, 1.8, 1)[:, 0]                                    # truth has a heavier shear tail
    t = SM.fit(x, truth)
    y = SM.apply(t, x)
    q_t = SM._quantiles(SM._band_values(SM.shears(truth[:, :2 * NH].reshape(300, 2, NH).astype(float))[1]), [0.99])
    q0 = SM._quantiles(SM._band_values(SM.shears(x[..., :2 * NH].reshape(300, 30, 2, NH).astype(float))[1]), [0.99])
    q1 = SM._quantiles(SM._band_values(SM.shears(y[..., :2 * NH].reshape(300, 30, 2, NH).astype(float))[1]), [0.99])
    assert all(abs(q1[b][0] - q_t[b][0]) < abs(q0[b][0] - q_t[b][0]) for b in range(4))      # closer to the truth in every band
    lp = lambda a: SM.uniform_filter1d(a[..., :2 * NH].reshape(300, 30, 2, NH), 15, axis=-1, mode="nearest")
    assert np.abs(lp(y) - lp(x)).mean() < 0.35 * np.abs(lp(x)).mean() + 0.05                  # large scale hardly moves
    assert np.array_equal(y[..., 2 * NH:], x[..., 2 * NH:])                                    # only the wind columns change


def test_gain_one_leaves_samples_alone_below_median():
    x = _profiles(100, 10, 1.0, 2)
    t = SM.fit(x, x[:, 0])                                                      # truth distributed like the samples: gain near 1
    body = t["gain"][:, : int(0.97 * t["gain"].shape[1])]                      # the far tail is noisy with 300 truth rows
    assert np.abs(body - 1.0).mean() < 0.1
    y = SM.apply(dict(grid=t["grid"], gain=np.ones_like(t["gain"])), x)
    assert np.allclose(y, x, atol=1e-4)


def test_seven_layer_groups_and_old_tables_still_work():
    x = _profiles(200, 20, 1.0, 3)
    truth = _profiles(200, 1, 1.8, 4)[:, 0]
    t7 = SM.fit(x, truth, edges=SM.EDGES7)
    assert t7["grid"].shape[0] == 7 and "edges" in t7
    y = SM.apply(t7, x)
    assert y.shape == x.shape and np.isfinite(y).all()
    t4 = SM.fit(x, truth)
    assert t4["grid"].shape[0] == 4 and "edges" not in t4 and SM.apply(t4, x).shape == x.shape


def test_full_distribution_fit_moves_the_bulk_too():
    x = _profiles(300, 20, 1.0, 5)
    truth = _profiles(300, 1, 1.5, 6)[:, 0]
    t = SM.fit(x, truth, full=True)
    y = SM.apply(t, x)
    med = lambda a: np.median(SM._band_values(SM.shears(a[..., :2 * SM.NH].reshape(*a.shape[:-1], 2, SM.NH).astype(float))[1])[1])
    tm = np.median(SM._band_values(SM.shears(truth[:, :2 * SM.NH].reshape(300, 2, SM.NH).astype(float))[1])[1])
    assert abs(med(y) - tm) < abs(med(x) - tm)                                  # the median shear moves toward the truth's


def test_lowest_level_is_not_moved():
    """Gemini bug 5: the wind at height 0 stays as sampled."""
    x = _profiles(300, 30, 1.0, 0)
    truth = _profiles(300, 1, 1.8, 1)[:, 0]
    y = SM.apply(SM.fit(x, truth), x)
    assert np.allclose(y[..., 0], x[..., 0], atol=1e-4) and np.allclose(y[..., NH], x[..., NH], atol=1e-4)


def test_threshold_weighted_crps_ignores_the_calm_bulk():
    """M3: twCRPS equals the CRPS at -inf, is zero when everything is below the threshold, and punishes a missed storm more than a missed calm."""
    from tempest.scoring.score import crps_ensemble, twcrps_ensemble
    rng = np.random.default_rng(0)
    x = np.abs(rng.normal(3, 1.5, size=(50, 40, 1)))
    y = np.abs(rng.normal(3, 1.5, size=(50, 1)))
    assert np.allclose(twcrps_ensemble(x, y, -np.inf), crps_ensemble(x, y))
    assert np.allclose(twcrps_ensemble(np.minimum(x, 5), np.minimum(y, 5), 50.0), 0.0)
    calm_miss = twcrps_ensemble(np.full((1, 40, 1), 3.0), np.array([[1.0]]), 8.0)
    storm_miss = twcrps_ensemble(np.full((1, 40, 1), 3.0), np.array([[12.0]]), 8.0)
    assert calm_miss[0, 0] == 0.0 and storm_miss[0, 0] > 3.0
