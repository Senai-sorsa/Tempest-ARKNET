"""Tropopause-relative coordinate (New_Plan 17, UR6; opt-in, nothing in the tool calls it yet).

    zt = tropopause(T, z)               # T (n, k) in K on heights z (k,) in m -> (n,) height of the lapse-rate tropopause, NaN if none
    rel = z[None, :] - zt[:, None]      # distance above (+) / below (-) the tropopause
    qm = fit_qmap(x, y, rel_x, rel_y)   # quantile map per distance bin, members x -> balloons y (both in the relative coordinate)
    x2 = apply_qmap(qm, x, rel)         # members corrected; columns outside the bins (or rows without a tropopause) unchanged

Tropopause rule (WMO 1957, the lapse-rate tropopause): the lowest level above `z_min` where the lapse rate falls to 2 K/km or less and its
average between that level and every level up to 2 km higher stays at 2 K/km or less. On a coarse grid the rule is applied between grid
levels (the level below the first such layer). Fallback (`coldest=True`): the coldest level between z_min and z_max when the rule finds none.
"""
import numpy as np

LAPSE_MAX = 2.0                                  # K/km
BINS = np.arange(-4000.0, 4000.1, 500.0)         # distance from the tropopause, m (bin edges)


def tropopause(T, z, z_min=5000.0, z_max=20000.0, coldest=True):
    T, z = np.atleast_2d(np.asarray(T, float)), np.asarray(z, float)
    out = np.full(len(T), np.nan)
    lapse = -np.diff(T, axis=1) / (np.diff(z) / 1000.0)            # K/km between levels i and i+1
    for r in range(len(T)):
        for i in range(len(z) - 1):
            if z[i] < z_min or z[i] > z_max or not np.isfinite(lapse[r, i]):
                continue
            if lapse[r, i] > LAPSE_MAX:
                continue
            top = z[i] + 2000.0
            j = np.flatnonzero((z > z[i]) & (z <= top))
            if not len(j) or not np.isfinite(T[r, j]).all():
                continue
            if all((T[r, i] - T[r, jj]) / ((z[jj] - z[i]) / 1000.0) <= LAPSE_MAX for jj in j):
                out[r] = z[i]
                break
        if np.isnan(out[r]) and coldest:
            k = np.flatnonzero((z >= z_min) & (z <= z_max) & np.isfinite(T[r]))
            if len(k):
                out[r] = z[k[np.argmin(T[r, k])]]
    return out


def fit_qmap(x, y, rel_x, rel_y, bins=BINS, nq=99, min_n=200):
    """members x (n, m, k) with distances rel_x (n, k); truths y (s, k) with rel_y (s, k) -> dict(bins, qx (B, nq), qy (B, nq), ok (B,)).
    Per distance bin: quantiles of all member values and of all truth values that fall in the bin (any height)."""
    qs = np.linspace(0.5 / nq, 1 - 0.5 / nq, nq)
    B = len(bins) - 1
    qx, qy, ok = np.zeros((B, nq)), np.zeros((B, nq)), np.zeros(B, bool)
    bx = np.digitize(np.broadcast_to(rel_x[:, None, :], x.shape), bins) - 1
    by = np.digitize(rel_y, bins) - 1
    for b in range(B):
        vx, vy = x[bx == b], y[by == b]
        vx, vy = vx[np.isfinite(vx)], vy[np.isfinite(vy)]
        if len(vy) >= min_n and len(vx) >= min_n:
            qx[b], qy[b], ok[b] = np.quantile(vx, qs), np.quantile(vy, qs), True
    return dict(bins=np.asarray(bins), qx=qx, qy=qy, ok=ok)


def apply_qmap(qm, x, rel):
    """members x (n, m, k), rel (n, k) -> corrected copy; a column whose distance is outside the fitted bins, or NaN, is unchanged."""
    out = np.array(x, float, copy=True)
    b = np.digitize(rel, qm["bins"]) - 1                                   # (n, k)
    for j in np.flatnonzero(qm["ok"]):
        sel = b == j                                                       # (n, k)
        if not sel.any():
            continue
        xs = out.transpose(0, 2, 1)[sel]                                   # (count, m)
        qx = np.maximum.accumulate(qm["qx"][j] + np.arange(qm["qx"].shape[1]) * 1e-9)
        mapped = np.interp(xs, qx, qm["qy"][j])
        tail_lo, tail_hi = xs < qx[0], xs > qx[-1]                         # outside the fitted range: shift by the end offsets
        mapped = np.where(tail_lo, xs + (qm["qy"][j][0] - qx[0]), np.where(tail_hi, xs + (qm["qy"][j][-1] - qx[-1]), mapped))
        o = out.transpose(0, 2, 1)
        o[sel] = mapped
    return out
