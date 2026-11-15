"""New_Plan 17 UR1 TAILCAL: fix the far tails per lead, touch nothing else (tempest/forecast/tailcal.py). No training.
Inputs: member files written by scripts/cpu_ur1_members.sh (il6_modeF.py --save-members, --stem-suffix _mem, existing networks, no retrain):
    data/kit/ur_members/<arm><tag>_s<seed>_y<year>.npz    arm = bin (N5 binned), sig (SIGMA stage 2), nest (SIGMA stage 3); tag '' NM/TX, _den Denver;
                                                          year 2022 (range map on 2021) and 2021 (range map on 2022)
Per arm x box x seed: the tail table is fitted on the 2021 members (variable x lead bin x side, pooled over heights) and judged on 2022; then the
swap (fit 2022, judge 2021). Scores as il6_modeF.py: mean over the 16 variable x band cells of CRPS and of the 99 % range coverage, by lead bin
1 / 3 / 5 / 7 / 9 (9 = beyond 7.5 d); cov90 = coverage of the members' 5-95 % range, same cells.
Step 0 (printed first): truths outside the 99 % range per variable x lead bin in the 2021 rows; under 200 in a cell -> that cell keeps factor 1
(tailcal min_rows counts rows, so the count is printed for the reader).

Rule (set 2026-11-13 in New_Plan 17.1 before any run), per arm:
  PASS: on the judged year cov99 within 0.005 of 0.99 at every lead 1 / 3 / 5 / 7 / 9, CRPS not worse than before by more than 0.2 % at any lead,
        cov90 within 0.003 of before; in all 4 box x seed runs AND in the swap.
  KILL: CRPS worse by more than 0.5 % at any lead (any run), or a factor differs between the fit years by more than 0.15.
  Otherwise MISS. The rule judges cov99 against 0.99, not against binned: for NEST / AV2 that replaces their old clause = user's call.
Tail tables are saved to data/kit/ur1_tail_<arm><tag>_s<seed>_fit<year>.npz (for an opt-in step later).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b25_ur1_tailcal.py [--arms bin,sig,nest]
Result: docs/results/logs/kit_b25_ur1_tailcal.log
"""
import argparse
import os

import numpy as np

import kit_common as K
from tempest.forecast import tailcal as TC
from ur_common import BEYOND, MEM, NEAR, by_lead, load_members, masks, score, var_of_col

LEADS = NEAR + (BEYOND,)
NAME = "b25_ur1_tailcal"


def cov90(x, y, chunk=500):
    from tempest.scoring.score import coverage90
    w, out = masks(), np.empty(len(y))
    for i in range(0, len(y), chunk):
        s = slice(i, i + chunk)
        out[s] = (coverage90(x[s], y[s], 0.90).astype(float) @ w).mean(1)
    return out


def judge(runs, gaps):
    """runs: list of dicts per (run, direction) with cov99_after (5,), crps_pct (5,), cov90_diff (5,); gaps: max factor difference per run -> verdict."""
    if any(np.nanmax(r["crps_pct"]) > 0.5 for r in runs) or any(g > 0.15 for g in gaps):
        return "KILL"
    ok = all(cov_holds(r["cov99_after"]) and np.nanmax(r["crps_pct"]) <= 0.2 and np.nanmax(np.abs(r["cov90_diff"])) <= 0.003 for r in runs)
    return "PASS" if ok else "MISS (record, no adoption)"


def cov_holds(c):
    """cov99 within 0.005 of 0.99 at every lead that has rows (a lead without rows, e.g. day 9 on the ensemble rows, is not a failure)."""
    c = np.asarray(c, float)
    return bool(np.isfinite(c).any() and np.all(np.abs(c[np.isfinite(c)] - 0.99) <= 0.005))


def one(fit_file, judge_file, vc):
    f, j = load_members(fit_file), load_members(judge_file)
    tab = TC.fit(f["x"], f["truth"], f["lead"], vc)
    del f
    x2 = TC.apply(tab, j["x"], j["lead"], vc)
    c0, v0 = score(j["x"], j["truth"])
    c1, v1 = score(x2, j["truth"])
    n0, n1 = cov90(j["x"], j["truth"]), cov90(x2, j["truth"])
    L = j["lead"]
    r = dict(cov99_before=by_lead(v0, L, LEADS), cov99_after=by_lead(v1, L, LEADS), crps_pct=100 * (by_lead(c1, L, LEADS) / by_lead(c0, L, LEADS) - 1),
             cov90_diff=by_lead(n1, L, LEADS) - by_lead(n0, L, LEADS))
    return tab, r


def step0(path, vc):
    from tempest.scoring.score import coverage90
    d = load_members(path)
    out = ~coverage90(d["x"], d["truth"], 0.99)
    return {(L, v): int(out[d["lead"] == L][:, vc == v].sum()) for L in LEADS for v in np.unique(vc)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="bin,sig,nest")
    a = ap.parse_args()
    vc = var_of_col()
    lines = [f"UR1 TAILCAL: tail table fit on one test year, judged on the other; mean over 16 cells by lead {LEADS}"]
    for arm in a.arms.split(","):
        runs, gaps, missing = [], [], []
        for box, tag in (("NM/TX", ""), ("Denver", "_den")):
            for s in (0, 1):
                f = {y: os.path.join(MEM, f"{arm}{tag}_s{s}_y{y}.npz") for y in (2021, 2022)}
                if not all(os.path.exists(p) for p in f.values()):
                    missing.append(f"{box} s{s}")
                    continue
                if not runs:
                    cnt = step0(f[2021], vc)
                    thin = [k for k, n in cnt.items() if n < 200]
                    lines.append(f"  step 0 ({arm} {box} s{s}, 2021): truths outside the 99 % range per variable x lead: "
                                 + ", ".join(f"{v}@{L} {n}" for (L, v), n in sorted(cnt.items())) + (f"; under 200: {len(thin)} cells" if thin else ""))
                tabs = {}
                for fy, jy in ((2021, 2022), (2022, 2021)):
                    tab, r = one(f[fy], f[jy], vc)
                    tabs[fy] = tab
                    if not os.environ.get("KIT_SMOKE"):
                        TC.save(os.path.join(K.OUT, f"ur1_tail_{arm}{tag}_s{s}_fit{fy}.npz"), tab)
                    runs.append(r)
                    lines.append(f"  {arm:<4} {box:<6} s{s} fit {fy} judge {jy}: cov99 " + " / ".join(f"{b:.4f}->{c:.4f}" for b, c in zip(r["cov99_before"], r["cov99_after"]))
                                 + "; CRPS change " + " / ".join(f"{p:+.2f}" for p in r["crps_pct"]) + " %; cov90 change " + " / ".join(f"{d:+.4f}" for d in r["cov90_diff"])
                                 + "; factors lo " + " ".join(f"{x:.2f}" for x in tab["lo"].mean(1)) + " hi " + " ".join(f"{x:.2f}" for x in tab["hi"].mean(1)) + " (mean over variables, by lead)")
                g = max(float(np.abs(tabs[2021]["lo"] - tabs[2022]["lo"]).max()), float(np.abs(tabs[2021]["hi"] - tabs[2022]["hi"]).max()))
                gaps.append(g)
                lines.append(f"       largest factor difference between fit years {g:.3f}")
        if missing:
            lines.append(f"  {arm}: incomplete, missing {', '.join(missing)} (run scripts/cpu_ur1_members.sh)")
            continue
        lines.append(f"  {arm} verdict: " + judge(runs, gaps))
    lines.append("Rule (pre-set, New_Plan 17.1): PASS = cov99 within 0.005 of 0.99 at every lead, CRPS <= +0.2 %, cov90 within 0.003, all 4 runs and the swap; "
                 "KILL = CRPS > +0.5 % at any lead or a factor gap > 0.15 between fit years.")
    K.report(NAME, lines)


def _selfcheck():
    from tempest.scoring.score import coverage90
    rng = np.random.default_rng(1)
    n, m, C = 3000, 199, 4
    y = rng.standard_t(3, size=(n, C)).astype(np.float32)                    # heavy-tailed truth
    x = rng.normal(0, 1.7, size=(n, m, C)).astype(np.float32)                 # members with too-light tails (sd of t3 = 1.73)
    vc, lead = np.array(["u", "u", "T", "T"]), np.repeat([1, 3, 5], n // 3)
    tab = TC.fit(x, y, lead, vc)
    x2 = TC.apply(tab, x, lead, vc)
    c, c2 = coverage90(x, y, 0.99).mean(), coverage90(x2, y, 0.99).mean()
    assert c < 0.985 and abs(c2 - 0.99) < 0.004 and (tab["lo"] > 1).all(), (c, c2, tab["lo"])
    assert np.array_equal(coverage90(x, y, 0.90), coverage90(x2, y, 0.90)), "the scorer's 90 % range must not move"
    _, q05, q95, _ = TC.quantiles(x)
    mid = (x >= q05[:, None]) & (x <= q95[:, None])
    assert np.array_equal(x2[mid], x[mid]), "the members inside the 90 % range must not move"
    assert np.array_equal(np.argsort(x2[:5], 1, kind="stable"), np.argsort(x[:5], 1, kind="stable")), "member order must not change"
    ok = dict(cov99_after=np.full(5, 0.99), crps_pct=np.zeros(5), cov90_diff=np.zeros(5))
    assert judge([ok] * 8, [0.05] * 4) == "PASS"
    assert judge([ok] * 7 + [{**ok, "crps_pct": np.array([0, 0, 0.6, 0, 0])}], [0.05] * 4) == "KILL"
    assert judge([ok] * 8, [0.2, 0, 0, 0]) == "KILL"
    assert judge([ok] * 7 + [{**ok, "cov99_after": np.array([0.98, 0.99, 0.99, 0.99, 0.99])}], [0.05] * 4).startswith("MISS")
    assert judge([{**ok, "cov99_after": np.array([0.99, 0.99, 0.99, 0.99, np.nan])}] * 8, [0.05] * 4) == "PASS"      # a lead without rows is not a failure
    assert not cov_holds([np.nan] * 5)


_selfcheck()
if __name__ == "__main__":
    main()
