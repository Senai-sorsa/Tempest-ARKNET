"""New_Plan 13 AV29, variation of AV28 (b17_av28_ft500.py; MISS 2026-11-13 13:30: wins 4 / 4 / 3 NM/TX, 3 / 3 / 1 Denver; all 24 point estimates
favour the world start; Denver seed 2 intervals end at +0.001 to +0.002). Same 12 networks, no training: also scored on 2021
(scripts/cpu_av29.sh, il6_modeF.py --test-year 2021: range map on 2022), per-row scores of 2021 and 2022 pooled per lead (as AV26, b13).

Rule (set before any result; written 2026-11-13 14:40; AV28's rule unchanged, on the pooled rows):
  wins[(box, seed)] = leads (1 / 3 / 5 / 7 d) where fine-tuned-500 minus own + 500 (pooled 2021 + 2022 rows) has a block bootstrap interval
  below 0 (1000 draws; blocks = 21-day blocks of the valid day spanning both years, as AV26; the AV29 row says 'day blocks over both years (as AV26)').
  PASS: wins >= 3 in both boxes for all three seeds. KILL: wins <= 1 in 3 or more of the 6 runs. Otherwise MISS.
  Forking-paths note: third variation of N2 (AV5, AV28, AV29); a PASS is not adoption (needs the user's go).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b19_av29_pooled.py
Result: docs/results/logs/kit_b19_av29_pooled.log
"""
import os

import numpy as np

import kit_common as K
from b5_modeF_world import LEADS
from b9_chorus_stage1 import BLOCK
from b16_av5_third_seed import SEEDS
from b17_av28_ft500 import judge

M = os.path.join(K.REPO, "models")


def pooled(stem):
    r = [np.load(os.path.join(M, stem + x + "_rows.npz")) for x in ("", "_t2021")]
    return {k: np.concatenate([v[k] for v in r]) for k in ("lead", "day", "crps")}


def wins_of(ft, own, draws=1000):
    """pooled rows of both arms -> (wins, text)."""
    assert (ft["day"] == own["day"]).all() and (ft["lead"] == own["lead"]).all(), "arms scored on different rows"
    n, iv = 0, []
    for L in LEADS:
        k = own["lead"] == L
        dm, lo, hi = K.block_boot(ft["crps"][k] - own["crps"][k], list(own["day"][k] // BLOCK), draws=draws)
        n += hi < 0
        iv.append(f"{L}d {100 * (ft['crps'][k].mean() / own['crps'][k].mean() - 1):+.2f} % {dm:+.4f} [{lo:+.4f}, {hi:+.4f}]")
    return int(n), ", ".join(iv)


def main():
    lines = [f"AV29: AV28 networks, fine-tuned 500 minus own + 500, 2021 + 2022 pooled, seeds {SEEDS}; row-mean CRPS by lead {LEADS}; {BLOCK}-day blocks"]
    wins, missing = {}, []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in SEEDS:
            st = [f"modeF_n2{a}{tag}_s{s}" for a in ("ft500", "own500")]
            if not all(os.path.exists(os.path.join(M, v + x + "_rows.npz")) for v in st for x in ("", "_t2021")):
                missing.append(f"{box} s{s}")
                continue
            ft, own = pooled(st[0]), pooled(st[1])
            wins[(box, s)], txt = wins_of(ft, own)
            lines.append(f"  {box:<6} s{s} ({len(own['crps'])} rows, {len(np.unique(own['day'] // BLOCK))} blocks): {txt}; wins {wins[(box, s)]} of 4")
    lines.append("Incomplete, missing: " + ", ".join(missing) if missing else "Verdict: " + judge(wins))
    K.report("b19_av29_pooled", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n = 4000
    own = {"lead": np.tile(list(LEADS), n // 4), "day": np.repeat(np.arange(18628, 18628 + n // 4), 4), "crps": rng.uniform(1, 3, n)}
    assert wins_of({**own, "crps": own["crps"] - 0.1}, own, draws=200)[0] == 4
    assert wins_of({**own, "crps": own["crps"] + 0.1}, own, draws=200)[0] == 0


_selfcheck()
if __name__ == "__main__":
    main()
