"""New_Plan 10.4 N6: full-size Mode F on the GPU (width 512, depth 4, 4 members, all 44 heights, no lat / lon): world fit + 300 steps on the
box rows, scored on each box's own 2022 test rows. Runs: scripts/gpu_n6_step0.sh, scripts/gpu_n6_full.sh (seeds 0 and 1):
    small own model   models/modeF_n2_base{,_den}{,_s1}   (ENSF2 HRES-only recipe, as shipped; from N2)
    big fine-tuned    models/modeF_n6ft{,_den}_s{0,1}
Step 0 (passed 2026-11-11 23:06, seed 0): validation CRPS 0.4986 at step 250 -> 0.4787 at step 2750 (data/n6_world_s0.log).
Metric: mean CRPS over the 16 variable x band cells by lead 1/3/5/7 d, 'network + PIT recal + range map + Schaake shuffle' (<stem>_eval.csv);
intervals: paired day-block bootstrap (valid days) on the per-row scores (<stem>_rows.npz, same test rows in both arms).
PASS (pre-set in the plan, written here before any fine-tune result): big at least 1 % better than the small model at every lead with an interval
      excluding 0, both boxes, both seeds, and mean cov99 within 0.003 of the small model at every lead.
KILL: not better (mean) at 2 or more leads in any box x seed. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_modeF_big.py
Result: docs/results/logs/kit_b5_modeF_big.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from b5_modeF_world import LEADS, METHOD, by_lead


def cov99(stem):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == METHOD].groupby("lead").cov99.mean().reindex(LEADS)


def judge(ratio, sig, dcov):
    """Per (box, seed): ratio = per-lead big / small, sig = per-lead bool (interval < 0), dcov = per-lead |cov99 difference| -> verdict."""
    if any((np.asarray(r) >= 1).sum() >= 2 for r in ratio.values()):
        return "KILL"
    ok = all((np.asarray(ratio[k]) <= 0.99).all() and all(sig[k]) and (np.asarray(dcov[k]) <= 0.003).all() for k in ratio)
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines = [f"N6 full-size Mode F (world fit + 300 box steps) vs the small own model; mean CRPS by lead {LEADS}, {METHOD}"]
    ratio, sig, dcov, missing = {}, {}, {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            own, big = os.path.join(M, f"modeF_n2_base{tag}{'' if s == 0 else '_s1'}"), os.path.join(M, f"modeF_n6ft{tag}_s{s}")
            if not all(os.path.exists(v + e) for v in (own, big) for e in ("_eval.csv", "_rows.npz")):
                missing.append(f"{box} s{s}")
                continue
            so, sb, ro, rb = by_lead(own), by_lead(big), np.load(own + "_rows.npz"), np.load(big + "_rows.npz")
            assert (ro["day"] == rb["day"]).all() and (ro["lead"] == rb["lead"]).all(), f"{box} s{s}: arms scored on different rows"
            iv, sg = [], []
            for L in LEADS:
                k = ro["lead"] == L
                dm, lo, hi = K.block_boot(rb["crps"][k] - ro["crps"][k], list(ro["day"][k]), draws=1000)
                sg.append(hi < 0)
                iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
            ratio[(box, s)], sig[(box, s)], dcov[(box, s)] = (sb / so).values, sg, (cov99(big) - cov99(own)).abs().values
            lines.append(f"  {box:<6} seed {s}: small " + " / ".join(f"{v:.3f}" for v in so) + "; big " + " / ".join(f"{v:.3f}" for v in sb)
                         + "  change " + " / ".join(f"{100 * (v - 1):+.1f}" for v in sb / so) + " %; big minus small: " + ", ".join(iv)
                         + "; cov99 difference " + " / ".join(f"{v:+.4f}" for v in (cov99(big) - cov99(own))))
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
        K.report("b5_modeF_big", lines)
        return
    lines.append("Rule (pre-set): PASS = big >= 1 % better at every lead with interval < 0, both boxes and seeds, cov99 within 0.003; KILL = not better at 2 or more leads.")
    lines.append("Verdict: " + judge(ratio, sig, dcov))
    K.report("b5_modeF_big", lines)


def _selfcheck():
    keys = [(b, s) for b in ("A", "B") for s in (0, 1)]
    yes, cov = {k: [True] * 4 for k in keys}, {k: [0.001] * 4 for k in keys}
    assert judge({k: [0.98] * 4 for k in keys}, yes, cov) == "PASS"
    assert judge({k: [0.995] * 4 for k in keys}, yes, cov).startswith("MISS")
    assert judge({k: [0.98] * 4 for k in keys}, {k: [True, True, True, False] for k in keys}, cov).startswith("MISS")
    assert judge({k: [0.98] * 4 for k in keys}, yes, {k: [0.004] * 4 for k in keys}).startswith("MISS")
    assert judge({k: ([0.98, 0.98, 1.0, 1.01] if k == keys[0] else [0.98] * 4) for k in keys}, yes, cov) == "KILL"


_selfcheck()
if __name__ == "__main__":
    main()
