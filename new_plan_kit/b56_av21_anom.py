"""New_Plan 13 AV21: learn in anomaly space (L3-8, SAMOS) instead of debiasing afterwards (L3-34 / L3-48: Denver -0.1918 -> -0.0253 with the logit fix).
The p2f network (configs/generator_p2f.toml) with anom_clim = true (configs/generator_av21.toml): its output is read as a standardised anomaly z and mapped to
(mu + sd z) of a per-grid-point harmonic climatology (constant + 3 annual + 2 diurnal harmonics, mean and log-spread, fitted on training rows only;
tempest/generator/model.py anom). Same training, range calibration 2021-23 and scoring 2024-25 (m 199, --extras) as p2f.
Denver zero-shot: the same network with the table refitted on Denver rows <= 2020 (scripts/av21_table.py), scored on the fill-top set with the NM/TX
calibration, vs p2f on the same set (models/l3_braw_fill_cal2021_headline.csv, -0.1918). Runner scripts/gpu_av21.sh.
mean skill15 = scripts/compare_headline.compare (kind unknown), as every L3 verdict.
Rule written 2026-11-14 before any AV21 run (New_Plan 13 AV21 row, unchanged):
PASS: Denver zero-shot at or above -0.088 (half the gap) with NM/TX within 0.0009 (mean skill15 >= p2f - 0.0009) and shape not FAIL.
KILL: NM/TX worse by more than 0.0015.
Otherwise MISS: record, no adoption (a model change needs the user in any case).
Correction 2026-11-14 15:10 (reading the result only, rule unchanged): compare_shape.py exits 1 on a shape FAIL, which check=True turned into a crash
(AV20 first verdict run 15:01:53); the exit code 0 / 1 is now accepted and the SHAPE RESULT line is read as before.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b56_av21_anom.py
Result: docs/results/logs/kit_b56_av21_anom.log
"""
import os
import subprocess
import sys

import pandas as pd

import kit_common as K

NAME = "b56_av21_anom"
TOL, KILL_TOL, DEN_MIN = 0.0009, 0.0015, -0.088
MD = os.path.join(K.REPO, "models")


def judge(d_nmtx, shape_fail, den):
    if d_nmtx < -KILL_TOL:
        return f"KILL (NM/TX {d_nmtx:+.4f} vs p2f, worse than -{KILL_TOL})"
    if den >= DEN_MIN and d_nmtx >= -TOL and not shape_fail:
        return f"PASS (Denver {den:+.4f} >= {DEN_MIN}, NM/TX {d_nmtx:+.4f} vs p2f, shape not FAIL)"
    return (f"MISS (Denver {den:+.4f} (needs >= {DEN_MIN}), NM/TX {d_nmtx:+.4f} vs p2f (needs >= -{TOL}), "
            f"shape {'FAIL' if shape_fail else 'not FAIL'})")


def main():
    from compare_headline import compare
    p = lambda n: os.path.join(MD, n)   # noqa: E731
    lines = ["AV21 anomaly-space generator (p2f + anom_clim: per-point harmonic climatology mean / spread; Denver table swapped, scripts/av21_table.py)"]
    _, s_n = compare(pd.read_csv(p("generator_80_p2f_cal2021_headline.csv")), pd.read_csv(p("av21_cal2021_headline.csv")), tol=TOL)
    d_nmtx = s_n["mean_skill15_new"] - s_n["mean_skill15_base"]
    lines.append(f"  NM/TX mean skill15: p2f {s_n['mean_skill15_base']:+.4f}, AV21 {s_n['mean_skill15_new']:+.4f} ({d_nmtx:+.4f})")
    run = subprocess.run([sys.executable, os.path.join(K.REPO, "scripts", "compare_shape.py"), p("generator_80_p2f_shape_diag.csv"), p("av21_shape_diag.csv"),
                         "--noise", p("generator_80_p2f_s1_shape_diag.csv"), p("generator_80_p2f_s2_shape_diag.csv")], capture_output=True, text=True)
    assert run.returncode in (0, 1), run.stderr   # compare_shape exits 1 on a shape FAIL
    sh = run.stdout
    res = [ln for ln in sh.splitlines() if ln.startswith("SHAPE RESULT")]
    assert len(res) == 1, sh
    lines += ["  shape vs p2f:"] + ["    " + ln for ln in sh.splitlines()[-6:]]
    t_d, s_d = compare(pd.read_csv(p("l3_braw_fill_cal2021_headline.csv")), pd.read_csv(p("av21_denfill_cal2021_headline.csv")))
    lines.append(f"  Denver fill-top zero-shot mean skill15: p2f {s_d['mean_skill15_base']:+.4f}, AV21 {s_d['mean_skill15_new']:+.4f} "
                 f"(L3-34 debias was -0.0253; rule line {DEN_MIN})")
    lines.append("  Denver per band (p2f -> AV21 skill15):")
    lines += [f"    {r['var']:<4} {r['band']:<9} {r.skill15_base:+.3f} -> {r.skill15_new:+.3f} ({r.d_skill15:+.3f})" for _, r in t_d.iterrows()]
    lines.append(f"AV21 rule (pre-set): PASS = Denver >= {DEN_MIN} with NM/TX >= p2f - {TOL} and shape not FAIL; KILL = NM/TX < p2f - {KILL_TOL}; else MISS.")
    lines.append("AV21 verdict: " + judge(d_nmtx, res[0].startswith("SHAPE RESULT: FAIL"), s_d["mean_skill15_new"]))
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
