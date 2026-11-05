"""Normal distribution: mean and standard deviation."""
import numpy as np

from tempest_weather.distributions.base import Dist, norm_cdf, norm_ppf, register


@register
class Normal(Dist):
    NAME = "normal"
    SUPPORT = "real"

    @staticmethod
    def fit(x):
        x = np.asarray(x, float)
        return dict(mean=x.mean(), std=max(x.std(ddof=1), 1e-12))

    @staticmethod
    def ppf(q, p):
        return p["mean"] + p["std"] * norm_ppf(q)

    @staticmethod
    def cdf(x, p):
        return norm_cdf((np.asarray(x, float) - p["mean"]) / p["std"])
