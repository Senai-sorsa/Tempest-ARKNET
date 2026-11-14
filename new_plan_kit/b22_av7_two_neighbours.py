"""New_Plan 13 AV7: O1 two neighbours at once again (b4_two_neighbours.py, same method, pairs and map), 600 hours per target instead of 200,
two NEW hour seeds (2 and 3). Why: O1 was better in 4 of 4 runs but the interval excluded 0 only once (too few hours).
Rule written 2026-11-13 before any AV7 result (New_Plan 13, unchanged from O1):
PASS: merged CRPS better than the best single neighbour with a day-block interval that excludes 0, merged coverage >= 0.80, at both targets
      (TCS, ELP) in both seeds.
KILL: the interval includes 0 at both targets in both seeds. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b22_av7_two_neighbours.py
Result: docs/results/logs/kit_b22_av7_two_neighbours.log (both seeds' tables, then the verdict)
"""
import re
import sys

import kit_common as K

NAME = "b22_av7_two_neighbours"


def judge(rows):
    """rows = [(hi, coverage)] for the 4 target x seed cells -> verdict."""
    if len(rows) == 4 and all(hi < 0 and cov >= 0.80 for hi, cov in rows):
        return "PASS"
    if len(rows) == 4 and all(hi >= 0 for hi, _ in rows):
        return "KILL"
    return "MISS (record, no adoption)" if len(rows) == 4 else f"INCOMPLETE ({len(rows)} of 4 cells)"


def cells(text):
    pat = r"merged minus best single \(\w+\) [+-][\d.]+ \[[+-][\d.]+, ([+-][\d.]+)\], merged coverage ([\d.]+)"
    return [(float(h), float(c)) for h, c in re.findall(pat, text)]


def main():
    import io
    from contextlib import redirect_stdout
    import b4_two_neighbours as B
    buf = io.StringIO()
    for s in (2, 3):
        sys.argv = ["b4", "--n", "600", "--seed", str(s), "--report", NAME]
        with redirect_stdout(buf):
            B.main()
    rows = cells(buf.getvalue())
    K.report(NAME, ["AV7 rule (pre-set): PASS = interval < 0 and coverage >= 0.80 at TCS and ELP in seeds 2 and 3; KILL = interval includes 0 in all 4.",
                    "AV7 verdict: " + judge(rows)])


def _selfcheck():
    t = "  merged minus best single (LRU) -0.043 [-0.096, -0.013], merged coverage 0.84  ok\n  merged minus best single (ALM) -0.105 [-0.153, +0.053], merged coverage 0.89  fail"
    assert cells(t) == [(-0.013, 0.84), (0.053, 0.89)]
    assert judge([(-0.01, 0.85)] * 4) == "PASS" and judge([(0.01, 0.85)] * 4) == "KILL"
    assert judge([(-0.01, 0.79)] + [(-0.01, 0.85)] * 3).startswith("MISS") and judge([(-0.01, 0.85)] * 3).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
