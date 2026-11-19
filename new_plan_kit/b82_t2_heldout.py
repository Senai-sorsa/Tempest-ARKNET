"""26.1 step 0 / plan item T2 (2026-11-19). REPORT ONLY (no verdict): how small can the noise of the vertical-corr error be made?
FINDING: the shipped tool refuses every IGRA site named in T2 except Denver (ABQ, AMA, FGZ lat 35, TUS lon -111, DRT lat 29 are outside the trained boxes lat 31-34 / lon -108..-101 and lat 38-40 / lon -106..-104), so a blind
kit at those sites needs new regional assets (REGION_PLAN.md) and is NOT run. What is possible inside the boxes: EPZ and MAF with a larger draw than b81 (600 each, 2024-25, balloon-corrected as b81) and Denver DNR 2016-2021 (before 2022).
Shipped tool, 50 members, 00Z and 12Z, profiles with >= 30 of 44 u levels, one member per case (as b81). Per site and pooled: vertical-corr error (b9 definition, u v T), CRPS u v T, 95 % interval from resampling whole days.
Cases are random draws; KIT_SEED picks them.
    PYTHONPATH=".;new_plan_kit" KIT_SEED=0 .venv/Scripts/python -W ignore new_plan_kit/b82_t2_heldout.py     Result: docs/results/logs/kit_b82_t2_heldout.log
"""
import argparse
import os

import numpy as np

import kit_common as K
import b9_gram_compare as B9

NM = 50
VARS = B9.VARS
STN = {"EPZ": (K.EPZ, (2024, 2025)), "MAF": (K.MAF, (2024, 2025)), "DNR": ("USM00072469", (2016, 2021))}


def pos(sid):
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", sid + ".npz"))
    return float(d["lat"][0]), float(d["lon"][0]), float(d["elev"][0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-station", type=int, default=600)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--stations", default=",".join(STN))
    a = ap.parse_args()
    seed = int(os.environ.get("KIT_SEED", 0))
    rng = np.random.default_rng(seed)
    C = []                                                   # (station, day, clim mean, balloon dict, members dict)
    skipped = {}
    for name in a.stations.split(","):
        sid, (y0, y1) = STN[name]
        lat, lon, elev = pos(sid)
        t, b = K.balloon(sid)
        full = np.isfinite(b["u"]).sum(1) >= 30
        idx = np.flatnonzero((t.year >= y0) & (t.year <= y1) & np.isin(t.hour, (0, 12)) & full)
        n0 = len(C)
        for k in rng.permutation(idx)[:int(a.per_station * 1.15)]:
            if len(C) - n0 >= a.per_station:
                break
            assert K.day_ok(t[k])
            mu, _ = B9.clim_stats(sid, t[k].month, t[k].hour)
            try:
                run = K.tool(lat, lon, t[k], seed=1000 * t[k].year + int(t[k].dayofyear), n=NM, elevation=elev)
            except ValueError:
                skipped[name] = skipped.get(name, 0) + 1
                continue
            C.append((name, f"{name}{t[k]:%Y-%m-%dT%H}"[:-3], mu, {q: b[q][k] for q in b}, {q: np.asarray(run[q], float) for q in VARS}))
        print(f"{name}: {len(C) - n0} cases ({skipped.get(name, 0)} skipped)", flush=True)
    n = len(C)
    assert n >= 8, f"only {n} cases"
    r = np.random.default_rng(seed + 77)
    js = r.integers(NM, size=n)
    src = {q: np.array([C[k][4][q][js[k]] - C[k][2][q] for k in range(n)]) for q in VARS}
    tru = {q: np.array([C[k][3][q] - C[k][2][q] for k in range(n)]) for q in VARS}
    crps = {q: np.array([np.nanmean(B9.crps_cols(C[k][4][q], C[k][3][q])) for k in range(n)]) for q in VARS}
    days = np.array([c[1] for c in C])
    sta = np.array([c[0] for c in C])
    err = lambda i: B9.vert_err({q: src[q][i] for q in VARS}, {q: tru[q][i] for q in VARS})
    L = [f"26.1 step 0 / T2 held-out IGRA sites (seed {seed}): shipped tool, {NM} members, balloon-corrected at EPZ / MAF, not at DNR; vertical-corr error (u v T) and CRPS, 95 % interval by whole days",
         "site   cases   vertical-corr error [95 %]          CRPS u   v      T"]
    for name in [*a.stations.split(","), "ALL"]:
        i = np.arange(n) if name == "ALL" else np.flatnonzero(sta == name)
        if len(i) < 30:
            continue
        v, lo, hi = B9.boot(lambda j: err(i[j]), days[i], a.boot)
        L.append(f"{name:<6} {len(i):>5}   {v:.3f} [{lo:.3f}, {hi:.3f}] width {hi - lo:.3f}   " + " ".join(f"{crps[q][i].mean():<6.3f}" for q in VARS))
    L.append("Reference: EPZ / MAF kit noise was about 0.03 (T2 row, section 23, 600 cases). 26.1 asks for a vs-shipped interval narrower than 0.01 (step 1).")
    L.append("Notes: report only; Denver = 2016-2021 (before 2022); EPZ / MAF 2024-25 (development window, never 2026). T2 sites outside the trained boxes are not run (tool refuses).")
    K.report("b82_t2_heldout", L)


if __name__ == "__main__":
    main()
