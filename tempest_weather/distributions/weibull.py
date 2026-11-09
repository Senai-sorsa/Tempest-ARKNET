"""Weibull distribution (positive values such as wind speed): shape k and scale, fitted by maximum likelihood."""
import numpy as np

from tempest_weather.distributions.base import Dist, register


@register
class Weibull(Dist):
    NAME = "weibull"
    SUPPORT = "positive"

    @staticmethod
    def fit(x):
        x = np.maximum(np.asarray(x, float), 1e-9)
        top = x.max()
        x = x / top                                               # the shape does not depend on the units; this keeps x**k finite
        lx = np.log(x)
        k = 1.2 / max(lx.std(ddof=1), 1e-6)                      # start from the log-spread
        for _ in range(100):                                      # Newton on the profile likelihood equation for k
            xk = x ** k
            f = (xk * lx).sum() / xk.sum() - 1.0 / k - lx.mean()
            df = ((xk * lx ** 2).sum() * xk.sum() - ((xk * lx).sum()) ** 2) / xk.sum() ** 2 + 1.0 / k ** 2
            step = f / df
            k = min(max(k - step, 1e-3), 200.0)
            if abs(step) < 1e-10:
                break
        return dict(shape=k, scale=top * (np.mean(x ** k)) ** (1.0 / k))

    @staticmethod
    def ppf(q, p):
        q = np.clip(np.asarray(q, float), 0.0, 1 - 1e-12)
        return p["scale"] * (-np.log1p(-q)) ** (1.0 / p["shape"])

    @staticmethod
    def cdf(x, p):
        return 1.0 - np.exp(-(np.maximum(np.asarray(x, float), 0) / p["scale"]) ** p["shape"])
