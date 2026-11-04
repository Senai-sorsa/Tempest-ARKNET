import numpy as np
import torch

from tempest.generator.features import FEATURES, features
from tempest.generator.model import energy_score
from tempest.generator.sample import Sampler
from tempest.generator.train import train
from tempest.profiles.diff import from_diff, to_diff


def test_diff_roundtrip():
    p = np.random.default_rng(0).normal(size=(5, 4, 44))
    d = to_diff(p)
    assert np.allclose(d[..., 0], p[..., 0]) and np.allclose(from_diff(d), p)


def test_features_shape():
    f = features(32.99, -106.97, 1400, 1350, np.arange(10), 9.5, 2027, np.zeros(10), 0, 5.0, -3.0)
    assert f.shape == (10, len(FEATURES)) and np.isfinite(f).all()


def test_energy_score_prefers_truth():
    g = torch.Generator().manual_seed(0)
    y = torch.randn(2000, 3, generator=g)
    right = torch.randn(2000, 4, 3, generator=g)
    narrow = 0.3 * torch.randn(2000, 4, 3, generator=g)
    assert energy_score(right, y) < energy_score(narrow, y)


def test_learns_mean_and_spread():
    # target = known mean that depends on the inputs + noise of known size
    rng = np.random.default_rng(1)
    n = 40000
    x = rng.uniform(-1, 1, (n, 2)).astype(np.float32)
    y = np.stack([2 * x[:, 0] + 0.5 * rng.normal(size=n),
                  x[:, 1] ** 2 + 0.2 * rng.normal(size=n)], axis=1).astype(np.float32)
    year = np.repeat(np.arange(10), n // 10)
    cfg = dict(width=64, depth=3, noise_dim=4, batch=1024, steps=3000, eval_every=500, val_years=2, lr=3e-3)
    s = Sampler(train(x, y, year, cfg, device="cpu", log=lambda *_: None), device="cpu")
    for x0 in ([0.5, -0.5], [-0.8, 0.9]):
        out = s(np.tile(np.float32(x0), (20000, 1)))
        mean = [2 * x0[0], x0[1] ** 2]
        assert np.allclose(out.mean(0), mean, atol=0.1), out.mean(0)
        assert np.allclose(out.std(0), [0.5, 0.2], rtol=0.25), out.std(0)
