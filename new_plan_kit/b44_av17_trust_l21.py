"""New_Plan 13 AV17: IL-10 trust layer refit on the CURRENT l21 stack (shipped l3_c4w + calib + shear map + shuffle c8 + lapse map), with
T and u at 12-18 km left at w = 1 (skipped: the band whose target changes around 2020, IL-67, where IL-10 lost T -0.0043).
"Forced to zero" in the AV17 row is read as "no blend" (w = 1, the model alone), since w = 0 would be pure climatology, the opposite of the intent.
Fit = IL-10's settings, read back from models/generator_80_p2f.trust2021.npz: 2021-23 rows, --min-gain 0.003, RH 5-12 / 12-18 km skipped,
no second range map; plus the two new skips. Fit on the DAY l21 file (the rows the stack is scored on). Runner: scripts/gpu_av17.sh.
Rule written 2026-11-14 before any AV17 result (New_Plan 13 AV17 row, unchanged):
PASS: ERA5 paired gain (mean skill15_unknown, trust minus base, averaged over score seeds 0/1/2) > 0.0009; balloons (sonde seed 0) mean skill15_unknown
      not worse by more than 0.0013; mean |cov99_unknown - 0.99| not worse by more than 0.0004 (ERA5, mean of 3 seeds, and balloons);
      no band worse (compare_headline rule (b): no band with disjoint intervals worse, any seed, ERA5 and balloons).
KILL: ERA5 paired gain < 0.0005. Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b44_av17_trust_l21.py
Result: docs/results/logs/kit_b44_av17_trust_l21.log
"""
import os

import pandas as pd

import kit_common as K

NAME = "b44_av17_trust_l21"
BASE = "models/l3_c4wl_s{}_cal2021_smap_shufc8_lmap_headline.csv"
NEW = "models/av17_s{}_cal2021_trust_smap_shufc8_lmap_headline.csv"
SBASE = "models/l3_c4wl_s0_sonde_cal2021_smap_headline.csv"
SNEW = "models/av17_s0_sonde_cal2021_trust_smap_headline.csv"


def judge(gains, sonde_d, cov_era5, cov_sonde, worse_bands):
    """gains = per-seed ERA5 mean skill15 differences; sonde_d = balloon difference; cov_* = change in mean |cov99 - 0.99|; worse_bands = count."""
    if len(gains) != 3 or sonde_d is None:
        return f"INCOMPLETE ({len(gains)} of 3 ERA5 seeds, balloons {'missing' if sonde_d is None else 'on file'})"
    g = sum(gains) / 3
    if g < 0.0005:
        return f"KILL (ERA5 gain {g:+.4f} < 0.0005)"
    if g > 0.0009 and sonde_d >= -0.0013 and cov_era5 <= 0.0004 and cov_sonde <= 0.0004 and worse_bands == 0:
        return f"PASS (ERA5 gain {g:+.4f})"
    return f"MISS (record, no adoption; ERA5 gain {g:+.4f})"


def main():
    from compare_headline import compare
    lines, gains, covs, worse = [], [], [], 0
    for s in (0, 1, 2):
        if not (os.path.exists(BASE.format(s)) and os.path.exists(NEW.format(s))):
            lines.append(f"ERA5 seed {s}: headline missing")
            continue
        t, m = compare(pd.read_csv(BASE.format(s)), pd.read_csv(NEW.format(s)))
        d = m["mean_skill15_new"] - m["mean_skill15_base"]
        cv = m["mean_abs_cov_dev_new"] - m["mean_abs_cov_dev_base"]
        w = t[(t.skill_flag == "WORSE") | (t.cov_flag == "WORSE")]
        gains.append(d), covs.append(cv)
        worse += len(w)
        lines.append(f"ERA5 seed {s}: mean skill15_unknown {m['mean_skill15_base']:+.4f} -> {m['mean_skill15_new']:+.4f} ({d:+.4f}); "
                     f"mean |cov99-0.99| {m['mean_abs_cov_dev_base']:.4f} -> {m['mean_abs_cov_dev_new']:.4f} ({cv:+.4f}); bands worse: "
                     + (", ".join(f"{r.var} {r.band}" for r in w.itertuples()) or "none"))
        lines.append("  per band d skill15: " + "; ".join(f"{r.var} {r.band} {r.d_skill15:+.4f}{' ' + r.skill_flag if r.skill_flag else ''}" for r in t.itertuples()))
    sonde_d = cov_s = None
    if os.path.exists(SBASE) and os.path.exists(SNEW):
        t, m = compare(pd.read_csv(SBASE), pd.read_csv(SNEW))
        sonde_d = m["mean_skill15_new"] - m["mean_skill15_base"]
        cov_s = m["mean_abs_cov_dev_new"] - m["mean_abs_cov_dev_base"]
        w = t[(t.skill_flag == "WORSE") | (t.cov_flag == "WORSE")]
        worse += len(w)
        lines.append(f"Balloons seed 0: mean skill15_unknown {m['mean_skill15_base']:+.4f} -> {m['mean_skill15_new']:+.4f} ({sonde_d:+.4f}); "
                     f"mean |cov99-0.99| ({cov_s:+.4f}); lowest cov99 {m['min_cov99_new']:.4f}; bands worse: "
                     + (", ".join(f"{r.var} {r.band}" for r in w.itertuples()) or "none"))
    else:
        lines.append("Balloons: headline missing")
    cov_e = sum(covs) / len(covs) if covs else 1.0
    lines.append("AV17 rule (pre-set): PASS = ERA5 gain > 0.0009 (mean of 3 seeds), balloons not worse by > 0.0013, cov error not worse by > 0.0004, "
                 "no band worse; KILL = ERA5 gain < 0.0005.")
    lines.append("AV17 verdict: " + judge(gains, sonde_d, cov_e, cov_s if cov_s is not None else 1.0, worse))
    K.report(NAME, lines)


def _selfcheck():
    assert judge([0.002] * 3, 0.0, 0.0, 0.0, 0).startswith("PASS")
    assert judge([0.0003] * 3, 0.0, 0.0, 0.0, 0).startswith("KILL")
    assert judge([0.0007] * 3, 0.0, 0.0, 0.0, 0).startswith("MISS")
    assert judge([0.002] * 3, -0.002, 0.0, 0.0, 0).startswith("MISS")
    assert judge([0.002] * 3, 0.0, 0.0, 0.0, 1).startswith("MISS")
    assert judge([0.002] * 2, 0.0, 0.0, 0.0, 0).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
