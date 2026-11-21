"""G0 harmonic climatology fitter (docs/plans/GLOBAL_PLAN.md G0): per point, mu and sigma of every column (height x variable)
as an annual (3 harmonics) x diurnal (2 harmonics, local solar time) Fourier series = 7 x 5 = 35 terms, fitted on the
training years only (any valid time in 2026 or later is refused).

    from tempest.geo.clim import fit, predict
    c = fit(times, lon, y)                  # one point: times (n,) datetime64 UTC, lon deg, y (n, k)
    mu, sigma = predict(c, times2, lon)     # (n2, k) each

mu: least squares. sigma: least squares on log(residual^2), + 1.2704 (= -E[log chi2_1]) so exp(0.5 * fit) is the
standard deviation for Gaussian residuals; always positive. The 1 deg global version with 12 EOFs is a G4 job.
"""
import numpy as np

N_ANNUAL, N_DIURNAL = 3, 2
LOGCHI2 = 1.2704


def basis(times, lon):
    t = np.asarray(times).astype("datetime64[s]").astype(np.int64)
    doy = (t / 86400.0) % 365.2425 / 365.2425 * 2 * np.pi
    lst = ((t % 86400) / 3600.0 + np.asarray(lon, float) / 15.0) % 24 / 24 * 2 * np.pi   # local solar time
    a = [np.ones_like(doy)] + [f(h * doy) for h in range(1, N_ANNUAL + 1) for f in (np.cos, np.sin)]
    d = [np.ones_like(lst)] + [f(h * lst) for h in range(1, N_DIURNAL + 1) for f in (np.cos, np.sin)]
    return np.stack([x * z for x in a for z in d], -1)          # (n, 35)


def fit(times, lon, y, last_year=2025):
    t = np.asarray(times).astype("datetime64[s]")
    if (t >= np.datetime64(f"{last_year + 1}-01-01")).any():
        raise ValueError(f"climatology fit refuses valid times after {last_year} (training years only)")
    X, y = basis(t, lon), np.asarray(y, float).reshape(len(t), -1)
    if len(t) < 3 * X.shape[1]:
        raise ValueError(f"{len(t)} rows is too few for {X.shape[1]} terms")
    mu, *_ = np.linalg.lstsq(X, y, rcond=None)
    ls, *_ = np.linalg.lstsq(X, np.log((y - X @ mu) ** 2 + 1e-12) + LOGCHI2, rcond=None)
    return {"mu": mu.astype(np.float32), "logvar": ls.astype(np.float32)}


def predict(c, times, lon):
    X = basis(times, lon)
    return X @ c["mu"], np.exp(0.5 * (X @ c["logvar"]))
