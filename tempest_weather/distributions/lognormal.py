"""Lognormal distribution (strictly positive values): mean and standard deviation of the logarithm."""
import numpy as np

from tempest_weather.distributions.base import Dist, norm_cdf, norm_ppf, register


@register
class Lognormal(Dist):
    NAME = "lognormal"
    SUPPORT = "positive"

    @staticmethod
    def fit(x):
        lx = np.log(np.maximum(np.asarray(x, float), 1e-12))
        return dict(mu=lx.mean(), sigma=max(lx.std(ddof=1), 1e-9))

    @staticmethod
    def ppf(q, p):
        return np.exp(p["mu"] + p["sigma"] * norm_ppf(q))

    @staticmethod
    def cdf(x, p):
        return norm_cdf((np.log(np.maximum(np.asarray(x, float), 1e-12)) - p["mu"]) / p["sigma"])
