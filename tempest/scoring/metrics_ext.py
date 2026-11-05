"""Shape and diagnostic metrics (AUTOPILOT.md: MAIN TARGET S1-S8 and M1-M18). Pure numpy; every function takes samples x (N, m, D) and truth y (N, D)
(physical columns, scoring.score layout: u, v, T, RH at 44 heights, then t2m, sp, rh2m) and returns per-column arrays unless noted.

    pit_values, pit_tv           probability-integral transform and its total-variation distance from flat (0 = perfect)          S1, M1
    coverage_levels              share of truths inside the central interval at several levels                                    S2
    standardized_moments         skewness and excess kurtosis of (value - sample median) / robust spread, truth vs samples        S3
    tail_exceedance              how often the truth passes the climatological tail quantiles vs the nominal rate                 S6, M2
    event_conditional_coverage   coverage among the most extreme truths vs what a perfect forecast gets                                              M3
    vertical_corr_error          distance between the residual correlation matrices across heights, truth vs samples             S5, M6
    shear_distance               KS and Wasserstein distance of neighbour-height vector shear, truth vs samples                   S6, M7
    brier_skill                  Brier skill score of event probabilities vs a base-rate forecast                                 M11
    drift_proxy                  horizontal displacement of a tracer rising at constant speed through the wind profile             M12
    direction_error              mean angular error of the median wind direction and circular spread mismatch                     M13
    bias_by_group                median error by calendar month / hour bin / year                                                  M4
    spread_skill                 ratio of ensemble spread to median error by group                                                M5
"""
import numpy as np

from tempest.profiles.to_heights import HEIGHTS

NH = len(HEIGHTS)


def pit_values(x, y, rng=None):
    """Randomised PIT of y among the m samples: share below plus a random part of the ties. (N, D) in [0, 1]."""
    rng = rng or np.random.default_rng(0)
    below = (x < y[:, None]).mean(1)
    tie = (x == y[:, None]).mean(1)
    return below + rng.random(below.shape) * tie


def pit_tv(pit, bins=10):
    """Total-variation distance of the PIT histogram from flat, per column: 0.5 * sum |share_i - 1/bins|."""
    idx = np.minimum((pit * bins).astype(int), bins - 1)
    h = np.stack([(idx == b).mean(0) for b in range(bins)])
    return 0.5 * np.abs(h - 1.0 / bins).sum(0)


def coverage_levels(pit, levels=(0.1, 0.25, 0.5, 0.75, 0.8, 0.9, 0.95, 0.99)):
    """(len(levels), D): share of PITs inside the central interval of each level; nominal equals the level."""
    return np.stack([((pit > (1 - l) / 2) & (pit < 1 - (1 - l) / 2)).mean(0) for l in levels])


def _robust_scale(x):
    q = np.percentile(x, [25, 75], axis=1)
    return np.maximum((q[1] - q[0]) / 1.349, 1e-9)


def _moments(z):
    m, s = z.mean(), z.std() + 1e-12
    return float((((z - m) / s) ** 3).mean()), float((((z - m) / s) ** 4).mean() - 3.0)


def standardized_moments(x, y):
    """(D, 4): skew_truth, skew_samples, kurt_truth, kurt_samples of values standardised as (value - sample median) / robust spread."""
    med, sc = np.median(x, 1), _robust_scale(x)
    zt = (y - med) / sc
    zs = (x - med[:, None]) / sc[:, None]
    out = np.zeros((y.shape[1], 4))
    for d in range(y.shape[1]):
        zd = np.clip(zt[:, d], -8, 8)
        zsd = np.clip(zs[:, :, d].ravel(), -8, 8)
        st, kt = _moments(zd)
        ss, ks = _moments(zsd)
        out[d] = (st, ss, kt, ks)
    return out


def tail_exceedance(x, y, clim, qs=(0.001, 0.01, 0.05, 0.95, 0.99, 0.999)):
    """clim (K, D): reference sample per column that defines the quantile thresholds. Returns (observed, predicted), each (len(qs), D): the frequency with which
    the truth is beyond each threshold (below for q < 0.5, above otherwise) and the mean probability the samples assign to it. A calibrated forecast has
    observed == predicted on average; both equal q (or 1 - q) only if the truth has the reference climate (a warmer year makes observed exceed it)."""
    obs = np.zeros((len(qs), y.shape[1]))
    pred = np.zeros_like(obs)
    for i, q in enumerate(qs):
        thr = np.quantile(clim, q, axis=0)
        below = q < 0.5
        obs[i] = (y < thr).mean(0) if below else (y > thr).mean(0)
        pred[i] = (x < thr).mean((0, 1)) if below else (x > thr).mean((0, 1))
    return obs, pred


def event_conditional_coverage(x, y, clim, tail=0.01, rng=None):
    """M3. Among the truths in the most extreme `tail` share of the climatology (either side), the share inside the samples' 99 % range, next to the
    value a perfectly calibrated forecast would get: the same statistic with one random sample member as pseudo-truth (exchangeable with the other
    members, so the pair is comparable; conditioning on an extreme OUTCOME makes the share fall below 0.99 even for a perfect forecast).
    Returns (inside, ideal_inside, n) per column; a gap inside < ideal_inside means extremes are missed more than they should be."""
    rng = rng or np.random.default_rng(0)
    lo, hi = np.quantile(clim, [tail / 2, 1 - tail / 2], axis=0)

    def share(xs, ys):
        pit = pit_values(xs, ys, rng)
        ext = (ys < lo) | (ys > hi)
        n = ext.sum(0)
        return np.where(n > 0, ((pit > 0.005) & (pit < 0.995) & ext).sum(0) / np.maximum(n, 1), np.nan), n

    inside, n = share(x, y)
    ideal, _ = share(x[:, 1:], x[:, 0])
    return inside, ideal, n


def vertical_corr_error(x, y, cols, n_draw=4000, rng=None):
    """Frobenius distance / size between the correlation matrices (over `cols`, the heights of one variable) of the residuals value - sample median,
    for the truth (one residual per row) and the samples (n_draw random sample members)."""
    rng = rng or np.random.default_rng(0)
    med = np.median(x[:, :, cols], 1)
    rt = y[:, cols] - med
    ri = rng.integers(0, x.shape[0], n_draw)
    rj = rng.integers(0, x.shape[1], n_draw)
    rs = x[ri, rj][:, cols] - med[ri]
    ct, cs = np.corrcoef(rt.T), np.corrcoef(rs.T)
    ct, cs = np.nan_to_num(ct), np.nan_to_num(cs)
    return float(np.linalg.norm(ct - cs) / ct.shape[0])


def _shear(u, v):
    return np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / (np.diff(HEIGHTS) / 1000.0)


def shear_distance(x, y, layer=slice(None)):
    """KS and Wasserstein-1 distance between the pooled neighbour shear values of truth and samples (rows x selected layers)."""
    st = _shear(y[:, :NH], y[:, NH:2 * NH])[:, layer].ravel()
    ss = _shear(x[..., :NH], x[..., NH:2 * NH])[..., layer].reshape(-1)
    a, b = np.sort(st), np.sort(ss)
    grid = np.unique(np.concatenate([a[:: max(1, len(a) // 2000)], b[:: max(1, len(b) // 2000)]]))
    ks = float(np.abs(np.searchsorted(a, grid, "right") / len(a) - np.searchsorted(b, grid, "right") / len(b)).max())
    qs = np.linspace(0.005, 0.995, 200)
    w1 = float(np.abs(np.quantile(a, qs) - np.quantile(b, qs)).mean())
    return ks, w1


def brier_skill(x, y, col_idx, threshold, above=True):
    """Brier skill score (vs the constant base-rate forecast) of the sample probability of `value beyond threshold` at columns col_idx (any of them: the
    event is that the maximum, or minimum if not above, over those columns passes the threshold). Returns (bss, brier, base_rate)."""
    f = lambda a: (a[..., col_idx].max(-1) if above else a[..., col_idx].min(-1))
    ev = (f(y) > threshold) if above else (f(y) < threshold)
    p = (f(x) > threshold).mean(1) if above else (f(x) < threshold).mean(1)
    base = ev.mean()
    bs = float(((p - ev) ** 2).mean())
    ref = float(((base - ev) ** 2).mean())
    return (1 - bs / ref if ref > 0 else np.nan), bs, float(base)


def drift_proxy(profile, heights=HEIGHTS, top_km=(3, 10, 18), rise=10.0):
    """Horizontal displacement (m) of a tracer rising at `rise` m/s from the first height to each top (km above ground) through u, v of `profile`
    (..., 4 * NH + ...) in the scorer layout: trapezoid integral of the wind over the time spent in each layer. Returns (..., len(top_km), 2) east, north."""
    u, v = profile[..., :NH], profile[..., NH:2 * NH]
    h = np.asarray(heights, float)
    out = []
    for top in top_km:
        k = int(np.searchsorted(h, top * 1000.0, "right"))
        k = min(max(k, 2), NH)
        dt = np.diff(h[:k]) / rise
        out.append(np.stack([(0.5 * (u[..., :k - 1] + u[..., 1:k]) * dt).sum(-1), (0.5 * (v[..., :k - 1] + v[..., 1:k]) * dt).sum(-1)], -1))
    return np.stack(out, -2)


def direction_error(x, y, cols_u, cols_v):
    """Mean absolute angular error (degrees) of the median wind direction vs truth over the columns, only where the truth speed exceeds 3 m/s."""
    mu, mv = np.median(x[..., cols_u], 1), np.median(x[..., cols_v], 1)
    d = np.degrees(np.angle(np.exp(1j * (np.arctan2(y[:, cols_u], y[:, cols_v]) - np.arctan2(mu, mv)))))
    ok = np.hypot(y[:, cols_u], y[:, cols_v]) > 3.0
    return float(np.abs(d[ok]).mean()) if ok.any() else float("nan")


def bias_by_group(x, y, group):
    """median error (truth - sample median) per group label per column: dict label -> (D,)."""
    err = y - np.median(x, 1)
    return {g: np.median(err[group == g], 0) for g in np.unique(group)}


def spread_skill(x, y, group):
    """per group per column: (ensemble spread = mean sample std) / (RMSE of the sample mean); 1 is ideal (finite-m factor ignored)."""
    sd = x.std(1, ddof=1)
    rmse_all = (y - x.mean(1)) ** 2
    return {g: np.sqrt((sd[group == g] ** 2).mean(0)) / np.sqrt(rmse_all[group == g].mean(0)) for g in np.unique(group)}
