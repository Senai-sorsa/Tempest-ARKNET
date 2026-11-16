"""New_Plan 20.2 step 4 / 21 item 5: SIGMA, NEST and AV30 (NEST + Student-t) re-scored under rule R1 (report only, no new run).
R1 (New_Plan 20.1): cov99 within 0.005 of 0.99 at every lead (1 / 3 / 5 / 7 d and beyond 7.5 d) AND CRPS not worse than binned by more than 0.2 %.
Source: models/modeF_n5_{bin,sig,nest,nestt}{,_den}_s{0,1}_eval.csv, method 'network + PIT recal + range map + Schaake shuffle' (as UR7, b24).
CRPS by lead = mean of the table's CRPS over variables and bands (same rows for all arms). Reading: all 4 runs of an arm pass both clauses = 'PASS under R1'
(adoption stays ASK_LATER); else 'still MISS under R1'. Report only: nothing is adopted, no PASS/KILL entered in the trial table.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b56_r1_cov99_rescore.py
Result: docs/results/logs/kit_b56_r1_cov99_rescore.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from ur_common import BEYOND, METHOD, NEAR, M

LEADS = NEAR + (BEYOND,)
ARMS = (("SIGMA", "sig"), ("NEST", "nest"), ("AV30", "nestt"))


def by_lead(stem):
    t = pd.read_csv(stem + "_eval.csv")
    t = t[t.method == METHOD]
    return t.groupby("lead").cov99.mean().reindex(LEADS).values, t.groupby("lead").crps.mean().reindex(LEADS).values


def r1(cov, crps, crps_bin):
    """-> (cov99 clause, CRPS clause) under R1 for one run."""
    return bool(np.all(np.abs(cov - 0.99) <= 0.005)), bool(np.all(crps <= crps_bin * 1.002))


def main():
    lines = [f"R1 re-score, leads {LEADS} (9 = beyond 7.5 d), '{METHOD}'; cov99 by lead / CRPS change vs binned (%)"]
    ok = {a: [] for a, _ in ARMS}
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            sb = os.path.join(M, f"modeF_n5_bin{tag}_s{s}")
            if not os.path.exists(sb + "_eval.csv"):
                lines.append(f"  {box} s{s}: no binned table")
                continue
            cb, rb = by_lead(sb)
            lines.append(f"  {box:<6} s{s}: binned cov99 " + " / ".join(f"{x:.4f}" for x in cb))
            for a, k in ARMS:
                st = os.path.join(M, f"modeF_n5_{k}{tag}_s{s}")
                if not os.path.exists(st + "_eval.csv"):
                    lines.append(f"    {a}: missing")
                    ok[a].append(False)
                    continue
                c, r = by_lead(st)
                p1, p2 = r1(c, r, rb)
                ok[a].append(p1 and p2)
                lines.append(f"    {a:<5} cov99 " + " / ".join(f"{x:.4f}" for x in c) + "  CRPS " + " / ".join(f"{100 * (x / y - 1):+.2f}" for x, y in zip(r, rb))
                             + f"  cov99 clause {'ok' if p1 else 'FAIL'}, CRPS clause {'ok' if p2 else 'FAIL'}")
    for a, _ in ARMS:
        lines.append(f"Reading {a}: " + ("PASS under R1 (adoption stays ASK_LATER)" if ok[a] and all(ok[a]) else "still MISS under R1"))
    K.report("b56_r1_cov99_rescore", lines)


def _selfcheck():
    c, r = np.array([0.99, 0.987, 0.993, 0.99, 0.986]), np.ones(5)
    assert r1(c, r, r) == (True, True)
    assert r1(c - 0.01, r, r)[0] is False and r1(c, r * 1.01, r)[1] is False


_selfcheck()
if __name__ == "__main__":
    main()
