"""Hourly coherence (group C, C1): make the samples of several hours one consistent sequence.

Each hour of a query comes from its own ensemble (marginals per hour are right, the samples of different hours are unrelated). Here the samples are tied together with a Gaussian
copula over time: per column (variable x height) the correlation between hour i and hour k is rho(|o_i - o_k|), the lag correlation of ERA5 anomalies of that season (scripts/c1_fit_lagcorr.py).
z_i = sum_k L_ik e_k with L the Cholesky factor of that Toeplitz matrix and e_k the normal scores of the ranks of a RANDOM WHOLE sample of hour k's own ensemble (independent permutation per hour), so the
vertical structure of every e_k is a real one and all columns of one sample keep their vertical relation. Hour i is then read back from its own sorted samples at probability Phi(z_i):
every hour keeps its marginal distribution exactly (up to the ensemble size) and sample j is one coherent sequence. numpy only.
"""
import numpy as np

from tempest_weather.distributions import norm_cdf, norm_ppf


def _scores(x):
    """(n, D) -> normal scores of the ranks per column."""
    r = np.argsort(np.argsort(x, axis=0), axis=0)
    return norm_ppf((r + 0.5) / len(x))


def _chol_by_column(rho, offsets, kappa=None, rho_x=None):
    """rho (L, D) lag correlations (L >= 1; lags above L-1 use the last), offsets (K,) hours -> (D, K, K) Cholesky factors of the per-column Toeplitz correlation matrices."""
    off = np.asarray(offsets)
    if rho_x is None:                                                      # integer lags (hours): row = lag
        lag = np.minimum(np.abs(off[:, None] - off[None, :]), rho.shape[0] - 1)
        R = np.moveaxis(rho[lag], -1, 0).astype(np.float64)              # (D, K, K)
    else:                                                                  # rows belong to the distances rho_x (km): linear interpolation between them, the last row beyond
        x = np.asarray(rho_x, float)
        pos = np.interp(np.abs(off[:, None] - off[None, :]).astype(float), x, np.arange(len(x)))
        i0 = np.floor(pos).astype(int)
        i1 = np.minimum(i0 + 1, len(x) - 1)
        w = (pos - i0)[..., None]
        R = np.moveaxis((1 - w) * rho[i0] + w * rho[i1], -1, 0).astype(np.float64)
        R[:, np.arange(len(off)), np.arange(len(off))] = 1.0
    if kappa is not None:                                                  # nugget: the part of the variance that is rough (balloon-like) and not shared between hours; hours apart share only kappa of the ERA5 correlation
        k = np.asarray(kappa, float)[:, None, None]
        R = k * R + (1 - k) * np.eye(len(off))[None]
    w, v = np.linalg.eigh((R + np.swapaxes(R, 1, 2)) / 2)
    R = np.einsum("dik,dk,djk->dij", v, np.maximum(w, 1e-6), v)
    d = np.sqrt(np.einsum("dii->di", R))
    R = R / d[:, :, None] / d[:, None, :]
    return np.linalg.cholesky(R + 1e-9 * np.eye(len(off))[None])


def sequence(samples, offsets, rho, rng=None, kappa=None, rho_x=None, rho_regime=None, regime_of=None):
    """samples: list of K arrays (n, D), the ensembles of the hours `offsets` (hours, K of them); rho (L, D). -> list of K arrays (n, D), sample j coherent over the K hours."""
    rng = rng or np.random.default_rng()
    K, (n, D) = len(samples), samples[0].shape
    perms = [rng.permutation(n) for _ in samples]
    e = np.stack([_scores(s[p]) for s, p in zip(samples, perms)], 0)      # (K, n, D): one whole random sample of each hour's ensemble
    if rho_regime is None:
        L = _chol_by_column(np.asarray(rho), offsets, kappa, rho_x)       # (D, K, K)
        z = np.einsum("dik,knd->ind", L, e)                                # (K, n, D)
    else:                                                                  # C3: the correlation depends on the weather regime of the trajectory (tercile of the 0-3 km shear of its first sample)
        reg = np.asarray(regime_of(samples[0][perms[0]]))                  # (n,) 0 .. R-1
        z = np.empty((len(samples), n, D))
        for r in range(len(rho_regime)):
            m = reg == r
            if m.any():
                Lr = _chol_by_column(np.asarray(rho_regime[r]), offsets, kappa, rho_x)
                z[:, m] = np.einsum("dik,knd->ind", Lr, e[:, m])
    out = []
    srt = [np.sort(s, axis=0) for s in samples]
    pos = lambda u: np.clip(u * n - 0.5, 0, n - 1)
    for i in range(K):
        p = pos(norm_cdf(z[i]))
        i0 = np.floor(p).astype(int)
        i1 = np.minimum(i0 + 1, n - 1)
        w = p - i0
        cols = np.arange(D)[None, :]
        out.append(srt[i][i0, cols] * (1 - w) + srt[i][i1, cols] * w)
    return out
