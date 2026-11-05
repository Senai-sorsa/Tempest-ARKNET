"""Gaussian copula: the rank correlations of the samples, with each variable's own marginal distribution (from the distribution files).
For simulators that need a parametric joint. Limits (documented, tested): it reproduces the marginals and the rank correlations, but loses tail
dependence, skewed relations between variables and any hard physical coupling such as density with temperature and pressure; use `whole_sample` when those matter.
"""
import numpy as np

from tempest_weather import distributions
from tempest_weather.distributions.base import norm_cdf, norm_ppf


def _ranks(x):
    return np.argsort(np.argsort(x, axis=0), axis=0)


class GaussianCopula:
    METHOD = "gaussian_copula"

    def __init__(self, columns, table, marginals):
        """table (n, V) samples; marginals: list of spec dicts (from distributions.describe), one per column."""
        self.columns, self.marginals = list(columns), list(marginals)
        t = np.asarray(table, float)
        z = norm_ppf((_ranks(t) + 0.5) / len(t))                        # normal scores of the ranks
        c = np.corrcoef(z, rowvar=False)
        self.corr = np.atleast_2d(c)
        self.corr = np.nan_to_num(self.corr)
        np.fill_diagonal(self.corr, 1.0)
        w, v = np.linalg.eigh(self.corr)                                # keep it a valid correlation matrix
        self.corr = (v * np.maximum(w, 1e-8)) @ v.T
        d = np.sqrt(np.diag(self.corr))
        self.corr = self.corr / np.outer(d, d)
        self._chol = np.linalg.cholesky(self.corr + 1e-10 * np.eye(len(self.corr)))
        self._dists = [distributions.build(m) for m in self.marginals]

    def draw(self, k, rng=None, stratified=False):
        rng = rng or np.random.default_rng()
        z = rng.standard_normal((k, len(self.columns))) @ self._chol.T
        u = norm_cdf(z)
        return None, np.stack([d.ppf(u[:, j]) for j, d in enumerate(self._dists)], 1)

    def spec(self):
        return dict(method=self.METHOD, columns=self.columns, correlation=self.corr, marginals=self.marginals,
                    note="draw z ~ N(0, correlation), u = Phi(z), value_j = ppf_j(u_j)")
