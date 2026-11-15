"""New_Plan 17 UR8: is N1's gain cross-fitting or the three extra training years? Three arms, test years 2024-25, seeds 0 and 100:
    p2f       models/generator_80_p2f{,_s1}       members train on <= 2020, range map 2021-23 (the shipped recipe)
    control   models/generator_80_n1sf{,_s1}      every member holds out the SAME 4 years (fold 0: 2008-09, 2016-17), so 29 of 33 years
                                                  incl. 2021-23, range map from those held-out years (scripts/gpu_ur8_control.sh)
    cross-fit models/generator_80_n1cf{,_s1}      N1: each member holds out its own 4 years (29 of 33 each), range map from held-out years
Numbers as b5_crossfit: mean over the headline rows of skill15_unknown (ERA5, balloons) and of |cov99_unknown - 0.99| (ERA5).
Rule (set 2026-11-13 in New_Plan 17.2 before any run):
  PASS (the gain is cross-fitting): cross-fit beats the control by at least 0.0006 ERA5 skill15 in both seeds, balloons not worse.
  KILL (the gain is the extra years): cross-fit minus control under 0.0003 in both seeds -> export the idea "more years" (the control's recipe),
        not the folds.  Otherwise MISS.
Caveat: the headline files are the plain-baseline form (as N1 was judged); model-vs-model differences keep their sign under AU-1.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b31_ur8_control.py
Result: docs/results/logs/kit_b31_ur8_control.log
"""
import os

import kit_common as K
from b5_crossfit import nums


def judge(rows):
    """rows: per seed (control era5, cross-fit era5, control balloon, cross-fit balloon) -> verdict."""
    d = [c - b for b, c, *_ in rows]
    if all(x < 0.0003 for x in d):
        return "KILL (the N1 gain is the extra years, not cross-fitting)"
    ok = all(x >= 0.0006 for x in d) and all(sc >= sb for _, _, sb, sc in rows)
    return "PASS (the gain is cross-fitting)" if ok else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines, rows = ["UR8: N1 cross-fit vs a same-fold control vs p2f, 2024-25; mean skill15_unknown (ERA5 / balloons), mean |cov99_unknown - 0.99| (ERA5)"], []
    for tag in ("", "_s1"):
        st = {a: (os.path.join(M, f"generator_80_{m}{tag}_{c}"), os.path.join(M, f"generator_80_{m}{tag}_sonde_{c}"))
              for a, m, c in (("p2f", "p2f", "cal2021"), ("control", "n1sf", "calcf"), ("cross-fit", "n1cf", "calcf"))}
        if not all(os.path.exists(p + "_headline.csv") for v in st.values() for p in v):
            lines.append(f"  seed{tag or '_s0'}: incomplete (run scripts/gpu_ur8_control.sh)")
            continue
        n = {a: (nums(e), nums(s)) for a, (e, s) in st.items()}
        rows.append((n["control"][0][0], n["cross-fit"][0][0], n["control"][1][0], n["cross-fit"][1][0]))
        lines.append(f"  seed{tag or '_s0'}: " + "; ".join(f"{a} ERA5 {v[0][0]:.4f} cov err {v[0][1]:.4f} balloons {v[1][0]:.4f}" for a, v in n.items())
                     + f"; cross-fit minus control ERA5 {n['cross-fit'][0][0] - n['control'][0][0]:+.4f}, control minus p2f {n['control'][0][0] - n['p2f'][0][0]:+.4f}")
    if len(rows) == 2:
        lines.append("Rule (pre-set): PASS = cross-fit - control >= 0.0006 in both seeds, balloons not worse; KILL = < 0.0003 in both.")
        lines.append("Verdict: " + judge(rows))
    K.report("b31_ur8_control", lines)


def _selfcheck():
    assert judge([(0.029, 0.0297, 0.011, 0.0115)] * 2).startswith("PASS")
    assert judge([(0.0295, 0.0297, 0.011, 0.0115)] * 2).startswith("KILL")
    assert judge([(0.029, 0.0297, 0.011, 0.0105)] * 2).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
