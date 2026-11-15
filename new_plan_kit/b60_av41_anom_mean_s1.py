"""New_Plan 13 AV41 (third of the AV21 line, a replicate): AV40 retrained on training seed 100. AV40 (MISS 2026-11-14 19:08: NM/TX +0.0004 vs p2f,
Denver fill-top -0.1918 -> -0.0150, both passing; shape FAIL on preclip_rate alone, 0.0256 -> 0.0266, +0.0010 vs seed noise 0.0005, worst RH 5-12 km;
vcorr_err better) may have failed the shape check on seed luck. AV41 = configs/generator_av41.toml (generator_av40 with seed = 100, as p2f_s1), same
training, range calibration 2021-23, scoring 2024-25 (m 199, --extras), compared with the seed-100 baseline p2f_s1
(models/generator_80_p2f_s1_cal2021_headline.csv, models/generator_80_p2f_s1_shape_diag.csv; shape seed noise from p2f seeds 0 / 200).
Denver zero-shot as AV40 (table refitted on Denver rows <= 2020 by scripts/av21_table.py, NM/TX calibration re-tagged), vs p2f on the fill-top set (-0.1918).
Runner scripts/gpu_av41.sh. mean skill15 = scripts/compare_headline.compare (kind unknown), as every L3 verdict.
Rule written 2026-11-14 19:27 before any AV41 run (New_Plan 13 AV41 row, unchanged; AV40 rule with the seed-100 baseline):
PASS: Denver zero-shot at or above -0.088 with NM/TX within 0.0009 (mean skill15 >= p2f_s1 - 0.0009) and shape vs p2f_s1 not FAIL.
KILL: NM/TX worse than p2f_s1 by more than 0.0015.
Otherwise MISS: record, no adoption (a model change needs the user in any case).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b60_av41_anom_mean_s1.py
Result: docs/results/logs/kit_b60_av41_anom_mean_s1.log
"""
import os
import subprocess
import sys

import pandas as pd

import kit_common as K

NAME = "b60_av41_anom_mean_s1"
TOL, KILL_TOL, DEN_MIN = 0.0009, 0.0015, -0.088
MD = os.path.join(K.REPO, "models")


def judge(d_nmtx, shape_fail, den):
    if d_nmtx < -KILL_TOL:
        return f"KILL (NM/TX {d_nmtx:+.4f} vs p2f_s1, worse than -{KILL_TOL})"
    if den >= DEN_MIN and d_nmtx >= -TOL and not shape_fail:
        return f"PASS (Denver {den:+.4f} >= {DEN_MIN}, NM/TX {d_nmtx:+.4f} vs p2f_s1, shape not FAIL)"
    return (f"MISS (Denver {den:+.4f} (needs >= {DEN_MIN}), NM/TX {d_nmtx:+.4f} vs p2f_s1 (needs >= -{TOL}), "
            f"shape {'FAIL' if shape_fail else 'not FAIL'})")


def main():
    from compare_headline import compare
    p = lambda n: os.path.join(MD, n)   # noqa: E731
    lines = ["AV41 = AV40 (climatology mean only) on training seed 100, vs p2f_s1 (Denver table swapped, scripts/av21_table.py)"]
    _, s_n = compare(pd.read_csv(p("generator_80_p2f_s1_cal2021_headline.csv")), pd.read_csv(p("av41_cal2021_headline.csv")), tol=TOL)
    d_nmtx = s_n["mean_skill15_new"] - s_n["mean_skill15_base"]
    lines.append(f"  NM/TX mean skill15: p2f_s1 {s_n['mean_skill15_base']:+.4f}, AV41 {s_n['mean_skill15_new']:+.4f} ({d_nmtx:+.4f})")
    run = subprocess.run([sys.executable, os.path.join(K.REPO, "scripts", "compare_shape.py"), p("generator_80_p2f_s1_shape_diag.csv"), p("av41_shape_diag.csv"),
                         "--noise", p("generator_80_p2f_shape_diag.csv"), p("generator_80_p2f_s2_shape_diag.csv")], capture_output=True, text=True)
    assert run.returncode in (0, 1), run.stderr   # compare_shape exits 1 on a shape FAIL
    sh = run.stdout
    res = [ln for ln in sh.splitlines() if ln.startswith("SHAPE RESULT")]
    assert len(res) == 1, sh
    lines += ["  shape vs p2f_s1:"] + ["    " + ln for ln in sh.splitlines()[-6:]]
    t_d, s_d = compare(pd.read_csv(p("l3_braw_fill_cal2021_headline.csv")), pd.read_csv(p("av41_denfill_cal2021_headline.csv")))
    lines.append(f"  Denver fill-top zero-shot mean skill15: p2f {s_d['mean_skill15_base']:+.4f}, AV41 {s_d['mean_skill15_new']:+.4f} "
                 f"(AV40 was -0.0150, AV21 -0.0007; rule line {DEN_MIN})")
    lines.append("  Denver per band (p2f -> AV41 skill15):")
    lines += [f"    {r['var']:<4} {r['band']:<9} {r.skill15_base:+.3f} -> {r.skill15_new:+.3f} ({r.d_skill15:+.3f})" for _, r in t_d.iterrows()]
    lines.append(f"AV41 rule (pre-set): PASS = Denver >= {DEN_MIN} with NM/TX >= p2f_s1 - {TOL} and shape vs p2f_s1 not FAIL; KILL = NM/TX < p2f_s1 - {KILL_TOL}; else MISS.")
    lines.append("AV41 verdict: " + judge(d_nmtx, res[0].startswith("SHAPE RESULT: FAIL"), s_d["mean_skill15_new"]))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.0, False, -0.05).startswith("PASS")
    assert judge(-0.0009, False, -0.088).startswith("PASS")
    assert judge(-0.001, False, -0.05).startswith("MISS")
    assert judge(0.0, True, -0.05).startswith("MISS")
    assert judge(0.0, False, -0.09).startswith("MISS")
    assert judge(-0.0016, False, -0.01).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
