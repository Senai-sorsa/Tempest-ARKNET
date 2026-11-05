"""Empirical distribution: the data to rebuild it is a table of quantiles (dense in the tails) taken from the samples themselves."""
import numpy as np

from tempest_weather.distributions.base import Dist, register

LEVELS = np.r_[0.0005, 0.001, 0.0025, 0.005, 0.0075, np.linspace(0.01, 0.99, 99), 0.9925, 0.995, 0.9975, 0.999, 0.9995]


@register
class Empirical(Dist):
    NAME = "empirical"
    SUPPORT = "real"

    @staticmethod
    def fit(x):
        x = np.asarray(x, float)
        return dict(levels=LEVELS, values=np.quantile(x, LEVELS), lo=x.min(), hi=x.max(), n=len(x))

    @staticmethod
    def ppf(q, p):
        """Linear between table points; beyond the outermost levels the end slope is extended up to the sample minimum / maximum."""
        q = np.clip(np.asarray(q, float), 0, 1)
        lv, v = p["levels"], p["values"]
        out = np.interp(q, lv, v)
        lo_s = (v[4] - v[0]) / (lv[4] - lv[0])
        hi_s = (v[-1] - v[-5]) / (lv[-1] - lv[-5])
        out = np.where(q < lv[0], np.maximum(v[0] + (q - lv[0]) * lo_s, p["lo"]), out)
        return np.where(q > lv[-1], np.minimum(v[-1] + (q - lv[-1]) * hi_s, p["hi"]), out)

    @staticmethod
    def cdf(x, p):
        return np.interp(np.asarray(x, float), p["values"], p["levels"], left=0.0, right=1.0)
