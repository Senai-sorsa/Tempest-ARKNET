"""New_Plan 13.1 AV1 (variation of N6, KILLED): lead split. The N6 big fine-tuned Mode F (models/modeF_n6ft{,_den}_s{0,1}) serves leads 1 and 3 d,
the shipped-recipe small own-box model (models/modeF_n2_base{,_den}{,_s1}) serves 5 and 7 d. No training. Split point fixed in the plan: between 3 and 5 d.
Runs: scripts/cpu_av1.sh scores both arms on 2021 (il6_modeF.py --test-year 2021: range map fit on 2022; 2021 is outside every network's fit and step choice).
Metric as N6: mean CRPS over the 16 variable x band cells by lead, 'network + PIT recal + range map + Schaake shuffle'; intervals = paired day-block
bootstrap on the per-row scores (same rows in both arms).

Rule (set before any 2021 result; written 2026-11-12 13:45, from the plan row):
  Step A, confirm on 2021: per box, the big / small mean-CRPS ratio per lead averaged over the two seeds must be < 1 at 1 and 3 d and >= 1 at 5 and 7 d,
          in both boxes. Otherwise KILL ("the validation year picks a different split").
  Step B, on 2022 (the parent's existing test tables): PASS = at 1 and 3 d big at least 1 % better than small with the interval excluding 0, every box x seed,
          and |cov99 difference| <= 0.003 at 1 and 3 d. Leads 5 and 7 d are the small model, so identical to shipped by construction.
          If step A passes and step B does not: MISS (record; standing note of section 13: a benefit with an interval excluding 0 gets one more AV row).
  Known before the run (parent's 2022 table): Denver seed 0 at 3 d is -1.4 % with interval [-0.069, +0.006], so step B cannot pass as written; step A
  still decides between KILL and MISS, and what a further variation may use.
  NM/TX 2022 had big better at 5 d (-1.9 %, interval < 0); the plan fixed the split at 3 / 5 d, so step A's ">= 1 at 5 d" is kept as written.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b8_av1_lead_split.py
Result: docs/results/logs/kit_b8_av1_lead_split.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b5_modeF_world import LEADS, METHOD, by_lead

M = os.path.join(K.REPO, "models")
ARMS = [(box, s, os.path.join(M, f"modeF_n2_base{tag}{'' if s == 0 else '_s1'}"), os.path.join(M, f"modeF_n6ft{tag}_s{s}"))
        for box, tag in (("NM/TX", ""), ("Denver", "_den")) for s in (0, 1)]


def cov99(stem):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == METHOD].groupby("lead").cov99.mean().reindex(LEADS)


def step_a(ratio):
    """ratio[(box, seed)] = per-lead big / small (LEADS order) -> (ok, per-box mean ratios)."""
    boxes = sorted({b for b, _ in ratio})
    mean = {b: np.mean([ratio[(b, s)] for s in (0, 1)], axis=0) for b in boxes}
    ok = all(m[0] < 1 and m[1] < 1 and m[2] >= 1 and m[3] >= 1 for m in mean.values())
    return ok, mean


def step_b(ratio, sig, dcov):
    """Per (box, seed): leads 1 and 3 d (indices 0, 1) at least 1 % better, interval < 0, |cov99 diff| <= 0.003."""
    return all((np.asarray(ratio[k])[:2] <= 0.99).all() and all(sig[k][:2]) and (np.asarray(dcov[k])[:2] <= 0.003).all() for k in ratio)


def verdict(a_ok, b_ok):
    return "KILL (2021 picks a different split)" if not a_ok else "PASS" if b_ok else "MISS (split confirmed on 2021; 2022 clause not met)"


def score(sfx, lines):
    ratio, sig, dcov, missing = {}, {}, {}, []
    for box, s, own0, big0 in ARMS:
        own, big = own0 + sfx, big0 + sfx
        if not all(os.path.exists(v + e) for v in (own, big) for e in ("_eval.csv", "_rows.npz")):
            missing.append(f"{box} s{s}")
            continue
        so, sb, ro, rb = by_lead(own), by_lead(big), np.load(own + "_rows.npz"), np.load(big + "_rows.npz")
        assert (ro["day"] == rb["day"]).all() and (ro["lead"] == rb["lead"]).all(), f"{box} s{s}{sfx}: arms scored on different rows"
        iv, sg = [], []
        for L in LEADS:
            k = ro["lead"] == L
            dm, lo, hi = K.block_boot(rb["crps"][k] - ro["crps"][k], list(ro["day"][k]), draws=1000)
            sg.append(hi < 0)
            iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
        dc = cov99(big) - cov99(own)
        ratio[(box, s)], sig[(box, s)], dcov[(box, s)] = (sb / so).values, sg, dc.abs().values
        lines.append(f"  {box:<6} seed {s}: small " + " / ".join(f"{v:.3f}" for v in so) + "; big " + " / ".join(f"{v:.3f}" for v in sb)
                     + "  change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in sb / so) + " %; big minus small: " + ", ".join(iv)
                     + "; cov99 difference " + " / ".join(f"{v:+.4f}" for v in dc))
    return ratio, sig, dcov, missing


def main():
    lines = [f"AV1 lead split (N6 big at 1-3 d, small at 5-7 d); mean CRPS by lead {LEADS}, {METHOD}", "Step A, 2021 (range map on 2022):"]
    r21, _, _, miss21 = score("_t2021", lines)
    lines.append("Step B, 2022 (parent's tables):")
    r22, s22, d22, miss22 = score("", lines)
    if miss21 or miss22:
        lines.append("Incomplete, missing: 2021 " + ", ".join(miss21) + "; 2022 " + ", ".join(miss22))
        K.report("b8_av1_lead_split", lines)
        return
    a_ok, mean = step_a(r21)
    lines.append("Step A per-box mean ratio over seeds (2021): " + "; ".join(f"{b} " + " / ".join(f"{v:.3f}" for v in m) for b, m in mean.items())
                 + f" -> split {'confirmed' if a_ok else 'NOT confirmed'}")
    b_ok = step_b(r22, s22, d22)
    lines.append(f"Step B (2022, 1 and 3 d >= 1 % better with interval < 0, cov99 within 0.003, every box x seed): {'met' if b_ok else 'not met'}")
    lines.append("Verdict: " + verdict(a_ok, b_ok))
    K.report("b8_av1_lead_split", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    good = {k: np.array([0.95, 0.97, 1.01, 1.03]) for k in keys}
    assert step_a(good)[0]
    assert not step_a({k: np.array([0.95, 0.97, 0.98, 1.03]) for k in keys})[0]          # big also better at 5 d: different split
    assert not step_a({**good, ("B", 0): np.array([0.95, 1.05, 1.01, 1.03]), ("B", 1): np.array([0.95, 1.01, 1.01, 1.03])})[0]
    yes, cov = {k: [True] * 4 for k in keys}, {k: [0.001] * 4 for k in keys}
    assert step_b(good, yes, cov)
    assert not step_b(good, {**yes, ("B", 0): [True, False, True, True]}, cov)
    assert not step_b({**good, ("A", 1): np.array([0.995, 0.97, 1, 1])}, yes, cov)
    assert not step_b(good, yes, {**cov, ("A", 0): [0.004, 0.001, 0, 0]})
    assert verdict(False, True).startswith("KILL") and verdict(True, True) == "PASS" and verdict(True, False).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
