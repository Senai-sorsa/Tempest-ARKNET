"""SIGMA stage 2 tables (tempest/forecast/sigma.py): recovers a known beta and s, and the target / draw round trip is exact."""
import numpy as np

from tempest.forecast import sigma as SG


def _rows(n=6000, seed=0):
    rng = np.random.default_rng(seed)
    lead = rng.choice([0.5, 1.0, 3.0, 5.0, 9.5], n)
    month = rng.integers(0, 12, n)
    valid = (np.datetime64("2016-01-15T00") + (month * 31 * 24).astype("timedelta64[h]")).astype("datetime64[ns]")
    lat, lon = rng.choice([32.0, 33.0], n), np.full(n, -105.0)
    clim = 10.0 + 5.0 * (lat == 33.0)
    anom_f = rng.normal(0, 2, (n, 2))
    b_true = np.where(lead[:, None] <= 1, 0.9, np.where(lead[:, None] <= 5, 0.6, 0.2))
    obs = clim[:, None] + b_true * anom_f + rng.normal(0, 1, (n, 2))
    return dict(year=np.full(n, 2016), valid=valid, lat=lat, lon=lon, valid_utc_hour=np.full(n, 12), lead_days=lead,
                obs=obs, hres=clim[:, None] + anom_f), b_true


def test_tables_recover_beta():
    d, _ = _rows()
    tab = SG.fit(d)
    assert abs(tab["beta"][0, 0] - 0.9) < 0.05 and abs(tab["beta"][2, 0] - 0.6) < 0.05 and abs(tab["beta"][9, 0] - 0.2) < 0.05
    assert np.allclose(tab["beta"][1], tab["beta"][0]) or np.allclose(tab["beta"][1], tab["beta"][2])     # day 2 had no rows: nearest day
    assert tab["srel"].min() >= SG.S_FLOOR


def test_round_trip_and_fallback():
    d, _ = _rows()
    tab = SG.fit(d)
    t = SG.target(tab, d)
    back = SG.to_residual(tab, d, t[:, None, :])[:, 0] + d["hres"]
    assert np.allclose(back, d["obs"], atol=1e-3)
    new = {k: v[:5].copy() for k, v in d.items()}
    new["lat"] = np.full(5, 40.0)                                           # unseen place -> month x hour fallback, no error
    base, s = SG.base_scale(tab, new)
    assert np.isfinite(base).all() and (s > 0).all()


def test_fit_years_guard():
    d, _ = _rows(200)
    d["year"] = np.full(200, 2022)
    try:
        SG.fit(d)
    except AssertionError:
        return
    raise AssertionError("2022 rows must be refused")


def test_nest_widths_rule():
    tab = {"srel": np.array([[0.1], [0.2], [0.3], [0.4], [0.5], [0.6], [0.7], [0.8], [0.9], [1.0]])}
    w = SG.nest_widths(tab, 512)
    assert w[0] == 512 and w[-1] == 128 and all(a >= b for a, b in zip(w, w[1:])) and all(x % 128 == 0 for x in w)


def test_nest_mask_is_strict():
    """A row at a narrow lead day must not depend on any weight of the units past its width; nest=None is the old network."""
    import torch
    from tempest.generator.model import Generator
    torch.manual_seed(0)
    widths = [64] * 5 + [16] * 5
    g = Generator(8, 6, noise_dim=4, width=64, depth=2, nest=dict(col=7, mu=0.0, sd=1.0, widths=widths)).eval()
    for blk in g.blocks:                                                    # FiLM starts at 0; give it weight so the check is not trivial
        torch.nn.init.normal_(blk.film.weight, std=0.1)
    cond = torch.randn(4, 8)
    cond[:, 7] = torch.tensor([0.5, 3.0, 7.0, 9.5])                         # lead days 1, 3, 7, 10 -> widths 64, 64, 16, 16
    eps = torch.randn(4, 4)
    out0 = g(cond, 1, eps)
    with torch.no_grad():
        g.inp.weight[16:] += 1.0
        for blk in g.blocks:
            blk.ff[0].weight[16:] += 1.0
            blk.ff[2].weight[16:] += 1.0
            blk.film.weight[16:64] += 1.0
        g.head[1].weight[:, 16:] += 1.0
    out1 = g(cond, 1, eps)
    assert torch.allclose(out0[2:], out1[2:], atol=1e-5), "narrow rows used units past their width"
    assert not torch.allclose(out0[:2], out1[:2]), "wide rows must use all units"
    torch.manual_seed(1)
    a = Generator(8, 6, noise_dim=4, width=64, depth=2).eval()
    torch.manual_seed(1)
    b = Generator(8, 6, noise_dim=4, width=64, depth=2, nest=dict(col=7, mu=0.0, sd=1.0, widths=[64] * 10)).eval()
    assert torch.allclose(a(cond, 1, eps), b(cond, 1, eps), atol=1e-6), "full width everywhere must equal the plain network"


def test_nest_train_save_sample(tmp_path):
    """train(nest_widths) -> checkpoint -> Sampler rebuilds the nested network (model_kw round trip)."""
    import torch
    from tempest.generator.sample import Sampler
    from tempest.generator.train import train
    rng = np.random.default_rng(0)
    n = 400
    cond = rng.normal(0, 1, (n, 4)).astype(np.float32)
    cond[:, 3] = rng.uniform(0.25, 10, n)
    target = rng.normal(0, 1, (n, 3)).astype(np.float32)
    year = np.where(np.arange(n) < 300, 2016, 2017)
    out = str(tmp_path / "nest.pt")
    cfg = dict(width=32, depth=1, noise_dim=4, steps=4, batch=64, eval_every=2, seed=0, linear_features=[], val_block_frac=0, val_years=1, nest_widths=[32] * 5 + [8] * 5)
    train(cond, target, year, cfg, out=out, device="cpu", meta=dict(cond_names=["a", "b", "c", "lead_days"]), log=lambda *a: None)
    ck = torch.load(out, map_location="cpu", weights_only=True)
    assert ck["model_kw"]["nest"]["col"] == 3 and ck["model_kw"]["nest"]["widths"][-1] == 8
    s = Sampler(ck, device="cpu")
    assert s.members[0][0].nest is not None
    x = s(np.repeat(cond[:5], 3, 0))
    assert np.isfinite(np.asarray(x)).all()
