"""Full PIT recalibration (IL-46 / IL-85): fix the whole shape of the predictive distribution, not only its 99 % ends.

For a group of columns (variable x height band) the probability-integral transforms (PIT) of the truth among the samples are pooled on a calibration set. If the forecast
were calibrated their CDF G would be the identity; where it is not, G tells exactly how probability is misplaced. The recalibrated predictive CDF is G(F(x)), so the
sorted samples (levels (i - 0.5) / m) are replaced by the ensemble's quantiles at levels G^-1((i - 0.5) / m). Order within a row is kept, so a rank-based step after it
(Schaake shuffle) still works; the ends beyond the sample range are handled by the range map that follows. Off by default.
"""
import numpy as np

GRID = np.linspace(0.0, 1.0, 201)


def pit_values(x, y, rng):
    below = (x < y[:, None]).mean(1)
    tie = (x == y[:, None]).mean(1)
    return below + rng.random(below.shape) * tie


def fit(x, y, groups, rng=None):
    """x (N, m, D) calibration samples, y (N, D) truth, groups (D,) int -> table dict(ginv (G, 201): G^-1 on GRID per group)."""
    rng = rng or np.random.default_rng(0)
    pit = pit_values(x, y, rng)
    ng = int(groups.max()) + 1
    ginv = np.zeros((ng, len(GRID)))
    for g in range(ng):
        p = np.sort(pit[:, groups == g].ravel())
        cdf = np.searchsorted(p, GRID, "right") / len(p)                     # G on GRID
        cdf = np.maximum.accumulate(cdf)
        cdf[-1] = 1.0
        u = np.linspace(0, 1, len(GRID))
        ginv[g] = np.interp(u, cdf + 1e-9 * np.arange(len(GRID)), GRID)       # inverse by interpolation
    return dict(ginv=ginv, groups=groups, m=np.array(x.shape[1]))


def apply(table, x, damp=1.0):
    """x (N, m, D) -> samples at the recalibrated quantile levels (same shape, sorted along m). damp in (0, 1]: 1 = the full correction, 0.5 = half way between the sorted input and the
    recalibrated samples (loop 2 H1: the full map gave better coverage and tails but a slightly worse PIT distance)."""
    m = x.shape[1]
    lev = (np.arange(m) + 0.5) / m
    xs = np.sort(x, axis=1)
    out = np.empty_like(xs)
    groups = table["groups"]
    for g in range(table["ginv"].shape[0]):
        new_lev = np.interp(lev, GRID, table["ginv"][g])                       # levels to read from the ensemble
        pos = np.clip(new_lev * m - 0.5, 0, m - 1)
        i0 = np.floor(pos).astype(int)
        i1 = np.minimum(i0 + 1, m - 1)
        w = (pos - i0)[None, :, None]
        cols = groups == g
        out[:, :, cols] = xs[:, i0][:, :, cols] * (1 - w) + xs[:, i1][:, :, cols] * w
    return xs + damp * (out - xs) if damp != 1.0 else out
