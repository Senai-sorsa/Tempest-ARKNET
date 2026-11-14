"""New_Plan 13 AV20: L3-4 SIREN location encoding (not adopted: NM/TX PASS + shape PASS, Denver fill-top -0.1562 vs p2f -0.1918, but Denver T 12-18 km
-0.02 -> -0.33) PLUS the L3-7 climatology inputs, extended to the upper air (scripts/av20_overlay.py on the l3x overlay: l3x clim means t2m, rh2m, T / RH 3 km,
u / v 5 km, and new: mean T 9 / 12 / 15 / 18 km, sd T 3 / 12 / 15 km, tropopause height of the mean profile, mean / sd u 12 km; per grid point x month,
years <= 2020 only; terrain and clock columns ignored). Config configs/generator_av20.toml = generator_l3_siren.toml + those inputs; same training,
range calibration 2021-23, scoring 2024-25 (m 199, --extras) as L3-4 (scripts/ap_l3.sh, scripts/ap_l3_fill.sh). Runner scripts/gpu_av20.sh.
Scores used: NM/TX models/av20_cal2021_headline.csv vs models/generator_80_p2f_cal2021_headline.csv; shape models/av20_shape_diag.csv vs p2f (seed noise s1/s2);
Denver zero-shot on the fill-top set models/av20_denfill_cal2021_headline.csv vs SIREN alone models/l3_siren_denfill_cal2021_headline.csv (-0.1562).
mean skill15 = scripts/compare_headline.compare (kind unknown), as every L3 verdict.
Rule written 2026-11-14 before any AV20 run (New_Plan 13 AV20 row, unchanged):
PASS: NM/TX within 0.0009 (mean skill15 >= p2f - 0.0009) and shape not FAIL; Denver zero-shot better than SIREN alone (-0.156 on the fill-top set)
      with T 12-18 km (skill15) not below -0.05.
KILL: Denver T 12-18 km still below -0.15.
Otherwise MISS: record, no adoption (a new input set is a model change and needs the user in any case).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b55_av20_siren_clim.py
Result: docs/results/logs/kit_b55_av20_siren_clim.log
"""
import os
import subprocess
import sys

import pandas as pd

import kit_common as K

NAME = "b55_av20_siren_clim"
TOL = 0.0009
MD = os.path.join(K.REPO, "models")


def judge(d_nmtx, shape_fail, den, den_siren, t_upper):
    if t_upper < -0.15:
        return f"KILL (Denver T 12-18 km {t_upper:+.3f} still below -0.15)"
    if d_nmtx >= -TOL and not shape_fail and den > den_siren and t_upper >= -0.05:
        return f"PASS (NM/TX {d_nmtx:+.4f} vs p2f, shape not FAIL, Denver {den:+.4f} vs SIREN {den_siren:+.4f}, T 12-18 km {t_upper:+.3f})"
    return (f"MISS (NM/TX {d_nmtx:+.4f} vs p2f (needs >= -{TOL}), shape {'FAIL' if shape_fail else 'not FAIL'}, Denver {den:+.4f} vs SIREN {den_siren:+.4f} "
            f"(needs better), T 12-18 km {t_upper:+.3f} (needs >= -0.05))")


def main():
    from compare_headline import compare
    p = lambda n: os.path.join(MD, n)   # noqa: E731
    lines = ["AV20 SIREN + climatology inputs (l3x clim + upper-air T / tropopause / u 12 km, scripts/av20_overlay.py)"]
    t_n, s_n = compare(pd.read_csv(p("generator_80_p2f_cal2021_headline.csv")), pd.read_csv(p("av20_cal2021_headline.csv")), tol=TOL)
    d_nmtx = s_n["mean_skill15_new"] - s_n["mean_skill15_base"]
    lines.append(f"  NM/TX mean skill15: p2f {s_n['mean_skill15_base']:+.4f}, AV20 {s_n['mean_skill15_new']:+.4f} ({d_nmtx:+.4f}; SIREN alone was +0.0278)")
    sh = subprocess.run([sys.executable, os.path.join(K.REPO, "scripts", "compare_shape.py"), p("generator_80_p2f_shape_diag.csv"), p("av20_shape_diag.csv"),
                         "--noise", p("generator_80_p2f_s1_shape_diag.csv"), p("generator_80_p2f_s2_shape_diag.csv")], capture_output=True, text=True, check=True).stdout
    res = [ln for ln in sh.splitlines() if ln.startswith("SHAPE RESULT")]
    assert len(res) == 1, sh
    lines += ["  shape vs p2f:"] + ["    " + ln for ln in sh.splitlines()[-6:]]
    t_d, s_d = compare(pd.read_csv(p("l3_siren_denfill_cal2021_headline.csv")), pd.read_csv(p("av20_denfill_cal2021_headline.csv")))
    _, s_b = compare(pd.read_csv(p("l3_braw_fill_cal2021_headline.csv")), pd.read_csv(p("av20_denfill_cal2021_headline.csv")))
    up = t_d[(t_d["var"] == "T") & (t_d["band"] == "12-18 km")]
    assert len(up) == 1
    t_up, t_up_siren = float(up.skill15_new.iloc[0]), float(up.skill15_base.iloc[0])
    lines.append(f"  Denver fill-top zero-shot mean skill15: p2f {s_b['mean_skill15_base']:+.4f}, SIREN {s_d['mean_skill15_base']:+.4f}, AV20 {s_d['mean_skill15_new']:+.4f}; "
                 f"T 12-18 km SIREN {t_up_siren:+.3f} -> AV20 {t_up:+.3f}")
    lines.append("  Denver per band (SIREN -> AV20 skill15):")
    lines += [f"    {r['var']:<4} {r['band']:<9} {r.skill15_base:+.3f} -> {r.skill15_new:+.3f} ({r.d_skill15:+.3f})" for _, r in t_d.iterrows()]
    lines.append("AV20 rule (pre-set): PASS = NM/TX >= p2f - 0.0009, shape not FAIL, Denver better than SIREN with T 12-18 km >= -0.05; KILL = Denver T 12-18 km < -0.15; else MISS.")
    lines.append("AV20 verdict: " + judge(d_nmtx, res[0].startswith("SHAPE RESULT: FAIL"), s_d["mean_skill15_new"], s_d["mean_skill15_base"], t_up))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.0, False, -0.15, -0.156, -0.04).startswith("PASS")
    assert judge(-0.001, False, -0.15, -0.156, -0.04).startswith("MISS")
    assert judge(0.0, True, -0.15, -0.156, -0.04).startswith("MISS")
    assert judge(0.0, False, -0.16, -0.156, -0.04).startswith("MISS")
    assert judge(0.0, False, -0.15, -0.156, -0.06).startswith("MISS")
    assert judge(0.01, False, -0.10, -0.156, -0.16).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
