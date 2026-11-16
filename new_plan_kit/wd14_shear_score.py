"""New_Plan 19 WD14: the shear-aware score block printed with every wind verdict. Pure numpy, no data read here.
members: (n, T, H) ensemble of u (and of v) at H heights; truth: (T, H). Heights default 10, 47, 116, 200 m (index 0 = 10 m, last = 200 m).
Prints/returns: CRPS u, v, speed; |cov90 - 0.90| of u, v; CRPS of the 200 - 10 m speed difference; variogram score (p = 0.5) of the (u, v) pairs across heights.
Pass template (New_Plan 19 WD14): a wind change must not worsen the shear CRPS or the variogram score by more than 0.5 %.
Written into the header once; old verdicts are re-scored only as a report."""
import numpy as np

HEIGHTS = (10, 47, 116, 200)


def crps(x, y):
    """Ensemble CRPS, mean over everything; x (n, ...) members, y (...) truth. Sorted-sample form, O(n log n)."""
    n = x.shape[0]
    xs = np.sort(x, axis=0)
    w = (2 * np.arange(1, n + 1) - n - 1).reshape((n,) + (1,) * (x.ndim - 1))
    return float((np.abs(x - y).mean(0) - (w * xs).sum(0) / n ** 2).mean())


def cov90_gap(x, y):
    lo, hi = np.quantile(x, [0.05, 0.95], axis=0)
    return float(abs(((y >= lo) & (y <= hi)).mean() - 0.90))


def variogram(ux, vx, uy, vy, p=0.5, maxn=200):
    """Variogram score over all height pairs of u and of v: sum |obs diff|^p vs the ensemble mean of |member diff|^p, mean over T."""
    n, T, H = ux.shape
    ux, vx = ux[:maxn], vx[:maxn]
    tot = 0.0
    for a in range(H):
        for b in range(a + 1, H):
            for m, o in ((ux, uy), (vx, vy)):
                tot += float(((np.abs(o[:, a] - o[:, b]) ** p - (np.abs(m[:, :, a] - m[:, :, b]) ** p).mean(0)) ** 2).mean())
    return tot


def shear_scores(ux, vx, uy, vy):
    sx, sy = np.hypot(ux, vx), np.hypot(uy, vy)
    return {"crps_u": crps(ux, uy), "crps_v": crps(vx, vy), "crps_speed": crps(sx, sy),
            "cov90_gap_u": cov90_gap(ux, uy), "cov90_gap_v": cov90_gap(vx, vy),
            "crps_shear_200_10": crps(sx[..., -1] - sx[..., 0], sy[:, -1] - sy[:, 0]),
            "variogram_p05": variogram(ux, vx, uy, vy)}


def line(d):
    return "  ".join(f"{k} {v:.4f}" for k, v in d.items())


def _selfcheck():
    r = np.random.default_rng(0)
    T, H, n = 400, 4, 200
    base = r.normal(size=(T, 1)) * np.arange(1, H + 1)
    uy, vy = base + r.normal(size=(T, H)), r.normal(size=(T, H))
    good = lambda: (base + r.normal(size=(n, T, H)), r.normal(size=(n, T, H)))
    ux, vx = good()
    d = shear_scores(ux, vx, uy, vy)
    assert d["cov90_gap_u"] < 0.05 and d["cov90_gap_v"] < 0.05, d
    # a too narrow ensemble must score worse on CRPS and variogram
    nu, nv = base + 0.2 * r.normal(size=(n, T, H)), 0.2 * r.normal(size=(n, T, H))
    dn = shear_scores(nu, nv, uy, vy)
    assert dn["crps_u"] > d["crps_u"] and dn["cov90_gap_u"] > d["cov90_gap_u"], (d, dn)
    assert abs(crps(np.zeros((5, 3)), np.ones(3)) - 1.0) < 1e-12  # point forecast: CRPS = |error|
    print("selfcheck ok:", line(d))


if __name__ == "__main__":
    _selfcheck()
