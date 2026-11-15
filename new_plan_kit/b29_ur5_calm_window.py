"""New_Plan 17 UR5: calm-window fix, the per-hour 10 m wind first, the hour-to-hour link second. Climate mode, CPU, no training, nothing in the
tool changes (every change below is applied to returned members in memory).
Cells as STRAND stage 1 / AV27 (b14): 12 ERA5 store points x 12 months x start 15 / 18 / 21 UTC, query date 2013-<month>-15; truth = ERA5 hourly
u10 / v10 (data/pilot/profiles80.zarr), truth years 2006-2020, map / link fit years 1991-2005 (b14's template years). Never 2026.
  --step 0  where does the 10 m speed drift? The tool's members at each post-processing stage (api assets 'post': pit, seasonal, rank / tpl
            (shuffle), smap (shear map), lmap (lapse map) switched off in memory, cumulative) against ERA5 at 4 points x months 1 / 4 / 7 / 10 x 3 hours:
            mean u, v, speed and P(speed < 5 m/s), tool minus ERA5 (2006-20). The range map itself cannot be switched off here (it is not a 'post' step).
  --step 1  (a) speed map: the 10 m speed mapped by quantile to the ERA5 speed of the same point, month and hour (fit 1991-2005), direction kept
            (u, v scaled by s' / s), on the shipped coherent sequence (atmosphere_sequence, offsets 0 / 1 / 2 h); (b) only if (a) leaves a 3-hour
            error above 0.02 at some limit: two lag correlations (calm / windy first hour, split at the cell median) fitted on 1991-2005 windows, the
            members of hours 1 and 2 re-ordered by a Gaussian chain with the regime's correlation (hour 0 order kept).
Rule (set 2026-11-13 in New_Plan 17.1 before any run), on the step-1 arm actually proposed ((a), or (a)+(b) if (b) runs), both seeds:
  PASS: per-hour gap |P_indep tool - truth| under 0.03 at every limit (5 / 8 / 10 m/s), mean 3-hour error at most half of the shipped
        sequence's (0.237 / 0.191 / 0.154, b14 seed 0), u and v 10 m cov90 (truth hours inside the members' 5-95 %) within 0.003 of before,
        u and v 10 m CRPS not worse by more than 0.0009.
  KILL: u or v cov90 moves by more than 0.01, or the 3-hour error is not better than shipped at any limit.  Otherwise MISS.
Also closes the AV27 side check (To-do): step 0 says whether the windier 10 m wind comes from one stage.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b29_ur5_calm_window.py --step 0      # ~1 h
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b29_ur5_calm_window.py --step 1      # ~1-2 h
Result: docs/results/logs/kit_b29_ur5_calm_window.log
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import norm

import kit_common as K
from b14_strand_stage1 import LATS, LIMITS, LONS, STARTS, TEMPLATE, TRUTH, probs, windows

SHIPPED_3H = {5.0: 0.237, 8.0: 0.191, 10.0: 0.154}
DROP = [("network + range map", ("pit", "seasonal", "rank", "rank_extra", "tpl", "smap", "lmap")), ("+ PIT recal", ("seasonal", "rank", "rank_extra", "tpl", "smap", "lmap")),
        ("+ seasonal", ("rank", "rank_extra", "tpl", "smap", "lmap")), ("+ shuffle", ("smap", "lmap")), ("+ shear map", ("lmap",)), ("shipped", ())]
QS = np.linspace(0.005, 0.995, 100)
NAME = "b29_ur5_calm_window"


def tool_stage(lat, lon, when, seed, n, drop):
    from tempest_weather import api
    A = api._assets()
    full = A["post"]
    A["post"] = {k: v for k, v in full.items() if k not in drop}
    try:
        return api.atmosphere_set(lat, lon, when, n=n, seed=seed, mode="ai")[0]
    finally:
        A["post"] = full


def era5_cells(pts_ll):
    ds = xr.open_zarr(K.REPO + "/data/pilot/profiles80.zarr")
    la, lo = ds.lat.values, ds.lon.values
    pts = [int(np.argmin((la - a) ** 2 + (lo - b) ** 2)) for a, b in pts_ll]
    sub = ds[["u10", "v10"]].isel(point=pts).sel(time=slice(TEMPLATE[0], TRUTH[1])).load()
    t = pd.DatetimeIndex(sub.time.values)
    assert t.year.max() <= 2020
    return pts, la, lo, t, sub.u10.values.astype(float), sub.v10.values.astype(float)


def speed_map(tool_s, era_s):
    """-> function s -> s' (quantile map from the tool's speed distribution to ERA5's, linear between QS knots, flat beyond)."""
    xt, xe = np.quantile(tool_s, QS), np.quantile(era_s, QS)
    xt = np.maximum.accumulate(xt + np.arange(len(xt)) * 1e-9)
    return lambda s: np.interp(s, xt, xe)


def apply_map(u, v, f):
    s = np.hypot(u, v)
    k = np.where(s > 1e-6, f(s) / np.maximum(s, 1e-6), 1.0)
    return u * k, v * k


def regime_rho(tpl):
    """real 3-hour windows (k, 3) -> (rho calm, rho windy, median of hour 0) of the normal scores of consecutive hours."""
    z = norm.ppf((np.argsort(np.argsort(tpl, 0), 0) + 0.5) / len(tpl))
    med = np.median(tpl[:, 0])
    r = []
    for sel in (tpl[:, 0] < med, tpl[:, 0] >= med):
        a = np.concatenate([z[sel, 0], z[sel, 1]])
        b = np.concatenate([z[sel, 1], z[sel, 2]])
        r.append(float(np.corrcoef(a, b)[0, 1]))
    return r[0], r[1], float(med)


def regime_link(w3, rho_c, rho_w, med, rng):
    """members (3, n) per-hour speeds -> (3, n): hour 0 kept; hours 1, 2 re-ordered by a Gaussian chain whose correlation is rho_c below the median
    of the previous hour and rho_w above. Each hour's member set is unchanged (only re-ordered)."""
    n = w3.shape[1]
    out = w3.copy()
    z = norm.ppf((np.argsort(np.argsort(w3[0])) + 0.5) / n)
    prev = w3[0]
    for h in (1, 2):
        rho = np.where(prev < med, rho_c, rho_w)
        z = rho * z + np.sqrt(1 - rho ** 2) * rng.standard_normal(n)
        out[h] = np.sort(w3[h])[np.argsort(np.argsort(z))]
        prev = out[h]
    return out


def cov90(m, y):
    lo, hi = np.percentile(m, 5), np.percentile(m, 95)
    return float(np.mean((y >= lo) & (y <= hi)))


def crps_vs(m, ys):
    return float(np.mean([K.crps1(m, y) for y in ys]))


def step0(lines):
    pl = [(LATS[i], LONS[j]) for i in (0, 2) for j in (0, 3)]
    pts, la, lo, t, U, V = era5_cells(pl)
    for name, drop in DROP:
        d = []
        for pi, p in enumerate(pts):
            for m in (1, 4, 7, 10):
                for h in STARTS:
                    k = (t.year >= int(TRUTH[0])) & (t.month == m) & (t.hour == h)
                    eu, ev = U[pi][k], V[pi][k]
                    try:
                        a = tool_stage(float(la[p]), float(lo[p]), f"2013-{m:02d}-15T{h:02d}:00:00+00:00", 0, 1024, drop)
                    except ValueError:
                        continue
                    tu, tv = a["u"][:, 0].astype(float), a["v"][:, 0].astype(float)
                    d.append((tu.mean() - eu.mean(), tv.mean() - ev.mean(), np.hypot(tu, tv).mean() - np.hypot(eu, ev).mean(), tu.std() - eu.std(), tv.std() - ev.std(),
                              (np.hypot(tu, tv) < 5).mean() - (np.hypot(eu, ev) < 5).mean()))
        d = np.array(d)
        lines.append(f"  step 0 {name:<22} ({len(d)} cells) tool minus ERA5: mean u {d[:, 0].mean():+.2f}, v {d[:, 1].mean():+.2f}, speed {d[:, 2].mean():+.2f} m/s; "
                     f"sd u {d[:, 3].mean():+.2f}, sd v {d[:, 4].mean():+.2f}; P(speed < 5) {d[:, 5].mean():+.3f}")


def step1(lines):
    from tempest_weather import api
    pl = [(a, b) for a in LATS for b in LONS]
    pts, la, lo, t, U, V = era5_cells(pl)
    W = np.hypot(U, V)
    res = {}
    for seed in (0, 1):
        rng = np.random.default_rng(200 + seed)
        R = {L: [] for L in LIMITS}
        cv = []
        for pi, p in enumerate(pts):
            ty = t.year
            for m in range(1, 13):
                for h in STARTS:
                    fitm = (ty >= int(TEMPLATE[0])) & (ty <= int(TEMPLATE[1]))
                    trm = ty >= int(TRUTH[0])
                    tpl = windows(W[pi][fitm], t[fitm], m, h)
                    tru = windows(W[pi][trm], t[trm], m, h)
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
                        hk = (h + k) % 24
                        sel = fitm & (t.month == m) & (t.hour == hk)
                        f = speed_map(seq[k], W[pi][sel])
                        mapped_u[k], mapped_v[k] = apply_map(uu[k], vv[k], f)
                    mp = np.hypot(mapped_u, mapped_v)
                    rc, rw, med = regime_rho(tpl)
                    lk = regime_link(mp, rc, rw, med, rng)
                    for L in LIMITS:
                        pr, pir = probs(tru.T, L)
                        if not 0.05 <= pir <= 0.95:
                            continue
                        R[L].append((pr, pir, probs(seq, L)[1], probs(seq, L)[0], probs(mp, L)[1], probs(mp, L)[0], probs(lk, L)[0]))
                    sel0 = trm & (t.month == m) & (t.hour == h)
                    eu, ev = U[pi][sel0], V[pi][sel0]
                    pick = rng.choice(len(eu), min(150, len(eu)), replace=False)
                    cv.append((cov90(uu[0], eu), cov90(mapped_u[0], eu), cov90(vv[0], ev), cov90(mapped_v[0], ev),
                               crps_vs(uu[0], eu[pick]), crps_vs(mapped_u[0], eu[pick]), crps_vs(vv[0], ev[pick]), crps_vs(mapped_v[0], ev[pick])))
        res[seed] = ({L: np.array(v) for L, v in R.items()}, np.array(cv))
    out = {}
    for seed, (R, cv) in res.items():
        d = cv.mean(0)
        e = {}
        for L in LIMITS:
            r = R[L]
            e[L] = dict(gap0=np.abs(r[:, 2] - r[:, 1]).mean(), gap1=np.abs(r[:, 4] - r[:, 1]).mean(), err_seq=np.abs(r[:, 3] - r[:, 0]).mean(),
                        err_map=np.abs(r[:, 5] - r[:, 0]).mean(), err_link=np.abs(r[:, 6] - r[:, 0]).mean(), n=len(r))
            lines.append(f"  step 1 seed {seed} L {L:>4.0f}: {e[L]['n']} cells; per-hour gap {e[L]['gap0']:.3f} -> {e[L]['gap1']:.3f}; 3-hour error shipped {e[L]['err_seq']:.3f}, "
                         f"map {e[L]['err_map']:.3f}, map + regime link {e[L]['err_link']:.3f}")
        lines.append(f"  step 1 seed {seed}: 10 m cov90 u {d[0]:.3f} -> {d[1]:.3f}, v {d[2]:.3f} -> {d[3]:.3f}; CRPS u {d[4]:.4f} -> {d[5]:.4f}, v {d[6]:.4f} -> {d[7]:.4f}")
        out[seed] = (e, d)
    return out


def judge(out):
    """out[seed] = (e[L] dict, d (8,) coverage / CRPS before-after) -> (verdict, arm)."""
    use_link = any(v["err_map"] > 0.02 for e, _ in out.values() for v in e.values())
    key = "err_link" if use_link else "err_map"
    arm = "map + regime link" if use_link else "map"
    if any(abs(d[1] - d[0]) > 0.01 or abs(d[3] - d[2]) > 0.01 for _, d in out.values()):
        return "KILL (u or v coverage moves by more than 0.01)", arm
    if all(v[key] >= SHIPPED_3H[L] for e, _ in out.values() for L, v in e.items()):
        return "KILL (3-hour error not better than shipped at any limit)", arm
    ok = all(v["gap1"] < 0.03 and v[key] <= 0.5 * SHIPPED_3H[L] for e, _ in out.values() for L, v in e.items()) and \
        all(abs(d[1] - d[0]) <= 0.003 and abs(d[3] - d[2]) <= 0.003 and d[5] - d[4] <= 0.0009 and d[7] - d[6] <= 0.0009 for _, d in out.values())
    return ("PASS" if ok else "MISS (record, no adoption)"), arm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, choices=(0, 1), required=True)
    a = ap.parse_args()
    K.ram_gate(4.0)
    lines = [f"UR5 calm-window fix, step {a.step}: climate mode, 10 m wind; truth ERA5 {TRUTH[0]}-{TRUTH[1]}, fit {TEMPLATE[0]}-{TEMPLATE[1]}"]
    if a.step == 0:
        step0(lines)
        lines.append("Step 0 is a measurement (no rule): the stage where the speed difference jumps is where to fix it.")
    else:
        v, arm = judge(step1(lines))
        lines.append(f"Rule (pre-set, New_Plan 17.1) on the arm '{arm}': PASS = per-hour gap < 0.03, 3-hour error <= half of shipped, u / v cov90 within 0.003, "
                     "u / v CRPS within +0.0009, both seeds; KILL = u or v cov90 moves > 0.01 or no limit better than shipped.")
        lines.append("Verdict: " + v)
    K.report(NAME, lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    tool_s, era_s = rng.gamma(4, 1.6, 4000), rng.gamma(4, 1.3, 4000)
    f = speed_map(tool_s, era_s)
    assert abs(np.median(f(tool_s)) - np.median(era_s)) < 0.1
    u, v = np.array([3.0, 0.0]), np.array([4.0, 2.0])
    u2, v2 = apply_map(u, v, lambda s: s / 2)
    assert np.allclose(np.hypot(u2, v2), [2.5, 1.0]) and np.allclose(np.arctan2(u2, v2), np.arctan2(u, v))
    base = rng.uniform(0, 10, 4000)
    tpl = np.stack([base, base + rng.normal(0, 0.5, 4000), base + rng.normal(0, 1.0, 4000)], 1)
    rc, rw, med = regime_rho(tpl)
    assert 0.8 < rc <= 1 and 0.8 < rw <= 1
    mem = rng.uniform(0, 10, (3, 1024))
    lk = regime_link(mem, rc, rw, med, rng)
    assert np.allclose(np.sort(lk, 1), np.sort(mem, 1)) and np.corrcoef(lk[0], lk[1])[0, 1] > 0.7
    e = {L: dict(gap1=0.01, err_map=0.5 * SHIPPED_3H[L] - 0.01, err_link=0.0) for L in LIMITS}
    d = np.array([0.9, 0.901, 0.9, 0.9, 1.0, 0.99, 1.0, 1.0])
    assert judge({0: (e, d), 1: (e, d)}) == ("PASS", "map + regime link")
    assert judge({0: (e, d + np.array([0, 0.02, 0, 0, 0, 0, 0, 0])), 1: (e, d)})[0].startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
