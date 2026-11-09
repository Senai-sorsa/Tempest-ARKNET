"""Common pieces of the distribution files: normal-distribution helpers (numpy only) and the registry."""
import math

import numpy as np

REGISTRY = {}


def register(cls):
    REGISTRY[cls.NAME] = cls
    return cls


def norm_cdf(z):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z, float) / math.sqrt(2.0)))


def norm_ppf(p):
    """Inverse normal CDF (Acklam's rational approximation, relative error about 1e-9)."""
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    lo, hi = 0.02425, 1 - 0.02425
    out = np.empty_like(p)
    m = p < lo
    q = np.sqrt(-2 * np.log(p[m]))
    out[m] = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    m = p > hi
    q = np.sqrt(-2 * np.log(1 - p[m]))
    out[m] = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    m = (p >= lo) & (p <= hi)
    q = p[m] - 0.5
    r = q * q
    out[m] = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    return out


class Dist:
    """Each distribution file defines a subclass with NAME, SUPPORT, fit(x) -> params dict, ppf(q, params), cdf(x, params), sample(params, n, rng) and spec(params)."""
    NAME = ""
    SUPPORT = "real"       # "real", "positive", "unit"

    @classmethod
    def sample(cls, params, n, rng):
        return cls.ppf(rng.random(n), params)

    @classmethod
    def spec(cls, params, units=""):
        return dict(type=cls.NAME, params={k: (float(v) if np.ndim(v) == 0 else np.asarray(v)) for k, v in params.items()}, units=units)
