"""AV21 anomaly-output option (model anom, train cfg anom_clim): off by default, table fit recovers a known climatology,
forward maps z to (mu + sd z - tm) / ts, and a tiny training run saves a checkpoint the Sampler reloads."""
import numpy as np
import torch

from tempest.generator.model import ANOM_COLS, Generator, anom_basis, fit_anom_table


def _rows(n, rng, pts=((35.0, -106.0), (32.0, -100.0))):
    k = rng.integers(0, len(pts), n)
    a, b = rng.uniform(0, 2 * np.pi, n), rng.uniform(0, 2 * np.pi, n)
    c6 = np.column_stack([np.array(pts)[k], np.sin(a), np.cos(a), np.sin(b), np.cos(b)])
    return c6, k, a, b


def test_default_has_no_anom_buffers():
    g = Generator(6, 3, noise_dim=4, width=16, depth=1)
    assert not any(n.startswith("anom") for n in g.state_dict())


def test_fit_recovers_climatology():
    rng = np.random.default_rng(0)
    c6, k, a, b = _rows(20000, rng)
    mean = 10 + 5 * k + 3 * np.cos(a) + 1.5 * np.sin(b)
    sd = 1 + k
    y = np.column_stack([mean + sd * rng.standard_normal(len(k)), np.zeros(len(k))])
    keys, cmu, clv = fit_anom_table(c6, y, np.array([1e-3, 1e-3]))
    assert keys.shape == (2, 2) and cmu.shape == (2, 11, 2)
    X = anom_basis(c6[:, 2], c6[:, 3], c6[:, 4], c6[:, 5], np)
    p = np.array([np.where((keys == np.round(r, 3)).all(1))[0][0] for r in c6[:500, :2]])
    fit_mu = np.einsum("bk,bk->b", X[:500], cmu[p, :, 0])
    fit_sd = np.exp(0.5 * np.einsum("bk,bk->b", X[:500], clv[p, :, 0]))
    assert np.abs(fit_mu - mean[:500]).max() < 0.15
    assert np.abs(fit_sd / sd[:500] - 1).max() < 0.15


def test_forward_maps_anomaly():
    rng = np.random.default_rng(1)
    c6, k, a, b = _rows(4000, rng)
    y = np.column_stack([20 + 4 * k + rng.standard_normal(len(k)), 5 * rng.standard_normal(len(k))])
    tab = fit_anom_table(c6, y, np.array([1e-3, 1e-3]))
    cm, cs = c6.mean(0), c6.std(0)
    tm, ts = y.mean(0), y.std(0)
    g = Generator(6, 2, noise_dim=4, width=16, depth=1,
                  anom=dict(cols=list(range(6)), mu=cm.tolist(), sd=cs.tolist(), P=2, tm=tm.tolist(), ts=ts.tolist()))
    g.set_anom(*tab)
    full = torch.tensor((c6[:8] - cm) / cs, dtype=torch.float32)
    z = torch.zeros(8, 1, 2)
    out = g._anom(full, z)[:, 0].numpy() * ts + tm
    X = anom_basis(c6[:8, 2], c6[:8, 3], c6[:8, 4], c6[:8, 5], np)
    want = np.einsum("bk,bkd->bd", X, tab[1][1 - k[:8]])   # keys sorted by lat: (32, -100) is table point 0 = pts index 1
    assert np.allclose(out, want, atol=1e-3)
    assert g(full, 3).shape == (8, 3, 2)


def test_train_and_reload(tmp_path):
    from tempest.generator.model import make_generator
    from tempest.generator.train import train
    rng = np.random.default_rng(2)
    n = 3000
    c6, k, a, b = _rows(n, rng)
    cond = np.column_stack([c6, rng.integers(2000, 2010, n)]).astype(np.float32)
    names = ANOM_COLS + ["year"]
    target = np.column_stack([10 + 3 * k + rng.standard_normal(n), rng.standard_normal(n)]).astype(np.float32)
    out = tmp_path / "m.pt"
    train(cond, target, cond[:, -1], cfg=dict(anom_clim=True, steps=4, eval_every=2, batch=64, width=16, depth=1, val_rows=200, val_years=2),
          out=str(out), device="cpu", log=lambda *_: None, meta=dict(cond_names=names, target_names=["a", "b"]))
    ck = torch.load(out, map_location="cpu", weights_only=True)   # rebuilt as Sampler does (Sampler itself rejects this toy feature list)
    c = ck["cfg"]
    model = make_generator("mlp", ck["n_cond"], ck["n_out"], c["noise_dim"], c["width"], c["depth"], linear_cols=ck.get("linear_cols"), **ck["model_kw"])
    model.load_state_dict(ck["state"])
    assert model.anom["P"] == 2 and float(model.anom_cmu.abs().sum()) > 0


def test_mean_only_ignores_spread():
    """AV40: anom mean_only maps z to (mu - tm) / ts + z, whatever the log-spread table holds."""
    rng = np.random.default_rng(3)
    c6, k, a, b = _rows(4000, rng)
    y = np.column_stack([20 + 4 * k + (1 + 3 * k) * rng.standard_normal(len(k)), 5 * rng.standard_normal(len(k))])
    tab = fit_anom_table(c6, y, np.array([1e-3, 1e-3]))
    cm, cs, tm, ts = c6.mean(0), c6.std(0), y.mean(0), y.std(0)
    g = Generator(6, 2, noise_dim=4, width=16, depth=1,
                  anom=dict(cols=list(range(6)), mu=cm.tolist(), sd=cs.tolist(), P=2, tm=tm.tolist(), ts=ts.tolist(), mean_only=True))
    g.set_anom(*tab)
    full = torch.tensor((c6[:8] - cm) / cs, dtype=torch.float32)
    z = torch.randn(8, 2, 2)
    out = g._anom(full, z).numpy()
    X = anom_basis(c6[:8, 2], c6[:8, 3], c6[:8, 4], c6[:8, 5], np)
    mu = np.einsum("bk,bkd->bd", X, tab[1][1 - k[:8]])
    assert np.allclose(out, (mu[:, None] - tm) / ts + z.numpy(), atol=1e-3)
