"""New_Plan 13 AV39 (second of the AV20 line): SIREN plus only the stratospheric climatology inputs. AV20 (MISS 2026-11-14 15:05: SIREN + l3x clim
+ 10 upper-air columns fixed Denver T 12-18 km -0.33 -> -0.08 but cost NM/TX 0.0025, shape FAIL, Denver low levels / sp worse) gave the network every
clim column; AV39 keeps clim_T_d12000 / d15000 / d18000 and clim_tropo only (configs/generator_av39.toml = generator_av20 with the other 12 clim columns
in ignore_inputs, on the same overlay files data/train/pilot80_dpd_av20.npz / denver_full_fill_dpd_av20.npz). Same training, range calibration 2021-23,
scoring 2024-25 (m 199, --extras) as AV20 / L3-4. Runner scripts/gpu_av39.sh.
Scores used: NM/TX models/av39_cal2021_headline.csv vs models/generator_80_p2f_cal2021_headline.csv; shape models/av39_shape_diag.csv vs p2f (seed noise s1/s2);
Denver zero-shot on the fill-top set models/av39_denfill_cal2021_headline.csv vs SIREN alone models/l3_siren_denfill_cal2021_headline.csv (-0.1562).
mean skill15 = scripts/compare_headline.compare (kind unknown), as every L3 verdict.
Rule written 2026-11-14 before any AV39 run (New_Plan 13 AV39 row, unchanged; same as AV20):
PASS: NM/TX within 0.0009 (mean skill15 >= p2f - 0.0009) and shape not FAIL; Denver zero-shot better than SIREN alone (-0.156 on the fill-top set)
      with T 12-18 km (skill15) not below -0.05.
KILL: Denver T 12-18 km still below -0.15.
Otherwise MISS: record, no adoption (a new input set is a model change and needs the user in any case).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b59_av39_siren_strat.py
Result: docs/results/logs/kit_b59_av39_siren_strat.log
"""
import os
import subprocess
import sys

import pandas as pd

import kit_common as K

NAME = "b59_av39_siren_strat"
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
    lines = ["AV39 SIREN + climatology inputs (l3x clim + upper-air T / tropopause / u 12 km, scripts/av39_overlay.py)"]
    t_n, s_n = compare(pd.read_csv(p("generator_80_p2f_cal2021_headline.csv")), pd.read_csv(p("av39_cal2021_headline.csv")), tol=TOL)
    d_nmtx = s_n["mean_skill15_new"] - s_n["mean_skill15_base"]
    lines.append(f"  NM/TX mean skill15: p2f {s_n['mean_skill15_base']:+.4f}, AV39 {s_n['mean_skill15_new']:+.4f} ({d_nmtx:+.4f}; SIREN alone was +0.0278, AV20 +0.0252)")
    run = subprocess.run([sys.executable, os.path.join(K.REPO, "scripts", "compare_shape.py"), p("generator_80_p2f_shape_diag.csv"), p("av39_shape_diag.csv"),
                         "--noise", p("generator_80_p2f_s1_shape_diag.csv"), p("generator_80_p2f_s2_shape_diag.csv")], capture_output=True, text=True)
    assert run.returncode in (0, 1), run.stderr   # compare_shape exits 1 on a shape FAIL
    sh = run.stdout
    res = [ln for ln in sh.splitlines() if ln.startswith("SHAPE RESULT")]
    assert len(res) == 1, sh
    lines += ["  shape vs p2f:"] + ["    " + ln for ln in sh.splitlines()[-6:]]
    t_d, s_d = compare(pd.read_csv(p("l3_siren_denfill_cal2021_headline.csv")), pd.read_csv(p("av39_denfill_cal2021_headline.csv")))
    _, s_b = compare(pd.read_csv(p("l3_braw_fill_cal2021_headline.csv")), pd.read_csv(p("av39_denfill_cal2021_headline.csv")))
    up = t_d[(t_d["var"] == "T") & (t_d["band"] == "12-18 km")]
    assert len(up) == 1
    t_up, t_up_siren = float(up.skill15_new.iloc[0]), float(up.skill15_base.iloc[0])
    lines.append(f"  Denver fill-top zero-shot mean skill15: p2f {s_b['mean_skill15_base']:+.4f}, SIREN {s_d['mean_skill15_base']:+.4f}, AV39 {s_d['mean_skill15_new']:+.4f}; "
                 f"T 12-18 km SIREN {t_up_siren:+.3f} -> AV39 {t_up:+.3f}")
    lines.append("  Denver per band (SIREN -> AV39 skill15):")
    lines += [f"    {r['var']:<4} {r['band']:<9} {r.skill15_base:+.3f} -> {r.skill15_new:+.3f} ({r.d_skill15:+.3f})" for _, r in t_d.iterrows()]
    lines.append("AV39 rule (pre-set): PASS = NM/TX >= p2f - 0.0009, shape not FAIL, Denver better than SIREN with T 12-18 km >= -0.05; KILL = Denver T 12-18 km < -0.15; else MISS.")
    lines.append("AV39 verdict: " + judge(d_nmtx, res[0].startswith("SHAPE RESULT: FAIL"), s_d["mean_skill15_new"], s_d["mean_skill15_base"], t_up))
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
