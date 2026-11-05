"""Forecast the climate-driver indices (ONI, WWV, QBO30, QBO50) h months ahead as a joint distribution.

    from tempest.ingest import indices, index_forecast
    tab = indices.load()
    draws = index_forecast.draw(tab, origin="2026-09-01", horizon=6, m=200, rng=rng)   # (m, 4) in indices.COLS order

Ridge regression of each index at origin + h on the last 6 months of all four indices and the calendar month (fitted
on every origin whose target is already known), with the residual covariance across the four indices at that horizon, so
draws keep ENSO / warm water volume / QBO relations. On 2012-2025 hindcasts this beat both the analog draw
(indices.analog, K = 8) and climatology at every horizon from 1 to 12 months (scripts/index_bakeoff.py; ONI mean CRPS
0.342 vs 0.424 vs 0.457). Beyond ~12 months ONI skill is gone: the draw widens to climatology on its own because the
regression has nothing left to explain.
"""
import numpy as np
import pandas as pd

from tempest.ingest import indices

COLS = indices.COLS  # oni, qbo30, qbo50, wwv
LAGS = 6


def _qbo_sd(tab, pos):
    """Standard deviations of qbo30 and qbo50 over the rows known at position `pos` (no later data)."""
    return np.array([tab["qbo30"].to_numpy()[:pos + 1].std() + 1e-9, tab["qbo50"].to_numpy()[:pos + 1].std() + 1e-9])


def _design(tab, idx, qbo_sd):
    """Regression inputs at origin positions idx: the last LAGS monthly values of all four indices, the calendar month, and the QBO phase: the angle of
    (qbo30, qbo50) in standardised phase space (the QBO is a ~28-month downward-propagating cycle, so the pair circles) as sin / cos plus its amplitude."""
    cols = [tab[c].to_numpy()[idx - L] for c in COLS for L in range(LAGS)]
    month = tab.index[idx].month.to_numpy()
    a30, a50 = tab["qbo30"].to_numpy()[idx] / qbo_sd[0], tab["qbo50"].to_numpy()[idx] / qbo_sd[1]
    theta, amp = np.arctan2(a50, a30), np.hypot(a30, a50)
    return np.stack(cols + [np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12), np.sin(theta), np.cos(theta), amp], 1)


def _psd_cov(resid):
    """Covariance of standardised residuals with the eigenvalues of the correlation matrix kept positive (a tiny negative eigenvalue made multivariate_normal warn)."""
    c = np.atleast_2d(np.corrcoef(resid.T))
    w, v = np.linalg.eigh(np.nan_to_num(c))
    c = (v * np.maximum(w, 1e-6)) @ v.T
    d = np.sqrt(np.diag(c))
    return c / np.outer(d, d) * np.outer(resid.std(0), resid.std(0))


def fit(tab, origin, horizon, ridge=3.0):
    """-> dict(mean_x, sd_x, beta (k, 4), mean_y (4,), cov (4, 4), scale (4,), qbo_sd) using only targets known at `origin`.
    Targets are standardised before the regression and the residual covariance (WWV is of order 1e13, the others of order 1: the raw covariance was numerically
    degenerate), `beta` and `cov` are returned in standardised units; draw() rescales."""
    tab = tab.dropna(subset=COLS)
    pos = tab.index.get_indexer([pd.Timestamp(origin)])[0]
    if pos < 0:
        raise ValueError(f"origin {origin} is not a month of the index table")
    qsd = _qbo_sd(tab, pos)
    org = np.arange(LAGS, pos - horizon + 1)
    X, Y = _design(tab, org, qsd), tab[COLS].to_numpy()[org + horizon]
    mx, sx = X.mean(0), X.std(0) + 1e-9
    Z = (X - mx) / sx
    my, sy = Y.mean(0), Y.std(0) + 1e-12
    Ys = (Y - my) / sy
    beta = np.linalg.solve(Z.T @ Z + ridge * len(Z) / 100 * np.eye(Z.shape[1]), Z.T @ Ys)
    resid = Ys - Z @ beta
    return dict(mean_x=mx, sd_x=sx, beta=beta, mean_y=my, cov=_psd_cov(resid), scale=sy, qbo_sd=qsd, pos=pos)


def draw(tab, origin, horizon, m, rng, ridge=3.0):
    """(m, 4) joint draws of the four indices `horizon` months after `origin`, columns in indices.COLS order."""
    tab = tab.dropna(subset=COLS)
    f = fit(tab, origin, horizon, ridge)
    x = (_design(tab, np.array([f["pos"]]), f["qbo_sd"]) - f["mean_x"]) / f["sd_x"]
    mean_s = (x @ f["beta"])[0]
    return f["mean_y"] + f["scale"] * rng.multivariate_normal(mean_s, f["cov"], size=m)
