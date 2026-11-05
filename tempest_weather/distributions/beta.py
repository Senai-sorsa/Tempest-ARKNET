"""Beta distribution (values between 0 and 1, such as relative humidity as a fraction): shape parameters a and b by the method of moments.
The quantile function is tabulated (numpy only) from the density, accurate to about 1e-4 in probability."""
import math

import numpy as np

from tempest_weather.distributions.base import Dist, register

_GRID = 4001


def _table(a, b):
    x = np.linspace(1e-6, 1 - 1e-6, _GRID)
    logpdf = (a - 1) * np.log(x) + (b - 1) * np.log1p(-x) - (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    pdf = np.exp(logpdf - logpdf.max())
    c = np.concatenate([[0], np.cumsum(0.5 * (pdf[1:] + pdf[:-1]) * np.diff(x))])
    return x, c / c[-1]


@register
class Beta(Dist):
    NAME = "beta"
    SUPPORT = "unit"

    @staticmethod
    def fit(x):
        x = np.clip(np.asarray(x, float), 1e-4, 1 - 1e-4)
        m, v = x.mean(), max(x.var(ddof=1), 1e-8)
        k = max(m * (1 - m) / v - 1, 1e-2)
        return dict(a=max(m * k, 1e-2), b=max((1 - m) * k, 1e-2))

    @staticmethod
    def ppf(q, p):
        x, c = _table(p["a"], p["b"])
        return np.interp(np.clip(np.asarray(q, float), 0, 1), c, x)

    @staticmethod
    def cdf(x, p):
        xs, c = _table(p["a"], p["b"])
        return np.interp(np.asarray(x, float), xs, c, left=0.0, right=1.0)
