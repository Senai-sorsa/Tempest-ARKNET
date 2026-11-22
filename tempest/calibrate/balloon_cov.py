"""G4 global covariate balloon correction (GLOBAL_PLAN G4 and section 5.1): ERA5 -> balloon departures from inputs that
exist everywhere, pooled over all IGRA stations; no lat/lon, no station id.

    python -m tempest.calibrate.balloon_cov pairs --out data/train/balloon_pairs.npz [--first-year 1991 --last-year 2025]
    python -m tempest.calibrate.balloon_cov fit   --pairs data/train/balloon_pairs.npz --out models/global/balloon_cov.npz
    python -m tempest.calibrate.balloon_cov cv    --pairs data/train/balloon_pairs.npz --out results/G4/balloon_cov_cv.csv

Pairs: each IGRA station that is a global store point (data/igra_heights, 44 model heights), soundings within 1 h of the
store's hour of that day, against the ERA5 store profile at that point (one UTC hour per day, so ~1 day in 6-8 pairs).
Per variable and height two ridge fits on the covariates: the mean departure d = balloon - ERA5, and log|d - mean|
(the spread: sd = exp(fit + 0.635), the log of a half-normal's typical size). Covariates: the ERA5 value, ERA5 shear
(m/s per km between neighbour heights), N^2, bulk Richardson number, sdor, slope, coast distance, land share, TPI,
sin / cos of the solar hour. Boundary-layer mean shifts (< 2 km) shrink to 0 outside the area of applicability
(tempest.scoring.spatial.shrink_weight on the DI). Fit years <= 2023; 2024-25 are the check.
cv: 1,000 km spatial blocks of stations (5 folds): bias and spread ratio before / after per variable and height band.
"""
import argparse
import os

import numpy as np

from tempest.profiles.to_heights import HEIGHTS, PROFILE

NH = len(HEIGHTS)
BL_TOP = 2000.0
STATICS = ["sdor", "slor", "coast_km", "lsm", "tpi_m"]
COVS = ["era", "shear", "n2", "ri"] + STATICS + ["sh_sin", "sh_cos"]
LOG_HALFNORMAL = 0.635                            # -E[log|z|] for z ~ N(0, 1), up to the half-normal's median offset
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def _match(st_times, store_times, tol_h=1):
    """Sounding times (n,), store times (one per day) -> (sounding index, store index) pairs within tol_h hours."""
    st = np.asarray(st_times, "datetime64[h]").astype(np.int64)
    so = np.asarray(store_times, "datetime64[h]").astype(np.int64)
    j = np.clip(np.searchsorted(so, st), 1, len(so) - 1)
    j = np.where(np.abs(so[j - 1] - st) <= np.abs(so[j] - st), j - 1, j)
    k = np.abs(so[j] - st) <= tol_h
    return np.flatnonzero(k), j[k]


def pairs(first=1991, last=2025, store=None, igra_dir="data/igra_heights", per_station=1000, seed=0, log=print):
    """-> dict(era (n, 4, 44), obs (n, 4, 44), point (n,), time (n,)) of matched soundings."""
    from tempest.geo import global_store as gs
    from tempest.geo import holdout
    from tempest.ingest.igra_to_heights import load
    store = store or gs.STORE
    if last > 2025:
        raise ValueError("G stages never read 2026")
    pts = gs.points(store)
    names = gs.months(first, last, store)
    times, where = [], []
    for name in names:
        with np.load(os.path.join(store, f"{name}.npz")) as d:
            vt = d["valid_time"].astype("datetime64[h]")
        times.append(vt)
        where += [(name, i) for i in range(len(vt))]
    times = np.concatenate(times)
    rng = np.random.default_rng(seed)
    need = {}                                                                         # month -> list of (point, day, obs)
    for p in np.flatnonzero(pts["igra"] != ""):
        f = os.path.join(igra_dir, f"{pts['igra'][p]}.npz")
        if not os.path.exists(f):
            continue
        d = load(f)
        i, j = _match(d["time"], times)
        holdout.check(times=d["time"][i], what=f"IGRA {pts['igra'][p]}")
        if len(i) > per_station:
            keep = np.sort(rng.choice(len(i), per_station, replace=False))
            i, j = i[keep], j[keep]
        obs = np.stack([d[v][i, :NH] for v in PROFILE], 1)
        for a, b in zip(range(len(i)), j):
            need.setdefault(where[b][0], []).append((p, where[b][1], obs[a]))
    from tempest.geo.statics import statics
    oro = statics(pts["lat"], pts["lon"])["oro_m"]
    out = []
    for name in names:
        if name not in need:
            continue
        m = gs.month(name, store)
        q = need[name]
        pp = np.array([x[0] for x in q])
        up, inv = np.unique(pp, return_inverse=True)
        pr, _ = gs.profiles(m, pts, up, oro_m=oro[up])
        day = np.array([x[1] for x in q])
        era = np.stack([pr[v][day, inv] for v in PROFILE], 1)
        out.append(dict(era=era.astype(np.float32), obs=np.stack([x[2] for x in q]).astype(np.float32),
                        point=pp.astype(np.int32), time=m["valid_time"][day].astype("datetime64[h]")))
        log(f"{name}: {sum(len(o['point']) for o in out):,} pairs")
    if not out:
        raise FileNotFoundError("no IGRA sounding matched a store hour")
    return {k: np.concatenate([o[k] for o in out]) for k in out[0]}


def covariates(era, point, time, pts, st=None):
    """ERA5 profiles (n, 4, 44) + place and time -> (n, 44, C) covariates per height, columns COVS (variable-free; the
    'era' column is filled per variable by the caller, here T)."""
    from tempest.geo.statics import statics
    st = st or statics(pts["lat"][point], pts["lon"][point])
    z = np.asarray(HEIGHTS, float)
    u, v, T = era[:, 0], era[:, 1], era[:, 2]
    dz = np.gradient(z) / 1000.0
    sh = np.hypot(np.gradient(u, axis=1), np.gradient(v, axis=1)) / dz              # m/s per km
    n2 = 9.80665 / T * (np.gradient(T, axis=1) / (dz * 1000.0) + 9.80665 / 1004.0)
    ri = n2 / np.maximum((sh / 1000.0) ** 2, 1e-6)
    hr = (np.asarray(time, "datetime64[h]").astype(np.int64) % 24 + pts["lon"][point] / 15.0) % 24
    n = len(era)
    cols = [T, sh, n2 * 1e4, np.clip(ri, -10, 10)] + [np.broadcast_to(np.asarray(st[k], float)[:, None], (n, NH)) for k in STATICS]
    cols += [np.broadcast_to(np.sin(2 * np.pi * hr / 24)[:, None], (n, NH)), np.broadcast_to(np.cos(2 * np.pi * hr / 24)[:, None], (n, NH))]
    return np.stack(cols, -1).astype(np.float32)


def _design(cov, era_v):
    c = cov.copy()
    c[..., 0] = era_v
    return np.concatenate([np.ones(c.shape[:-1] + (1,), np.float32), c], -1)


def _ridge(X, y, lam):
    ok = np.isfinite(y) & np.isfinite(X).all(1)
    X, y = X[ok], y[ok]
    if len(y) < 50:
        return np.zeros(X.shape[1])
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-6
    Z = np.concatenate([X[:, :1], (X[:, 1:] - mu) / sd], 1)
    b = np.linalg.solve(Z.T @ Z + lam * len(y) * np.diag([0] + [1] * (Z.shape[1] - 1)), Z.T @ y)
    return np.concatenate([[b[0] - (b[1:] * mu / sd).sum()], b[1:] / sd])          # coefficients on the raw design


def fit(pr, pts, lam=1e-3, years=(1991, 2023)):
    """-> dict(mean (4, 44, C+1), logsd (4, 44, C+1), names) from pairs pr."""
    yr = pr["time"].astype("datetime64[Y]").astype(int) + 1970
    k = (yr >= years[0]) & (yr <= years[1])
    cov = covariates(pr["era"][k], pr["point"][k], pr["time"][k], pts)
    mean = np.zeros((len(PROFILE), NH, len(COVS) + 1))
    logsd = np.zeros_like(mean)
    for vi in range(len(PROFILE)):
        for h in range(NH):
            X = _design(cov[:, h], pr["era"][k][:, vi, h])
            d = pr["obs"][k][:, vi, h] - pr["era"][k][:, vi, h]
            mean[vi, h] = _ridge(X, d, lam)
            r = np.log(np.abs(d - X @ mean[vi, h]) + 1e-6)
            logsd[vi, h] = _ridge(X, r, lam)
    return dict(mean=mean, logsd=logsd, names=np.array(["1"] + COVS), years=np.array(years))


def predict(tab, era, cov, di=None, thr=None):
    """era (n, 4, 44), cov (n, 44, C) -> mean shift, sd (n, 4, 44). With di (n,) and thr: shifts below BL_TOP shrink
    toward 0 outside the area of applicability."""
    mu, sd = np.empty_like(era), np.empty_like(era)
    for vi in range(len(PROFILE)):
        X = _design(cov, era[:, vi])
        mu[:, vi] = np.einsum("nhc,hc->nh", X, tab["mean"][vi])
        sd[:, vi] = np.exp(np.einsum("nhc,hc->nh", X, tab["logsd"][vi]) + LOG_HALFNORMAL)
    if di is not None:
        from tempest.scoring.spatial import shrink_weight
        bl = np.asarray(HEIGHTS) < BL_TOP
        mu[:, :, bl] *= shrink_weight(np.asarray(di), thr)[:, None, None]
    return mu, sd


def cv(pr, pts, k=5, size_km=1000.0, seed=0, lam=1e-3):
    """Leave-station-blocks-out: per variable and height band, mean departure (bias) and the ratio of the departure's
    spread to the predicted sd, before (ERA5 as is, sd = ERA5-free spread of d) and after the correction."""
    import pandas as pd
    from tempest.scoring.spatial import block_folds_km
    us = np.unique(pr["point"])
    fold_of = dict(zip(us, block_folds_km(pts["lat"][us], pts["lon"][us], size_km, k, seed)))
    folds = np.array([fold_of[p] for p in pr["point"]])
    yr = pr["time"].astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for f in range(k):
        tr, te = (folds != f) & (yr <= 2023), (folds == f) & (yr >= 2024)
        if not te.any() or not tr.any():
            continue
        tab = fit({q: v[tr] for q, v in pr.items()}, pts, lam)
        e, o = pr["era"][te], pr["obs"][te]
        mu, sd = predict(tab, e, covariates(e, pr["point"][te], pr["time"][te], pts))
        d0, d1 = o - e, o - e - mu
        for vi, v in enumerate(PROFILE):
            for lo, hi in BANDS:
                h = (np.asarray(HEIGHTS) >= lo) & (np.asarray(HEIGHTS) < hi)
                a, b, s = d0[:, vi, h], d1[:, vi, h], sd[:, vi, h]
                rows.append(dict(fold=f, var=v, band=f"{lo}-{hi}", n=int(np.isfinite(a).sum()), bias_before=float(np.nanmean(a)),
                                 bias_after=float(np.nanmean(b)), mae_before=float(np.nanmean(np.abs(a))),
                                 mae_after=float(np.nanmean(np.abs(b))), spread_ratio=float(np.nanstd(b) / np.nanmean(s))))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("pairs")
    a.add_argument("--out", required=True)
    a.add_argument("--first-year", type=int, default=1991)
    a.add_argument("--last-year", type=int, default=2025)
    a.add_argument("--per-station", type=int, default=1000)
    for n in ("fit", "cv"):
        b = sp.add_parser(n)
        b.add_argument("--pairs", required=True)
        b.add_argument("--out", required=True)
        b.add_argument("--ridge", type=float, default=1e-3)
    g = ap.parse_args()
    from tempest.geo import global_store as gs
    os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
    if g.cmd == "pairs":
        pr = pairs(g.first_year, g.last_year, per_station=g.per_station)
        with open(g.out, "wb") as fh:
            np.savez(fh, **pr)
        print(f"wrote {g.out}: {len(pr['point']):,} pairs at {len(np.unique(pr['point']))} stations", flush=True)
        return
    pr, pts = dict(np.load(g.pairs)), gs.points()
    if g.cmd == "fit":
        tab = fit(pr, pts, g.ridge)
        with open(g.out, "wb") as fh:
            np.savez(fh, **tab)
        print(f"wrote {g.out}", flush=True)
    else:
        df = cv(pr, pts, lam=g.ridge)
        df.to_csv(g.out, index=False)
        print(df.groupby(["var", "band"])[["bias_before", "bias_after", "mae_before", "mae_after", "spread_ratio"]].mean().round(3).to_string(), flush=True)


if __name__ == "__main__":
    main()
