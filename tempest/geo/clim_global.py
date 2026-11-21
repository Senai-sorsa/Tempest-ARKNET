"""G4 global climatology anchor (GLOBAL_PLAN G4, D): mean and spread of every profile column as an annual x diurnal
harmonic series (tempest.geo.clim basis, 35 terms), compressed to 12 EOFs over the columns and stored on a 1 deg grid.

    python -m tempest.geo.clim_global fit --out models/global/clim_1deg.npz [--first-year 1991 --last-year 2023]
    from tempest.geo import clim_global as cg
    tab = cg.load("models/global/clim_1deg.npz")
    mu, sd = cg.predict(tab, lat, lon, times)        # (n, K) in the columns of tab["names"] (u, v, T, RH at 44 heights, t2m, sp, rh2m)

Fit: pass 1 over the store accumulates per point the normal equations of y on the basis (training years only) -> mean
coefficients; pass 2 fits log(residual^2) on the same basis (the tempest.geo.clim spread model; E[y^2] - mu^2 cancels
catastrophically for sp). Each coefficient set (P, 35, K) -> standardised -> EOFs over the K columns (12 kept) -> per
point loadings (35 x 12) -> inverse-distance weights (4 nearest store points) onto the 1 deg grid, stored float16.
"""
import argparse
import os

import numpy as np

from tempest.geo.clim import basis

N_EOF = 12


def columns():
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    return [f"{v}_{int(h)}" for v in PROFILE for h in HEIGHTS] + ["t2m", "sp", "rh2m"]


def _rows(m, pts, oro):
    """Decoded store month -> y (days, P, K) physical columns."""
    from tempest.geo import global_store as gs
    from tempest.profiles.to_heights import PROFILE, fill_top
    pr, rh2m = gs.profiles(m, pts, oro_m=oro)
    top = [fill_top(pr[v]) for v in PROFILE]                                      # heights above the 50 hPa top, as build_global
    return np.concatenate(top + [m["t2m"][..., None], m["sp"][..., None], rh2m[..., None]], -1)


def accumulate(first=1991, last=2023, store=None, every=1, c_mu=None, eps=None):
    """One pass over the store months (every = keep 1 day in n). Without c_mu: per point XtX (P, B, B) and Xty (P, B, K)
    of the columns y, plus pooled column variances. With c_mu (P, B, K): Xtz of z = log(residual^2 + eps) + 1.2704
    (the tempest.geo.clim spread model; exp(0.5 * fit) is the standard deviation)."""
    from tempest.geo import global_store as gs
    from tempest.geo.clim import LOGCHI2
    from tempest.geo.statics import statics
    if last > 2023:
        raise ValueError("the global climatology uses training years only (<= 2023)")
    store = store or gs.STORE
    pts = gs.points(store)
    oro = statics(pts["lat"], pts["lon"])["oro_m"]
    P, K, B = len(pts["lat"]), len(columns()), basis(np.array(["2000-01-01"], "datetime64[h]"), 0.0).shape[1]
    xtx, xty = np.zeros((P, B, B)), np.zeros((P, B, K))
    s1, s2, n = np.zeros(K), np.zeros(K), 0
    for name in gs.months(first, last, store):
        m = gs.month(name, store)
        y = _rows(m, pts, oro)[::every]                                                 # (d, P, K)
        t = m["valid_time"][::every]
        X = basis(np.repeat(t, P), np.tile(pts["lon"], len(t))).reshape(len(t), P, B)
        ok = np.isfinite(y).all(-1, keepdims=True)                                     # rows with a gap drop out whole
        X0, y0 = np.where(ok, X, 0.0), np.where(ok, y, 0.0)
        if c_mu is not None:
            r = y0 - np.einsum("dpb,pbk->dpk", X0, c_mu)
            y0 = np.where(ok, np.log(r * r + eps) + LOGCHI2, 0.0)
        else:
            xtx += np.einsum("dpa,dpb->pab", X0, X0)
            s1, s2, n = s1 + y0.sum((0, 1)), s2 + (y0 * y0).sum((0, 1)), n + int(ok.sum())
        xty += np.einsum("dpa,dpk->pak", X0, y0)
        print(f"{name}{' (spread pass)' if c_mu is not None else ''}: {ok.mean():.1%} complete rows", flush=True)
    var = s2 / max(n, 1) - (s1 / max(n, 1)) ** 2
    return pts, xtx, xty, var


def solve(xtx, xty, ridge=1e-6):
    """Per point least squares (P, B, B), (P, B, K) -> coefficients (P, B, K)."""
    reg = (ridge * np.trace(xtx, axis1=1, axis2=2)[:, None, None] + 1e-9) * np.eye(xtx.shape[1])  # +1e-9: points with no rows
    return np.linalg.solve(xtx + reg, xty)


def compress(c, n_eof=N_EOF):
    """(P, B, K) coefficients -> EOFs over K of the standardised coefficients: loadings (P, B, n_eof)."""
    P, B, K = c.shape
    flat = c.reshape(P * B, K)
    mean, scale = flat.mean(0), flat.std(0) + 1e-9
    u, s, vt = np.linalg.svd((flat - mean) / scale, full_matrices=False)
    return dict(load=(u[:, :n_eof] * s[:n_eof]).reshape(P, B, n_eof), eof=vt[:n_eof], mean=mean, scale=scale,
                explained=float((s[:n_eof] ** 2).sum() / (s ** 2).sum()))


def to_grid(lat, lon, values, res=1.0, k=4):
    """Point values (P, ...) -> 1 deg grid (nlat, nlon, ...) by inverse-distance weights over the k nearest points."""
    from scipy.spatial import cKDTree
    from tempest.scoring.spatial import xyz
    glat = np.arange(-90, 90 + res / 2, res)
    glon = np.arange(-180, 180, res)
    la, lo = np.meshgrid(glat, glon, indexing="ij")
    d, i = cKDTree(xyz(lat, lon)).query(xyz(la.ravel(), lo.ravel()), k)
    w = 1.0 / np.maximum(d, 1e-6) ** 2
    w /= w.sum(1, keepdims=True)
    g = np.einsum("nk,nk...->n...", w, np.asarray(values)[i])
    return glat, glon, g.reshape(len(glat), len(glon), *np.asarray(values).shape[1:])


def fit(first=1991, last=2023, store=None, every=1, res=1.0):
    pts, xtx, xty, var = accumulate(first, last, store, every)
    c_mu = solve(xtx, xty)
    eps = 1e-4 * np.maximum(var, 1e-12)                       # keeps log(r^2) finite where a column sits at its bound
    _, _, xtz, _ = accumulate(first, last, store, every, c_mu=c_mu, eps=eps)
    c_lv = solve(xtx, xtz)
    tab = dict(names=np.array(columns()), first=first, last=last, n_eof=N_EOF)
    for k, c in (("mu", c_mu), ("logvar", c_lv)):
        e = compress(c)
        glat, glon, g = to_grid(pts["lat"], pts["lon"], e["load"], res)
        tab |= {f"{k}_grid": g.astype(np.float16), f"{k}_eof": e["eof"].astype(np.float32),
                f"{k}_mean": e["mean"].astype(np.float32), f"{k}_scale": e["scale"].astype(np.float32),
                f"{k}_explained": e["explained"]}
    tab |= dict(lat=glat, lon=glon)
    return tab


def load(path):
    return dict(np.load(path))


def _bilinear(tab, g, lat, lon):
    glat, glon = tab["lat"], tab["lon"]
    res = float(glat[1] - glat[0])
    fi = (np.clip(np.asarray(lat, float), -90, 90) - glat[0]) / res
    fj = ((np.asarray(lon, float) + 180) % 360 - 180 - glon[0]) / res
    i0 = np.clip(np.floor(fi).astype(int), 0, len(glat) - 2)
    j0 = np.floor(fj).astype(int) % len(glon)
    j1 = (j0 + 1) % len(glon)                                                       # wraps at the date line
    a, b = (fi - i0)[:, None, None], (fj - np.floor(fj))[:, None, None]
    g = g.astype(np.float32)
    return (1 - a) * ((1 - b) * g[i0, j0] + b * g[i0, j1]) + a * ((1 - b) * g[i0 + 1, j0] + b * g[i0 + 1, j1])


def predict(tab, lat, lon, times):
    """-> mu, sd (n, K) at the points and UTC times (local solar time from lon, as tempest.geo.clim)."""
    X = basis(np.asarray(times), np.asarray(lon, float))                               # (n, B)
    out = {}
    for k in ("mu", "logvar"):
        load_ = _bilinear(tab, tab[f"{k}_grid"], lat, lon)                              # (n, B, E)
        coef = np.einsum("nbe,ek->nbk", load_, tab[f"{k}_eof"]) * tab[f"{k}_scale"] + tab[f"{k}_mean"]
        out[k] = np.einsum("nb,nbk->nk", X, coef)
    return out["mu"], np.exp(0.5 * out["logvar"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--first-year", type=int, default=1991)
    f.add_argument("--last-year", type=int, default=2023)
    f.add_argument("--every", type=int, default=1, help="keep one day in n (RAM / time)")
    f.add_argument("--res", type=float, default=1.0, help="grid step in degrees (G5 bundle: 2 deg ~27 MB, 1 deg ~110 MB)")
    a = ap.parse_args()
    t = fit(a.first_year, a.last_year, every=a.every, res=a.res)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "wb") as fh:
        np.savez(fh, **t)
    print(f"wrote {a.out}: {os.path.getsize(a.out) / 1e6:.0f} MB, EOF share explained mu {t['mu_explained']:.4f} "
          f"logvar {t['logvar_explained']:.4f}", flush=True)


if __name__ == "__main__":
    main()
