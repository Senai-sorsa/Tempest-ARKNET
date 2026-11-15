"""New_Plan 17 UR7: the 99 % and 90 % range of SIGMA stage 2 by lead, beside N5 binned, NEST and the climate pool. No new run: the numbers are
the cov99 / cov90 columns of the existing evaluation tables (<stem>_eval.csv, method 'network + PIT recal + range map + Schaake shuffle';
cov90 is not stored, so only cov99 is printed). Models: models/modeF_n5_{bin,sig,nest}{,_den}_s{0,1}.

Reading set in New_Plan 17.2 before this script was run (2026-11-13): cov99 within 0.005 of 0.99 at every lead = ready to offer for export;
otherwise SIGMA waits for UR1 (TAILCAL). Measurement, no PASS/KILL. Note: the cov99 numbers were first looked at while this script was written
(same evening), after the reading was set.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b24_ur7_sigma_cov.py
Result: docs/results/logs/kit_b24_ur7_sigma_cov.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K
from ur_common import BEYOND, METHOD, NEAR, M

LEADS = NEAR + (BEYOND,)
ARMS = (("binned", "bin"), ("SIGMA", "sig"), ("NEST", "nest"))


def cov99(stem, method=METHOD):
    t = pd.read_csv(stem + "_eval.csv")
    return t[t.method == method].groupby("lead").cov99.mean().reindex(LEADS).values


def reading(c):
    """cov99 by lead (5,) -> the 17.2 reading."""
    return "ready to offer for export" if np.all(np.abs(np.asarray(c) - 0.99) <= 0.005) else "waits for UR1 (TAILCAL)"


def main():
    lines = [f"UR7: cov99 by lead {LEADS} (9 = beyond 7.5 d), '{METHOD}', from the existing _eval.csv tables; climate = 'climatology (2016-20 pool)' of the SIGMA run"]
    verdicts = []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            st = {a: os.path.join(M, f"modeF_n5_{k}{tag}_s{s}") for a, k in ARMS}
            if not all(os.path.exists(v + "_eval.csv") for v in st.values()):
                lines.append(f"  {box} s{s}: missing eval tables")
                continue
            row = {a: cov99(v) for a, v in st.items()}
            row["climate"] = cov99(st["SIGMA"], "climatology (2016-20 pool)")
            lines.append(f"  {box:<6} s{s}: " + "; ".join(f"{a} " + " / ".join(f"{x:.4f}" for x in c) for a, c in row.items()))
            verdicts.append(reading(row["SIGMA"]))
    lines.append("Reading (New_Plan 17.2): SIGMA " + (verdicts[0] if len(set(verdicts)) == 1 else "mixed: " + ", ".join(verdicts)) if verdicts else "Reading: no tables")
    K.report("b24_ur7_sigma_cov", lines)


def _selfcheck():
    assert reading([0.99, 0.987, 0.993, 0.99, 0.986]) == "ready to offer for export"
    assert reading([0.976, 0.99, 0.99, 0.99, 0.99]).startswith("waits")


_selfcheck()
if __name__ == "__main__":
    main()
