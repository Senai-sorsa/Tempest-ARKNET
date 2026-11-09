"""Loop 3 options (docs/plans/GLOBAL_PLAN.md G1): spherical harmonics, context FiLM, terrain head, ignore_inputs, overlay files.
All off by default; these check the new paths work and that the default network is unchanged."""
import numpy as np
import torch

from tempest.geo.sh import sh
from tempest.generator.model import Generator
from tempest.generator.sample import Sampler
from tempest.generator.train import load_npz, train


def test_sh_orthonormal_and_torch_matches_numpy():
    n = 200
    lat = np.degrees(np.arcsin((np.arange(n) + 0.5) / n * 2 - 1))          # equal-area rings
    lon = (np.arange(2 * n) + 0.5) / (2 * n) * 360 - 180
    la, lo = (a.ravel() for a in np.meshgrid(lat, lon, indexing="ij"))
    y = sh(la, lo, 6)
    assert y.shape[1] == 49 and np.abs(y.T @ y / len(y) - np.eye(49)).max() < 0.01
    assert np.allclose(sh(torch.tensor(la[:9]), torch.tensor(lo[:9]), 6).numpy(), y[:9])
    assert np.allclose(sh(np.array([10.0]), np.array([180.0]), 6), sh(np.array([10.0]), np.array([-180.0]), 6))  # no date-line seam


def test_default_network_unchanged():
    keys = set(Generator(5, 3, 4, 16, 2, linear_cols=[4]).state_dict())
    assert not any(k.startswith(("ctx", "siren", "th_", "geo")) for k in keys)


def _data(n=20000, seed=0):
    rng = np.random.default_rng(seed)
    lat, lon = rng.uniform(30, 40, n), rng.uniform(-110, -100, n)
    terr = rng.normal(size=n)
    year = np.repeat(np.arange(2000, 2010), n // 10)
    cond = np.stack([lat, lon, terr, year], 1).astype(np.float32)
    y = np.stack([0.3 * (lat - 35) + 0.5 * terr, 0.2 * (lon + 105)], 1) + 0.2 * rng.normal(size=(n, 2))
    return cond, y.astype(np.float32), year


def test_options_train_and_sample(tmp_path):
    cond, y, year = _data()
    meta = dict(cond_names=["lat", "lon", "terr", "year"], target_names=["a", "b"])
    base = dict(width=32, depth=2, noise_dim=4, batch=512, steps=300, eval_every=100, val_years=2, lr=3e-3)
    for extra in (dict(geo_sh=4), dict(geo_sh=4, geo_siren=16), dict(geo_sh=3, context_inputs=["terr"]),
                  dict(terrain_head_inputs=["terr"]), dict(ignore_inputs=["lat", "lon"])):
        ck = train(cond, y, year, {**base, **extra}, device="cpu", log=lambda *_: None, meta=meta)
        torch.save(ck, tmp_path / "m.pt")
        s = Sampler(torch.load(tmp_path / "m.pt", weights_only=False), device="cpu")
        out = s(cond[:500])
        assert out.shape == (500, 2) and np.isfinite(out).all(), extra
    # ignore_inputs: the network output cannot depend on lat/lon
    c2 = cond[:500].copy(); c2[:, :2] += 3
    torch.manual_seed(0); a = s(cond[:500])
    torch.manual_seed(0); b = s(c2)
    assert np.allclose(a, b, atol=1e-5)


def test_overlay_npz(tmp_path):
    cond, y, year = _data(200)
    np.savez(tmp_path / "base.npz", cond=cond, target=y, year=year, cond_names=np.array(["lat", "lon", "terr", "year"]))
    wide = np.concatenate([cond, cond[:, :1] * 2], 1)
    np.savez(tmp_path / "ov.npz", base_npz=np.array(str(tmp_path / "base.npz")), cond=wide,
             cond_names=np.array(["lat", "lon", "terr", "year", "x"]))
    from tempest.generator import features
    try:
        d = load_npz(tmp_path / "ov.npz")
        assert np.array_equal(d["cond"], wide) and np.array_equal(d["target"], y) and "base_npz" not in d
        assert list(d["cond_names"])[-1] == "x"
    finally:
        features.set_active(features.BASE_FEATURES)   # load_npz activates the file's column list module-wide


def test_qmc_noise():
    """L3-37: eps=None is the plain torch.randn draw; Sobol blocks are balanced (block mean ~4x closer to 0 than random)."""
    from tempest.generator.sample import sobol_normal
    g = Generator(4, 6, noise_dim=8, width=16, depth=1).eval()
    c = torch.randn(5, 4)
    torch.manual_seed(0); a = g(c, 1)
    torch.manual_seed(0); b = g(c, 1, eps=torch.randn(5, 1, 8).view(5, -1))
    assert torch.equal(a, b)
    torch.manual_seed(1)
    q, r = sobol_normal(100, 128, 8).view(100, 128, 8), torch.randn(100, 128, 8)
    assert torch.isfinite(q).all() and q.mean(1).abs().mean() < r.mean(1).abs().mean() / 3


def test_fill_mask_ignores_filled_heights():
    """review 2026-11-07: with fill_mask the heights above fill_top_idx count 0. Junk there, shuffled between rows (same column
    statistics, so the same normalisation), leaves the validation loss unchanged with the mask and changes it without."""
    from tempest.generator.train import N_PROF
    import pytest
    rng = np.random.default_rng(1)
    n, nh = 6000, N_PROF // 4
    cond = rng.normal(size=(n, 3)).astype(np.float32)
    year = np.repeat(np.arange(2000, 2010), n // 10)
    y = (0.1 * rng.normal(size=(n, N_PROF + 3))).astype(np.float32)
    tops = np.full((n, 4), nh - 1, np.int8)
    tops[::3] = nh - 6                                                     # a third of the rows: top 5 heights filled
    pr = y[:, :N_PROF].reshape(n, 4, nh).copy()
    pr[::3, :, :nh - 5] = 0.0                                             # equal lower parts: shuffled junk keeps every normalisation statistic
    pr[::3, :, nh - 5:] = 3.0 * rng.normal(size=pr[::3, :, nh - 5:].shape)  # junk the mask must ignore
    y[:, :N_PROF] = pr.reshape(n, -1)
    pr[::3, :, nh - 5:] = pr[::3, :, nh - 5:][rng.permutation(len(pr[::3]))]
    y2 = y.copy()
    y2[:, :N_PROF] = pr.reshape(n, -1)
    meta = dict(cond_names=["a", "b", "c"], target_names=[str(i) for i in range(N_PROF + 3)])
    cfg = dict(width=32, depth=2, noise_dim=4, batch=256, steps=40, eval_every=20, val_years=2, lr=3e-3, fill_mask=True)
    run = lambda t, c, **k: train(cond, t, year, c, device="cpu", log=lambda *_: None, meta=meta, **k)["val_loss"]  # noqa: E731
    a, b = run(y, cfg, fill_top_idx=tops), run(y2, cfg, fill_top_idx=tops)
    off = {**cfg, "fill_mask": False}
    c, d = run(y, off), run(y2, off)
    assert np.isfinite(a) and abs(a - b) < 0.1 * abs(c - d), (a, b, c, d)          # float summation order leaves ~1e-5
    with pytest.raises(ValueError):
        run(y, cfg)
