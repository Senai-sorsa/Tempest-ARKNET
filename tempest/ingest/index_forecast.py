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


def _design(tab, idx):
    cols = [tab[c].to_numpy()[idx - L] for c in COLS for L in range(LAGS)]
    month = tab.index[idx].month.to_numpy()
    return np.stack(cols + [np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)], 1)


def fit(tab, origin, horizon, ridge=3.0):
    """-> dict(mean_x, sd_x, beta (k, 4), mean_y (4,), cov (4, 4)) using only targets known at `origin`."""
    tab = tab.dropna(subset=COLS)
    pos = tab.index.get_indexer([pd.Timestamp(origin)])[0]
    if pos < 0:
        raise ValueError(f"origin {origin} is not a month of the index table")
    org = np.arange(LAGS, pos - horizon + 1)
    X, Y = _design(tab, org), tab[COLS].to_numpy()[org + horizon]
    mx, sx = X.mean(0), X.std(0) + 1e-9
    Z = (X - mx) / sx
    my = Y.mean(0)
    beta = np.linalg.solve(Z.T @ Z + ridge * len(Z) / 100 * np.eye(Z.shape[1]), Z.T @ (Y - my))
    resid = (Y - my) - Z @ beta
    return dict(mean_x=mx, sd_x=sx, beta=beta, mean_y=my, cov=np.cov(resid.T), pos=pos)


def draw(tab, origin, horizon, m, rng, ridge=3.0):
    """(m, 4) joint draws of the four indices `horizon` months after `origin`, columns in indices.COLS order."""
    tab = tab.dropna(subset=COLS)
    f = fit(tab, origin, horizon, ridge)
    x = (_design(tab, np.array([f["pos"]])) - f["mean_x"]) / f["sd_x"]
    mean = f["mean_y"] + (x @ f["beta"])[0]
    return rng.multivariate_normal(mean, f["cov"], size=m)
