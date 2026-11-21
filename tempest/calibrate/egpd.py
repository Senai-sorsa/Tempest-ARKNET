"""G4 shear tail (GLOBAL_PLAN G4, section 5.2): extended GPD for the balloon step shear |dV| / dz between neighbour
model heights, F(y) = H_xi(y / sigma)^kappa with H_xi(x) = 1 - (1 + xi x)^(-1/xi) (Naveau et al. 2016; covers the whole
range, no threshold). xi and kappa per height band, sigma = exp(b0 + b1 ERA5 shear + b2 N^2 + b3 height) per row.

    python -m tempest.calibrate.egpd fit --pairs data/train/balloon_pairs.npz --out models/global/egpd.npz
    python -m tempest.calibrate.egpd check --pairs data/train/balloon_pairs.npz --out results/G4/egpd_check.csv

check: 1,000 km station blocks (5 folds), fit on the others (<= 2023), held-out 2024-25 rows: model vs empirical 99th
and 99.9th percentiles per band; gate |model / empirical - 1| <= 10 %.
"""
import argparse
import os

import numpy as np
from scipy.optimize import minimize

from tempest.profiles.to_heights import HEIGHTS

BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]
QS = (0.99, 0.999)
TOL = 0.10


def _h(x, xi):
    return -np.expm1(-np.log1p(xi * x) / xi)


def cdf(y, sigma, xi, kappa):
    return _h(np.maximum(y, 0) / sigma, xi) ** kappa


def ppf(p, sigma, xi, kappa):
    return sigma * np.expm1(-xi * np.log1p(-np.asarray(p) ** (1 / kappa))) / xi


def nll(y, sigma, xi, kappa):
    """Negative log density summed; y > 0."""
    x = y / sigma
    lh = np.log(_h(x, xi))
    lpdf = np.log(kappa) + (kappa - 1) * lh - (1 / xi + 1) * np.log1p(xi * x) - np.log(sigma)
    return -lpdf.sum()


def _unpack(th, X):
    k = X.shape[1]
    return np.exp(X @ th[:k]), np.exp(th[k]), np.exp(th[k + 1])         # sigma, xi > 0 (heavy tail), kappa > 0


def fit_band(y, X):
    """y (n,) > 0, X (n, k) with a constant column -> theta (sigma coefficients, log xi, log kappa)."""
    y, X = np.asarray(y, np.float64), np.asarray(X, np.float64)          # float32 rows flatten the finite-difference gradient
    ok = np.isfinite(y) & (y > 0) & np.isfinite(X).all(1)
    y, X = y[ok], X[ok]
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Z = np.concatenate([X[:, :1], (X[:, 1:] - mu) / sd], 1)                  # standardised covariates, mean NLL: well scaled
    th0 = np.zeros(Z.shape[1] + 2)
    th0[0], th0[-2] = np.log(np.median(y)), np.log(0.1)

    def f(th):
        s, xi, ka = _unpack(th, Z)
        v = nll(y, s, xi, ka) / len(y)
        return v if np.isfinite(v) else 1e10
    r = minimize(f, th0, method="L-BFGS-B", bounds=[(-20, 20)] * Z.shape[1] + [(-6, 0.0), (-4, 4)])  # xi <= 1: finite mean
    th = r.x.copy()
    th[1:Z.shape[1]] = r.x[1:Z.shape[1]] / sd                                   # back to coefficients on the raw X
    th[0] = r.x[0] - (r.x[1:Z.shape[1]] * mu / sd).sum()
    return th


def step_shear(prof):
    """(n, 4, 44) profiles (u, v first) -> (n, 43) |dV| / dz in m/s per km at the layer midpoints."""
    dz = np.diff(np.asarray(HEIGHTS, float)) / 1000.0
    return np.hypot(np.diff(prof[:, 0], axis=1), np.diff(prof[:, 1], axis=1)) / dz


def design(era):
    """ERA5 profiles (n, 4, 44) -> covariates per layer (n, 43, 5): 1, log(1 + ERA5 step shear), N^2 (1e-4 s^-2),
    height (km), log layer depth (sigma ~ power laws in shear and depth)."""
    zm = 0.5 * (np.asarray(HEIGHTS[1:], float) + np.asarray(HEIGHTS[:-1], float))
    T = era[:, 2]
    n2 = 9.80665 / (0.5 * (T[:, 1:] + T[:, :-1])) * (np.diff(T, axis=1) / np.diff(np.asarray(HEIGHTS, float)) + 9.80665 / 1004.0)
    sh = step_shear(era)
    n = len(era)
    ldz = np.log(np.diff(np.asarray(HEIGHTS, float)) / 1000.0)
    return np.stack([np.ones_like(sh), np.log1p(sh), n2 * 1e4, np.broadcast_to(zm / 1000.0, (n, len(zm))),
                     np.broadcast_to(ldz, (n, len(zm)))], -1)


def _band_mask(lo, hi):
    zm = 0.5 * (np.asarray(HEIGHTS[1:], float) + np.asarray(HEIGHTS[:-1], float))
    return (zm >= lo) & (zm < hi)


def fit(pr, years=(1991, 2023)):
    yr = pr["time"].astype("datetime64[Y]").astype(int) + 1970
    k = (yr >= years[0]) & (yr <= years[1])
    y, X = step_shear(pr["obs"][k]), design(pr["era"][k])
    th = np.stack([fit_band(y[:, m].ravel(), X[:, m].reshape(-1, X.shape[-1])) for m in (_band_mask(*b) for b in BANDS)])
    return dict(theta=th, bands=np.array(BANDS), years=np.array(years))


def quantiles(tab, era, qs=QS):
    """-> (n, 43, len(qs)) predicted shear quantiles."""
    X = design(era)
    out = np.full(X.shape[:2] + (len(qs),), np.nan)
    for b, th in zip(BANDS, tab["theta"]):
        m = _band_mask(*b)
        s, xi, ka = _unpack(th, X[:, m])
        for j, q in enumerate(qs):
            out[:, m, j] = ppf(q, s, xi, ka)
    return out


def check(pr, pts, k=5, size_km=1000.0, seed=0):
    """Held-out station blocks: the model's unconditional quantile (mean of the per-row CDFs inverted by bisection on the
    pooled rows) against the empirical quantile per band."""
    import pandas as pd
    from tempest.scoring.spatial import block_folds_km
    us = np.unique(pr["point"])
    fold_of = dict(zip(us, block_folds_km(pts["lat"][us], pts["lon"][us], size_km, k, seed)))
    folds = np.array([fold_of[p] for p in pr["point"]])
    yr = pr["time"].astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for f in range(k):
        tr, te = (folds != f) & (yr <= 2023), (folds == f) & (yr >= 2024)
        if not tr.any() or not te.any():
            continue
        tab = fit({q: v[tr] for q, v in pr.items()})
        y, X = step_shear(pr["obs"][te]), design(pr["era"][te])
        for b, th in zip(BANDS, tab["theta"]):
            m = _band_mask(*b)
            yb, Xb = y[:, m].ravel(), X[:, m].reshape(-1, X.shape[-1])
            ok = np.isfinite(yb) & np.isfinite(Xb).all(1)
            yb, Xb = yb[ok], Xb[ok]
            s, xi, ka = _unpack(th, Xb)
            for q in QS:
                lo, hi = 0.0, float(np.nanmax(yb)) * 10 + 1
                for _ in range(60):                                         # mixture quantile by bisection
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if cdf(mid, s, xi, ka).mean() < q else (lo, mid)
                emp = float(np.quantile(yb, q))
                rows.append(dict(fold=f, band=f"{b[0]}-{b[1]}", q=q, n=len(yb), model=0.5 * (lo + hi), empirical=emp,
                                 ratio=0.5 * (lo + hi) / emp))
    df = pd.DataFrame(rows)
    df["pass"] = (df["ratio"] - 1).abs() <= TOL
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("fit", "check"):
        b = sp.add_parser(n)
        b.add_argument("--pairs", required=True)
        b.add_argument("--out", required=True)
    g = ap.parse_args()
    pr = dict(np.load(g.pairs))
    os.makedirs(os.path.dirname(g.out) or ".", exist_ok=True)
    if g.cmd == "fit":
        tab = fit(pr)
        with open(g.out, "wb") as fh:
            np.savez(fh, **tab)
        print(f"wrote {g.out}: xi per band {np.exp(tab['theta'][:, -2]).round(3)}, kappa {np.exp(tab['theta'][:, -1]).round(3)}")
    else:
        from tempest.geo import global_store as gs
        df = check(pr, gs.points())
        df.to_csv(g.out, index=False)
        print(df.groupby(["band", "q"])[["model", "empirical", "ratio"]].mean().round(3).to_string())
        print(f"gate (all |ratio - 1| <= {TOL:.0%}): {'PASS' if df['pass'].all() else 'FAIL'}")


if __name__ == "__main__":
    main()
