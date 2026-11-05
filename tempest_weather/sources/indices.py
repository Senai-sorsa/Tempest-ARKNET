"""Climate-driver indices for the generator inputs: observed values from the exported snapshot, a joint ridge forecast beyond the last observed month.

Order of the four indices everywhere in this file: oni, qbo30, qbo50, wwv (the order of tempest.ingest.indices.COLS). The forecast is the one tested in
scripts/index_bakeoff.py: ridge regression of each index h months ahead on the last 6 months of all four and the calendar month, with the residual covariance
across the indices, so draws keep ENSO / warm water volume / QBO relations. It is a numpy copy of tempest.ingest.index_forecast.
"""
import numpy as np

COLS = ["oni", "qbo30", "qbo50", "wwv"]
LAGS = 6


class Indices:
    def __init__(self, z):
        self.months = np.asarray(z["months"])                                        # yyyymm of each row
        self.table = np.stack([z[c] for c in COLS], 1).astype(float)                 # (T, 4)
        self.gm_months, self.gmst = np.asarray(z["gmst_months"]), np.asarray(z["gmst"], float)

    @staticmethod
    def yyyymm(ts):
        return ts.year * 100 + ts.month

    def last(self):
        return int(self.months[-1])

    def observed(self, ts):
        i = np.flatnonzero(self.months == self.yyyymm(ts))
        return self.table[i[0]] if len(i) else None

    def gmst_at(self, ts):
        i = np.searchsorted(self.gm_months, self.yyyymm(ts), side="right") - 1
        return float(self.gmst[max(i, 0)])

    def _design(self, idx):
        cols = [self.table[idx - L, c] for c in range(4) for L in range(LAGS)]
        month = self.months[idx] % 100
        return np.array(cols + [np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)], float)

    def forecast(self, ts, ridge=3.0):
        """-> (mean (4,), cov (4, 4), horizon_months) for the month of ts after the last observed one (horizon capped at 12)."""
        last_i = len(self.months) - 1
        y, m = divmod(self.last(), 100)
        h = max(1, min(12, (ts.year - y) * 12 + ts.month - m))
        org = np.arange(LAGS, last_i - h + 1)
        X = np.stack([self._design(i) for i in org])
        Y = self.table[org + h]
        mx, sx = X.mean(0), X.std(0) + 1e-9
        Z = (X - mx) / sx
        my = Y.mean(0)
        beta = np.linalg.solve(Z.T @ Z + ridge * len(Z) / 100 * np.eye(Z.shape[1]), Z.T @ (Y - my))
        cov = np.cov(((Y - my) - Z @ beta).T)
        d = np.sqrt(np.diag(cov))                                              # make it a valid covariance in a scale-free way (WWV is ~1e13, ONI ~1):
        corr = (cov + cov.T) / 2 / np.outer(d, d)                              # clip the eigenvalues of the CORRELATION matrix, then rescale
        w, v = np.linalg.eigh(corr)
        corr = (v * np.maximum(w, 1e-9)) @ v.T
        dd = np.sqrt(np.diag(corr))
        cov = corr / np.outer(dd, dd) * np.outer(d, d)
        mean = my + ((self._design(last_i) - mx) / sx) @ beta
        return mean, cov, h

    def draws(self, ts, n, rng, expected=False):
        """-> ((n, 4) values in COLS order, note). `expected` returns the expected value n times (no spread)."""
        obs = self.observed(ts)
        if obs is not None:
            return np.tile(obs, (n, 1)), "observed"
        mean, cov, h = self.forecast(ts)
        if expected:
            return np.tile(mean, (n, 1)), f"expected value of the ridge forecast, {h} months ahead"
        return rng.multivariate_normal(mean, cov, size=n, check_valid="ignore"), f"ridge forecast draws, {h} months ahead"
