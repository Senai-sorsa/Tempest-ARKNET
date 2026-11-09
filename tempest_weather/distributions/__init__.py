"""Distribution types, one file each. `describe(samples, setting)` turns samples of one variable into a plain description:
{"type": name, "params": {...}, "units": "", "note": ...} from which the distribution can be rebuilt with `build(spec)`.

Standard types (settings 0 and 1) are chosen by the variable's physical support, then checked against the samples: the candidate whose quantiles at
0.5, 1, 5, 50, 95, 99, 99.5 % are closest (in units of the samples' inter-quartile range) wins, but only if its worst tail error is below `MAX_TAIL_ERR`;
otherwise the empirical table is returned and the note says why. Empirical types (settings 2 and 3) are always `empirical`.
"""
import numpy as np

from tempest_weather.distributions import beta, empirical, gumbel, lognormal, normal, weibull  # noqa: F401  (importing registers the types)
from tempest_weather.distributions.base import REGISTRY, norm_cdf, norm_ppf  # noqa: F401

MAX_TAIL_ERR = 0.35
CHECK_LEVELS = np.array([0.005, 0.01, 0.05, 0.5, 0.95, 0.99, 0.995])
CANDIDATES = {"real": ["normal", "gumbel"], "positive": ["weibull", "lognormal", "gumbel", "normal"], "unit": ["beta", "normal"]}


def support_of(x, hint=None):
    if hint:
        return hint
    x = np.asarray(x)
    if x.min() >= 0 and x.max() <= 1.0:
        return "unit"
    return "positive" if x.min() > 0 else "real"


def describe(samples, setting_standard, support=None, units=""):
    """samples (n,) -> spec dict. setting_standard: True for a standard distribution (settings 0, 1), False for the empirical one (2, 3)."""
    x = np.asarray(samples, float)
    if np.ptp(x) < 1e-12:
        return dict(type="constant", params=dict(value=float(x[0])), units=units, note="no spread")
    if not setting_standard:
        return REGISTRY["empirical"].spec(REGISTRY["empirical"].fit(x), units) | dict(note="empirical quantile table")
    iqr = max(np.subtract(*np.quantile(x, [0.75, 0.25])), 1e-12)
    target = np.quantile(x, CHECK_LEVELS)
    fits = {}
    for name in CANDIDATES[support_of(x, support)]:
        cls = REGISTRY[name]
        try:
            p = cls.fit(x)
            err = float(np.abs(cls.ppf(CHECK_LEVELS, p) - target).max() / iqr)
        except (FloatingPointError, ValueError, ZeroDivisionError):
            continue
        if np.isfinite(err):
            fits[name] = (err, p)
    best, best_err, best_p = None, np.inf, None
    if fits:
        best = min(fits, key=lambda k: fits[k][0])
        if "normal" in fits and fits["normal"][0] <= fits[best][0] + 0.03:   # the simplest type wins a near tie
            best = "normal"
        best_err, best_p = fits[best]
    if best is None or best_err > MAX_TAIL_ERR:
        return REGISTRY["empirical"].spec(REGISTRY["empirical"].fit(x), units) | dict(note=f"no standard type fits the tails (best error {best_err:.2f} IQR): empirical returned")
    return REGISTRY[best].spec(best_p, units) | dict(note=f"{best}, worst checked quantile error {best_err:.2f} IQR")


def build(spec):
    """spec -> object with ppf(q), cdf(x), sample(n, rng)."""
    if spec["type"] == "constant":
        v = spec["params"]["value"]
        return type("Constant", (), dict(ppf=staticmethod(lambda q: np.full(np.shape(q), v)), cdf=staticmethod(lambda x: (np.asarray(x) >= v).astype(float)),
                                         sample=staticmethod(lambda n, rng=None: np.full(n, v))))
    cls, p = REGISTRY[spec["type"]], spec["params"]
    return type(cls.NAME, (), dict(ppf=staticmethod(lambda q: cls.ppf(q, p)), cdf=staticmethod(lambda x: cls.cdf(x, p)),
                                   sample=staticmethod(lambda n, rng=None: cls.sample(p, n, rng or np.random.default_rng()))))
