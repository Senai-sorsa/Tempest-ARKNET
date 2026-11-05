"""Gust module (PHASED_PLAN 3.1): the peak gust to expect at 10 m given the model's wind, as a distribution.

G = max(reported gust, sustained wind) follows a Gumbel distribution whose location mu is linear in the inputs and
whose scale beta = exp(linear), fitted by maximum likelihood on airport reports. (A first version modelled "is a gust
reported" and the excess over the wind separately; it forced gusts to be at least the model wind, which is false when
the model wind runs above the airport's, and its 99 % range held only 59 % of the truth. Dropped; see PLAN.)
Two variants: "wind" (the model's 10 m wind + season + hour + station flag; works for any future date, where the
generator's own 10 m wind sample is the input) and "wind+fg" (adds ERA5's own gust field fg10, past dates only).
All speeds in m/s.
"""
import numpy as np
from scipy.optimize import minimize

KT = 0.514444  # m/s per knot
EULER = 0.5772156649


def design(ws, doy, hour, fg=None, station=None):
    """Input matrix: 1, ws, ws^2, season and hour harmonics, optional station flag and ERA5 gust (fg, fg - ws)."""
    ws = np.asarray(ws, float)
    a, h = 2 * np.pi * np.asarray(doy, float) / 365.25, 2 * np.pi * np.asarray(hour, float) / 24.0
    cols = [np.ones_like(ws), ws, ws ** 2 / 10.0, np.sin(a), np.cos(a), np.sin(h), np.cos(h)]
    if station is not None:
        cols.append(np.asarray(station, float))
    if fg is not None:
        fg = np.asarray(fg, float)
        cols += [fg, fg - ws]
    return np.stack(cols, 1)


def _nll(p, X, g, l2):
    k = X.shape[1]
    theta, phi = p[:k], p[k:]
    mu, beta = X @ theta, np.exp(np.clip(X @ phi, -5, 5))
    z = (g - mu) / beta
    return np.sum(np.log(beta) + z + np.exp(-z)) + l2 * (np.sum(theta[1:] ** 2) + np.sum(phi[1:] ** 2))


def fit(X, g, l2=1.0):
    """X (n, k), observed peak gust g (n,) -> dict(theta, phi) (location and log-scale coefficients)."""
    k = X.shape[1]
    sd = g.std() * np.sqrt(6) / np.pi
    p0 = np.zeros(2 * k)
    p0[0], p0[k] = g.mean() - EULER * sd, np.log(sd)
    r = minimize(_nll, p0, args=(X, g, l2), method="L-BFGS-B")
    return dict(theta=r.x[:k], phi=r.x[k:])


def params(model, X):
    """-> mu, beta for each row of X."""
    return X @ model["theta"], np.exp(np.clip(X @ model["phi"], -5, 5))


def sample(model, X, m, rng):
    """X (n, k) -> (n, m) gust samples (never negative)."""
    mu, beta = params(model, X)
    u = np.clip(rng.random((len(X), m)), 1e-12, 1 - 1e-12)
    return np.maximum(mu[:, None] - beta[:, None] * np.log(-np.log(u)), 0.0)
