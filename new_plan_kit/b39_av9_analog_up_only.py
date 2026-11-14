"""New_Plan 13 AV9: O4 analog tail fix again (b4_analog_tail.py, same library 2015-23, test 2024-25, K = 40), but the gap shift is applied
only when it is > 0 (--up-only): the upper tail moves up as before, and no ensemble is pushed down onto the 0 m/s floor, so the spread is kept.
Why: O4's two-way shift gave better CRPS at both sites (intervals < 0) but TCS coverage fell 0.89 -> 0.83.
The analog has no random draw, so the "second hour seed" of New_Plan 13 is replaced by two replicates: odd and even test days (disjoint).
Rule written 2026-11-13 before any AV9 result (New_Plan 13):
PASS: fix minus plain CRPS day-block interval < 0 AND coverage not lower than plain by more than 0.02, at TCS and MAF in both day halves
      (then it replaces the plain analog as the referee, after the user's go).
KILL: coverage still falls by more than 0.02 in any site x half. Otherwise MISS: record, no change.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b39_av9_analog_up_only.py
Result: docs/results/logs/kit_b39_av9_analog_up_only.log
"""
import re
import sys

import kit_common as K

NAME = "b39_av9_analog_up_only"


def cells(text):
    pat = r"  half \w+ days +fix minus plain CRPS [+-][\d.]+ \[[+-][\d.]+, ([+-][\d.]+)\]  coverage ([\d.]+) -> ([\d.]+)"
    return [(float(h), float(c1) - float(c0)) for h, c0, c1 in re.findall(pat, text)]


def judge(rows):
    """rows = [(interval upper end, coverage change)] for the 4 site x half cells."""
    if len(rows) != 4:
        return f"INCOMPLETE ({len(rows)} of 4 cells)"
    if any(dc < -0.02 - 1e-9 for _, dc in rows):
        return "KILL"
    if all(hi < 0 for hi, _ in rows):
        return "PASS"
    return "MISS (record, no change)"


def main():
    import io
    from contextlib import redirect_stdout
    import b4_analog_tail as B
    buf = io.StringIO()
    sys.argv = ["b4", "--up-only", "--report", NAME]
    with redirect_stdout(buf):
        B.main()
    K.report(NAME, ["AV9 rule (pre-set): PASS = interval < 0 and coverage drop <= 0.02 at TCS and MAF in odd and even days; KILL = a drop > 0.02.",
                    "AV9 verdict: " + judge(cells(buf.getvalue()))])


def _selfcheck():
    t = "  half odd days  fix minus plain CRPS -0.0100 [-0.0170, -0.0040]  coverage 0.89 -> 0.88\n  half even days fix minus plain CRPS -0.0100 [-0.0170, +0.0040]  coverage 0.89 -> 0.83"
    assert [(h, round(c, 2)) for h, c in cells(t)] == [(-0.004, -0.01), (0.004, -0.06)]
    assert judge([(-0.01, -0.01)] * 4) == "PASS" and judge([(-0.01, -0.03)] + [(-0.01, 0.0)] * 3) == "KILL"
    assert judge([(0.01, -0.01)] + [(-0.01, 0.0)] * 3).startswith("MISS") and judge([(-0.01, 0.0)] * 3).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
