"""New_Plan 17 UR9: IL-207b per-site wind factor (b3_il207b_site_shift.py), one NEW hour seed (2), same method, cells, fit and test years,
300 hours per site, 21-day blocks: the wrapped script bootstraps single days; during this run its block_boot gets the day labels turned into
21-day blocks (in memory, AU-4 default), so the printed interval is the 21-day one.
The 15.4 re-read (docs/results/au15_4_reread.md) named IL-207b seed 1 as the interval to confirm.
Rule (set 2026-11-13 in New_Plan 17.2 before any run):
  PASS: TCS CRPS interval below 0, TCS coverage not lower than shipped, MAF within 0.0009 of shipped (point) and its coverage 0.85-0.95.
  KILL: TCS interval includes 0 -> the factor stays opt-in with a warning.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b32_ur9_il207b_seed2.py        # about 30 min
Result: docs/results/logs/kit_b32_ur9_il207b_seed2.log (the wrapped script's lines, then the UR9 verdict)
"""
import re
import sys

import kit_common as K
from ur_common import captured_report

NAME = "b32_ur9_il207b_seed2"
PAT = r"shipped CRPS ([\d.]+) cov ([\d.]+) \| factor CRPS ([\d.]+) cov ([\d.]+) \| minus shipped ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]"


def cells(lines):
    """-> [(site, crps0, cov0, crps1, cov1, diff, lo, hi)] in the order of the wrapped script (TCS, MAF)."""
    out, site = [], None
    for ln in lines:
        m0 = re.match(r"(\w+): fit", ln)
        if m0:
            site = m0.group(1)
        m = re.search(PAT, ln)
        if m:
            out.append((site, *map(float, m.groups())))
    return out


def judge(c):
    d = {x[0]: x for x in c}
    if "TCS" not in d or "MAF" not in d:
        return "INCOMPLETE"
    t, m = d["TCS"], d["MAF"]
    if t[7] >= 0:
        return "KILL (TCS interval includes 0: the factor stays opt-in with a warning)"
    ok = t[4] >= t[2] and m[5] <= 0.0009 and 0.85 <= m[4] <= 0.95
    return "PASS" if ok else "MISS (record, no adoption)"


def blocks21(labels):
    """ISO day labels -> 21-day block labels (a label that is not a date is kept)."""
    import pandas as pd
    out = []
    for x in labels:
        try:
            out.append(str((pd.Timestamp(x).toordinal()) // 21))
        except (ValueError, TypeError):
            out.append(x)
    return out


def main():
    import b3_il207b_site_shift as B
    sys.argv = ["b3", "--n", "300", "--seed", "2"]
    old = K.block_boot
    K.block_boot = lambda v, days, **kw: old(v, blocks21(days), **kw)
    try:
        with captured_report() as got:
            B.main()
    finally:
        K.block_boot = old
    K.report(NAME, got + ["UR9 rule (pre-set): PASS = TCS interval < 0 and coverage not lower, MAF within +0.0009 and coverage 0.85-0.95; KILL = TCS interval includes 0.",
                          "UR9 verdict: " + judge(cells(got))])


def _selfcheck():
    t = ["TCS: fit 290 hours (0 skipped); factors a 1.0", "  test 280 hours (3 skipped): shipped CRPS 1.500 cov 0.81 | factor CRPS 1.420 cov 0.85 | minus shipped -0.080 [-0.120, -0.040]  ok",
         "MAF: fit 300 hours (0 skipped); factors a 1.0", "  test 290 hours (0 skipped): shipped CRPS 1.300 cov 0.92 | factor CRPS 1.3005 cov 0.91 | minus shipped +0.000 [-0.010, +0.011]  ok"]
    c = cells(t)
    assert [x[0] for x in c] == ["TCS", "MAF"] and c[0][7] == -0.040
    assert judge(c) == "PASS"
    assert judge([("TCS", 1.5, 0.81, 1.42, 0.85, -0.08, -0.12, 0.001), c[1]]).startswith("KILL")
    b = blocks21(["2023-01-01", "2023-01-02", "2023-02-15"])
    assert b[0] == b[1] != b[2]


_selfcheck()
if __name__ == "__main__":
    main()
