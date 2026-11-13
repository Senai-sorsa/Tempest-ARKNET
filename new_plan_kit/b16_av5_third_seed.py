"""New_Plan 13 AV5, confirmation of N2 (world-start fine-tune; MISS on the 'world as is within 1 %' clause, fine-tuned -0.8 to -2.7 %, 16 of 16
intervals below 0; control: the gain is the world start). No new model: a third training seed (2) of own / world / fine-tuned / own + 300,
both boxes (scripts/cpu_av5.sh, same recipe as cpu_n2_full.sh + cpu_n2_control.sh). Judged on the fine-tuned model alone, against own + 300.

Rule (set before any result; written 2026-11-13 09:25, from the AV5 row):
  per box and seed, wins = leads (1 / 3 / 5 / 7 d) where fine-tuned minus own + 300 has a paired day-block bootstrap interval below 0
  (mean CRPS, 'network + PIT recal + range map + Schaake shuffle', 1000 draws, same rows as b5_modeF_world.py).
  PASS: wins >= 3 in both boxes for all three seeds (0 and 1 re-scored from the existing models, 2 new).
  KILL: seed 2 fails (no interval below 0) at 2 or more leads in a box.
  Otherwise MISS. Dropping N2's 'world as is' clause stays the user's call; a PASS here is not adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b16_av5_third_seed.py
Result: docs/results/logs/kit_b16_av5_third_seed.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_world import LEADS, by_lead

SEEDS = (0, 1, 2)


def stems(tag, s):
    own = f"modeF_n2_base{tag}" + ("" if s == 0 else f"_s{s}")
    return {"own": own, "fine-tuned": f"modeF_n2ft{tag}_s{s}", "own+300": f"modeF_n2own300{tag}_s{s}"}


def judge(wins):
    """wins[(box, seed)] = leads with interval < 0 (fine-tuned minus own + 300) -> verdict."""
    if any(4 - wins[(b, 2)] >= 2 for b, s in wins if s == 2):
        return "KILL (third seed fails at 2 or more leads in a box)"
    return "PASS" if all(n >= 3 for n in wins.values()) else "MISS (record)"


def score(stems_fn, lines):
    """stems_fn(tag, seed) -> {'own', 'fine-tuned', 'own+300' (the control)} model stems; appends lines -> wins[(box, seed)]. Shared with b17 (AV28)."""
    M = os.path.join(K.REPO, "models")
    wins = {}
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in SEEDS:
            st = {k: os.path.join(M, v) for k, v in stems_fn(tag, s).items()}
            miss = [v for v in st.values() if not (os.path.exists(v + "_eval.csv") and os.path.exists(v + "_rows.npz"))]
            assert not miss, f"missing: {miss}"
            sc = {k: by_lead(v) for k, v in st.items()}
            rw = {k: np.load(v + "_rows.npz") for k, v in st.items()}
            assert all((rw[k]["day"] == rw["own"]["day"]).all() and (rw[k]["lead"] == rw["own"]["lead"]).all() for k in rw), f"{box} s{s}: arms on different rows"
            n, iv = 0, []
            for L in LEADS:
                k = rw["own"]["lead"] == L
                dm, lo, hi = K.block_boot(rw["fine-tuned"]["crps"][k] - rw["own+300"]["crps"][k], list(rw["own"]["day"][k]), draws=1000)
                n += hi < 0
                iv.append(f"{L}d {dm:+.3f} [{lo:+.3f}, {hi:+.3f}]")
            wins[(box, s)] = int(n)
            lines.append(f"  {box:<6} s{s}: own " + " / ".join(f"{v:.3f}" for v in sc["own"]) + "; fine-tuned change vs own "
                         + " / ".join(f"{100 * (v - 1):+.1f}" for v in sc["fine-tuned"] / sc["own"]) + " %; vs own+300 "
                         + " / ".join(f"{100 * (v - 1):+.1f}" for v in sc["fine-tuned"] / sc["own+300"]) + " %; minus own+300: " + ", ".join(iv) + f"; wins {n} of 4")
    return wins


def main():
    lines = [f"AV5: N2 fine-tuned (world start + 300 steps) vs own + 300, seeds {SEEDS}; mean CRPS by lead {LEADS}"]
    wins = score(stems, lines)
    lines.append("Verdict: " + judge(wins))
    K.report("b16_av5_third_seed", lines)


def _selfcheck():
    k = lambda a, b: {(x, s): (b if (s == 2 and x == "B") else a) for x in ("A", "B") for s in SEEDS}
    assert judge(k(3, 4)) == "PASS"
    assert judge(k(3, 2)).startswith("KILL")
    assert judge({**k(3, 3), ("A", 0): 2}).startswith("MISS")      # an older seed short, the third seed fine
    assert stems("", 0)["own"] == "modeF_n2_base" and stems("_den", 1)["own"] == "modeF_n2_base_den_s1"


_selfcheck()
if __name__ == "__main__":
    main()
