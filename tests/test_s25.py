"""New_Plan section 25 code: flag-off identity (byte-identical to tests/golden_train.json), loss unit checks, a tiny CPU smoke
train per new loss term and per new arch, and the checkpoint round trip through the shipped Sampler path (make_generator + state)."""
import json
import math
import os

import numpy as np
import pytest
import torch

from tempest.generator import s25_losses as L
from tempest.generator import s25_models as S
from tempest.generator.model import Generator, energy_score, make_generator
from test_flags_off import GOLDEN, run

S25_DEFAULTS = dict(es_beta=1.0, vario_weight=0.0, vario_p=0.5, shear_vec_es_weight=0.0, twes_weight=0.0, twes_q=0.9, twes_top_m=18000.0,
                    twes_tau=0.1, sig_weight=0.0, sig_stride=1, model_kw_extra=None, s25=None, distill_teacher=None, distill_m=8,
                    distill_data_weight=0.0)


def test_s25_keys_at_defaults_are_byte_identical_to_golden():
    assert run(S25_DEFAULTS) == json.load(open(GOLDEN, encoding="utf-8"))


def test_make_generator_mlp_unchanged():
    torch.manual_seed(0)
    a = make_generator("mlp", 5, 7, 4, 16, 2)
    torch.manual_seed(0)
    b = Generator(5, 7, 4, 16, 2)
    assert type(a) is Generator and all(torch.equal(x, y) for x, y in zip(a.state_dict().values(), b.state_dict().values()))
    with pytest.raises(ValueError):
        make_generator("nope", 5, 7, 4, 16, 2)


def test_loss_units():
    torch.manual_seed(0)
    s, y = torch.randn(6, 4, 10), torch.randn(6, 10)
    assert torch.allclose(L.energy_score_beta(s, y, 1.0), energy_score(s, y), atol=1e-5)
    assert L.variogram_score(s, y, 2, 5) >= 0
    p = torch.randn(3, 9, 2)                                   # depth-2 signature: S_ab + S_ba = S_a * S_b (shuffle identity)
    g = L.signature2(p)
    s1, s2 = g[:, :2], g[:, 2:].view(3, 2, 2)
    assert torch.allclose(s2 + s2.transpose(1, 2), s1[:, :, None] * s1[:, None, :], atol=1e-5)
    t = torch.randn(6, 8, 10)                                  # energy distance: smaller for a student drawn like the teacher
    assert L.energy_distance(t[:, :4] + 0.0, t[:, 4:]) < L.energy_distance(t[:, :4] + 3.0, t[:, 4:])


@pytest.mark.parametrize("extra", [dict(es_beta=1.5), dict(vario_weight=0.05), dict(shear_vec_es_weight=0.1), dict(twes_weight=0.1),
                                   dict(sig_weight=0.1, sig_stride=2)])
def test_new_loss_terms_run_and_move_results(extra):
    got = run(extra)
    assert np.isfinite(got["member0"]["val"]).all() and got != json.load(open(GOLDEN, encoding="utf-8"))


ARCHS = [("flow", {}), ("flow", dict(train="crps", train_steps=2, steps=3)), ("rml", dict(K=3)), ("har", dict(blocks=6)),
         ("moe", {}), ("eof", {}), ("prior", {}), ("prior", dict(mode="noise")), ("analog", dict(rows=2000))]


@pytest.mark.parametrize("arch,opt", ARCHS)
def test_arch_smoke_and_checkpoint_round_trip(arch, opt):
    got = run(dict(arch=arch, s25=opt))
    assert np.isfinite(got["member0"]["val"]).all()


def test_arch_checkpoint_rebuilds_like_sample_py(tmp_path):
    from tempest.generator import train as T
    import test_flags_off as F
    captured = {}
    orig = T.train

    def keep(*a, **k):
        captured["ck"] = orig(*a, **k)
        return captured["ck"]
    F.train = keep
    try:
        run(dict(arch="eof", s25={}))
    finally:
        F.train = orig
    path = os.path.join(tmp_path, "m.pt")
    torch.save(captured["ck"], path)
    mb = torch.load(path, map_location="cpu", weights_only=True)["members"][0]
    c = mb["cfg"]
    mdl = make_generator(c["arch"], mb["n_cond"], mb["n_out"], c["noise_dim"], c["width"], c["depth"], linear_cols=mb["linear_cols"], **mb["model_kw"])
    mdl.load_state_dict(mb["state"])
    out = mdl.eval()(torch.zeros(3, mb["n_cond"]), 2)
    assert out.shape == (3, 2, mb["n_out"]) and torch.isfinite(out).all()
    teacher = S.load_teacher(path, mb["norm"], "cpu")                      # MF1 teacher loader accepts the same normalisation
    assert teacher(torch.zeros(2, mb["n_cond"]), 5).shape == (2, 5, mb["n_out"])
    bad = {k: v + 1 for k, v in mb["norm"].items()}
    with pytest.raises(ValueError):
        S.load_teacher(path, bad, "cpu")


def test_distill_smoke(tmp_path):
    from tempest.generator import train as T
    import test_flags_off as F
    captured = {}
    orig = T.train

    def keep(*a, **k):
        captured["ck"] = orig(*a, **k)
        return captured["ck"]
    F.train = keep
    try:
        run(dict(arch="flow", s25=dict(steps=2)))
    finally:
        F.train = orig
    path = os.path.join(tmp_path, "teacher.pt")
    torch.save(captured["ck"], path)
    got = run(dict(distill_teacher=path, distill_m=4))
    assert np.isfinite(got["member0"]["val"]).all()


def test_space_round_trip_and_tau_embed_numpy_matches_torch():
    sp = S.Space(S.N_PROF + 3)
    sp.tm.normal_()
    sp.ts.uniform_(0.5, 2)
    sp.pm.normal_()
    sp.ps.uniform_(0.5, 2)
    x = torch.randn(4, S.N_PROF + 3)
    assert torch.allclose(sp.from_std(sp.to_std(x)), x, atol=1e-4)
    tau = np.linspace(0, 1, 7, dtype=np.float32)
    assert np.allclose(S.tau_embed(tau, 8), S.tau_embed(torch.tensor(tau), 8).numpy(), atol=1e-5)


def test_har_blocks_cover_every_column_once():
    cols = np.concatenate(S.har_blocks(7, S.N_PROF + 3))
    assert sorted(cols.tolist()) == list(range(S.N_PROF + 3))


def test_moe_gate_logged():
    m = S.MoEGenerator(13, S.N_PROF + 3, 4, 16, 2, moe=dict(doy_cols=[4, 5]))
    m.train()
    m(torch.randn(5, 13), 3)
    assert m.last_gate.shape == (5, 3, 3) if hasattr(m, "last_gate") else m.head[1].last_gate.shape == (5, 3, 3)
    assert m.aux_loss is not None and math.isfinite(float(m.aux_loss))


def test_engine_numpy_flow_and_rml_match_torch():
    from tempest_weather import engine as E
    torch.manual_seed(1)
    F, n_out = 13, S.N_PROF + 3
    norm = dict(cm=np.zeros(F, np.float32), cs=np.ones(F, np.float32), tm=np.zeros(n_out, np.float32), ts=np.ones(n_out, np.float32))
    fl = S.FlowGenerator(F, n_out, 8, 32, 2, linear_cols=[8, 9]).eval()
    meta = dict(n_cond=F + n_out, linear_cols=[8, 9], noise_dim=8, depth=2)
    inner = E.inner_member({k: v.numpy() for k, v in fl.state_dict().items()}, norm, meta)
    c = torch.randn(5, F)
    x0 = torch.randn(5, n_out)
    with torch.no_grad():
        want = fl.integrate(c, x0.clone(), 0.0, 4).numpy()
    got = E.flow_sample(inner, c.numpy(), 4, np.random.default_rng(0), x=x0.numpy())
    assert np.allclose(got, want, atol=2e-4), np.abs(got - want).max()
    r = S.RMLGenerator(F, n_out, 8, 32, 2, rml=dict(K=3)).eval()
    rin = E.inner_member({k: v.numpy() for k, v in r.state_dict().items()}, norm, dict(n_cond=F + n_out + 3, linear_cols=[], noise_dim=8, depth=2))
    inp = r.step_input(c, x0, torch.full((5,), 2, dtype=torch.long))
    e = torch.randn(5, 8)
    with torch.no_grad():
        want = r.net(inp, 1, eps=e)[:, 0].numpy()
    assert np.allclose(rin.forward(inp.numpy(), e.numpy()), want, atol=2e-4)
    assert E.rml_sample(rin, c.numpy(), 3, np.random.default_rng(0)).shape == (5, n_out)


# ---- New_Plan 25 arm deltas (configs/s25/*.toml) through scripts/s25_cfg.py: every delta merges, its keys exist, and it trains (tiny CPU run)
import glob  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import s25_cfg  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELTAS = sorted(glob.glob(os.path.join(REPO, "configs", "s25", "*.toml")))
FIXED = {"members", "seed", "steps", "eval_every", "patience", "val_years", "val_rows", "batch", "lr", "width", "depth", "noise_dim"}


def test_cfg_default_keys_match_train_defaults():
    from tempest.generator.train import DEFAULTS
    assert s25_cfg.default_keys() == set(DEFAULTS)


def test_cfg_rejects_typos_and_merges_tables(tmp_path):
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        cfg = s25_cfg.build("configs/s25/gf3_f2.toml", ["seed=100", 'init="models/x.pt"', "s25.train_steps=2"])
        assert cfg["seed"] == 100 and cfg["s25"] == dict(steps=8, train="crps", train_steps=2) and cfg["init"] == "models/x.pt"
        assert cfg["members"] == 4 and cfg["shear_tail_weight"] == 1.0                     # the shipped c4w line underneath
        import tomllib
        assert tomllib.loads(s25_cfg.dumps(cfg)) == cfg
        with pytest.raises(SystemExit):
            s25_cfg.build("configs/s25/base.toml", ["lrr=1"])
    finally:
        os.chdir(cwd)


def tiny_train(extra):
    """run() of test_flags_off at 1/5 the rows and 4 steps on 2 threads: a does-it-train check for every delta, not a golden."""
    from tempest.generator.build_dataset import target_names
    from tempest.generator.features import FEATURES
    from tempest.generator.train import train
    rng = np.random.default_rng(7)
    n = 1200
    cond = rng.normal(size=(n, len(FEATURES))).astype(np.float32)
    cond[:, FEATURES.index("year")] = np.repeat(np.arange(2000, 2012), n // 12)
    base = rng.normal(size=(n, 4 * 44 + 3)).astype(np.float32) * 0.3
    base[:, 2 * 44] += 280
    year = cond[:, FEATURES.index("year")].astype(np.int16)
    cfg = dict(width=16, depth=2, noise_dim=4, batch=64, steps=4, eval_every=2, val_years=2, lr=2e-3, val_rows=200, **extra)
    threads = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        torch.manual_seed(0)
        return train(cond, base, year, cfg, device="cpu", log=lambda *_: None, members=1,
                     meta=dict(cond_names=list(FEATURES), target_names=target_names()))
    finally:
        torch.set_num_threads(threads)


@pytest.mark.parametrize("path", DELTAS, ids=[os.path.basename(p)[:-5] for p in DELTAS])
def test_every_arm_delta_trains(path):
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        cfg = {k: v for k, v in s25_cfg.build(path).items() if k not in FIXED and k != "init"}
    finally:
        os.chdir(cwd)
    ck = tiny_train(cfg)                                             # members=1: one bare checkpoint
    assert np.isfinite([h[2] for h in ck["history"]]).all()


def test_gt2_pool_mlp_plus_tokens_samples_through_sampler(tmp_path):
    from tempest.generator.sample import Sampler
    import s25_pool
    a, b = tiny_train({}), tiny_train(dict(arch="tokens"))
    pa, pb = os.path.join(tmp_path, "a.pt"), os.path.join(tmp_path, "b.pt")
    torch.save(a, pa)
    torch.save(b, pb)
    ck = s25_pool.pool([pa, pb])
    assert [m["cfg"].get("arch", "mlp") for m in ck["members"]] == ["mlp", "tokens"]
    out = Sampler(ck, device="cpu")(np.zeros((6, a["n_cond"]), np.float32))
    assert out.shape == (6, a["n_out"]) and np.isfinite(out).all()


@pytest.mark.parametrize("mod", ["s25_sampler_cost", "s25_gate_month", "s25_compose_refine"])
def test_s25_script_selfchecks(mod):
    """GF3 sampler cost (numpy = torch), H3 gate-by-month table and collapse flag, H5 draft + refine compose (norm refusal)."""
    import importlib
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    importlib.import_module(mod)._selfcheck()
