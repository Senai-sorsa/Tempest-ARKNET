"""Spatial test harness (docs/plans/GLOBAL_PLAN.md section 6), used by the G2-G4 launchers.

Folds:   block_folds (2 / 10 / 20 degree blocks), group_folds (box / Koppen / continent ids), knndm (kNNDM, Linnenbrink 2024:
         folds whose CV nearest-neighbour distances match the prediction-to-training distances), continent().
AOA:     aoa_fit / aoa_di / aoa_flag (Meyer & Pebesma 2021 dissimilarity index in the standardised, importance-weighted
         input space; threshold = 95th percentile of the training CV DI), di_error_fit / di_error (monotone DI -> error
         curve), shrink_weight (DI-gated shrinkage of the BL bias toward zero, G4).
Checks:  seam_check (no step along a transect beyond the seed tolerance), rotate_lon / reverse_lat (involution inputs),
         gates: gate_g2 / gate_g3 / gate_g4 read the score outputs and write one verdict CSV.

    python -m tempest.scoring.spatial gate-g2 --dir results/G2      (reads results/G2/lobo_*/ score files)
    python -m tempest.scoring.spatial {subset,regroup,seam,rotate,aoa,gate-g3,gate-g4} ...   (G3 / G4 steps, see -h)
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

R_KM = 6371.0


def xyz(lat, lon):
    la, lo = np.deg2rad(np.asarray(lat, float)), np.deg2rad(np.asarray(lon, float))
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


# ---------------------------------------------------------------- folds
def block_folds(lat, lon, size_deg, k=5, seed=0):
    """Fold 0..k-1 per row: square lat/lon blocks of size_deg, each block wholly in one fold (random, fixed by seed)."""
    bi = np.floor((np.asarray(lat, float) + 90) / size_deg).astype(np.int64)
    bj = np.floor((np.asarray(lon, float) % 360) / size_deg).astype(np.int64)
    _, inv = np.unique(bi * 100000 + bj, return_inverse=True)
    return np.random.default_rng(seed).integers(0, k, inv.max() + 1)[inv]


def block_folds_km(lat, lon, size_km, k=5, seed=0):
    """As block_folds with blocks of about size_km on a side (G3: 1,000 km), latitude-dependent longitude width."""
    dlat = np.rad2deg(size_km / R_KM)
    bi = np.floor((np.asarray(lat, float) + 90) / dlat).astype(np.int64)
    cosc = np.maximum(np.cos(np.deg2rad(-90 + (bi + 0.5) * dlat)), 0.05)
    bj = np.floor((np.asarray(lon, float) % 360) / (dlat / cosc)).astype(np.int64)
    _, inv = np.unique(bi * 100000 + bj, return_inverse=True)
    return np.random.default_rng(seed).integers(0, k, inv.max() + 1)[inv]


def group_folds(groups):
    """Leave-one-group-out: fold id = rank of the group id (LOBO / LOCO / leave-continent-out)."""
    _, inv = np.unique(np.asarray(groups), return_inverse=True)
    return inv


CONTINENTS = ["north_america", "south_america", "europe", "africa", "asia", "oceania", "antarctica", "ocean"]


def continent(lat, lon, land=None):
    """Coarse continent id (index into CONTINENTS) from lat/lon boxes; land (bool) False -> 'ocean'.
    shortcut: rectangular boxes, not coastlines; points near the Suez / Panama / Urals edges can land in the neighbour.
    Good enough for leave-continent-out folds; upgrade to a polygon set if a fold boundary matters."""
    la, lo = np.asarray(lat, float), (np.asarray(lon, float) + 180) % 360 - 180
    c = np.full(la.shape, CONTINENTS.index("asia"))
    c[(lo < -30) & (la >= 13)] = CONTINENTS.index("north_america")
    c[(lo < -30) & (la < 13)] = CONTINENTS.index("south_america")
    c[(lo >= -30) & (lo < 60) & (la >= 36)] = CONTINENTS.index("europe")
    c[(lo >= -30) & (lo < 52) & (la < 36)] = CONTINENTS.index("africa")
    c[(lo >= 110) & (la < -10)] = CONTINENTS.index("oceania")
    c[(lo >= 140) & (la < 0)] = CONTINENTS.index("oceania")
    c[la < -60] = CONTINENTS.index("antarctica")
    if land is not None:
        c[~np.asarray(land, bool)] = CONTINENTS.index("ocean")
    return c


def _nnd_cv(X, folds):
    """Distance from each row to the nearest row of another fold (CV nearest-neighbour distance)."""
    from scipy.spatial import cKDTree
    out = np.full(len(X), np.inf)
    for f in np.unique(folds):
        a, b = folds == f, folds != f
        if b.any():
            out[a] = cKDTree(X[b]).query(X[a])[0]
    return out


def knndm(train_lat, train_lon, pred_lat, pred_lon, k=10, seed=0, n_try=12):
    """kNNDM folds (k) for the training points: k-means clusters of the training points are merged into k folds; the
    cluster count is chosen so that the CV nearest-neighbour distance distribution best matches the prediction-to-
    training distances (Wasserstein W). Random k-fold (one cluster per point) is one of the candidates.
    -> (folds, W of the chosen split, W of random k-fold)."""
    from scipy.cluster.vq import kmeans2
    from scipy.spatial import cKDTree
    from scipy.stats import wasserstein_distance
    Xt, Xp = xyz(train_lat, train_lon), xyz(pred_lat, pred_lon)
    target = cKDTree(Xt).query(Xp)[0]
    rng = np.random.default_rng(seed)
    n = len(Xt)
    rand = rng.integers(0, k, n)
    best = (wasserstein_distance(_nnd_cv(Xt, rand), target), rand)
    w_rand = best[0]
    for q in np.unique(np.geomspace(k, max(k + 1, n // 2), n_try).astype(int)):
        _, lab = kmeans2(Xt, int(q), seed=int(rng.integers(1 << 31)), minit="++")
        sizes = np.bincount(lab, minlength=q)
        fold_of, load = np.zeros(q, int), np.zeros(k)
        for c in np.argsort(-sizes):                                       # biggest clusters first, to the lightest fold
            fold_of[c] = int(np.argmin(load))
            load[fold_of[c]] += sizes[c]
        f = fold_of[lab]
        w = wasserstein_distance(_nnd_cv(Xt, f), target)
        if w < best[0]:
            best = (w, f)
    return best[1], best[0], w_rand


# ---------------------------------------------------------------- AOA / DI
def aoa_fit(X, folds, weights=None, q=0.95):
    """Training inputs X (N, F), CV folds (N,), importance weights (F,) -> dict(mu, sd, w, ref, dbar, thr, di_cv).
    DI = distance to the nearest training row / mean training nearest-neighbour distance; the threshold is the q-th
    percentile of the CV DI (distance to the nearest row of another fold), so 95 % of the training rows are inside."""
    from scipy.spatial import cKDTree
    X = np.asarray(X, float)
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    w = np.ones(X.shape[1]) if weights is None else np.asarray(weights, float)
    Z = (X - mu) / sd * w
    tree = cKDTree(Z)
    dbar = tree.query(Z, k=2)[0][:, 1].mean()
    dbar = dbar if dbar > 0 else 1.0
    di_cv = _nnd_cv(Z, np.asarray(folds)) / dbar
    return dict(mu=mu, sd=sd, w=w, ref=Z, dbar=dbar, thr=float(np.quantile(di_cv[np.isfinite(di_cv)], q)), di_cv=di_cv)


def aoa_di(f, X):
    from scipy.spatial import cKDTree
    Z = (np.asarray(X, float) - f["mu"]) / f["sd"] * f["w"]
    return cKDTree(f["ref"]).query(Z)[0] / f["dbar"]


FLAGS = np.array(["inside", "near", "outside"])


def aoa_flag(di, thr, near=1.5):
    """'inside' (DI <= thr), 'near' (<= near * thr), 'outside'."""
    di = np.asarray(di, float)
    return FLAGS[(di > thr).astype(int) + (di > near * thr).astype(int)]


def di_error_fit(di, err, n_bins=10):
    """Monotone (non-decreasing) DI -> expected error curve from binned means: dict(x, y) for np.interp."""
    di, err = np.asarray(di, float), np.asarray(err, float)
    edges = np.unique(np.quantile(di, np.linspace(0, 1, n_bins + 1)))
    b = np.clip(np.searchsorted(edges, di, "right") - 1, 0, len(edges) - 2)
    x = np.array([di[b == i].mean() for i in range(len(edges) - 1) if (b == i).any()])
    y = np.array([err[b == i].mean() for i in range(len(edges) - 1) if (b == i).any()])
    return dict(x=x, y=np.maximum.accumulate(y))


def di_error(fit, di):
    return np.interp(np.asarray(di, float), fit["x"], fit["y"])


def shrink_weight(di, thr):
    """Weight on a learned boundary-layer bias: 1 inside the AOA, falling linearly to 0 at twice the threshold."""
    return np.clip(2.0 - np.asarray(di, float) / thr, 0.0, 1.0)


# ---------------------------------------------------------------- checks
def seam_check(x, stats, tol):
    """Statistics along a transect (x sorted; stats {name: (n,)}), seed tolerance {name: tol} -> DataFrame of the
    largest step per statistic: the jump between neighbours beyond the local linear trend (second difference / 2)."""
    o = np.argsort(np.asarray(x, float))
    rows = []
    for k, v in stats.items():
        v = np.asarray(v, float)[o]
        step = np.abs(np.diff(v, 2)) / 2 if len(v) > 2 else np.abs(np.diff(v))
        i = int(np.argmax(step))
        rows.append(dict(stat=k, max_step=float(step[i]), at=float(np.asarray(x, float)[o][i + 1]), tol=float(tol[k]),
                         ok=bool(step[i] <= tol[k])))
    return pd.DataFrame(rows)


def rotate_lon(cond, names, deg=180.0):
    """Every input of the column moved by deg of longitude; the local solar hour columns are kept (they are solar)."""
    c = np.array(cond, np.float32, copy=True)
    i = names.index("lon")
    c[:, i] = (c[:, i] + deg + 180) % 360 - 180
    return c


def reverse_lat(cond, names):
    """Latitude mirrored and the season shifted by half a year (doy + 182.6 d), so the season matches."""
    c = np.array(cond, np.float32, copy=True)
    c[:, names.index("lat")] *= -1
    s, co = names.index("doy_sin"), names.index("doy_cos")
    c[:, s], c[:, co] = -c[:, s], -c[:, co]                                           # angle + pi
    return c


def involution_artifact(sample_mean, cond, names, cols, how="rotate"):
    """sample_mean(cond) -> (N, C) member mean. Mean |difference| on columns cols between the original and the moved
    inputs, with the moved inputs taken back to the same place: for a model without location leaks it is ~0
    only if the statics move with the column (the caller passes statics of the moved place in cond already)."""
    moved = rotate_lon(cond, names) if how == "rotate" else reverse_lat(cond, names)
    a, b = sample_mean(cond)[:, cols], sample_mean(moved)[:, cols]
    return float(np.mean(np.abs(a - b)))


# ---------------------------------------------------------------- gates
def _summary(stem):
    p = stem + "_report/summary.csv"
    return pd.read_csv(p) if os.path.exists(p) else None


def igra_shear99(lat0, lat1, lon0, lon1, years=(2024, 2025), store="data/igra_heights", q=0.99):
    """99th percentile of the 10 m - 1 km shear magnitude (m/s) of IGRA soundings inside the box in the gate years,
    or NaN when no station / sounding is there. Holdout places are refused by holdout.check."""
    from tempest.geo import holdout
    from tempest.ingest.igra_to_heights import load
    from tempest.profiles.to_heights import HEIGHTS
    j1 = int(np.argmin(np.abs(np.asarray(HEIGHTS) - 1000.0)))
    vals = []
    for p in sorted(glob.glob(os.path.join(store, "*.npz"))):
        d = load(p)
        la, lo = float(np.asarray(d["lat"]).ravel()[0]), (float(np.asarray(d["lon"]).ravel()[0]) + 180) % 360 - 180
        if not (lat0 <= la <= lat1 and lon0 <= lo <= lon1):
            continue
        holdout.check([la], [lo])
        t = np.asarray(d["time"]).astype("datetime64[Y]").astype(int) + 1970
        k = (t >= years[0]) & (t <= years[1])
        s = np.hypot(d["u"][k, j1] - d["u"][k, 0], d["v"][k, j1] - d["v"][k, 0])
        vals.append(s[np.isfinite(s)])
    v = np.concatenate(vals) if vals else np.array([])
    return float(np.quantile(v, q)) if len(v) > 50 else np.nan


def gate_g2(rows):
    """rows: list of dict(box, stem, igra_q99) for each leave-one-box-out score (stem = score output stem).
    Gates (GLOBAL_PLAN G2): CRPSS > 0 vs the box's ERA5 climatology in every band; cov90 in 87-93 % in every band;
    shear99 (10 m - 1 km) within +-12 % of ERA5 and +-15 % of IGRA."""
    out = []
    for r in rows:
        s = _summary(r["stem"])
        t = pd.read_csv(r["stem"] + "_tail.csv") if os.path.exists(r["stem"] + "_tail.csv") else None
        if s is None:
            out.append(dict(box=r["box"], verdict="MISSING", why=f"no {r['stem']}_report/summary.csv"))
            continue
        why = []
        bad = s[s.skill_unknown <= 0]
        why += [f"CRPSS {v} {b} {x:+.3f}" for v, b, x in zip(bad["var"], bad.band, bad.skill_unknown)]
        bad = s[(s.cov90_unknown < 0.87) | (s.cov90_unknown > 0.93)]
        why += [f"cov90 {v} {b} {x:.3f}" for v, b, x in zip(bad["var"], bad.band, bad.cov90_unknown)]
        sh = np.nan
        if t is not None and "q99_model" in t:
            row = t[t.field == "shear_10m_1km"].iloc[0]
            sh = row.q99_model / row.q99_truth - 1
            if abs(sh) > 0.12:
                why.append(f"shear99 vs ERA5 {sh:+.1%}")
            if np.isfinite(r.get("igra_q99", np.nan)):
                si = row.q99_model / r["igra_q99"] - 1
                if abs(si) > 0.15:
                    why.append(f"shear99 vs IGRA {si:+.1%}")
        else:
            why.append("no tail quantiles (score with --tail)")
        out.append(dict(box=r["box"], min_crpss=float(s.skill_unknown.min()), cov90_lo=float(s.cov90_unknown.min()),
                        cov90_hi=float(s.cov90_unknown.max()), shear99_vs_era5=sh, verdict="PASS" if not why else "FAIL",
                        why="; ".join(why)))
    return pd.DataFrame(out)


def gate_unseen(crps_seen, crps_unseen, var):
    """G3: unseen-station CRPS within 0.08 K (T) / 0.15 m/s (wind) of the seen stations."""
    lim = {"T": 0.08, "u": 0.15, "v": 0.15}
    return {v: dict(gap=float(crps_unseen[v] - crps_seen[v]), lim=lim[v], ok=bool(crps_unseen[v] - crps_seen[v] <= lim[v]))
            for v in var if v in lim}


def gate_g4(rows, knndm_crps=None, block_crps=None, block_ci=None, rot_artifact=None):
    """rows: list of dict(fold, stem) for LOCO / leave-continent-out scores. CRPSS > 0 everywhere and 99 / 99.9th
    shear error < 10 %; kNNDM CV within the block-CV bootstrap band; rotate-longitude artifact < 0.05 K."""
    out = []
    for r in rows:
        s = _summary(r["stem"])
        t = pd.read_csv(r["stem"] + "_tail.csv") if os.path.exists(r["stem"] + "_tail.csv") else None
        why = [] if s is not None else ["no summary"]
        if s is not None:
            why += [f"CRPSS {v} {b} {x:+.3f}" for v, b, x in zip(s["var"], s.band, s.skill_unknown) if x <= 0]
        if t is not None and "q999_model" in t:
            row = t[t.field == "shear_10m_1km"].iloc[0]
            for q in ("q99", "q999"):
                e = row[f"{q}_model"] / row[f"{q}_truth"] - 1
                if abs(e) >= 0.10:
                    why.append(f"shear {q} {e:+.1%}")
        else:
            why.append("no tail quantiles")
        out.append(dict(fold=r["fold"], verdict="PASS" if not why else "FAIL", why="; ".join(why)))
    if knndm_crps is not None and block_ci is not None:
        ok = block_ci[0] <= knndm_crps <= block_ci[1]
        out.append(dict(fold="kNNDM vs block CV", verdict="PASS" if ok else "FAIL",
                        why="" if ok else f"kNNDM CRPS {knndm_crps:.4f} outside block band {block_ci[0]:.4f}-{block_ci[1]:.4f}"))
    if rot_artifact is not None:
        out.append(dict(fold="rotate-longitude", verdict="PASS" if rot_artifact < 0.05 else "FAIL", why=f"artifact {rot_artifact:.3f} K"))
    return pd.DataFrame(out)


def bootstrap_ci(x, groups, n=1000, seed=0, q=(0.025, 0.975)):
    """Block bootstrap (resample groups, e.g. day blocks or folds) of the mean of x -> (lo, hi)."""
    x, groups = np.asarray(x, float), np.asarray(groups)
    u, inv = np.unique(groups, return_inverse=True)
    s, c = np.bincount(inv, x), np.bincount(inv)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(u), (n, len(u)))
    m = s[pick].sum(1) / c[pick].sum(1)
    return tuple(float(v) for v in np.quantile(m, q))


def stem_crps(stem, var=("u", "v", "T")):
    """Mean over bands of the model CRPS per variable from a score summary (crps_clim * (1 - skill_unknown)); None if missing."""
    s = _summary(stem)
    if s is None:
        return None
    s = s.assign(crps=s.crps_clim * (1 - s.skill_unknown))
    return {v: float(s.loc[s["var"] == v, "crps"].mean()) for v in var if (s["var"] == v).any()}


def fold_rows(d, by, size_km=1000.0, k=5, seed=0, koppen_tab=None, pred_n=20000):
    """New row_group for a build_global file (row_point sidecar): 'block' (size_km blocks, k folds), 'knndm' (k folds
    against a uniform global prediction set of pred_n points), 'continent', 'koppen' (needs koppen_tab)."""
    from tempest.geo import global_store as gs
    pts = gs.points()
    up, inv = np.unique(np.asarray(d["row_point"]), return_inverse=True)
    la, lo = pts["lat"][up], pts["lon"][up]
    if by == "block":
        g = block_folds_km(la, lo, size_km, k, seed)
    elif by == "knndm":
        i = np.arange(pred_n) + 0.5                                                    # Fibonacci sphere: uniform over the Earth
        plat, plon = np.rad2deg(np.arcsin(1 - 2 * i / pred_n)), (np.rad2deg(np.pi * (1 + 5 ** 0.5) * i) + 180) % 360 - 180
        g = knndm(la, lo, plat, plon, k, seed)[0]
    elif by == "continent":
        from tempest.geo.statics import statics
        g = continent(la, lo, statics(la, lo)["lsm"] > 0.5)
    elif by == "koppen":
        from tempest.geo import koppen
        g = koppen.lookup(koppen_tab, la, lo)
    else:
        raise ValueError(by)
    return np.asarray(g)[inv].astype(np.int16)


def _shear_t2m(raw):
    """Raw targets (n, D) -> 10 m - 1 km shear magnitude (m/s) and t2m (K)."""
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    nh = len(HEIGHTS)
    j1 = int(np.argmin(np.abs(np.asarray(HEIGHTS) - 1000.0)))
    du, dv = raw[:, 1:j1 + 1].sum(1), raw[:, nh + 1:nh + j1 + 1].sum(1)          # u, v stored as 10 m value + height steps
    return np.hypot(du, dv), raw[:, len(PROFILE) * nh]


def transect_stats(model, cond, x, m=50, bin_w=2.0, seed=0):
    """Model draws at every row -> per x bin (bin_w wide): median t2m, mean member spread of t2m, 99th shear 10 m - 1 km."""
    import torch
    from tempest.generator.sample import Sampler
    smp = Sampler(model)
    torch.manual_seed(seed)
    out = smp(np.repeat(np.asarray(cond, np.float32), m, 0))
    sh, t2 = (v.reshape(len(cond), m) for v in _shear_t2m(out))
    b = np.floor(np.asarray(x, float) / bin_w)
    rows = []
    for u in np.unique(b):
        j = b == u
        rows.append(dict(x=(u + 0.5) * bin_w, n=int(j.sum()), median_t2m=float(np.median(t2[j])),
                         spread_t2m=float(t2[j].std(1).mean()), shear99=float(np.quantile(sh[j], 0.99))))
    return pd.DataFrame(rows)


def seam(models, cond, x, m=50, bin_w=2.0):
    """Seam test (G3): stats per x bin for every seed model; step of the seed mean vs the seed tolerance (the largest
    seed-to-seed difference of that statistic over the bins)."""
    if len(models) < 2:
        raise SystemExit("seam needs two or more seed models: the tolerance is the seed spread")
    tabs = [transect_stats(p, cond, x, m, bin_w) for p in models]
    keys = ["median_t2m", "spread_t2m", "shear99"]
    st = np.stack([t[keys].to_numpy() for t in tabs])                                    # (seeds, bins, stats)
    tol = {k: float((st[..., i].max(0) - st[..., i].min(0)).max()) for i, k in enumerate(keys)}
    return seam_check(tabs[0]["x"].to_numpy(), {k: st[..., i].mean(0) for i, k in enumerate(keys)}, tol)


def rotate_artifact(model, cond, names, m=20, seed=0):
    """Rotate-longitude test (G4): mean |change| of the member-mean T profile (K) when every column moves 180 deg of
    longitude (solar hour kept), same noise. A model without a lon input gives 0 by construction."""
    import torch
    from tempest.generator.sample import Sampler
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    if "lon" not in names:
        return 0.0
    smp, nh, it = Sampler(model), len(HEIGHTS), PROFILE.index("T")

    def tmean(c):
        torch.manual_seed(seed)
        r = smp(np.repeat(np.asarray(c, np.float32), m, 0))
        return np.cumsum(r[:, it * nh:(it + 1) * nh], 1).reshape(len(c), m, nh).mean(1)  # 10 m value + steps -> profile
    return float(np.mean(np.abs(tmean(cond) - tmean(rotate_lon(cond, names)))))


def gate_g3(seen, unseen, block_stems=(), seam_tabs=(), modef=None):
    """seen / unseen: score stems per seed (lists); block_stems: 1,000 km block-CV fold stems (CRPSS > 0 reported);
    seam_tabs: (name, seam frame); modef: (continental csv, per-box csv) of modeF_global score at NM/TX -> verdict frame."""
    rows = []
    for a, b in zip(seen, unseen):
        cs, cu = stem_crps(a), stem_crps(b)
        if cs is None or cu is None:
            rows.append(dict(check=f"unseen {b}", verdict="MISSING", why="no summary"))
            continue
        for v, g in gate_unseen(cs, cu, ["T", "u", "v"]).items():
            rows.append(dict(check=f"unseen {v} {os.path.basename(b)}", value=g["gap"], lim=g["lim"], verdict="PASS" if g["ok"] else "FAIL"))
    for st in block_stems:
        s = _summary(st)
        mn = float(s.skill_unknown.min()) if s is not None else np.nan
        rows.append(dict(check=f"block CV {os.path.basename(st)} min CRPSS", value=mn, lim=0.0,
                         verdict="MISSING" if s is None else ("PASS" if mn > 0 else "FAIL")))
    for name, t in seam_tabs:
        for r in t.itertuples():
            rows.append(dict(check=f"seam {name} {r.stat}", value=r.max_step, lim=r.tol, verdict="PASS" if r.ok else "FAIL"))
    if modef is not None and all(os.path.exists(p) for p in modef):
        c, b = (pd.read_csv(p) for p in modef)
        j = c.merge(b, on=["lead_days", "var"], suffixes=("_cont", "_box"))
        j = j[(j.lead_days >= 1) & (j.lead_days <= 7)]
        bad = j[j.crps_cor_cont >= j.crps_cor_box]
        rows.append(dict(check="Mode F continental vs per-box NM/TX 1-7 d", value=float((j.crps_cor_cont / j.crps_cor_box).mean()) if len(j) else np.nan,
                         lim=1.0, verdict="PASS" if bad.empty and len(j) else "FAIL",
                         why="; ".join(f"{v} {L} d" for v, L in zip(bad["var"], bad.lead_days))))
    elif modef is not None:
        rows.append(dict(check="Mode F continental vs per-box", verdict="MISSING", why="no Mode F score files (needs data/raw/wb2_hres_global)"))
    return pd.DataFrame(rows)


def _cond_rows(path, first=2024, last=2025, rows=20000, seed=0):
    from tempest.generator.train import load_npz
    d = load_npz(path)
    yr = np.asarray(d["year"])
    k = np.flatnonzero((yr >= first) & (yr <= min(last, 2025)))                         # G stages never read 2026
    k = np.sort(np.random.default_rng(seed).choice(k, min(rows, len(k)), replace=False))
    return d, k


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gate-g2", help="leave-one-box-out verdict from the score files listed in DIR/lobo_runs.csv")
    g.add_argument("--dir", required=True)
    q = sp.add_parser("subset", help="rows of one row_group (and years) of a dataset -> a smaller file (fold scoring)")
    q.add_argument("--data", required=True)
    q.add_argument("--group", type=int, required=True)
    q.add_argument("--first-year", type=int, default=2024)
    q.add_argument("--last-year", type=int, default=2025)
    q.add_argument("--out", required=True)
    r = sp.add_parser("regroup", help="copy of a build_global file with row_group = block / knndm / continent / koppen folds")
    r.add_argument("--data", required=True)
    r.add_argument("--by", choices=["block", "knndm", "continent", "koppen"], required=True)
    r.add_argument("--k", type=int, default=5)
    r.add_argument("--size-km", type=float, default=1000.0)
    r.add_argument("--koppen")
    r.add_argument("--out", required=True)
    e = sp.add_parser("seam", help="seam transect (x = longitude) from two or more seed models")
    e.add_argument("--data", required=True)
    e.add_argument("--models", nargs="+", required=True)
    e.add_argument("--bin", type=float, default=2.0)
    e.add_argument("--rows", type=int, default=20000)
    e.add_argument("--m", type=int, default=50)
    e.add_argument("--out", required=True)
    o = sp.add_parser("rotate", help="rotate-longitude artifact (K) of one model")
    o.add_argument("--data", required=True)
    o.add_argument("--model", required=True)
    o.add_argument("--rows", type=int, default=2000)
    o.add_argument("--out", required=True)
    v = sp.add_parser("aoa", help="AOA / DI table from training rows (<= 2023), folds = the file's row_group")
    v.add_argument("--data", required=True)
    v.add_argument("--rows", type=int, default=20000)
    v.add_argument("--out", required=True)
    g3 = sp.add_parser("gate-g3")
    g3.add_argument("--seen", nargs="+", required=True, help="score stems on the seen IGRA sites, one per seed")
    g3.add_argument("--unseen", nargs="+", required=True, help="score stems on the held IGRA sites, same seed order")
    g3.add_argument("--blocks", nargs="*", default=[])
    g3.add_argument("--seam", nargs="*", default=[], help="seam csv files")
    g3.add_argument("--modef", nargs=2, metavar=("CONT_CSV", "BOX_CSV"))
    g3.add_argument("--out", required=True)
    g4 = sp.add_parser("gate-g4", help="reads DIR/loco_runs.csv, DIR/knndm_runs.csv, DIR/block_runs.csv (fold,stem), DIR/rotate.txt")
    g4.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd in ("subset", "regroup", "aoa", "seam", "rotate", "gate-g3"):
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    if a.cmd == "gate-g2":
        runs = pd.read_csv(os.path.join(a.dir, "lobo_runs.csv"))                    # box, stem, lat0, lat1, lon0, lon1
        rows = [dict(box=r.box, stem=r.stem, igra_q99=igra_shear99(r.lat0, r.lat1, r.lon0, r.lon1)) for r in runs.itertuples()]
        v = gate_g2(rows)
        v.to_csv(os.path.join(a.dir, "gate_g2.csv"), index=False)
        print(v.to_string(index=False))
        print("G2 gate:", "PASS" if (v.verdict == "PASS").all() else "FAIL")
    elif a.cmd == "subset":
        d = dict(np.load(a.data))
        n = len(d["year"])
        k = (np.asarray(d["row_group"]) == a.group) & (d["year"] >= a.first_year) & (d["year"] <= min(a.last_year, 2025))
        with open(a.out, "wb") as fh:
            np.savez(fh, **{q: (x[k] if np.ndim(x) and len(x) == n else x) for q, x in d.items()})
        print(f"wrote {a.out}: {k.sum():,} rows of group {a.group}")
    elif a.cmd == "regroup":
        d = dict(np.load(a.data))
        d["row_group"] = fold_rows(d, a.by, a.size_km, a.k, koppen_tab=dict(np.load(a.koppen)) if a.koppen else None)
        d["group_kind"] = np.array(a.by)
        with open(a.out, "wb") as fh:
            np.savez(fh, **d)
        print(f"wrote {a.out}: row_group = {a.by}, counts {np.bincount(d['row_group']).tolist()}")
    elif a.cmd == "seam":
        from tempest.geo import global_store as gs
        d, k = _cond_rows(a.data, rows=a.rows)
        lon = gs.points()["lon"][np.asarray(d["row_point"])[k]]
        t = seam(a.models, d["cond"][k], lon, a.m, a.bin)
        t.to_csv(a.out, index=False)
        print(t.to_string(index=False))
    elif a.cmd == "rotate":
        d, k = _cond_rows(a.data, rows=a.rows)
        art = rotate_artifact(a.model, d["cond"][k], [str(x) for x in d["cond_names"]])
        with open(a.out, "w") as fh:
            fh.write(f"{art}\n")
        print(f"rotate-longitude artifact {art:.4f} K")
    elif a.cmd == "aoa":
        d, k = _cond_rows(a.data, 1991, 2023, a.rows)
        f = aoa_fit(d["cond"][k], np.asarray(d["row_group"])[k])
        f.pop("di_cv")
        with open(a.out, "wb") as fh:
            np.savez(fh, **{q: np.asarray(x, np.float32) for q, x in f.items()}, cond_names=d["cond_names"])
        print(f"wrote {a.out}: DI threshold {f['thr']:.3f} over {len(k):,} rows")
    elif a.cmd == "gate-g3":
        v = gate_g3(a.seen, a.unseen, a.blocks, [(os.path.basename(p), pd.read_csv(p)) for p in a.seam], a.modef)
        v.to_csv(a.out, index=False)
        print(v.to_string(index=False))
        print("G3 gate:", "PASS" if len(v) and (v.verdict == "PASS").all() else "FAIL")
    elif a.cmd == "gate-g4":
        def rd(n):
            p = os.path.join(a.dir, n)
            return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame(columns=["fold", "stem"])
        mean_t = lambda df: [c["T"] for c in (stem_crps(s) for s in df.stem) if c and "T" in c]
        kn, bl = mean_t(rd("knndm_runs.csv")), mean_t(rd("block_runs.csv"))
        rot = os.path.join(a.dir, "rotate.txt")
        with open(rot) if os.path.exists(rot) else open(os.devnull) as fh:
            txt = fh.read().strip()
        v = gate_g4([dict(fold=r.fold, stem=r.stem) for r in rd("loco_runs.csv").itertuples()],
                    knndm_crps=float(np.mean(kn)) if kn else None,
                    block_ci=bootstrap_ci(bl, np.arange(len(bl))) if len(bl) > 1 else None,
                    rot_artifact=float(txt) if txt else None)
        v.to_csv(os.path.join(a.dir, "gate_g4.csv"), index=False)
        print(v.to_string(index=False))
        print("G4 gate:", "PASS" if len(v) and (v.verdict == "PASS").all() else "FAIL")


if __name__ == "__main__":
    main()
