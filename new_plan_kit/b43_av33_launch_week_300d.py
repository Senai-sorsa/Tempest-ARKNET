"""New_Plan 13 AV33: AV32 again (b4_launch_week_replay.py, same method, k = 3 / 7 / 14, start IL-207b, alpha 1/60) with 300 test days
per site instead of 150 (--n 300), seeds 0 and 1. AV32 (MISS 2026-11-14): seed 1 passed at both sites, seed 0 TCS -0.008 and MAF +0.007 with
intervals reaching 0. AV32 setup: the decaying average starts from the IL-207b per-site cell factor (--start il207b) instead of 1.0; the base arm
is that IL-207b factor alone, and the decay step is alpha = 1/60 per day instead of 1/30 (AV32). Why: AV10 (alpha 1/30) beat IL-207b alone at TCS in both seeds
with intervals just reaching 0, but MAF seed 0 was worse (+0.017) while its daily factor swung 0.79-1.25; half the step moves the factor half as far on an odd day.
Rule written 2026-11-14 before any AV33 result (New_Plan 13, AV32's rule unchanged):
PASS: at k = 7, CRPS minus IL-207b alone with a day-block interval < 0 and coverage not lower (2 dp), at TCS and MAF in both seeds.
KILL: at k = 7, not better than the IL-207b factor alone (difference >= 0) at both sites in both seeds. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b43_av33_launch_week_300d.py
Result: docs/results/logs/kit_b43_av33_launch_week_300d.log (both seeds' tables, then the verdict)
"""
import re
import sys

import kit_common as K

NAME = "b43_av33_launch_week_300d"


def judge(rows):
    """rows = [(difference, ok)] for the 4 site x seed k = 7 rows -> verdict."""
    if len(rows) != 4:
        return f"INCOMPLETE ({len(rows)} of 4 cells)"
    if all(ok for _, ok in rows):
        return "PASS"
    if all(d >= 0 for d, _ in rows):
        return "KILL"
    return "MISS (record, no adoption)"


def cells(text):
    pat = r"  k=7 +CRPS [\d.]+  coverage [\d.]+  minus IL-207b alone ([+-][\d.]+) \[[+-][\d.]+, [+-][\d.]+\]  (ok|fail)"
    return [(float(d), r == "ok") for d, r in re.findall(pat, text)]


def main():
    import io
    from contextlib import redirect_stdout
    import b4_launch_week_replay as B
    buf = io.StringIO()
    for s in (0, 1):
        sys.argv = ["b4", "--seed", str(s), "--start", "il207b", "--alpha", str(1 / 60), "--n", "300", "--report", NAME]
        with redirect_stdout(buf):
            B.main()
    K.report(NAME, ["AV33 rule (pre-set): PASS = k = 7 minus IL-207b alone interval < 0 and coverage not lower at TCS and MAF in seeds 0 and 1; "
                    "KILL = difference >= 0 in all 4.", "AV33 verdict: " + judge(cells(buf.getvalue()))])


def _selfcheck():
    t = ("  k=7        CRPS 1.609  coverage 0.81  minus IL-207b alone -0.0435 [-0.0697, -0.0177]  ok\n"
         "  k=7        CRPS 1.522  coverage 0.90  minus IL-207b alone +0.0083 [-0.0125, +0.0291]  fail\n"
         "  k=3        CRPS 1.522  coverage 0.90  minus IL-207b alone +0.0083 [-0.0125, +0.0291]")
    assert cells(t) == [(-0.0435, True), (0.0083, False)]
    assert judge([(-0.01, True)] * 4) == "PASS" and judge([(0.01, False)] * 4) == "KILL"
    assert judge([(-0.01, False)] + [(-0.01, True)] * 3).startswith("MISS") and judge([(-0.01, True)] * 3).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
