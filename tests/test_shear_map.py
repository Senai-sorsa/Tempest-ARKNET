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
