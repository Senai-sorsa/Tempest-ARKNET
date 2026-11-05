"""Gumbel (extreme-value type I, for maxima such as gusts): location and scale, fitted by maximum likelihood."""
import numpy as np

from tempest_weather.distributions.base import Dist, register


@register
class Gumbel(Dist):
    NAME = "gumbel"
    SUPPORT = "real"

    @staticmethod
    def fit(x):
        x = np.asarray(x, float)
        beta = max(x.std(ddof=1) * np.sqrt(6) / np.pi, 1e-9)
        for _ in range(100):  # fixed point of the likelihood equation for the scale
            w = np.exp(-(x - x.min()) / beta)
            new = x.mean() - (x * w).sum() / w.sum()
            if abs(new - beta) < 1e-10 * beta:
                break
            beta = max(new, 1e-9)
        loc = x.min() - beta * np.log(np.mean(np.exp(-(x - x.min()) / beta)))
        return dict(loc=loc, scale=beta)

    @staticmethod
    def ppf(q, p):
        q = np.clip(np.asarray(q, float), 1e-12, 1 - 1e-12)
        return p["loc"] - p["scale"] * np.log(-np.log(q))

    @staticmethod
    def cdf(x, p):
        return np.exp(-np.exp(-(np.asarray(x, float) - p["loc"]) / p["scale"]))
