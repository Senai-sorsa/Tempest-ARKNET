"""New_Plan 13 AV19: L3-26 Student-t noise model (models/l3_studt.pt, no retrain) judged INSIDE the full stack (calibration + Schaake shuffle with template cell 8
+ its own shear map + its own lapse map), which re-imposes the vertical correlation and shear on which it failed alone (vcorr_err 0.076 -> 0.109, shear KS).
Base = the p2f generator (models/generator_80_p2f, trained on the same data/train/pilot80_dpd.npz) with ITS full stack: g80lm_lmap_s{0,1,2} (seed 0 is the paired base,
seeds 1/2 give the shape-noise tolerance). studt's shear map and lapse map are fitted with p2f's recipe (shear_map --shuffle --full --template-cell 8; lapse_map after it).
(Checked 2026-11-14: p2f's cell-8 map came from scripts/ap_il96.sh with exactly these flags on the same data; its lapse map from scripts/ap_g_lmap80.sh, same command.)
Denver zero-shot (data/train/denver_full_fill_dpd.npz, as the L3-26 retry): studt stack vs p2f stack, both scored here, seed 0. One seed suffices: p2f Denver seeds 1/2
differ from seed 0 by -0.0001 / -0.0003 (l3_p2fden_s* headlines), ~30x below the 0.01 bar. Runner: scripts/gpu_av19.sh.
Rule written 2026-11-14 before any AV19 run (New_Plan 13 AV19 row, unchanged):
PASS: NM/TX stack headline within the paired tolerance (studt mean skill15_unknown >= p2f stack seed 0 - 0.0009) AND shape not FAIL (scripts/compare_shape.py vs p2f stack
      seed 0, seed noise from seeds 1/2: no metric WORSE) AND Denver zero-shot gain over the base >= 0.01 (mean skill15_unknown, studt stack minus p2f stack).
KILL: event-coverage gap still worse beyond its tolerance (compare_shape event_cov_gap flagged WORSE).
Otherwise MISS: record, no adoption.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b46_av19_studt_stack.py
Result: docs/results/logs/kit_b46_av19_studt_stack.log
Correction 2026-11-14 10:30 (input format only, rule unchanged): the first verdict run passed the scorer's _diag.csv to compare_shape, which needs
scripts/diagnose.py output; shape inputs are now diagnose.py runs with the same full stack (diagnose.py gained --lapse-map), p2f seeds 0/1/2 and studt seed 0.
"""
import os

import pandas as pd

import kit_common as K

NAME = "b46_av19_studt_stack"
STK = "_cal2021_smap_shufc8_lmap"
BASE = "models/g80lm_lmap_s{}" + STK
NEW = "models/av19_s0" + STK
DBASE = "models/av19_p2fden" + STK
DNEW = "models/av19_studtden" + STK
TOL = 0.0009
SHAPE = "models/av19_shape_{}.csv"   # scripts/diagnose.py output with the full stack (scripts/gpu_av19_shape.sh)


def judge(d_nmtx, shape_worse, d_den):
    """d_nmtx = studt minus p2f NM/TX mean skill15; shape_worse = list of WORSE shape metrics; d_den = Denver gain. None = missing."""
    if d_nmtx is None or shape_worse is None or d_den is None:
        return "INCOMPLETE (" + ", ".join(n for n, v in (("NM/TX headline", d_nmtx), ("shape", shape_worse), ("Denver", d_den)) if v is None) + " missing)"
    if "event_cov_gap" in shape_worse:
        return "KILL (event-coverage gap still worse beyond its tolerance)"
    if d_nmtx >= -TOL and not shape_worse and d_den >= 0.01:
        return f"PASS (NM/TX {d_nmtx:+.4f}, shape PASS, Denver {d_den:+.4f})"
    return (f"MISS (record, no adoption; NM/TX {d_nmtx:+.4f} (needs >= -{TOL}), shape worse: {', '.join(shape_worse) or 'none'}, "
            f"Denver {d_den:+.4f} (needs >= 0.01))")


def headline(base, new, label, lines):
    from compare_headline import compare
    if not (os.path.exists(base + "_headline.csv") and os.path.exists(new + "_headline.csv")):
        lines.append(f"{label}: headline missing")
        return None
    t, m = compare(pd.read_csv(base + "_headline.csv"), pd.read_csv(new + "_headline.csv"))
    d = m["mean_skill15_new"] - m["mean_skill15_base"]
    w = t[(t.skill_flag == "WORSE") | (t.cov_flag == "WORSE")]
    lines.append(f"{label}: mean skill15_unknown {m['mean_skill15_base']:+.4f} -> {m['mean_skill15_new']:+.4f} ({d:+.4f}); mean |cov99-0.99| "
                 f"{m['mean_abs_cov_dev_base']:.4f} -> {m['mean_abs_cov_dev_new']:.4f}; bands worse (report only): "
                 + (", ".join(f"{r.var} {r.band}" for r in w.itertuples()) or "none"))
    lines.append("  per band d skill15: " + "; ".join(f"{r.var} {r.band} {r.d_skill15:+.4f}{' ' + r.skill_flag if r.skill_flag else ''}" for r in t.itertuples()))
    return d


def main():
    from compare_shape import compare as shape
    lines = []
    d_nmtx = headline(BASE.format(0), NEW, "NM/TX seed 0 (studt stack vs p2f stack)", lines)
    worse = None
    files = [SHAPE.format("p2f_s0"), SHAPE.format("studt_s0"), SHAPE.format("p2f_s1"), SHAPE.format("p2f_s2")]
    if all(os.path.exists(f) for f in files):
        t = shape(files[0], files[1], files[2:])
        worse = list(t.metric[t.flag == "WORSE"])
        lines.append("Shape (tolerance = p2f stack seed spread, seeds 1/2):")
        lines += ["  " + s for s in t.round(4).to_string(index=False).splitlines()]
    else:
        lines.append("Shape: diag missing")
    d_den = headline(DBASE, DNEW, "Denver zero-shot seed 0 (studt stack vs p2f stack)", lines)
    lines.append("AV19 rule (pre-set): PASS = NM/TX within -0.0009, shape not FAIL, Denver gain >= 0.01; KILL = event_cov_gap WORSE; else MISS.")
    lines.append("AV19 verdict: " + judge(d_nmtx, worse, d_den))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.0, [], 0.02).startswith("PASS")
    assert judge(-0.0005, [], 0.01).startswith("PASS")
    assert judge(-0.002, [], 0.02).startswith("MISS")
    assert judge(0.0, ["vcorr_err"], 0.02).startswith("MISS")
    assert judge(0.0, [], 0.005).startswith("MISS")
    assert judge(0.0, ["event_cov_gap"], 0.02).startswith("KILL")
    assert judge(None, [], 0.02).startswith("INCOMPLETE")


_selfcheck()
if __name__ == "__main__":
    main()
