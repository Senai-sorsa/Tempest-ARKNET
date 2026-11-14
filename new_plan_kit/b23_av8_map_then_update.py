"""New_Plan 13 AV8: S1 site map first, update second again (b4_debias_then_update.py, same method, arms and test hours), with
120 prior hours per cell for the map instead of 40 (steadier factors), and the neighbours outside the trained area left out (IL-209:
ONM, FST, ABQ; ABQ is not in S1's pairs). Pairs: TCS <- own, LRU; MAF <- own, PEQ. Seeds 0 and 1 (S1's seeds; the factor check
compares the two seeds' maps, so the seed numbers are kept). Factors go to data/kit/b23_av8_map_then_update_factors_seed{0,1}.json.
Rule written 2026-11-13 before any AV8 result (New_Plan 13, unchanged from S1):
PASS: map + B coverage >= 0.80 at every servable pair in both seeds, CRPS(map + B) - CRPS(B) <= +0.0009 at every pair, and every cell
      factor within 0.05 between the seeds.
KILL: the largest cell factor gap between seeds is still above 0.05. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b23_av8_map_then_update.py
Result: docs/results/logs/kit_b23_av8_map_then_update.log (both seeds' tables, then the verdict)
"""
import re
import sys

import kit_common as K

NAME = "b23_av8_map_then_update"


def judge(pairs_ok, gap):
    """pairs_ok = [bool per seed], gap = largest cell factor gap (None if not computed) -> verdict."""
    if gap is None or len(pairs_ok) != 2:
        return "INCOMPLETE"
    if gap > 0.05:
        return "KILL"
    return "PASS" if all(pairs_ok) else "MISS (record, no adoption)"


def seed_ok(text):
    """A seed's pairs pass when no 'map B' row and no missing-neighbour line says fail."""
    return bool(re.search(r"minus B .* ok", text)) and not re.search(r"minus B .* fail|counts as fail", text)


def gap_of(text):
    m = re.search(r"largest cell gap ([\d.]+)", text)
    return float(m.group(1)) if m else None


def main():
    import io
    from contextlib import redirect_stdout
    import b4_debias_then_update as B
    outs = []
    for s in (0, 1):
        buf = io.StringIO()
        sys.argv = ["b4", "--fit", "120", "--seed", str(s), "--drop", "ONM,FST,ABQ", "--report", NAME]
        with redirect_stdout(buf):
            B.main()
        outs.append(buf.getvalue())
    K.report(NAME, ["AV8 rule (pre-set): PASS = map + B coverage >= 0.80 and CRPS minus B <= +0.0009 at every pair, both seeds, factor gap <= 0.05; KILL = gap > 0.05.",
                    "AV8 verdict: " + judge([seed_ok(o) for o in outs], gap_of(outs[1]))])


def _selfcheck():
    ok = "  LRU  map B  n 100  CRPS 1.2  coverage 0.84  minus B -0.010 [-0.02, -0.001]  ok\n"
    bad = ok.replace("  ok", "  fail")
    assert seed_ok(ok) and not seed_ok(ok + bad) and not seed_ok(ok + "  PEQ: no usable reports -> counts as fail")
    assert gap_of("Factor stability vs seed 0: largest cell gap 0.031 (ok, rule <= 0.05)") == 0.031
    assert judge([True, True], 0.03) == "PASS" and judge([True, True], 0.06) == "KILL"
    assert judge([True, False], 0.03).startswith("MISS") and judge([True, True], None) == "INCOMPLETE"


_selfcheck()
if __name__ == "__main__":
    main()
