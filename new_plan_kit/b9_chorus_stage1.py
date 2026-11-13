"""New_Plan 14.4 CHORUS stage 1 (no training): feed the shipped-recipe own-box mode F (models/modeF_n2_base{,_den}{,_s1}) the closed-rule mix of the
newest run and the 36 h older run (scripts/chorus_stage1_rows.py; weights from 2018-20 error moments) in place of the newest run alone, 2022, same rows.
Runs: scripts/cpu_chorus1.sh (models/chorus_{new,mix}{,_den}{,_s1}). Metric as N2 / N6 / AV1: mean CRPS over the 16 variable x band cells by lead,
'network + PIT recal + range map + Schaake shuffle'; intervals = paired block bootstrap on the per-row scores with 21-day blocks of the valid day
(AU-4 default, diag.BLOCK_DAYS).

Rule (set before any result; written 2026-11-13 02:08, from the plan's stage 1 text, applied to every box x seed):
  PASS: mix minus newest < 0 with the whole interval below 0 at 5 and 7 d, AND mix / newest <= 1.005 at 1 and 3 d, in all 4 box x seed runs.
  KILL: no lead has a lower mix point estimate in any run ("no lead better").
  Otherwise MISS (record; section 13's standing note: a benefit with an interval excluding 0 gets one more variation row).
  Deviation from the plan text, stated before the run: the archive has no 12 h older run (12Z starts sit 36 h before each 00Z start), so the older
  run is 36 h older; the plan asked for rows rebuilt at fixed points to get pairs, here every test row gets its pair directly (same point, same valid time).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_chorus_stage1.py
Result: docs/results/logs/kit_b9_chorus_stage1.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b5_modeF_world import LEADS, METHOD, by_lead

M = os.path.join(K.REPO, "models")
RUNS = [(box, s, os.path.join(M, f"chorus_new{tag}{'' if s == 0 else '_s1'}"), os.path.join(M, f"chorus_mix{tag}{'' if s == 0 else '_s1'}"))
        for box, tag in (("NM/TX", ""), ("Denver", "_den")) for s in (0, 1)]
BLOCK = 21


def cov99(stem):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == METHOD].groupby("lead").cov99.mean().reindex(LEADS)


def judge(ratio, below):
    """ratio[run] = mix / newest per lead (LEADS order); below[run] = whole interval < 0 per lead -> verdict."""
    ok = all(below[k][2] and below[k][3] and ratio[k][0] <= 1.005 and ratio[k][1] <= 1.005 for k in ratio)
    kill = all((np.asarray(r) >= 1).all() for r in ratio.values())
    return "PASS" if ok else "KILL (no lead better)" if kill else "MISS (record, no adoption)"


def main():
    lines = [f"CHORUS stage 1: newest run vs closed-rule mix (newest + 36 h older), 2022; mean CRPS by lead {LEADS}, {METHOD}; {BLOCK}-day blocks"]
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
        lines.append(f"  {box:<6} seed {s}: newest " + " / ".join(f"{v:.4f}" for v in sn) + "; mix " + " / ".join(f"{v:.4f}" for v in sm)
                     + "  change " + " / ".join(f"{100 * (v - 1):+.2f}" for v in sm / sn) + " %; mix minus newest: " + ", ".join(iv)
                     + "; cov99 mix minus newest " + " / ".join(f"{v:+.4f}" for v in dc))
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
    else:
        lines.append("Verdict: " + judge(ratio, below))
    K.report("b9_chorus_stage1", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    r, y = {k: np.array([1.004, 0.99, 0.97, 0.95]) for k in keys}, {k: [False, False, True, True] for k in keys}
    assert judge(r, y) == "PASS"
    assert judge({**r, ("B", 1): np.array([1.006, 0.99, 0.97, 0.95])}, y).startswith("MISS")      # 1 d worse by more than 0.5 %
    assert judge(r, {**y, ("A", 0): [False, False, False, True]}).startswith("MISS")              # 5 d interval not below 0
    assert judge({k: np.array([1.0, 1.01, 1.02, 1.0]) for k in keys}, {k: [False] * 4 for k in keys}).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
