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


def _design(tab, idx, qbo_sd, qbo_phase=False):
    """Regression inputs at origin positions idx: the last LAGS monthly values of all four indices and the calendar month (the design of
    scripts/index_bakeoff.py and of the tool's tempest_weather/sources/indices.py). qbo_phase=True adds the QBO phase: the angle of (qbo30, qbo50) in
    standardised phase space as sin / cos plus its amplitude (fix F-28). AU-8: on the 2012-25 hindcast the phase terms made every index worse at almost
    every horizon (ONI CRPS +2 to +8 %, QBO +1 to +4 %; models/au8_index_bakeoff.csv), so they are off by default; True is the switch back."""
    cols = [tab[c].to_numpy()[idx - L] for c in COLS for L in range(LAGS)]
    month = tab.index[idx].month.to_numpy()
    if not qbo_phase:
        return np.stack(cols + [np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)], 1)
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


def fit(tab, origin, horizon, ridge=3.0, qbo_phase=False):
    """-> dict(mean_x, sd_x, beta (k, 4), mean_y (4,), cov (4, 4), scale (4,), qbo_sd) using only targets known at `origin`.
    Targets are standardised before the regression and the residual covariance (WWV is of order 1e13, the others of order 1: the raw covariance was numerically
    degenerate), `beta` and `cov` are returned in standardised units; draw() rescales."""
    tab = tab.dropna(subset=COLS)
    pos = tab.index.get_indexer([pd.Timestamp(origin)])[0]
    if pos < 0:
        raise ValueError(f"origin {origin} is not a month of the index table")
    qsd = _qbo_sd(tab, pos)
    org = np.arange(LAGS, pos - horizon + 1)
    X, Y = _design(tab, org, qsd, qbo_phase), tab[COLS].to_numpy()[org + horizon]
    mx, sx = X.mean(0), X.std(0) + 1e-9
    Z = (X - mx) / sx
    my, sy = Y.mean(0), Y.std(0) + 1e-12
    Ys = (Y - my) / sy
    beta = np.linalg.solve(Z.T @ Z + ridge * len(Z) / 100 * np.eye(Z.shape[1]), Z.T @ Ys)
    resid = Ys - Z @ beta
    return dict(resid=resid, mean_x=mx, sd_x=sx, beta=beta, mean_y=my, cov=_psd_cov(resid), scale=sy, qbo_sd=qsd, pos=pos, qbo_phase=qbo_phase)


def draw(tab, origin, horizon, m, rng, ridge=3.0, qbo_phase=False):
    """(m, 4) joint draws of the four indices `horizon` months after `origin`, columns in indices.COLS order."""
    tab = tab.dropna(subset=COLS)
    f = fit(tab, origin, horizon, ridge, qbo_phase)
    x = (_design(tab, np.array([f["pos"]]), f["qbo_sd"], qbo_phase) - f["mean_x"]) / f["sd_x"]
    mean_s = (x @ f["beta"])[0]
    return f["mean_y"] + f["scale"] * rng.multivariate_normal(mean_s, f["cov"], size=m)


def draw_lag(tab, origin, horizon, lag, oni, rng, ridge=3.0):
    """AU-16: ONI `lag` months before the target month, jointly with `oni` (the target month's draws from draw(..., horizon, ...) at the same origin).
    If that month is already observed at the origin it is the observed value; otherwise a draw at horizon - lag whose standardised error has the
    correlation of the two horizons' hindcast residuals with the target's error (was an independent draw)."""
    tab = tab.dropna(subset=COLS)
    h2 = horizon - lag
    f = fit(tab, origin, horizon, ridge)
    if h2 <= 0:
        return np.full(len(oni), tab["oni"].to_numpy()[f["pos"] + h2])
    g = fit(tab, origin, h2, ridge)
    rho = float(np.corrcoef(f["resid"][:, 0], g["resid"][:len(f["resid"]), 0])[0, 1])      # same origins: the h - lag fit has lag more at the end
    mean = lambda q: q["mean_y"][0] + q["scale"][0] * ((_design(tab, np.array([q["pos"]]), q["qbo_sd"]) - q["mean_x"]) / q["sd_x"] @ q["beta"])[0, 0]
    sd = lambda q: q["scale"][0] * np.sqrt(q["cov"][0, 0])
    z = (np.asarray(oni, float) - mean(f)) / sd(f)
    return mean(g) + sd(g) * (rho * z + np.sqrt(max(1 - rho * rho, 0.0)) * rng.standard_normal(len(z)))
