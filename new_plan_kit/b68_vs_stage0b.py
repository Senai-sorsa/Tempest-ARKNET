"""New_Plan 12.3 VS stage 0b: member against balloon variance per vertical scale. Scales from nested coarse views of the 44 heights: views with 7, 13, 25 and 44 heights (evenly spaced indices, linear in height between).
Scale increment s1 = view13 - view7, s2 = view25 - view13, s3 = view44 - view25 (the finest). For every case the variance over heights of each increment (u, v, T) is taken per profile; per source
ratio = mean member variance / mean balloon variance (members = the shipped stack, EPZ and MAF 00Z / 12Z balloons, the b65 case set; plan text says El Paso and Midland 2021-22, here the b9 cases 2024-25 as in b65 / E5; never 2026).
Rule (set 2026-11-16 before running; New_Plan 12.3 stage 0b): the hand-over scale is the finest scale where the member holds >= 80 % of the balloon variance (u, v and T each). KILL (close VS) = the member holds >= 80 % at the finest scale s3 in u, v and T.
Otherwise PROCEED (stage 2 is worth building); report the hand-over scale. Report every ratio.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b68_vs_stage0b.py [--per-group 100] [--m 50]
Result: docs/results/logs/kit_b68_vs_stage0b.log
"""
import argparse

import numpy as np

import b9_gram_compare as B9
import kit_common as K

NAME = "b68_vs_stage0b"
VARS = ("u", "v", "T")


def view(n):
    ci = np.unique(np.round(np.linspace(0, K.NH - 1, n)).astype(int))
    W = np.stack([np.interp(K.H, K.H[ci], np.eye(len(ci))[i]) for i in range(len(ci))], 1)
    return lambda x: x[..., ci] @ W.T


V = [view(n) for n in (7, 13, 25, 44)]


def incs(x):
    """x (..., 44) -> variances over heights of the three increments (..., 3)."""
    return np.stack([((V[i + 1](x) - V[i](x)) ** 2).mean(-1) for i in range(3)], -1)


def judge(ratio):
    """ratio (3 scales, 3 vars) member / balloon variance -> (verdict, hand-over scale index or None)."""
    ok = (ratio >= 0.80).all(1)
    hand = max([i for i in range(3) if ok[i]], default=None)
    return ("KILL (members hold >= 80 % at the finest scale)" if ok[2] else "PROCEED"), hand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=100)
    ap.add_argument("--m", type=int, default=50)
    a = ap.parse_args()
    K.ram_gate(3.0)
    rng = np.random.default_rng(0)
    bal = {q: [] for q in VARS}
    mem = {q: [] for q in VARS}
    n = 0
    for cid, sid, t, b in B9.cases(a.per_group, rng):
        lat, lon, elev = K.station_pos(sid)
        try:
            ship = K.tool(lat, lon, t, seed=1000 * t.year + int(t.dayofyear), n=a.m, elevation=elev)
        except ValueError:
            continue
        if not all(np.isfinite(b[q]).all() for q in VARS):
            continue
        for q in VARS:
            bal[q].append(incs(np.asarray(b[q], float)))
            mem[q].append(incs(np.asarray(ship[q], float)).mean(0))
        n += 1
    ratio = np.array([[np.mean([m[s] for m in mem[q]]) / np.mean([x[s] for x in bal[q]]) for q in VARS] for s in range(3)])
    lines = [f"VS stage 0b: {n} cases (EPZ / MAF 00Z 12Z 2024-25), {a.m} members; variance of each scale increment, member / balloon (u, v, T)"]
    for s, name in enumerate(("s1 7->13 heights", "s2 13->25", "s3 25->44 (finest)")):
        lines.append(f"  {name:20s} " + "  ".join(f"{q} {ratio[s, i]:.2f}" for i, q in enumerate(VARS)))
    v, hand = judge(ratio)
    lines.append("Rule (pre-set): hand-over = finest scale with member >= 80 % of balloon variance in u, v and T; KILL (close VS) if that holds at the finest scale; else PROCEED.")
    lines.append("Verdict: " + v + (f"; hand-over scale s{hand + 1}" if hand is not None else "; no scale holds 80 % in all three"))
    K.report(NAME, lines)


def _selfcheck():
    x = np.tile(K.H / 100.0, (2, 1))
    assert np.allclose(incs(x), 0, atol=1e-9)
    assert judge(np.full((3, 3), 0.9))[0].startswith("KILL") and judge(np.array([[1.] * 3, [0.9] * 3, [0.5] * 3]))[0] == "PROCEED"


_selfcheck()
if __name__ == "__main__":
    main()
