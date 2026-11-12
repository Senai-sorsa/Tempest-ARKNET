"""New_Plan 10.4 N1: cross-fitted generator members (scripts/n1_crossfit.py, scripts/gpu_n1_crossfit.sh) against p2f, seeds 0 and 100.
    baseline   models/generator_80_p2f{,_s1}     (members train on <= 2020; range map from 2021-23)
    cross-fit  models/generator_80_n1cf{,_s1}    (each member leaves out its own 4 years of 2008-23; range map from held-out years)
Test years 2024-25, never seen by either arm. Numbers: mean over the headline rows of skill15_unknown and of |cov99_unknown - 0.99|
(ERA5: <stem>_cal*_headline.csv; balloons: <stem>_sonde_cal*_headline.csv).
Step 1 (data <= 2020 with fixed steps reproduces p2f within 0.0006): PASS without a run, every p2f member's best step is its last
(data/phase2_train_p2f.log), so p2f is that model.
Rule (pre-set in the plan; my reading of its numbers written here before any score exists): PASS = both seeds: ERA5 skill15 >= 0.0287
(p2f seed 0 has 0.0277), balloon skill15 not lower than the same seed's baseline by more than 0.0013, ERA5 coverage error not higher by
more than 0.0004. KILL = ERA5 skill15 gain under 0.0006 in either seed. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b5_crossfit.py
Result: docs/results/logs/kit_b5_crossfit.log
"""
import os

import pandas as pd

import kit_common as K


def nums(stem):
    """Headline file -> (mean skill15_unknown, mean |cov99_unknown - 0.99|)."""
    h = pd.read_csv(stem + "_headline.csv")
    return float(h.skill15_unknown.mean()), float((h.cov99_unknown - 0.99).abs().mean())


def judge(rows):
    """rows: per seed (base era5 skill, new era5 skill, base balloon skill, new balloon skill, base coverage error, new coverage error)."""
    if any(n - b < 0.0006 for b, n, *_ in rows):
        return "KILL"
    ok = all(n >= 0.0287 and sn >= sb - 0.0013 and cn <= cb + 0.0004 for b, n, sb, sn, cb, cn in rows)
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    M = os.path.join(K.REPO, "models")
    lines, rows = ["N1 cross-fitted members vs p2f, test years 2024-25; mean skill15_unknown (ERA5, balloons) and mean |cov99_unknown - 0.99| (ERA5)"], []
    for tag in ("", "_s1"):
        f = [os.path.join(M, s) for s in (f"generator_80_p2f{tag}_cal2021", f"generator_80_n1cf{tag}_calcf",
                                          f"generator_80_p2f{tag}_sonde_cal2021", f"generator_80_n1cf{tag}_sonde_calcf")]
        if not all(os.path.exists(s + "_headline.csv") for s in f):
            lines.append(f"Incomplete, missing seed '{tag or '_s0'}'")
            continue
        (b, cb), (n, cn), (sb, _), (sn, _) = (nums(s) for s in f)
        rows.append((b, n, sb, sn, cb, cn))
        lines.append(f"  seed{tag or '_s0'}: ERA5 skill15 {b:.4f} -> {n:.4f} ({n - b:+.4f}); balloons {sb:.4f} -> {sn:.4f} ({sn - sb:+.4f}); "
                     f"coverage error {cb:.4f} -> {cn:.4f} ({cn - cb:+.4f})")
    if len(rows) == 2:
        lines.append("Rule (pre-set): PASS = both seeds ERA5 skill15 >= 0.0287, balloons not worse by > 0.0013, coverage error not worse by > 0.0004; KILL = gain < 0.0006 in either seed.")
        lines.append("Verdict: " + judge(rows))
    K.report("b5_crossfit", lines)


def _selfcheck():
    assert judge([(0.0277, 0.0290, 0.02, 0.02, 0.002, 0.002)] * 2) == "PASS"
    assert judge([(0.0277, 0.0290, 0.02, 0.02, 0.002, 0.002), (0.0271, 0.0275, 0.02, 0.02, 0.002, 0.002)]) == "KILL"
    assert judge([(0.0277, 0.0284, 0.02, 0.02, 0.002, 0.002)] * 2).startswith("MISS")
    assert judge([(0.0277, 0.0290, 0.02, 0.018, 0.002, 0.002)] * 2).startswith("MISS")
    assert judge([(0.0277, 0.0290, 0.02, 0.02, 0.002, 0.003)] * 2).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
