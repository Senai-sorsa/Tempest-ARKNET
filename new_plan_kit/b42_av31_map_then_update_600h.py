"""New_Plan 13 AV31: AV8 again (S1 site map first, update second; b4_debias_then_update.py, same method and arms, 120 prior hours per cell,
ONM / FST / ABQ left out) with 600 test hours per target instead of 200. Why: AV8 (MISS) had a stable map (gap 0.029) and map + B beat B at
7 of 8 pair-seeds; its one failed clause was TCS own report seed 0, +0.002 [-0.025, +0.029], a point estimate inside its noise. Pairs: TCS <- own, LRU; MAF <- own, PEQ. Seeds 0 and 1 (S1's seeds; the factor check
compares the two seeds' maps, so the seed numbers are kept). Factors go to data/kit/b42_av31_map_then_update_600h_factors_seed{0,1}.json.
Rule written 2026-11-14 before any AV31 result (New_Plan 13, AV8's rule unchanged):
PASS: map + B coverage >= 0.80 at every servable pair in both seeds, CRPS(map + B) - CRPS(B) <= +0.0009 at every pair, and every cell
      factor within 0.05 between the seeds.
KILL: the largest cell factor gap between seeds is still above 0.05. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b42_av31_map_then_update_600h.py
Result: docs/results/logs/kit_b42_av31_map_then_update_600h.log (both seeds' tables, then the verdict)
"""
import re
import sys

import kit_common as K

NAME = "b42_av31_map_then_update_600h"


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
        sys.argv = ["b4", "--n", "600", "--fit", "120", "--seed", str(s), "--drop", "ONM,FST,ABQ", "--report", NAME]
        with redirect_stdout(buf):
            B.main()
        outs.append(buf.getvalue())
    K.report(NAME, ["AV31 rule (pre-set): PASS = map + B coverage >= 0.80 and CRPS minus B <= +0.0009 at every pair, both seeds, factor gap <= 0.05; KILL = gap > 0.05.",
                    "AV31 verdict: " + judge([seed_ok(o) for o in outs], gap_of(outs[1]))])


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
