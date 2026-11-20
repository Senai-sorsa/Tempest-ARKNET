"""New_Plan 28.11 item 12 step 4: WD1 (b40 PASS) re-scored through the TOOL PATH: api.atmosphere_sequence with the post/ur5 table (scripts/build_ur5.py, fit
1991-2005) put into the installed assets in memory, OPTIONS["ur5_sequence"] off (= shipped) vs on. Same cells (b14 LATS x LONS), months, start hours 15 / 18 / 21 UTC,
offsets 0 / 1 / 2, n 1024, seeds 0 and 1, truth ERA5 2006-2020 as b40. Same rule as b40 (set 2026-11-15) except the "CRPS within +0.0009 of the map alone" part,
which has no tool-path arm (map alone was settled in b40). Extra report (no rule): 10 m -> 50 m shear p99 off / on, since only the 10 m level moves.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b89_wd1_tool_path.py models/ur5_wd1_shipped.npz     # ~40 min
Result: docs/results/logs/kit_b89_wd1_tool_path.log
"""
import sys

import numpy as np

import kit_common as K
from b14_strand_stage1 import LATS, LIMITS, LONS, STARTS, TEMPLATE, TRUTH, probs, windows
from b29_ur5_calm_window import SHIPPED_3H, cov90, crps_vs, era5_cells

NAME = "b89_wd1_tool_path"


def run(seed, table):
    from tempest_weather import api
    A = api._assets()
    pl = [(a, b) for a in LATS for b in LONS]
    pts, la, lo, t, U, V = era5_cells(pl)
    W = np.hypot(U, V)
    rng = np.random.default_rng(200 + seed)
    R = {L: [] for L in LIMITS}
    cv, sh = [], []
    post = A["post"]
    try:
        A["post"] = dict(post, ur5=table)
        for pi, p in enumerate(pts):
            for m in range(1, 13):
                for h in STARTS:
                    trm = t.year >= int(TRUTH[0])
                    fitm = (t.year >= int(TEMPLATE[0])) & (t.year <= int(TEMPLATE[1]))
                    if len(windows(W[pi][fitm], t[fitm], m, h)) < 100:
                        continue
                    tru = windows(W[pi][trm], t[trm], m, h)
                    if len(tru) < 100:
                        continue
                    arms = []
                    for on in (False, True):
                        api.OPTIONS["ur5_sequence"] = on
                        try:
                            atms, info = api.atmosphere_sequence(float(la[p]), float(lo[p]), f"2013-{m:02d}-15T{h:02d}:00:00+00:00", offsets=(0, 1, 2), n=1024, seed=seed, mode="ai")
                        except ValueError:
                            break
                        assert on == ("sequence-10m-wind:ur5-wd1" in info[0]["quality"]), (on, info[0]["quality"])
                        arms.append(atms)
                    if len(arms) < 2:
                        continue
                    uu = [np.stack([a["u"][:, 0] for a in x]).astype(float) for x in arms]
                    vv = [np.stack([a["v"][:, 0] for a in x]).astype(float) for x in arms]
                    w0, w1 = np.hypot(uu[0], vv[0]), np.hypot(uu[1], vv[1])
                    for L in LIMITS:
                        pr, pir = probs(tru.T, L)
                        if 0.05 <= pir <= 0.95:
                            R[L].append((pr, pir, probs(w0, L)[1], probs(w0, L)[0], probs(w1, L)[1], probs(w1, L)[0]))
                    s0 = trm & (t.month == m) & (t.hour == h)
                    eu, ev = U[pi][s0], V[pi][s0]
                    pk = rng.choice(len(eu), min(150, len(eu)), replace=False)
                    cv.append((cov90(uu[0][0], eu), cov90(uu[1][0], eu), cov90(vv[0][0], ev), cov90(vv[1][0], ev),
                               crps_vs(uu[0][0], eu[pk]), crps_vs(uu[1][0], eu[pk]), crps_vs(vv[0][0], ev[pk]), crps_vs(vv[1][0], ev[pk])))
                    sh.append([(x[1]["u"][:, 1] - x[1]["u"][:, 0], x[1]["v"][:, 1] - x[1]["v"][:, 0]) for x in arms])
    finally:
        A["post"], api.OPTIONS["ur5_sequence"] = post, True
    return {L: np.array(v) for L, v in R.items()}, np.array(cv), sh


def judge(out):
    """b40 rule without the map-alone part. out[seed] = (e per L, d (8,))."""
    ok = True
    for e, d in out.values():
        if abs(d[1] - 0.90) > 0.02 or abs(d[3] - 0.90) > 0.02 or d[5] - d[4] > 0.0009 or d[7] - d[6] > 0.0009:
            return "KILL (cov90 outside 0.88-0.92 or CRPS worse than shipped by more than 0.0009)"
        ok &= all(v["gap1"] < 0.03 and v["err"] <= 0.5 * SHIPPED_3H[L] for L, v in e.items())
        ok &= abs(d[1] - 0.90) <= abs(d[0] - 0.90) and abs(d[3] - 0.90) <= abs(d[2] - 0.90)
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    z = np.load(sys.argv[1])
    table = {k: z[k] for k in ("lat", "lon", "xt", "xe", "ok", "rho", "s")}
    K.ram_gate(4.0)
    lines = [f"WD1 through the tool path (api.atmosphere_sequence, table {sys.argv[1]}, s_u {table['s'][0]:.2f} s_v {table['s'][1]:.2f}): climate mode, 10 m wind; "
             f"truth ERA5 {TRUTH[0]}-{TRUTH[1]}, table fit {TEMPLATE[0]}-{TEMPLATE[1]}"]
    out = {}
    for seed in (0, 1):
        R, cv, sh = run(seed, table)
        e = {L: dict(gap0=np.abs(r[:, 2] - r[:, 1]).mean(), gap1=np.abs(r[:, 4] - r[:, 1]).mean(), err0=np.abs(r[:, 3] - r[:, 0]).mean(),
                     err=np.abs(r[:, 5] - r[:, 0]).mean(), n=len(r)) for L, r in R.items()}
        d = cv.mean(0)
        out[seed] = (e, d)
        for L in LIMITS:
            lines.append(f"  seed {seed} L {L:>4.0f}: {e[L]['n']} cells; per-hour gap {e[L]['gap0']:.3f} -> {e[L]['gap1']:.3f}; 3-hour error off {e[L]['err0']:.3f} -> on {e[L]['err']:.3f} "
                         f"(b40 shipped {SHIPPED_3H[L]:.3f})")
        lines.append(f"  seed {seed}: 10 m cov90 u {d[0]:.3f} -> {d[1]:.3f}, v {d[2]:.3f} -> {d[3]:.3f}; CRPS u {d[4]:.4f} -> {d[5]:.4f}, v {d[6]:.4f} -> {d[7]:.4f}")
        s_off = np.concatenate([np.hypot(*c[0]) for c in sh]) / 0.04
        s_on = np.concatenate([np.hypot(*c[1]) for c in sh]) / 0.04
        lines.append(f"  seed {seed}: 10 -> 50 m shear at hour +1 (m/s per km) p50 / p99 off {np.percentile(s_off, 50):.1f} / {np.percentile(s_off, 99):.1f}, "
                     f"on {np.percentile(s_on, 50):.1f} / {np.percentile(s_on, 99):.1f} (report only)")
    lines.append("Rule (b40, set 2026-11-15, minus the map-alone part): PASS = per-hour gap < 0.03, 3-hour error <= half of shipped, u / v cov90 in 0.88-0.92 and no farther "
                 "from 0.90 than shipped; KILL = CRPS worse than shipped by > 0.0009 or cov90 outside 0.88-0.92; both seeds, all limits.")
    lines.append("WD1 tool-path verdict: " + judge(out))
    lines.append("Port check (item 12): the tool-path numbers should match b40 (3-hour error 0.030 / 0.021 / 0.014, gap 0.045 / 0.044 / 0.026, cov90 u / v ~0.90) within seed noise; "
                 "b40 itself was a technicality MISS on the L 5 / 8 gap, taken in by the 2026-11-20 ruling (item 9).")
    K.report(NAME, lines)


if __name__ == "__main__":
    main()
