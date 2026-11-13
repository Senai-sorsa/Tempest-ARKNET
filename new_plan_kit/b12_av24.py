"""New_Plan 13 AV24 (variation of CHORUS stage 1, b9_chorus_stage1.py): the stage 1 closed-rule mix of the newest and the 36 h older run (same 2018-20
weights) in EVERY year's rows; mode F retrained on mixed inputs with the shipped small recipe (same flags and seeds as models/modeF_n2_base*), PIT recal
and range map on mixed 2021, scored on mixed 2022 (the stage 1 test rows). Runs: scripts/cpu_av24.sh (models/av24_mix{,_den}{,_s1}); compared with the
stage 1 newest-run scores on the same rows (models/chorus_new{,_den}{,_s1}). Metric and intervals as stage 1 (21-day blocks).

Rule (set before any result; written 2026-11-13 06:35; stage 1's rule unchanged, as the AV24 row says):
  PASS: mix minus newest < 0 with the whole interval below 0 at 5 and 7 d, AND mix / newest <= 1.005 at 1 and 3 d, in all 4 box x seed runs.
  KILL: no lead has a lower mix point estimate in any run. Otherwise MISS (record).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b12_av24.py
Result: docs/results/logs/kit_b12_av24.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_world import LEADS, METHOD, by_lead
from b9_chorus_stage1 import BLOCK, cov99, judge

M = os.path.join(K.REPO, "models")
RUNS = [(box, s, os.path.join(M, f"chorus_new{tag}{'' if s == 0 else '_s1'}"), os.path.join(M, f"av24_mix{tag}{'' if s == 0 else '_s1'}"))
        for box, tag in (("NM/TX", ""), ("Denver", "_den")) for s in (0, 1)]


def main():
    lines = [f"AV24: newest-run models vs models retrained on the mix in every year, 2022; mean CRPS by lead {LEADS}, {METHOD}; {BLOCK}-day blocks"]
    ratio, below, missing = {}, {}, []
    for box, s, new, mix in RUNS:
        if not all(os.path.exists(v + e) for v in (new, mix) for e in ("_eval.csv", "_rows.npz")):
            missing.append(f"{box} s{s}")
            continue
        sn, sm, rn, rm = by_lead(new), by_lead(mix), np.load(new + "_rows.npz"), np.load(mix + "_rows.npz")
        assert (rn["day"] == rm["day"]).all() and (rn["lead"] == rm["lead"]).all(), f"{box} s{s}: arms scored on different rows"
        iv, bl = [], []
        for L in LEADS:
            k = rn["lead"] == L
            dm, lo, hi = K.block_boot(rm["crps"][k] - rn["crps"][k], list(rn["day"][k] // BLOCK), draws=2000)
            bl.append(hi < 0)
            iv.append(f"{L}d {dm:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        dc = cov99(mix) - cov99(new)
        ratio[(box, s)], below[(box, s)] = (sm / sn).values, bl
        lines.append(f"  {box:<6} seed {s}: newest " + " / ".join(f"{v:.4f}" for v in sn) + "; mix retrained " + " / ".join(f"{v:.4f}" for v in sm)
                     + "  change " + " / ".join(f"{100 * (v - 1):+.2f}" for v in sm / sn) + " %; mix minus newest: " + ", ".join(iv)
                     + "; cov99 mix minus newest " + " / ".join(f"{v:+.4f}" for v in dc))
    lines.append("Incomplete, missing: " + ", ".join(missing) if missing else "Verdict: " + judge(ratio, below))
    K.report("b12_av24", lines)


if __name__ == "__main__":
    main()
