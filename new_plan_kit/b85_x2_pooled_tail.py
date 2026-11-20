"""New_Plan 29.5 X2 / 27.3: ONE pooled 2021 + 2022 tail table per box and seed on the ur2_ftnest members (SIGMA + NEST + world start + 500, PIT recal),
judged on the 2023-24 members (scripts/cpu_x2_ftnest_members.sh -> data/kit/ur_members/ftnest<tag>_s<seed>_tf2324.npz). No training. The table is
fitted on 2021 and 2022 only (27.6 guard); 2023-24 is the verdict period. Tool: tempest/forecast/tailcal.py (members inside the 90 % range do not move).
Fit files (UR2 stage 3): ftnest<tag>_s<S>_y2022.npz (test 2022) and ftnest<tag>_s<S>_y2022_y2021.npz (test 2021).

Pre-set rule (written 2026-11-19 before any result; New_Plan 29.5 X2). Per box (NM/TX, Denver) x seed (0, 1), leads 1 / 3 / 5 / 7 / 9 d, 16-cell means:
  PASS: cov99 within 0.005 of 0.99 at every lead, in all 4 runs; CRPS not worse than before the table by more than 0.3 % at any lead;
        largest factor difference between the 2021-only and 2022-only tables <= 0.15 (all boxes, seeds); cov90 change within 0.003 (information, not a clause).
  KILL: CRPS worse by more than 0.5 % at any lead, or a factor difference between the fit years above 0.15.   Else MISS and close.
  A PASS goes to ASK_LATER 44 as a pipeline choice (default off), never shipped by the loop.
Shrink toward 1: the tailcal fit keeps factor 1 in cells with under 200 rows and smooths across leads (as in UR1); no further shrink in the verdict arm.
Information arm (not in the verdict): the same table with half the stretch, 1 + 0.5 (f - 1).
Deviation, stated: the saved members are the PIT column (il6_modeF.py --save-members), not the no-PIT column; the tail table sets cov99 directly, and the
27.8 numbers show PIT vs no-PIT moves CRPS by under 0.05 %. Both seeds of both boxes are needed; the 2023-24 rows are a development-period re-score.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b85_x2_pooled_tail.py
Result: docs/results/logs/kit_b85_x2_pooled_tail.log
"""
import copy
import os

import numpy as np

import kit_common as K
from b25_ur1_tailcal import cov90, cov_holds
from tempest.forecast import tailcal as TC
from ur_common import BEYOND, MEM, NEAR, by_lead, load_members, score, var_of_col

NAME = "b85_x2_pooled_tail"
LEADS = NEAR + (BEYOND,)


def shrink(tab, w):
    t = copy.deepcopy(tab)
    t["lo"], t["hi"] = 1 + w * (tab["lo"] - 1), 1 + w * (tab["hi"] - 1)
    return t


def judge(runs, gaps):
    if any(np.nanmax(r["crps_pct"]) > 0.5 for r in runs) or any(g > 0.15 for g in gaps):
        return "KILL"
    return "PASS" if all(cov_holds(r["cov99_after"]) and np.nanmax(r["crps_pct"]) <= 0.3 for r in runs) else "MISS (record, no adoption)"


def quant(path, vc):
    d = load_members(path)
    return TC.quantiles(d["x"]), d["truth"], d["lead"]


def main():
    vc = var_of_col()
    lines = ["X2: pooled 2021 + 2022 tail table on ftnest members, judged on 2023-24; mean over 16 cells by lead " + str(LEADS)]
    runs, gaps, missing = [], [], []
    for box, tag in (("NM/TX", ""), ("Denver", "_den")):
        for s in (0, 1):
            fit = [os.path.join(MEM, f"ftnest{tag}_s{s}_y2022{x}.npz") for x in ("", "_y2021")]
            jp = os.path.join(MEM, f"ftnest{tag}_s{s}_tf2324.npz")
            if not all(os.path.exists(p) for p in fit + [jp]):
                missing.append(f"{box} s{s}")
                continue
            qs, ts, ls = zip(*(quant(p, vc) for p in fit))
            tabs = [TC.fit_from_quantiles(q, t, l, vc) for q, t, l in zip(qs, ts, ls)]
            tab = TC.fit_from_quantiles(np.concatenate(qs, 1), np.concatenate(ts), np.concatenate(ls), vc)
            g = max(float(np.abs(tabs[0][k] - tabs[1][k]).max()) for k in ("lo", "hi"))
            gaps.append(g)
            j = load_members(jp)
            c0, v0 = score(j["x"], j["truth"])
            n0, L = cov90(j["x"], j["truth"]), j["lead"]
            out = {}
            for tname, t in (("table", tab), ("half", shrink(tab, 0.5))):
                x2 = TC.apply(t, j["x"], L, vc)
                c1, v1 = score(x2, j["truth"])
                out[tname] = dict(cov99_before=by_lead(v0, L, LEADS), cov99_after=by_lead(v1, L, LEADS), crps_pct=100 * (by_lead(c1, L, LEADS) / by_lead(c0, L, LEADS) - 1),
                                  cov90_diff=by_lead(cov90(x2, j["truth"]), L, LEADS) - by_lead(n0, L, LEADS))
                del x2
            runs.append(out["table"])
            for tname, r in out.items():
                lines.append(f"  {box:<6} s{s} {tname:<5}: cov99 " + " / ".join(f"{b:.4f}->{c:.4f}" for b, c in zip(r["cov99_before"], r["cov99_after"]))
                             + "; CRPS change " + " / ".join(f"{p:+.2f}" for p in r["crps_pct"]) + " %; cov90 change " + " / ".join(f"{d:+.4f}" for d in r["cov90_diff"]))
            lines.append(f"       factors (pooled, mean over variables, by lead) lo " + " ".join(f"{x:.2f}" for x in tab["lo"].mean(1)) + " hi "
                         + " ".join(f"{x:.2f}" for x in tab["hi"].mean(1)) + f"; largest 2021-vs-2022 factor difference {g:.3f}")
            del j
    if missing:
        lines.append(f"X2 verdict: incomplete, missing {', '.join(missing)} (scripts/cpu_x2_ftnest_members.sh)")
    else:
        lines.append("X2 verdict (pre-set rule, both boxes, both seeds): " + judge(runs, gaps))
    lines.append("Rule: PASS = cov99 within 0.005 of 0.99 at every lead, CRPS <= +0.3 % at every lead, factor gap between fit years <= 0.15; KILL = CRPS > +0.5 % or gap > 0.15.")
    K.report(NAME, lines)


def _selfcheck():
    ok = dict(cov99_after=np.full(5, 0.99), crps_pct=np.zeros(5))
    assert judge([ok] * 4, [0.1] * 4) == "PASS"
    assert judge([ok] * 3 + [{**ok, "crps_pct": np.array([0, 0, 0.4, 0, 0])}], [0.1] * 4).startswith("MISS")
    assert judge([ok] * 4, [0.2] * 4) == "KILL"
    assert judge([ok] * 3 + [{**ok, "cov99_after": np.array([0.97, 0.99, 0.99, 0.99, 0.99])}], [0.1] * 4).startswith("MISS")
    t = dict(lo=np.full((2, 2), 1.4), hi=np.full((2, 2), 0.8))
    assert np.allclose(shrink(t, 0.5)["lo"], 1.2) and np.allclose(shrink(t, 0.5)["hi"], 0.9) and t["lo"][0, 0] == 1.4


_selfcheck()
if __name__ == "__main__":
    main()
