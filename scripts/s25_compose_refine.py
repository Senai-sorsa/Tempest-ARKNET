"""New_Plan 25 H5: compose draft + refine. The paired base (one-step Engression, the shipped kind) is the frozen draft; a flow trained with
tau_min = 1 - t0 (configs/s25/h5_t02.toml / h5_t04.toml, 3 Euler steps) refines it. Member k of the base pairs with member k of the flow
(the counts must match: both come from the same base config). Refuses different normalisations / inputs / outputs and never overwrites.

    python scripts/s25_compose_refine.py --draft models/s25/base_s0.pt --flow models/s25/h5_t02f_s0.pt --out models/s25/h5_t02_s0.pt
    python scripts/s25_compose_refine.py --selfcheck
"""
import argparse
import os
import sys

import torch

DRAFT_KW = ("interactions",)            # base cfg flags the Generator reads (passed via the draft kw)


def _members(ck):
    return ck["members"] if "members" in ck else [ck]


def compose_member(d, f):
    if f["cfg"].get("arch") != "flow" or "tau_min" not in (f.get("model_kw", {}).get("flow") or {}):
        raise SystemExit("refine checkpoint must be arch flow with a tau_min (configs/s25/h5_*.toml)")
    if d["cfg"].get("arch", "mlp") != "mlp":
        raise SystemExit(f"draft must be the one-step mlp (got {d['cfg'].get('arch')})")
    for k in ("n_cond", "n_out"):
        if d[k] != f[k]:
            raise SystemExit(f"{k} differs: draft {d[k]} vs flow {f[k]}")
    if list(d.get("linear_cols") or []) != list(f.get("linear_cols") or []):
        raise SystemExit("linear_cols differ")
    if f.get("product_pairs"):
        raise SystemExit("flow with product_pairs is not supported by the compose")
    for k in ("cm", "cs", "tm", "ts"):
        if not torch.equal(torch.as_tensor(d["norm"][k]), torch.as_tensor(f["norm"][k])):
            raise SystemExit(f"normalisation {k} differs (draft and flow must be trained on the same data)")
    dc = d["cfg"]
    dkw = {**{k: True for k in DRAFT_KW if dc.get(k)}, **({"product_pairs": d["product_pairs"]} if d.get("product_pairs") else {}),
           **d.get("model_kw", {})}
    fkw = dict(f["model_kw"])
    mkw = {**{k: v for k, v in fkw.items() if k != "flow"},
           "refine": dict(draft=dict(noise_dim=dc["noise_dim"], width=dc["width"], depth=dc["depth"], kw=dkw), flow=fkw["flow"])}
    state = {**{"draft." + k: v for k, v in d["state"].items()}, **{"flow." + k: v for k, v in f["state"].items()}}
    return {**f, "state": state, "cfg": {**f["cfg"], "arch": "refine", "interactions": False}, "model_kw": mkw,
            "composed_from": dict(draft_seed=dc.get("seed"), flow_seed=f["cfg"].get("seed"))}


def compose(draft_ck, flow_ck):
    D, F = _members(draft_ck), _members(flow_ck)
    if len(D) != len(F):
        raise SystemExit(f"member counts differ: draft {len(D)} vs flow {len(F)}")
    out = [compose_member(d, f) for d, f in zip(D, F)]
    return out[0] if len(out) == 1 else dict(members=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draft")
    ap.add_argument("--flow")
    ap.add_argument("--out")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selfcheck()
    if not (a.draft and a.flow and a.out):
        ap.error("--draft, --flow and --out are required")
    if os.path.exists(a.out):
        raise SystemExit(f"{a.out} exists; refusing to overwrite")
    ck = compose(torch.load(a.draft, map_location="cpu", weights_only=True), torch.load(a.flow, map_location="cpu", weights_only=True))
    from tempest.generator.sample import Sampler
    Sampler(ck, "cpu")                                                          # must load before it is written
    torch.save(ck, a.out + ".part")
    os.replace(a.out + ".part", a.out)
    print(f"wrote {a.out} ({len(_members(ck))} member(s))")


def _selfcheck():
    from tempest.generator import s25_models as S
    from tempest.generator.model import Generator
    from tempest.generator.sample import Sampler
    torch.manual_seed(0)
    F, n_out = 13, S.N_PROF + 3
    norm = dict(cm=torch.zeros(F), cs=torch.ones(F), tm=torch.zeros(n_out), ts=torch.ones(n_out))
    g = Generator(F, n_out, 8, 32, 2, linear_cols=[8]).eval()
    fl = S.FlowGenerator(F, n_out, 4, 16, 2, flow=dict(tau_min=0.8, steps=3), linear_cols=[8]).eval()
    base = dict(state=g.state_dict(), norm=norm, n_cond=F, n_out=n_out, linear_cols=[8], cfg=dict(arch="mlp", noise_dim=8, width=32, depth=2))
    fk = dict(state=fl.state_dict(), norm=norm, n_cond=F, n_out=n_out, linear_cols=[8], cfg=dict(arch="flow", noise_dim=4, width=16, depth=2),
              model_kw=dict(flow=dict(tau_min=0.8, steps=3)))
    ck = compose(dict(members=[base, base]), dict(members=[fk, fk]))
    m, _ = Sampler(ck, "cpu").members[0]
    assert type(m).__name__ == "RefineGenerator"
    c = torch.randn(5, F)
    with torch.no_grad():
        torch.manual_seed(1)
        y = m(c, 3)
        torch.manual_seed(1)
        d = g(c, 3).reshape(15, -1)                                             # the same draft, then the refiner by hand
        x = 0.2 * torch.randn_like(d) + 0.8 * d
        want = fl.integrate(c.repeat_interleave(3, 0), x, 0.8).view(5, 3, -1)
    assert y.shape == (5, 3, n_out) and torch.allclose(y, want, atol=1e-5), float((y - want).abs().max())
    bad = dict(fk, norm={**norm, "cm": torch.ones(F)})
    try:
        compose(base, bad)
        raise AssertionError("different normalisation was accepted")
    except SystemExit:
        pass
    print("selfcheck ok")


if __name__ == "__main__":
    sys.exit(main())
