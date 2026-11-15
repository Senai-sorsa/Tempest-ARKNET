"""New_Plan 19 WD1: UR5 (speed map + regime link, b29) re-scored with its own u / v spread refit and cov90 judged by distance to 0.90. Climate mode, CPU, no training.
Same cells, seeds, template years (1991-2005) and truth years (2006-2020) as b29 step 1. After the speed map the members of each hour are scaled around their own
mean, u' = mean + s_u (u - mean), same for v; s_u and s_v are ONE number each per seed, chosen on the FIT years (ERA5 1991-2005 at the same point / month / hour)
so that the mean 5-95 % coverage over all cells is as near 0.90 as a 0.01 grid allows. The regime link and the probabilities are then computed on the refitted
members. Judged on the truth years (never 2026).
Rule (set 2026-11-15 in New_Plan 19 WD1 before any run), both seeds, all three limits L = 5 / 8 / 10 m/s:
  PASS: per-hour gap < 0.03, 3-hour error <= half of shipped (0.237 / 0.191 / 0.154), u and v 10 m cov90 inside 0.88-0.92 AND |cov90 - 0.90| not worse than shipped,
        u and v CRPS not worse than the map alone (s = 1) by more than 0.0009.
  KILL: u or v CRPS worse than shipped by more than 0.0009, or cov90 outside 0.88-0.92 after the refit.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b40_wd1_ur5_refit.py     # ~1-2 h
Result: docs/results/logs/kit_b40_wd1_ur5_refit.log
"""
import numpy as np

import kit_common as K
from b14_strand_stage1 import LIMITS, STARTS, TEMPLATE, TRUTH, LATS, LONS, probs, windows
from b29_ur5_calm_window import SHIPPED_3H, apply_map, cov90, crps_vs, era5_cells, regime_link, regime_rho, speed_map

NAME = "b40_wd1_ur5_refit"
GRID = np.round(np.arange(0.70, 1.2001, 0.01), 2)


def scale(x, s):
    """x (3, n) -> mean + s (x - mean) per hour (row)."""
    m = x.mean(1, keepdims=True)
    return m + s * (x - m)


def pick_scale(cells, key):
    """cells: list of dicts with 'mu' (hour-0 mapped members, one comp) and 'fit' (fit-year truths) -> s on GRID with mean cov90 nearest 0.90."""
    best, bs = 9.0, 1.0
    for s in GRID:
        c = np.mean([cov90(scale(c_[key][None], s)[0], c_["fit_" + key]) for c_ in cells])
        if abs(c - 0.90) < best:
            best, bs = abs(c - 0.90), float(s)
    return bs


def evaluate(cells, su, sv, seed):
    """-> (R per limit (n, 7), cv (n, 6)): same R columns as b29 step 1 with the link on the scaled members; cv = cov90 u/v shipped, refit, CRPS u/v shipped, refit."""
    rng = np.random.default_rng(300 + seed)
    R = {L: [] for L in LIMITS}
    cv = []
    for c in cells:
        mu, mv = scale(c["mapped_u"], su), scale(c["mapped_v"], sv)
        mp = np.hypot(mu, mv)
        lk = regime_link(mp, c["rc"], c["rw"], c["med"], rng)
        for L in LIMITS:
            pr, pir = probs(c["tru"].T, L)
            if not 0.05 <= pir <= 0.95:
                continue
            R[L].append((pr, pir, probs(c["seq"], L)[1], probs(c["seq"], L)[0], probs(mp, L)[1], probs(mp, L)[0], probs(lk, L)[0]))
        eu, ev, pk = c["eu"], c["ev"], c["pick"]
        cv.append((cov90(c["uu"][0], eu), cov90(mu[0], eu), cov90(c["vv"][0], ev), cov90(mv[0], ev),
                   crps_vs(c["uu"][0], eu[pk]), crps_vs(mu[0], eu[pk]), crps_vs(c["vv"][0], ev[pk]), crps_vs(mv[0], ev[pk])))
    return {L: np.array(v) for L, v in R.items()}, np.array(cv)


def collect(seed):
    from tempest_weather import api
    pl = [(a, b) for a in LATS for b in LONS]
    pts, la, lo, t, U, V = era5_cells(pl)
    W = np.hypot(U, V)
    rng = np.random.default_rng(200 + seed)
    cells = []
    for pi, p in enumerate(pts):
        ty = t.year
        for m in range(1, 13):
            for h in STARTS:
                fitm = (ty >= int(TEMPLATE[0])) & (ty <= int(TEMPLATE[1]))
                trm = ty >= int(TRUTH[0])
                tpl, tru = windows(W[pi][fitm], t[fitm], m, h), windows(W[pi][trm], t[trm], m, h)
                if len(tpl) < 100 or len(tru) < 100:
                    continue
                try:
                    atms, _ = api.atmosphere_sequence(float(la[p]), float(lo[p]), f"2013-{m:02d}-15T{h:02d}:00:00+00:00", offsets=(0, 1, 2), n=1024, seed=seed, mode="ai")
                except ValueError:
                    continue
                uu = np.stack([a["u"][:, 0] for a in atms]).astype(float)
                vv = np.stack([a["v"][:, 0] for a in atms]).astype(float)
                seq = np.hypot(uu, vv)
                mapped_u, mapped_v = np.empty_like(uu), np.empty_like(vv)
                for k in range(3):
                    sel = fitm & (t.month == m) & (t.hour == (h + k) % 24)
                    mapped_u[k], mapped_v[k] = apply_map(uu[k], vv[k], speed_map(seq[k], W[pi][sel]))
                rc, rw, med = regime_rho(tpl)
                s0f, s0t = fitm & (t.month == m) & (t.hour == h), trm & (t.month == m) & (t.hour == h)
                eu, ev = U[pi][s0t], V[pi][s0t]
                cells.append(dict(uu=uu, vv=vv, seq=seq, mapped_u=mapped_u, mapped_v=mapped_v, rc=rc, rw=rw, med=med, tru=tru, eu=eu, ev=ev,
                                  pick=rng.choice(len(eu), min(150, len(eu)), replace=False), fit_mapped_u=U[pi][s0f], fit_mapped_v=V[pi][s0f]))
    return cells


def summarize(R, cv):
    e = {L: dict(gap1=np.abs(r[:, 4] - r[:, 1]).mean(), err_link=np.abs(r[:, 6] - r[:, 0]).mean(), n=len(r)) for L, r in R.items()}
    return e, cv.mean(0)


def judge(out):
    """out[seed] = (e per L, d (8,) = cov90 u: shipped, refit; v: shipped, refit; CRPS u: shipped, refit; v: shipped, refit, d_map (8,) same with s = 1)."""
    ok = True
    for e, d, dm in out.values():
        if abs(d[1] - 0.90) > 0.02 or abs(d[3] - 0.90) > 0.02 or d[5] - d[4] > 0.0009 or d[7] - d[6] > 0.0009:
            return "KILL (cov90 outside 0.88-0.92 or CRPS worse than shipped by more than 0.0009)"
        ok &= all(v["gap1"] < 0.03 and v["err_link"] <= 0.5 * SHIPPED_3H[L] for L, v in e.items())
        ok &= abs(d[1] - 0.90) <= abs(d[0] - 0.90) and abs(d[3] - 0.90) <= abs(d[2] - 0.90)
        ok &= d[5] - dm[5] <= 0.0009 and d[7] - dm[7] <= 0.0009
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    K.ram_gate(4.0)
    lines = [f"WD1 UR5 re-score with spread refit: climate mode, 10 m wind; truth ERA5 {TRUTH[0]}-{TRUTH[1]}, fit {TEMPLATE[0]}-{TEMPLATE[1]}"]
    out = {}
    for seed in (0, 1):
        cells = collect(seed)
        for c in cells:
            c["u"], c["fit_u"], c["v"], c["fit_v"] = c["mapped_u"][0], c["fit_mapped_u"], c["mapped_v"][0], c["fit_mapped_v"]
        su, sv = pick_scale(cells, "u"), pick_scale(cells, "v")
        Rm, cvm = evaluate(cells, 1.0, 1.0, seed)
        R, cv = evaluate(cells, su, sv, seed)
        e, d = summarize(R, cv)
        _, dm = summarize(Rm, cvm)
        out[seed] = (e, d, dm)
        lines.append(f"  seed {seed}: refit scale u {su:.2f}, v {sv:.2f} (fit on {TEMPLATE[0]}-{TEMPLATE[1]})")
        for L in LIMITS:
            lines.append(f"  seed {seed} L {L:>4.0f}: {e[L]['n']} cells; per-hour gap {e[L]['gap1']:.3f}; 3-hour error map + link + refit {e[L]['err_link']:.3f} (shipped {SHIPPED_3H[L]:.3f})")
        lines.append(f"  seed {seed}: 10 m cov90 u {d[0]:.3f} -> {d[1]:.3f} (map alone {dm[1]:.3f}), v {d[2]:.3f} -> {d[3]:.3f} (map alone {dm[3]:.3f}); "
                     f"CRPS u {d[4]:.4f} -> {d[5]:.4f} (map alone {dm[5]:.4f}), v {d[6]:.4f} -> {d[7]:.4f} (map alone {dm[7]:.4f})")
    lines.append("Rule (set 2026-11-15, New_Plan 19 WD1): PASS = gap < 0.03, 3-hour error <= half of shipped, u / v cov90 in 0.88-0.92 and no farther from 0.90 than shipped, "
                 "CRPS within +0.0009 of the map alone; KILL = CRPS worse than shipped by > 0.0009 or cov90 outside 0.88-0.92; both seeds, all limits.")
    lines.append("Verdict: " + judge(out))
    K.report(NAME, lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    x = rng.normal(2, 3, (3, 2000))
    assert np.allclose(scale(x, 1.0), x) and abs(scale(x, 0.5).std() - 1.5) < 0.1 and np.allclose(scale(x, 0.5).mean(1), x.mean(1))
    cells = [dict(u=rng.normal(0, 1, 5000), fit_u=rng.normal(0, 1.15, 4000)) for _ in range(3)]
    s = pick_scale(cells, "u")
    assert 1.08 < s < 1.22, s  # members sd 1, truth sd 1.15 -> scale ~1.15
    e = {L: dict(gap1=0.01, err_link=0.01, n=5) for L in LIMITS}
    d = np.array([0.93, 0.90, 0.96, 0.91, 1.0, 1.0, 1.0, 1.0])
    assert judge({0: (e, d, d)}) == "PASS"
    assert judge({0: (e, d + np.array([0, 0.03, 0, 0, 0, 0, 0, 0]), d)}).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
