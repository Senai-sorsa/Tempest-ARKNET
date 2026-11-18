"""New_Plan 25 H3: gate weights of the mixture-of-experts generator by month, and the collapse check the H3 rule reads.

    python scripts/s25_gate_month.py models/s25/h3_moe_s0.pt data/train/pilot80_l21_day_dpd.npz --out models/s25/h3_moe_s0_gate.csv
    python scripts/s25_gate_month.py --selfcheck

Rows: verdict years 2024-25 (--rows, spread evenly), m samples per row, every member. Writes month, w0..w{E-1} (mean gate weight),
top_share (share of row x sample draws whose largest weight > 0.9) and collapse; the extra row month == "all" carries the item flag:
collapse = one expert holds > 90 % weight on > 90 % of draws (New_Plan H3 kill condition).
"""
import argparse
import sys

import numpy as np
import pandas as pd
import torch

COLLAPSE_W, COLLAPSE_SHARE = 0.9, 0.9


def gate_table(models_norms, cond, months, m=4):
    """models_norms: [(MoEGenerator, norm dict of tensors)]; cond (N, F) raw; months (N,) ints -> DataFrame (per month + "all")."""
    probs = []
    with torch.inference_mode():
        for mdl, n in models_norms:
            c = (torch.as_tensor(cond, dtype=torch.float32) - n["cm"]) / n["cs"]
            mdl(c, m)
            probs.append(mdl.head[1].last_gate.float().cpu().numpy())         # (N, m, E)
    p = np.concatenate(probs, 1)                                                # (N, members*m, E)
    E = p.shape[-1]
    rows = []
    for mo, sel in [(int(k), months == k) for k in np.unique(months)] + [("all", np.ones(len(months), bool))]:
        q = p[sel].reshape(-1, E)
        top = float((q.max(1) > COLLAPSE_W).mean())
        dom = float(np.bincount(q.argmax(1), minlength=E).max() / len(q))      # the same expert must hold it, not a different one per draw
        rows.append(dict(month=mo, **{f"w{e}": float(q[:, e].mean()) for e in range(E)}, top_share=top,
                         collapse=bool(top > COLLAPSE_SHARE and dom > COLLAPSE_SHARE)))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", nargs="?")
    ap.add_argument("data", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--rows", type=int, default=6000)
    ap.add_argument("--m", type=int, default=4)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selfcheck()
    if not (a.model and a.data and a.out):
        ap.error("model, data and --out are required")
    from tempest.generator.sample import Sampler
    from tempest.generator.train import load_npz
    from tempest.scoring.ridge_drivers import row_months
    torch.set_num_threads(4)
    d = load_npz(a.data)
    yr = np.asarray(d["year"])
    idx = np.flatnonzero((yr >= 2024) & (yr <= 2025))
    if not len(idx):
        raise SystemExit("no 2024-25 rows")
    idx = idx[np.linspace(0, len(idx) - 1, min(a.rows, len(idx))).astype(int)]
    cond = np.asarray(d["cond"][idx], np.float32)
    months = row_months(cond, yr[idx]).month.to_numpy()
    s = Sampler(a.model, "cpu")
    if not all(hasattr(mm.head[1], "last_gate") for mm, _ in s.members):
        raise SystemExit(f"{a.model} is not a moe generator")
    t = gate_table(s.members, cond, months, a.m)
    t.to_csv(a.out, index=False)
    print(t.round(3).to_string(index=False))
    print(f"wrote {a.out}")


def _selfcheck():
    from tempest.generator import s25_models as S
    torch.manual_seed(0)
    F, n_out = 13, S.N_PROF + 3
    norm = dict(cm=torch.zeros(F), cs=torch.ones(F), tm=torch.zeros(n_out), ts=torch.ones(n_out))
    g = S.MoEGenerator(F, n_out, 4, 16, 2, moe=dict(doy_cols=[4, 5])).eval()
    months = np.repeat(np.arange(1, 13), 5)
    t = gate_table([(g, norm)], np.random.default_rng(0).standard_normal((60, F)).astype(np.float32), months, 3)
    assert list(t.month) == list(range(1, 13)) + ["all"] and np.allclose(t[["w0", "w1", "w2"]].sum(1), 1, atol=1e-5)
    with torch.no_grad():                                                       # force expert 0: the check must flag a collapse
        g.head[1].gate[2].bias[:] = torch.tensor([50.0, 0.0, 0.0])
    assert bool(gate_table([(g, norm)], np.zeros((24, F), np.float32), np.repeat([1, 2], 12)).collapse.iloc[-1])
    print("selfcheck ok")


if __name__ == "__main__":
    sys.exit(main())
