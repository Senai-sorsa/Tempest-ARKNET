"""New_Plan 13 AV18: IL-54 shear-tail loss weight 2.0 (generator_p2g; discarded: balloons +0.0010 vs p2f, at the margin) on two more training seeds.
configs/generator_p2g_s1.toml / _s2.toml = p2g with seed 100 / 200, the seeds of p2f_s1 / p2f_s2, so each new run has a paired p2f run (same seed,
weight 1.0). Same pipeline as IL-54 (scripts/phase2_variant.sh, FEAT=base DS=pilot80_dpd: train, range calibration 2021-23, joint, ERA5 score
2024-25 m 199, balloon score, physics). Runner scripts/gpu_av18.sh.
Scores: balloons models/generator_80_p2g_sN_sonde_cal2021_headline.csv vs generator_80_p2f_sN_sonde_cal2021_headline.csv; ERA5 the _cal2021_headline.csv pair.
mean skill15 = scripts/compare_headline.compare (kind unknown), as IL-54.
Rule written 2026-11-14 before any AV18 run (New_Plan 13 AV18 row, unchanged):
PASS: balloons gain at least 0.0013 in BOTH new seeds (p2g_sN - p2f_sN mean skill15 >= +0.0013) with ERA5 not lower in either (p2g_sN - p2f_sN >= 0).
Otherwise MISS, and the IL-54 line is closed for good (no KILL tier in the row: the row says "else closed").
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b57_av18_shear_tail_seeds.py
Result: docs/results/logs/kit_b57_av18_shear_tail_seeds.log
"""
import os

import pandas as pd

import kit_common as K

NAME = "b57_av18_shear_tail_seeds"
GAIN = 0.0013
MD = os.path.join(K.REPO, "models")


def judge(pairs):
    """pairs: [(d_sonde, d_era5), ...] per seed, p2g - p2f mean skill15."""
    if all(ds >= GAIN and de >= 0 for ds, de in pairs):
        return "PASS (" + "; ".join(f"seed {i + 1}: balloons {ds:+.4f}, ERA5 {de:+.4f}" for i, (ds, de) in enumerate(pairs)) + ")"
    return ("MISS, IL-54 line closed (" + "; ".join(f"seed {i + 1}: balloons {ds:+.4f} (needs >= +{GAIN}), ERA5 {de:+.4f} (needs >= 0)"
                                                    for i, (ds, de) in enumerate(pairs)) + ")")


def main():
    from compare_headline import compare
    p = lambda n: pd.read_csv(os.path.join(MD, n))   # noqa: E731
    lines = ["AV18 IL-54 shear-tail weight 2.0 (p2g) on seeds 100 / 200, paired with p2f_s1 / p2f_s2 (weight 1.0)"]
    pairs = []
    for s in (1, 2):
        _, ss = compare(p(f"generator_80_p2f_s{s}_sonde_cal2021_headline.csv"), p(f"generator_80_p2g_s{s}_sonde_cal2021_headline.csv"))
        _, se = compare(p(f"generator_80_p2f_s{s}_cal2021_headline.csv"), p(f"generator_80_p2g_s{s}_cal2021_headline.csv"))
        ds, de = ss["mean_skill15_new"] - ss["mean_skill15_base"], se["mean_skill15_new"] - se["mean_skill15_base"]
        pairs.append((ds, de))
        lines.append(f"  seed {s}: balloons p2f {ss['mean_skill15_base']:+.4f} -> p2g {ss['mean_skill15_new']:+.4f} ({ds:+.4f}); "
                     f"ERA5 p2f {se['mean_skill15_base']:+.4f} -> p2g {se['mean_skill15_new']:+.4f} ({de:+.4f})")
    lines.append("  seed 0 (IL-54, for reference): balloons +0.0083 -> +0.0093 (+0.0010), ERA5 +0.0277 -> +0.0278")
    lines.append(f"AV18 rule (pre-set): PASS = balloons >= +{GAIN} in both seeds with ERA5 >= 0 in both; else MISS and the line is closed.")
    lines.append("AV18 verdict: " + judge(pairs))
    K.report(NAME, lines)


def _selfcheck():
    assert judge([(0.0013, 0.0), (0.002, 0.0001)]).startswith("PASS")
    assert judge([(0.0012, 0.0), (0.002, 0.0)]).startswith("MISS")
    assert judge([(0.002, -0.0001), (0.002, 0.0)]).startswith("MISS")
    assert judge([(0.002, 0.0), (0.001, 0.001)]).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
