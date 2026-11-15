"""New_Plan 17 UR2: one forecast engine, stacked in a fixed order; one verdict per stage. Rows: <stem>_mem_rows.npz (2022) and
<stem>_mem_t2021_rows.npz (2021) of scripts/cpu_ur1_members.sh, gpu_ur2_stage3.sh, gpu_ur2_stage45.sh; members in data/kit/ur_members/.
    --stage 3   world start + 500 box steps (models/ur2_ftnest<tag>_s<S>)   vs NEST (models/modeF_n5_nest<tag>_s<S>)
                step 0 (report only): the world network as it is (models/ur2_wnest_s<S>_{nm,den}, 2022) vs NEST; control own NEST + 500 (information)
    --stage 4   mixed input rows (models/ur2_s4mix_<base><tag>_s<S>)        vs the kept stage on plain rows (--base nest | ft)
    --stage 5   ensemble spread scales s (models/ur2_s5_<base>_m<mix><tag>_s<S>_e1) vs the same recipe without it (_e0), same ensemble rows
Rule (set 2026-11-13 in New_Plan 17.1 before any run): a stage is KEPT if, in every box x seed run (seeds 0 / 1 / 2, both boxes; 2021 + 2022
pooled, 21-day blocks), the mean over leads 1 / 3 / 5 / 7 d of the per-lead change is at most -0.5 % with its interval below 0, no lead is worse
by more than 0.5 %, and UR1's coverage rule holds for the stage's networks (tail table fit on one year, judged on the other: cov99 within
0.005 of 0.99 at every lead, CRPS <= +0.2 %). Stage 3 KILL: not better than NEST at any lead in both boxes (the stack closes at NEST + UR1).
Otherwise NOT KEPT (the next stage is tried once on the last kept stage). Forking paths: one more forecast-mode variation on 2021-22; the final
word comes from UR15 (2024-25 rows).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b26_ur2_stack.py --stage 3 [--base nest] [--mix 0]
Result: docs/results/logs/kit_b26_ur2_stack.log
"""
import argparse
import os

import numpy as np

import kit_common as K
from ur_common import BLOCK, MEM, NEAR, M, have_rows, paired, pooled_rows

SEEDS = (0, 1, 2)
BOXES = (("NM/TX", ""), ("Denver", "_den"))
YRS = ("_mem", "_mem_t2021")


def lead_mean_ci(a, b, draws=1000, seed=0):
    """mean over NEAR leads of the per-lead percent change of a vs b, with a 21-day block interval (whole blocks resampled for all leads together)."""
    assert (a["day"] == b["day"]).all() and (a["lead"] == b["lead"]).all(), "arms scored on different rows"
    blk = b["day"] // BLOCK
    ub, inv = np.unique(blk, return_inverse=True)
    sums = {}
    for L in NEAR:
        k = b["lead"] == L
        sums[L] = tuple(np.bincount(inv[k], w, minlength=len(ub)) for w in (a["crps"][k], b["crps"][k]))
    point = np.mean([100 * (sums[L][0].sum() / sums[L][1].sum() - 1) for L in NEAR])
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(ub), (draws, len(ub)))
    boot = np.mean([100 * (sums[L][0][pick].sum(1) / sums[L][1][pick].sum(1) - 1) for L in NEAR], 0)
    return float(point), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def coverage_ok(name):
    """UR1's coverage clause on a stage's member files (<name>_y2021 / _y2022) -> (ok, text); None if the files are missing."""
    f = {y: os.path.join(MEM, f"{name}_y{y}.npz") for y in (2021, 2022)}
    if not all(os.path.exists(p) for p in f.values()):
        return None, "members missing"
    from b25_ur1_tailcal import cov_holds, one
    from ur_common import var_of_col
    vc, oks, txt = var_of_col(), [], []
    for fy, jy in ((2021, 2022), (2022, 2021)):
        _, r = one(f[fy], f[jy], vc)
        ok = bool(cov_holds(r["cov99_after"]) and np.nanmax(r["crps_pct"]) <= 0.2)
        oks.append(ok)
        txt.append(f"fit {fy}: cov99 " + "/".join(f"{x:.3f}" for x in r["cov99_after"]) + f" CRPS max {np.nanmax(r['crps_pct']):+.2f} %")
    return all(oks), "; ".join(txt)


def judge(runs, stage):
    """runs[(box, seed)] = dict(mean, hi, worst, any_better, cov_ok) -> verdict."""
    if stage == 3 and all(not any(r["any_better"] for (b, _), r in runs.items() if b == box) for box in {k[0] for k in runs}):
        return "KILL (stack closes at NEST + UR1)"
    if all(r["mean"] <= -0.5 and r["hi"] < 0 and r["worst"] <= 0.5 and r["cov_ok"] is True for r in runs.values()):
        return "KEPT"
    return "NOT KEPT (record; next stage on the last kept one)"


def arms(stage, base, mix, tag, s):
    """-> (new stem, reference stem, new member name, label)."""
    ref_base = f"modeF_n5_nest{tag}_s{s}" if base == "nest" else f"ur2_ftnest{tag}_s{s}"
    if stage == 3:
        return f"ur2_ftnest{tag}_s{s}", f"modeF_n5_nest{tag}_s{s}", f"ftnest{tag}_s{s}", "world start + 500 vs NEST"
    if stage == 4:
        return f"ur2_s4mix_{base}{tag}_s{s}", ref_base, f"s4mix_{base}{tag}_s{s}", f"mixed rows vs {base} on plain rows"
    return f"ur2_s5_{base}_m{mix}{tag}_s{s}_e1", f"ur2_s5_{base}_m{mix}{tag}_s{s}_e0", f"s5_{base}_m{mix}{tag}_s{s}_e1", "ensemble scale vs none, same rows"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, choices=(3, 4, 5), required=True)
    ap.add_argument("--base", choices=("nest", "ft"), default="nest")
    ap.add_argument("--mix", type=int, choices=(0, 1), default=0)
    a = ap.parse_args()
    lines = [f"UR2 stage {a.stage} (base {a.base}, mix {a.mix}): 2021 + 2022 pooled, {BLOCK}-day blocks; change by lead {NEAR} and mean of leads"]
    runs, missing = {}, []
    for box, tag in BOXES:
        for s in SEEDS:
            new, ref, mname, label = arms(a.stage, a.base, a.mix, tag, s)
            if not (have_rows(new, YRS) and have_rows(ref, YRS)):
                missing.append(f"{box} s{s}")
                continue
            A, B = pooled_rows(new, YRS), pooled_rows(ref, YRS)
            per = [paired(A, B, L) for L in NEAR]
            mean, lo, hi = lead_mean_ci(A, B)
            cov, ctxt = coverage_ok(mname)
            runs[(box, s)] = dict(mean=mean, hi=hi, worst=max(p[0] for p in per), any_better=any(p[3] < 0 for p in per), cov_ok=cov)
            lines.append(f"  {box:<6} s{s} {label}: " + ", ".join(f"{L}d {p[0]:+.2f} % [{p[2]:+.4f}, {p[3]:+.4f}]" for L, p in zip(NEAR, per))
                         + f"; mean of leads {mean:+.2f} % [{lo:+.2f}, {hi:+.2f}]; UR1 clause: {ctxt}")
            if a.stage == 3:
                for extra, lab in ((f"ur2_wnest_s{s}{tag or '_nm'}", "step 0, world as it is"), (f"ur2_own500nest{tag}_s{s}", "control own NEST + 500")):
                    yrs = ("",) if extra.startswith("ur2_wnest") else YRS
                    refy = ("_mem",) if extra.startswith("ur2_wnest") else YRS
                    if have_rows(extra, yrs) and have_rows(ref, refy):
                        X, R = pooled_rows(extra, yrs), pooled_rows(ref, refy)
                        lines.append(f"           {lab} (information): " + ", ".join(f"{L}d {paired(X, R, L)[0]:+.2f} %" for L in NEAR))
    if missing:
        lines.append("Incomplete, missing: " + ", ".join(missing))
    else:
        lines.append("Verdict: " + judge(runs, a.stage))
    K.report("b26_ur2_stack", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n = 4000
    b = {"lead": np.tile(list(NEAR), n // 4), "day": np.repeat(np.arange(18628, 18628 + n // 4), 4), "crps": rng.uniform(1, 3, n)}
    m, lo, hi = lead_mean_ci({**b, "crps": b["crps"] * 0.98}, b, draws=200)
    assert abs(m + 2.0) < 1e-6 and hi < 0
    good = dict(mean=-1.0, hi=-0.2, worst=0.1, any_better=True, cov_ok=True)
    keys = [(bx, s) for bx in ("A", "B") for s in SEEDS]
    assert judge({k: good for k in keys}, 4) == "KEPT"
    assert judge({k: ({**good, "cov_ok": None} if k == keys[0] else good) for k in keys}, 4).startswith("NOT KEPT")
    assert judge({k: dict(good, any_better=False, mean=0.3, hi=0.5) for k in keys}, 3).startswith("KILL")
    assert arms(4, "ft", 0, "_den", 2)[1] == "ur2_ftnest_den_s2"


_selfcheck()
if __name__ == "__main__":
    main()
