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


def test_trend_and_driver_paths():
    # target = x + 0.3 per year + 0.5 * oni + noise; year and oni take the straight-line path, queried 6 years past the data
    rng = np.random.default_rng(2)
    n = 40000
    x, oni = rng.uniform(-1, 1, n).astype(np.float32), rng.normal(size=n).astype(np.float32)
    year = np.repeat(np.arange(2000, 2010), n // 10)
    y = (x + 0.3 * (year - 2000) + 0.5 * oni + 0.2 * rng.normal(size=n)).astype(np.float32)[:, None]
    cfg = dict(width=64, depth=3, noise_dim=4, batch=1024, steps=3000, eval_every=500, val_years=2, lr=3e-3)
    ckpt = train(np.stack([x, year, oni], 1).astype(np.float32), y, year, cfg, device="cpu", log=lambda *_: None,
                 meta=dict(cond_names=["x", "year", "oni"]))
    assert ckpt["linear_cols"] == [1, 2]
    s = Sampler(ckpt, device="cpu")
    for o in (-1.5, 1.5):
        out = s(np.tile(np.float32([0.5, 2015, o]), (20000, 1)))
        assert abs(out.mean() - (0.5 + 0.3 * 15 + 0.5 * o)) < 0.3, (o, out.mean())


def test_to_physical_roundtrip_and_rh_clip():
    from tempest.generator.sample import SURFACE, to_physical
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    rng = np.random.default_rng(3)
    prof = rng.normal(50, 10, (6, len(PROFILE), len(HEIGHTS)))
    prof[:, PROFILE.index("RH"), :3] = [120, -5, 60]
    sfc = np.tile([300.0, 85000.0, 130.0], (6, 1))
    out = to_physical(np.concatenate([to_diff(prof).reshape(6, -1), sfc], 1))
    p = out[:, :-3].reshape(prof.shape)
    rh = PROFILE.index("RH")
    assert np.allclose(p[:, rh, :3], [100, 0, 60])
    assert np.allclose(np.delete(p, rh, 1), np.delete(prof, rh, 1))
    assert np.allclose(out[:, -3:], [300, 85000, 100]) and SURFACE[-1] == "rh2m"


def test_crps_matches_definition():
    from tempest.scoring.score import crps_ensemble
    rng = np.random.default_rng(4)
    x, y = rng.normal(size=(7, 9, 3)), rng.normal(size=(7, 3))
    brute = np.abs(x - y[:, None]).mean(1) - 0.5 * np.abs(x[:, :, None] - x[:, None]).mean((1, 2))
    assert np.allclose(crps_ensemble(x, y), brute)


def test_afcrps_matches_fair_crps_and_prefers_truth():
    from tempest.generator.model import afcrps
    g = torch.Generator().manual_seed(5)
    x, y = torch.randn(50, 4, 3, generator=g), torch.randn(50, 3, generator=g)
    fair = (x - y[:, None]).abs().mean(1) - (x[:, :, None] - x[:, None]).abs().sum((1, 2)) / (2 * 4 * 3)
    assert torch.allclose(afcrps(x, y, alpha=1.0), fair.mean())
    y = torch.randn(4000, 3, generator=g)
    assert afcrps(torch.randn(4000, 4, 3, generator=g), y) < afcrps(0.3 * torch.randn(4000, 4, 3, generator=g), y)


def test_ensemble_sampler_splits_rows_across_members():
    rng = np.random.default_rng(6)
    x = rng.uniform(-1, 1, (4000, 1)).astype(np.float32)
    y = (3 * x + 0.1 * rng.normal(size=(4000, 1))).astype(np.float32)
    year = np.repeat(np.arange(4), 1000)
    cfg = dict(width=16, depth=1, noise_dim=2, batch=256, steps=200, eval_every=100, val_years=1)
    ck = train(x, y, year, cfg, device="cpu", log=lambda *_: None, members=2)["members"]  # trained side by side
    assert [c["cfg"]["seed"] for c in ck] == [0, 1] and not torch.equal(ck[0]["state"]["inp.weight"], ck[1]["state"]["inp.weight"])
    s = Sampler(dict(members=ck), device="cpu")
    assert len(s.members) == 2
    out = s(np.zeros((1000, 1), np.float32))
    a, b = Sampler(ck[0], device="cpu"), Sampler(ck[1], device="cpu")
    assert out.shape == (1000, 1) and np.isfinite(out).all()
    assert abs(out[0::2].mean() - a(np.zeros((1000, 1), np.float32)).mean()) < 0.1
    assert abs(out[1::2].mean() - b(np.zeros((1000, 1), np.float32)).mean()) < 0.1


def test_variogram_and_gaussian_baseline():
    from tempest.scoring.score import gaussian_samples, variogram_score
    rng = np.random.default_rng(7)
    cov = 0.9 ** np.abs(np.subtract.outer(np.arange(179), np.arange(179)))  # smooth, height-correlated
    truth = rng.multivariate_normal(np.full(179, 50.0), cov, 300)
    right = rng.multivariate_normal(np.full(179, 50.0), cov, (300, 40))
    shuffled = right[:, :, rng.permutation(179)]  # same values per height on average, wrong vertical structure
    assert variogram_score(right[..., :44], truth[:, :44]).mean() < variogram_score(shuffled[..., :44], truth[:, :44]).mean()
    g = gaussian_samples(rng.multivariate_normal(np.full(179, 50.0), cov, 3000), 200, 20, rng)
    assert g.shape == (200, 20, 179) and np.isfinite(g).all() and abs(g.mean() - 50) < 0.2


def test_load_npz_matches_np_load(tmp_path):
    from tempest.generator.train import load_npz
    rng = np.random.default_rng(8)
    arrs = dict(cond=rng.normal(size=(50, 3)).astype(np.float32), year=np.arange(50, dtype=np.int16),
                names=np.array(["lat", "lon", "year"]))
    np.savez(tmp_path / "a.npz", **arrs)
    np.savez_compressed(tmp_path / "b.npz", **arrs)
    for f in ("a.npz", "b.npz"):
        d = load_npz(tmp_path / f)
        assert all(np.array_equal(d[k], v) and d[k].dtype == v.dtype for k, v in arrs.items())


def test_report_writes_charts(tmp_path):
    import pandas as pd
    from tempest.scoring.report import report
    rng = np.random.default_rng(9)
    prof, h, sfc = ["u", "T"], np.array([10.0, 500, 2000]), ["t2m"]
    cols = [f"{v}_{x:g}" for v in prof for x in h] + sfc
    res = pd.DataFrame({"column": cols, **{f"{s}_{k}": rng.random(len(cols)) for s in ("crps", "cov90", "skill")
                                           for k in ("clim", "gauss", "known", "unknown")}})
    vs = pd.DataFrame({"var": prof, **{f"vs_skill_{k}": rng.random(2) for k in ("gauss", "known", "unknown")}})
    files = report(tmp_path / "r", res, vs, rng.integers(0, 11, (50, 7)), (rng.random((2, 7)), rng.random((2, 10, 7))),
                   [[(1, 0.5, 0.6), (2, 0.4, 0.5)], None], prof, h, sfc)
    assert {"training_curves.png", "skill_by_height.png", "rank_histograms.png", "example_profiles.png"} <= set(files)


def test_sp_offset_roundtrip():
    # sp = standard pressure at elev_grid + weather: trained on the departure, sampled back in Pa
    from tempest.generator.sample import standard_pressure
    rng = np.random.default_rng(10)
    n = 20000
    z = rng.uniform(800, 2400, n)
    cond = np.stack([z, rng.uniform(-1, 1, n)], 1).astype(np.float32)
    y = (standard_pressure(z) + 300 * cond[:, 1] + 100 * rng.normal(size=n))[:, None].astype(np.float32)
    cfg = dict(width=32, depth=2, noise_dim=2, batch=1024, steps=1500, eval_every=500, val_years=1, lr=3e-3)
    ck = train(cond, y, np.repeat(np.arange(4), n // 4), cfg, device="cpu", log=lambda *_: None,
               meta=dict(cond_names=["elev_grid", "x"], target_names=["sp"]))
    assert ck["sp_offset"] == [0, 0] and ck["norm"]["ts"][0] < 1000  # learned scale is weather, not elevation
    out = Sampler(ck, device="cpu")(np.tile(np.float32([1500, 0.5]), (5000, 1)))
    assert abs(out.mean() - (standard_pressure(1500) + 150)) < 40


def test_to_site_moves_surface_only():
    from tempest.generator.sample import to_site
    phys = np.full((2, 179), 50.0)
    phys[:, -3:] = [300.0, 85000.0, 40.0]
    out = to_site(phys.copy(), 1262.0, np.array([1262.0, 1254.0]))
    assert np.allclose(out[0], phys[0]) and np.allclose(out[1, :-3], phys[1, :-3])
    assert np.isclose(out[1, -3], 300.052) and 85075 < out[1, -2] < 85085 and out[1, -1] == 40


def test_block_split_keeps_a_gap():
    from tempest.generator.features import FEATURES
    from tempest.generator.train import split
    days = np.arange(20 * 365)
    year = 2000 + days // 365
    a = 2 * np.pi * (days % 365 + 1) / 365.25
    cond = np.zeros((len(days), len(FEATURES)), np.float32)
    cond[:, FEATURES.index("doy_sin")], cond[:, FEATURES.index("doy_cos")] = np.sin(a), np.cos(a)
    tr, val = split(year, cond, FEATURES, dict(val_block_frac=0.1, val_years=3))
    assert not (tr & val).any() and 0.05 < val.mean() < 0.15 and len(np.unique(year[val])) >= 15
    vd, td = days[val], days[tr]
    assert np.abs(td[:, None] - vd[None, :]).min() >= 3  # no training day within 3 days of a validation day
    tr0, val0 = split(year, cond, FEATURES, dict(val_years=3))
    assert (val0 == (year >= 2017)).all() and (tr0 == ~val0).all()
