"""New_Plan 17 UR15 + UR13: the forecast-mode verdicts again, each with its OWN rule unchanged, on the 2023-24 rows of scripts/ur15_opendata.py
(ECMWF open data, 00Z starts, leads 1 / 3 / 5 / 7 / 9 d; scored by scripts/cpu_ur15_eval.sh: <stem>_tf2324_{eval.csv,rows.npz}). 21-day blocks.
  --gate   the sanity gate set in ur15_opendata.py before any result: the raw forecast error (mean |forecast - ERA5| over all columns) must grow
           with lead in the 2023-24 rows and its lead-bin-1 size must be within 30 % of the 2022 WB2 rows' (data/modeF_v2{,_denver}/2022.npz).
           If the gate fails, no verdict below is read (the input world moved: 9 levels, 0.4 deg).
Families (rule of each, unchanged):
  UR13 / AV24  chorus_new (plain rows) vs av24_mix (mixed rows: the 12Z run 36 h older, as stage 1): CHORUS stage 1's rule
               (b9_chorus_stage1.judge): PASS = interval < 0 at 5 and 7 d and mix / newest <= 1.005 at 1 and 3 d in all 4 box x seed; KILL = no lead better.
  AV29         ft500 vs own500, seeds 0-2: AV28's rule (b17.judge): PASS = interval < 0 at >= 3 of 4 leads in all 6 runs; KILL = <= 1 in 3 or more runs.
  SIGMA        vs binned: N5's leads-1-7 clause (within +0.5 % at every lead) and, at day 9 only (the one long lead fetched), better than binned
               with the interval below 0 (the 8 / 10 d and the climate-model clauses cannot be tested here).
  NEST         vs binned: N6's rule (>= 1 % better at every lead with interval < 0, both boxes and seeds, cov99 within 0.003 of binned); also shown:
               UR1's form (cov99 within 0.005 of 0.99).
  UR2 stage 3  ur2_ftnest vs NEST, seeds 0-2 (if scored): UR2's stage rule without the coverage clause (mean of leads <= -0.5 % with interval < 0,
               no lead worse by > 0.5 %), information unless UR2 stage 3 was KEPT on 2021-22.
Bands (set 2026-11-13 before any result, after the end-to-end check of the row builder): every score, interval and the gate use the 12 cells
BELOW 12 km (u, v, T, RH x 0-1 / 1-5 / 5-12 km). The open data has no 150 / 100 hPa level, so 12-18 km is interpolated from 200 to 50 hPa across
the tropopause (one sample day: T 12-18 km 1-d error 3.4 K vs 0.5 K in the WB2 rows; below 12 km 0.6-1.5 K vs 0.4-1.1 K). 12-18 km is printed as
information only. Rows files need crps16 (il6_modeF.py --save-cell-rows, set by cpu_ur15_eval.sh).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b37_ur15_third_period.py [--gate]
Result: docs/results/logs/kit_b37_ur15_third_period.log
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K
from b9_chorus_stage1 import judge as judge_av24
from b17_av28_ft500 import judge as judge_av29
from b26_ur2_stack import lead_mean_ci
from ur_common import METHOD, NEAR, M, paired

NAME = "b37_ur15_third_period"
SUF = "_tf2324"


TOP = "12-18 km"


def keep_cells():
    from tempest.forecast import modeP as P
    return np.array([b != TOP for _, b, _ in P.names()])


def rows(stem):
    """per-row CRPS over the 12 cells below 12 km (from crps16)."""
    p = os.path.join(M, stem + SUF + "_rows.npz")
    if not os.path.exists(p):
        return None
    z = np.load(p)
    assert "crps16" in z.files, f"{p} lacks crps16: re-score with il6_modeF.py --save-cell-rows"
    return {"lead": z["lead"], "day": z["day"], "crps": z["crps16"][:, keep_cells()].mean(1)}


def by_lead(stem, col="crps", top=False):
    t = pd.read_csv(os.path.join(M, stem + SUF + "_eval.csv"))
    t = t[(t.method == METHOD) & ((t.band == TOP) if top else (t.band != TOP))]
    return t.groupby("lead")[col].mean().reindex(list(NEAR)).values


def gate(lines):
    from tempest.forecast.modeF import lead_bin
    ok = True
    for box, b, dn in (("NM/TX", "nmtx", ""), ("Denver", "denver", "_denver")):
        p = os.path.join(K.REPO, f"data/ur15_{b}_od/2324.npz")
        if not os.path.exists(p):
            lines.append(f"  gate {box}: rows missing")
            ok = False
            continue
        from tempest.forecast.modeF import HEIGHTS
        low = np.asarray(HEIGHTS) < 12000                                     # the gate, like the scores, below 12 km
        d, w = np.load(p), np.load(os.path.join(K.REPO, f"data/modeF_v2{dn}/2022.npz"))
        err = lambda x, L: np.abs(x["hres"][lead_bin(x["lead_days"]) == L][..., low] - x["obs"][lead_bin(x["lead_days"]) == L][..., low]).mean()
        w = {k: w[k] for k in ("hres", "obs", "lead_days", "start_hour", "valid_utc_hour")}
        same = (w["start_hour"] == 0) & (w["valid_utc_hour"] == 0)                     # like with like: the open-data rows are 00Z starts at 00Z valid times
        w = {k: v[same] for k, v in w.items()}
        e, e22 = [err(d, L) for L in NEAR], err(w, 1)
        grows, near = bool(np.all(np.diff(e) > 0)), abs(e[0] / e22 - 1) <= 0.30
        ok &= grows and near
        lines.append(f"  gate {box}: 2023-24 error below 12 km by lead {NEAR} " + " / ".join(f"{x:.3f}" for x in e) + f" (grows: {grows}); 2022 WB2 lead 1 {e22:.3f} "
                     f"(ratio {e[0] / e22:.2f}, within 30 %: {near})")
    lines.append("  gate: " + ("PASS (verdicts below may be read)" if ok else "FAIL (the input world moved: no verdict below is read)"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    lines = ["UR15 third period 2023-24 (ECMWF open data, 00Z starts, leads 1 / 3 / 5 / 7 / 9 d)"]
    if not gate(lines) or a.gate:
        K.report(NAME, lines)
        return
    boxes = (("NM/TX", ""), ("Denver", "_den"))
    # UR13 / AV24
    ratio, below = {}, {}
    for box, tag in boxes:
        for s, sfx in ((0, ""), (1, "_s1")):
            A, B = rows(f"av24_mix{tag}{sfx}"), rows(f"chorus_new{tag}{sfx}")
            if A is None or B is None:
                continue
            per = [paired(A, B, L) for L in NEAR]
            ratio[(box, s)], below[(box, s)] = [1 + p[0] / 100 for p in per], [p[3] < 0 for p in per]
            lines.append(f"  AV24 {box} s{s}: mix / newest " + ", ".join(f"{L}d {p[0]:+.2f} % [{p[2]:+.4f}, {p[3]:+.4f}]" for L, p in zip(NEAR, per)))
    lines.append("  UR13 / AV24 verdict: " + (judge_av24(ratio, below) if len(ratio) == 4 else f"incomplete ({len(ratio)} of 4 runs)"))
    # AV29
    wins = {}
    for box, tag in boxes:
        for s in (0, 1, 2):
            A, B = rows(f"modeF_n2ft500{tag}_s{s}"), rows(f"modeF_n2own500{tag}_s{s}")
            if A is None or B is None:
                continue
            per = [paired(A, B, L) for L in NEAR]
            wins[(box, s)] = sum(p[3] < 0 for p in per)
            lines.append(f"  AV29 {box} s{s}: ft500 / own500 " + ", ".join(f"{L}d {p[0]:+.2f} %" for L, p in zip(NEAR, per)) + f"; wins {wins[(box, s)]} of 4")
    lines.append("  AV29 verdict: " + (judge_av29(wins) if len(wins) == 6 else f"incomplete ({len(wins)} of 6 runs)"))
    # SIGMA and NEST vs binned
    sig_ok, sig9_ok, nest_ok, nest_ur1, n = True, True, True, True, 0
    for box, tag in boxes:
        for s in (0, 1):
            st = {k: f"modeF_n5_{k}{tag}_s{s}" for k in ("bin", "sig", "nest")}
            if not all(os.path.exists(os.path.join(M, v + SUF + "_eval.csv")) for v in st.values()):
                continue
            n += 1
            cb, cs, cn = (by_lead(v) for v in st.values())
            vb, vn = by_lead(st["bin"], "cov99"), by_lead(st["nest"], "cov99")
            Rb, Rn = rows(st["bin"]), rows(st["nest"])
            iv = [paired(Rn, Rb, L)[3] < 0 for L in NEAR]
            sig_ok &= bool(np.all(cs / cb - 1 <= 0.005))
            nest_ok &= bool(np.all(cn / cb <= 0.99) and all(iv) and np.all(np.abs(vn - vb) <= 0.003))
            nest_ur1 &= bool(np.all(np.abs(vn - 0.99) <= 0.005))
            Rs = rows(st["sig"])
            d9 = paired(Rs, Rb, 9) if (Rb["lead"] == 9).any() else None             # day 9: the one beyond-7.5 d lead fetched
            sig9_ok = bool(sig9_ok and d9 is not None and d9[3] < 0)
            lines.append(f"  {box} s{s}: SIGMA / binned " + " / ".join(f"{100 * (x - 1):+.1f}" for x in cs / cb) + " %" + (f" (9 d {d9[0]:+.1f} % [{d9[2]:+.3f}, {d9[3]:+.3f}])" if d9 else "")
                         + "; NEST / binned " + " / ".join(f"{100 * (x - 1):+.1f}" for x in cn / cb)
                         + " %; cov99 binned " + "/".join(f"{x:.3f}" for x in vb) + " NEST " + "/".join(f"{x:.3f}" for x in vn)
                         + "; 12-18 km (information) SIGMA / NEST vs binned " + " / ".join(f"{100 * (a_ / b_ - 1):+.1f}" for a_, b_ in zip(by_lead(st["sig"], top=True), by_lead(st["bin"], top=True)))
                         + " | " + " / ".join(f"{100 * (a_ / b_ - 1):+.1f}" for a_, b_ in zip(by_lead(st["nest"], top=True), by_lead(st["bin"], top=True))) + " %")
    if n == 4:
        lines.append(f"  SIGMA (N5 leads 1-7 clause): {'holds' if sig_ok else 'fails'}; SIGMA at 9 d better than binned (interval < 0): {'holds' if sig9_ok else 'fails'}; "
                     f"NEST (N6 rule): {'PASS' if nest_ok else 'not passed'}; NEST cov99 in UR1's form: {'holds' if nest_ur1 else 'fails'}")
    else:
        lines.append(f"  SIGMA / NEST: incomplete ({n} of 4 runs)")
    # UR2 stage 3 (information unless KEPT on 2021-22)
    for box, tag in boxes:
        for s in (0, 1, 2):
            A, B = rows(f"ur2_ftnest{tag}_s{s}"), rows(f"modeF_n5_nest{tag}_s{s}")
            if A is None or B is None:
                continue
            m, lo, hi = lead_mean_ci(A, B)
            lines.append(f"  UR2 stage 3 {box} s{s}: world start + 500 vs NEST, mean of leads {m:+.2f} % [{lo:+.2f}, {hi:+.2f}]; worst lead {max(paired(A, B, L)[0] for L in NEAR):+.2f} %")
    K.report(NAME, lines)


if __name__ == "__main__":
    main()
