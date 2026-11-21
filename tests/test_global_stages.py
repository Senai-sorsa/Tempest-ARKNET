"""G2-G5 code on tiny synthetic data (docs/plans/GLOBAL_PLAN.md): no stores, no training runs."""
import os

import numpy as np
import pandas as pd
import pytest
import torch


def test_koppen_classify():
    from tempest.geo.koppen import classify
    t = np.array([[26.0] * 12,                                           # tropical, wet
                  [25.0] * 12,                                           # hot, dry
                  [5.0] * 12,                                            # polar: warmest month < 10 C
                  np.linspace(-10, 20, 12),                              # cold winter
                  np.linspace(5, 20, 12)])                               # mild winter
    p = np.array([[200.0] * 12, [1.0] * 12, [50.0] * 12, [60.0] * 12, [80.0] * 12])
    assert classify(t, p, np.array([0.0, 25.0, 75.0, 50.0, 45.0])).tolist() == [0, 1, 4, 3, 2]


def test_clim_global_solve_compress_grid():
    from tempest.geo import clim_global as cg
    rng = np.random.default_rng(0)
    X = rng.normal(size=(3, 200, 5))
    c = rng.normal(size=(3, 5, 4))
    xtx, xty = np.einsum("pnb,pnc->pbc", X, X), np.einsum("pnb,pnk->pbk", X, X @ c)
    assert np.allclose(cg.solve(xtx, xty), c, atol=1e-4)
    low = rng.normal(size=(30, 6, 2)) @ rng.normal(size=(2, 7))          # rank 2 over the 7 columns
    e = cg.compress(low, n_eof=2)
    assert e["load"].shape == (30, 6, 2) and e["explained"] > 0.999
    rec = (e["load"] @ e["eof"]) * e["scale"] + e["mean"]
    assert np.allclose(rec, low, atol=1e-6)
    lat, lon = np.array([10.0, -40.0, 60.0, 0.0]), np.array([20.0, 100.0, -150.0, 0.0])
    glat, glon, g = cg.to_grid(lat, lon, np.array([1.0, 2.0, 3.0, 4.0]), res=10.0)
    assert g.shape == (len(glat), len(glon)) and abs(g[list(glat).index(10.0), list(glon).index(20.0)] - 1.0) < 1e-6


def test_modef_crps_gauss_and_summary():
    from tempest.forecast.modeF_global import crps_gauss, summary
    rng = np.random.default_rng(1)
    mu, sd, y = 1.0, 2.0, 0.3
    d = rng.normal(mu, sd, 400000)
    mc = np.abs(d - y).mean() - 0.5 * np.abs(d - rng.permutation(d)).mean()
    assert abs(crps_gauss(np.array([mu]), np.array([sd]), np.array([y]))[0] - mc) < 0.01
    t = crps_gauss(torch.tensor([mu]), torch.tensor([sd]), torch.tensor([y]))
    assert abs(float(t[0]) - mc) < 0.01
    s = summary(np.ones((4, 1, 3)))
    assert s.shape == (4, 7) and (s[:, 3:6] == 0).all() and (s[:, 6] == 0).all()


def test_egpd_recovers_tail():
    from tempest.calibrate import egpd
    rng = np.random.default_rng(2)
    sigma, xi, kappa = 2.0, 0.2, 1.5
    y = egpd.ppf(rng.uniform(size=20000), sigma, xi, kappa)
    assert np.allclose(egpd.cdf(egpd.ppf(np.array([0.5, 0.99]), sigma, xi, kappa), sigma, xi, kappa), [0.5, 0.99])
    X = np.stack([np.ones_like(y), rng.normal(size=len(y))], 1)          # a covariate with no effect
    th = egpd.fit_band(y, X)
    assert abs(np.exp(th[0]) - sigma) < 0.3 and abs(th[1]) < 0.05
    assert abs(np.exp(th[-2]) - xi) < 0.06 and abs(np.exp(th[-1]) - kappa) < 0.3


def test_balloon_match_and_ridge():
    from tempest.calibrate.balloon_cov import _match, _ridge
    store = np.array(["2020-01-01T00", "2020-01-02T06", "2020-01-03T12"], "datetime64[h]")
    snd = np.array(["2020-01-01T01", "2020-01-02T00", "2020-01-03T11", "2020-01-03T14"], "datetime64[h]")
    i, j = _match(snd, store)
    assert i.tolist() == [0, 2] and j.tolist() == [0, 2]
    rng = np.random.default_rng(3)
    X = np.concatenate([np.ones((500, 1)), rng.normal(5, 3, (500, 2))], 1)
    b = _ridge(X, X @ np.array([1.0, 2.0, -0.5]), 1e-9)
    assert np.allclose(b, [1.0, 2.0, -0.5], atol=1e-4)
    assert not _ridge(X[:10], np.ones(10), 1e-3).any()                  # too few rows: no correction


def _summary_file(tmp, stem, crps, skill=0.1):
    os.makedirs(stem + "_report", exist_ok=True)
    pd.DataFrame(dict(var=list(crps), band="all", crps_clim=[c / (1 - skill) for c in crps.values()],
                      skill_unknown=skill, cov90_unknown=0.9)).to_csv(stem + "_report/summary.csv", index=False)
    return stem


def test_spatial_gates(tmp_path):
    from tempest.scoring import spatial as sp
    seen = _summary_file(tmp_path, str(tmp_path / "seen"), dict(T=1.0, u=2.0, v=2.0))
    near = _summary_file(tmp_path, str(tmp_path / "near"), dict(T=1.05, u=2.1, v=2.1))
    far = _summary_file(tmp_path, str(tmp_path / "far"), dict(T=1.2, u=2.1, v=2.1))
    assert sp.stem_crps(seen) == pytest.approx(dict(u=2.0, v=2.0, T=1.0))
    assert sp.stem_crps(str(tmp_path / "none")) is None
    x = np.arange(20.0)
    smooth = sp.seam_check(x, dict(a=0.1 * x), dict(a=0.05))
    jump = sp.seam_check(x, dict(a=np.where(x < 10, 0.0, 1.0)), dict(a=0.05))
    assert smooth.ok.all() and not jump.ok.any() and jump["at"][0] in (9.0, 10.0)
    v = sp.gate_g3([seen, seen], [near, far], [seen], [("t", smooth)], modef=(str(tmp_path / "a.csv"), str(tmp_path / "b.csv")))
    unseen_t = v[v.check.str.startswith("unseen T")].verdict.tolist()
    assert unseen_t == ["PASS", "FAIL"] and "MISSING" in v.verdict.tolist()
    g4 = sp.gate_g4([dict(fold="k0", stem=seen)], knndm_crps=1.0, block_ci=(0.9, 1.1), rot_artifact=0.01)
    assert g4.verdict.tolist() == ["FAIL", "PASS", "PASS"] and "no tail quantiles" in g4.why[0]
    lo, hi = sp.bootstrap_ci(np.r_[np.ones(50), 3 * np.ones(50)], np.repeat(np.arange(10), 10))
    assert 1.0 <= lo < 2.0 < hi <= 3.0


def test_generator_chi_input_matches_internal_draw():
    from tempest.generator.model import Generator
    torch.manual_seed(0)
    g = Generator(5, 7, noise_dim=8, width=16, depth=1, noise_t=dict(dims=3, nu=4)).eval()
    cond, eps = torch.randn(4, 5), torch.randn(4 * 2, 8)
    with torch.no_grad():
        torch.manual_seed(1)
        a = g(cond, 2, eps=eps)
        torch.manual_seed(1)
        chi = torch.distributions.Chi2(torch.tensor(4.0)).sample((4, 2, 3))
        b = g(cond, 2, eps=eps, chi=chi.reshape(8, 3))
    assert torch.allclose(a, b)
    plain = Generator(5, 7, noise_dim=8, width=16, depth=1).eval()
    with torch.no_grad():
        assert torch.allclose(plain(cond, 2, eps=eps), plain(cond, 2, eps=eps, chi=chi.reshape(8, 3)))   # ignored without noise_t


def test_export_onnx_step_shear():
    from tempest.export_onnx import NH, step_shear
    raw = np.zeros((2, 4 * NH))
    raw[:, 1] = 3.0                                                     # first u step
    s = step_shear(raw)
    assert s.shape == (2, NH - 1) and s[0, 0] > 0 and (s[:, 1:] == 0).all()
