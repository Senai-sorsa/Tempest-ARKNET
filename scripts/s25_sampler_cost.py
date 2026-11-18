"""New_Plan 25 GF3: cost of the numpy Euler sampler (tempest_weather.engine.flow_sample, the code a shipped flow would use) at 4 / 8 / 16 steps.

    python scripts/s25_sampler_cost.py --model models/s25/gf3_f1_s0.pt --base models/s25/base_s0.pt --data data/train/pilot80_l21_day_dpd.npz
    python scripts/s25_sampler_cost.py --selfcheck

Prints one line per step count: forward passes per sample, wall ms per 1000 samples (numpy, first member, best of 2), the cost relative
to the one-pass base MLP, and the RMS gap (normalised units) to a 32-step solve from the same start noise (how far the cheap solve is from
converged). First line: the numpy-vs-torch agreement on this checkpoint (max |diff| over 64 rows, 8 steps); a gap > 1e-3 means the numpy
member does not cover this network's options and the timings do not describe a shippable sampler. Report only: GF3's rule reads this log.
"""
import argparse
import sys
import time

import numpy as np
import torch

from tempest_weather import engine as E

COVERED = {"flow"}                       # model_kw keys the numpy inner member reproduces (plain Engression net + linear_cols)


def _np(d):
    return {k: (v.numpy() if isinstance(v, torch.Tensor) else np.asarray(v)).astype(np.float32) for k, v in d.items()}


def inner_of(m):
    c = m["cfg"]
    meta = dict(n_cond=m["n_cond"] + m["n_out"], linear_cols=list(m.get("linear_cols") or []), noise_dim=c["noise_dim"], depth=c["depth"])
    return E.inner_member(_np(m["state"]), _np(m["norm"]), meta)


def one_step_of(m):
    c = m["cfg"]
    meta = dict(n_cond=m["n_cond"], linear_cols=list(m.get("linear_cols") or []), noise_dim=c["noise_dim"], depth=c["depth"])
    return E.Member(_np(m["state"]), _np(m["norm"]), meta)


def best_ms(f, n):
    t = []
    for _ in range(2):
        t0 = time.perf_counter()
        f()
        t.append(time.perf_counter() - t0)
    return 1000.0 * min(t) * 1000.0 / n


def cost_lines(ck, cond, steps=(4, 8, 16), base=None, torch_model=None):
    m = ck.get("members", [ck])[0]
    if m["cfg"].get("arch", "mlp") != "flow":
        raise SystemExit(f"not a flow checkpoint (arch {m['cfg'].get('arch', 'mlp')})")
    extra = sorted(set(m.get("model_kw", {})) - COVERED) + (["interactions"] if m["cfg"].get("interactions") else []) \
        + (["product_pairs"] if m.get("product_pairs") else [])
    inner = inner_of(m)
    nm = _np(m["norm"])
    cn = ((cond - nm["cm"]) / nm["cs"]).astype(np.float32)
    rng = np.random.default_rng(0)
    L = []
    if torch_model is not None:
        x0 = rng.standard_normal((min(64, len(cn)), m["n_out"])).astype(np.float32)
        with torch.no_grad():
            want = torch_model.integrate(torch.as_tensor(cn[:len(x0)]), torch.as_tensor(x0), 0.0, 8).numpy()
        gap = float(np.abs(E.flow_sample(inner, cn[:len(x0)], 8, rng, x=x0.copy()) - want).max())
        L.append(f"numpy vs torch (8 steps, {len(x0)} rows): max |diff| {gap:.2e}" + ("  MISMATCH: timings not shippable" if gap > 1e-3 else " ok")
                 + (f"; uncovered options {extra}" if extra else ""))
    elif extra:
        L.append(f"uncovered options {extra}: the numpy member may not reproduce this network")
    base_ms = None
    if base is not None:
        b = one_step_of(base.get("members", [base])[0])
        bn = _np(base.get("members", [base])[0]["norm"])
        bc = ((cond - bn["cm"]) / bn["cs"]).astype(np.float32)
        e = rng.standard_normal((len(bc), b.noise_dim)).astype(np.float32)
        base_ms = best_ms(lambda: b.forward(bc, e), len(bc))
        L.append(f"base one-step MLP: 1 forward pass, {base_ms:.1f} ms / 1000 samples")
    x0 = rng.standard_normal((len(cn), m["n_out"])).astype(np.float32)
    ref = E.flow_sample(inner, cn, 32, rng, x=x0.copy())
    for s in steps:
        ms = best_ms(lambda: E.flow_sample(inner, cn, s, rng, x=x0.copy()), len(cn))
        rms = float(np.sqrt(np.mean((E.flow_sample(inner, cn, s, rng, x=x0.copy()) - ref) ** 2)))
        rel = f", {ms / base_ms:.1f} x base" if base_ms else ""
        L.append(f"flow {s:2d} Euler steps: {s} forward passes, {ms:.1f} ms / 1000 samples{rel}; RMS gap to 32 steps {rms:.4f} (normalised)")
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--base")
    ap.add_argument("--data")
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selfcheck()
    if not (a.model and a.data):
        ap.error("--model and --data are required")
    from tempest.generator.sample import Sampler
    from tempest.generator.train import load_npz
    d = load_npz(a.data)
    idx = np.flatnonzero(np.asarray(d["year"]) >= a.first_year)[:a.rows]
    if not len(idx):
        raise SystemExit(f"no rows from {a.first_year} in {a.data}")
    cond = np.asarray(d["cond"][idx], np.float32)
    ck = torch.load(a.model, map_location="cpu", weights_only=True)
    tm = Sampler(ck, "cpu").members[0][0]
    base = torch.load(a.base, map_location="cpu", weights_only=True) if a.base else None
    print(f"model {a.model}, {len(cond)} rows from {a.first_year}")
    for line in cost_lines(ck, cond, base=base, torch_model=tm):
        print(line)


def _selfcheck():
    from tempest.generator import s25_models as S
    from tempest.generator.model import Generator
    torch.manual_seed(0)
    F, n_out = 13, S.N_PROF + 3
    norm = dict(cm=torch.zeros(F), cs=torch.ones(F), tm=torch.zeros(n_out), ts=torch.ones(n_out))
    fl = S.FlowGenerator(F, n_out, 8, 32, 2, linear_cols=[8]).eval()
    ck = dict(state=fl.state_dict(), norm=norm, n_cond=F, n_out=n_out, linear_cols=[8], cfg=dict(arch="flow", noise_dim=8, depth=2),
              model_kw=dict(flow=dict(steps=8)))
    g = Generator(F, n_out, 8, 32, 2, linear_cols=[8]).eval()
    base = dict(state=g.state_dict(), norm=norm, n_cond=F, n_out=n_out, linear_cols=[8], cfg=dict(arch="mlp", noise_dim=8, depth=2))
    L = cost_lines(ck, np.random.default_rng(1).standard_normal((200, F)).astype(np.float32), base=base, torch_model=fl)
    print("\n".join(L))
    assert L[0].endswith(" ok"), L[0]
    gaps = [float(x.split("RMS gap to 32 steps ")[1].split()[0]) for x in L if x.startswith("flow")]
    assert len(gaps) == 3 and gaps[0] >= gaps[2], gaps            # more steps -> closer to the converged solve
    print("selfcheck ok")


if __name__ == "__main__":
    sys.exit(main())
