"""New_Plan 13 AV28, variation of AV5 (KILL 2026-11-13 10:48 by its rule: the third seed's Denver 5 d interval reached +0.001, so 2 of 4 leads;
but every point estimate in all 6 box x seed runs favours the world start, and 1 d / 7 d intervals are below 0 everywhere -> benefit shown, parent N2
not closed; the AV5 row named the next step itself: more fine-tune steps).
What changes: the fine-tune and its control run 500 steps instead of 300 (scripts/cpu_av28.sh): world network + 500 steps on the box rows vs the
box's own model + 500 steps on the same rows; same seeds 0 / 1 / 2, recipe, rows and scoring as AV5 (b16.score).

Rule (set before any result; written 2026-11-13 10:55):
  wins[(box, seed)] = leads (1 / 3 / 5 / 7 d) where fine-tuned-500 minus own + 500 has a day-block bootstrap interval below 0.
  PASS: wins >= 3 in both boxes for all three seeds (AV5's PASS clause).
  KILL (no benefit, the parent closes): wins <= 1 in 3 or more of the 6 box x seed runs.
  Otherwise MISS. Forking-paths note: second variation of N2 after AV5; the step count was named in the AV5 row before its result.
  A PASS is not adoption (no shipped path uses the world start; the user decides, as for N2-B).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b17_av28_ft500.py
Result: docs/results/logs/kit_b17_av28_ft500.log
"""
import kit_common as K
from b16_av5_third_seed import LEADS, SEEDS, score, stems as stems300


def stems(tag, s):
    return {"own": stems300(tag, s)["own"], "fine-tuned": f"modeF_n2ft500{tag}_s{s}", "own+300": f"modeF_n2own500{tag}_s{s}"}    # key 'own+300' = the control slot


def judge(wins):
    if all(n >= 3 for n in wins.values()):
        return "PASS"
    if sum(n <= 1 for n in wins.values()) >= 3:
        return "KILL (no benefit from the world start at 500 steps)"
    return "MISS (record)"


def main():
    lines = [f"AV28: N2 fine-tuned 500 steps vs own + 500 steps (lines say own+300 = the control slot, here + 500), seeds {SEEDS}; mean CRPS by lead {LEADS}"]
    wins = score(stems, lines)
    lines.append("Verdict: " + judge(wins))
    K.report("b17_av28_ft500", lines)


def _selfcheck():
    k = lambda v: {(b, s): v for b in ("A", "B") for s in SEEDS}
    assert judge(k(3)) == "PASS"
    assert judge(k(2)).startswith("MISS")
    assert judge({**k(4), ("A", 0): 1, ("A", 1): 0, ("B", 2): 1}).startswith("KILL")
    assert judge({**k(4), ("A", 0): 1, ("A", 1): 0}).startswith("MISS")
    assert stems("_den", 2) == {"own": "modeF_n2_base_den_s2", "fine-tuned": "modeF_n2ft500_den_s2", "own+300": "modeF_n2own500_den_s2"}


_selfcheck()
if __name__ == "__main__":
    main()
