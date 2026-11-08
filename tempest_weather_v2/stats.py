"""Distributions and coupling (spec 2 and 3). numpy only.

* `fit_best(x)`: best standard family (normal, lognormal, weibull, gumbel, beta) by Kolmogorov-Smirnov distance, a tail goodness check (`fit_ok`) and the empirical quantile table, always included.
* `Coupled`: joint draws of chosen columns. Methods: "whole_sample" (resample real whole atmospheres: exact coupling, keeps joint extremes, cannot invent combinations),
  "gaussian_copula" (empirical marginals + Gaussian copula: loses joint tails), "t_copula" (Student-t copula with low-rank correlation, nu fitted by profile likelihood; keeps joint tails
  approximately, adjustable). Conditioning in t-space uses the exact conditional Student-t: nu' = nu + d_obs and a scale factor (nu + x1' S11^-1 x1) / (nu + d_obs).
"""
import math

import numpy as np

from tempest_weather.distributions import norm_cdf, norm_ppf

__all__ = ["fit_best", "Coupled", "FAMILIES", "tail_check"]

QUANTILES = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
EULER = 0.5772156649015329


def _erf(x):
    x = np.asarray(x, float)
    s = np.sign(x)
    t = 1.0 / (1.0 + 0.3275911 * np.abs(x))
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def _grid_cdf(pdf, lo, hi, n=4000):
    g = np.linspace(lo, hi, n)
    d = pdf(g)
    c = np.concatenate([[0.0], np.cumsum(0.5 * (d[1:] + d[:-1]) * np.diff(g))])
    return g, c / c[-1]


# ---- families: fit(x) -> (params dict, cdf(x) callable) or None when the data do not suit the family
def _normal(x):
    mu, sd = float(x.mean()), float(x.std()) + 1e-12
    return dict(mu=mu, sigma=sd), lambda v: 0.5 * (1.0 + _erf((np.asarray(v, float) - mu) / (sd * math.sqrt(2.0))))


def _lognormal(x):
    if x.min() <= 0:
        return None
    lx = np.log(x)
    mu, sd = float(lx.mean()), float(lx.std()) + 1e-12
    return dict(mu=mu, sigma=sd), lambda v: 0.5 * (1.0 + _erf((np.log(np.maximum(np.asarray(v, float), 1e-300)) - mu) / (sd * math.sqrt(2.0))))


def _weibull(x):
    if x.min() <= 0:
        return None
    xs = np.sort(x)
    F = (np.arange(1, len(xs) + 1) - 0.3) / (len(xs) + 0.4)                       # median ranks
    A, B = np.polyfit(np.log(xs), np.log(-np.log(1.0 - F)), 1)                      # ln(-ln(1-F)) = k ln x - k ln lambda
    k, lam = float(A), float(np.exp(-B / A))
    if not (0.1 < k < 100):
        return None
    return dict(shape=k, scale=lam), lambda v: 1.0 - np.exp(-(np.maximum(np.asarray(v, float), 0.0) / lam) ** k)


def _gumbel(x):
    beta = float(x.std()) * math.sqrt(6.0) / math.pi + 1e-12
    mu = float(x.mean()) - EULER * beta
    return dict(mu=mu, beta=beta), lambda v: np.exp(-np.exp(-(np.asarray(v, float) - mu) / beta))


def _beta(x):
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-9:
        return None
    pad = 0.02 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    y = (x - lo) / (hi - lo)
    m, v = float(y.mean()), float(y.var()) + 1e-12
    k = m * (1 - m) / v - 1.0
    if k <= 0:
        return None
    a, b = m * k, (1 - m) * k
    if a <= 0 or b <= 0:
        return None
    lg = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    pdf = lambda t: np.exp(lg + (a - 1) * np.log(np.clip(t, 1e-12, 1)) + (b - 1) * np.log(np.clip(1 - t, 1e-12, 1)))
    g, c = _grid_cdf(pdf, 1e-6, 1 - 1e-6)
    return dict(a=a, b=b, lo=lo, hi=hi), lambda v: np.interp((np.asarray(v, float) - lo) / (hi - lo), g, c, left=0.0, right=1.0)


FAMILIES = {"normal": _normal, "lognormal": _lognormal, "weibull": _weibull, "gumbel": _gumbel, "beta": _beta}


def _ppf_from_cdf(cdf, lo, hi, q):
    g = np.linspace(lo, hi, 6000)
    return np.interp(q, np.clip(cdf(g), 0, 1), g)


def tail_check(x, cdf, tol=0.25):
    """Compare the fitted and the empirical quantiles at 1, 5, 95 and 99 %: ok when no difference exceeds `tol` of the 5-95 % range."""
    lo, hi = float(x.min()), float(x.max())
    pad = 0.5 * (hi - lo) + 1e-9
    qs = (0.01, 0.05, 0.95, 0.99)
    fit = _ppf_from_cdf(cdf, lo - pad, hi + pad, np.array(qs))
    emp = np.quantile(x, qs)
    scale = float(np.quantile(x, 0.95) - np.quantile(x, 0.05)) + 1e-12
    return bool(np.abs(fit - emp).max() <= tol * scale), float(np.abs(fit - emp).max() / scale)


def fit_best(x, families=None):
    """-> dict(type, params, fit_ok, ks, tail_err, quantiles {p: value}, n). `type` is None (and fit_ok False) when no family passes."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    out = dict(n=int(len(x)), quantiles={p: float(np.quantile(x, p)) for p in QUANTILES}, type=None, params={}, fit_ok=False)
    if len(x) < 10 or float(x.std()) < 1e-12:
        out["note"] = "constant or too few values" if len(x) >= 1 else "no values"
        return out
    xs = np.sort(x)
    ecdf_hi, ecdf_lo = np.arange(1, len(xs) + 1) / len(xs), np.arange(0, len(xs)) / len(xs)
    best = None
    for name in (families or FAMILIES):
        r = FAMILIES[name](x)
        if r is None:
            continue
        params, cdf = r
        F = np.clip(cdf(xs), 0.0, 1.0)
        ks = float(max(np.abs(F - ecdf_hi).max(), np.abs(F - ecdf_lo).max()))
        ok, terr = tail_check(x, cdf)
        cand = dict(type=name, params=params, ks=ks, tail_err=terr, fit_ok=ok)
        if best is None or (cand["fit_ok"], -cand["ks"]) > (best["fit_ok"], -best["ks"]):
            best = cand
    if best is not None:
        out.update(best)
    return out


# ---------------------------------------------------------------------------------------------------- copulas
def _t_table(nu, half=60.0, n=24001):
    g = np.linspace(-half, half, n)
    lg = math.lgamma((nu + 1) / 2.0) - math.lgamma(nu / 2.0) - 0.5 * math.log(nu * math.pi)
    d = np.exp(lg - (nu + 1) / 2.0 * np.log1p(g * g / nu))
    c = np.concatenate([[0.0], np.cumsum(0.5 * (d[1:] + d[:-1]) * np.diff(g))])
    return g, c / c[-1]


def _t_logpdf_mv(x, S_inv, logdet, nu):
    d = x.shape[1]
    q = np.einsum("ij,jk,ik->i", x, S_inv, x)
    return (math.lgamma((nu + d) / 2.0) - math.lgamma(nu / 2.0) - 0.5 * d * math.log(nu * math.pi) - 0.5 * logdet - (nu + d) / 2.0 * np.log1p(q / nu))


class Coupled:
    """Joint draws of the chosen columns. Build with `Coupled(data, names, method=...)` (data (N, D) in the units you want back); see the module docstring."""

    METHODS = ("whole_sample", "gaussian_copula", "t_copula")

    def __init__(self, data, names, method="whole_sample", k=None, seed=0):
        if method not in self.METHODS:
            raise ValueError(f"method must be one of {self.METHODS}, not {method!r}")
        self.data, self.names, self.method, self.seed = np.asarray(data, float), list(names), method, seed
        n, D = self.data.shape
        self._sorted = np.sort(self.data, axis=0)
        self._probs = (np.arange(n) + 0.5) / n
        self.flags = []
        self.shift = np.zeros(D)
        self.scale = np.ones(D)
        self.nu = None
        if method != "whole_sample":
            ranks = np.argsort(np.argsort(self.data, axis=0), axis=0)
            self._z = norm_ppf((ranks + 0.5) / n)
            c = np.corrcoef(self._z, rowvar=False) if D > 1 else np.ones((1, 1))
            self.corr = self._fix(np.nan_to_num(c))
            self.k = k or max(1, min(D, 6))
            self.corr_lr = self._low_rank(self.corr, self.k) if method == "t_copula" else self.corr
            if method == "t_copula":
                self.nu = self._fit_nu(ranks)
        self._cond = None

    # ---- fitting helpers
    @staticmethod
    def _fix(c):
        c = 0.5 * (c + c.T)
        np.fill_diagonal(c, 1.0)
        w, v = np.linalg.eigh(c)
        c = (v * np.maximum(w, 1e-8)) @ v.T
        d = np.sqrt(np.diag(c))
        return c / np.outer(d, d)

    @staticmethod
    def _low_rank(c, k):
        w, v = np.linalg.eigh(c)
        o = np.argsort(w)[::-1][:k]
        lr = (v[:, o] * w[o]) @ v[:, o].T
        np.fill_diagonal(lr, 1.0)                           # top-k eigenmodes + a diagonal that restores unit variance
        return Coupled._fix(lr)

    def _fit_nu(self, ranks):
        n, D = ranks.shape
        u = (ranks + 0.5) / n
        S = self.corr_lr
        S_inv = np.linalg.inv(S)
        logdet = float(np.linalg.slogdet(S)[1])
        best, best_ll = 40.0, -np.inf
        for nu in (2.5, 3, 4, 5, 6, 8, 12, 20, 40, 100):
            g, c = _t_table(nu)
            x = np.interp(u, c, g)
            lg1 = math.lgamma((nu + 1) / 2.0) - math.lgamma(nu / 2.0) - 0.5 * math.log(nu * math.pi)
            uni = (lg1 - (nu + 1) / 2.0 * np.log1p(x * x / nu)).sum(1)
            ll = float((_t_logpdf_mv(x, S_inv, logdet, nu) - uni).sum())
            if ll > best_ll:
                best, best_ll = float(nu), ll
        return best

    # ---- marginals
    def _to_data(self, u):
        out = np.empty_like(u)
        for j in range(u.shape[1]):
            out[:, j] = np.interp(u[:, j], self._probs, self._sorted[:, j])
        return out

    def _apply_knobs(self, x):
        if not (np.any(self.shift) or np.any(self.scale != 1.0)):
            return x
        med = np.median(self.data, axis=0)
        return med + self.scale * (x - med) + self.shift

    # ---- public
    def draw(self, n, seed=None):
        rng = np.random.default_rng(self.seed if seed is None else seed)
        if self.method == "whole_sample":
            x = self.data[rng.integers(0, len(self.data), n)] if self._cond is None else self._draw_conditional(n, rng)
        else:
            x = self._draw_copula(n, rng)
        return self._apply_knobs(x)

    def _draw_copula(self, n, rng):
        D = len(self.names)
        if self._cond is not None:
            return self._draw_conditional(n, rng)
        L = np.linalg.cholesky(self.corr_lr + 1e-10 * np.eye(D))
        z = rng.standard_normal((n, D)) @ L.T
        if self.method == "gaussian_copula":
            return self._to_data(norm_cdf(z))
        t = z / np.sqrt(rng.chisquare(self.nu, (n, 1)) / self.nu)
        g, c = _t_table(self.nu)
        return self._to_data(np.interp(t, g, c))

    def condition(self, obs):
        """Condition on observed values {name: value}. Gaussian: normal-score update; t_copula: the exact conditional Student-t (nu' = nu + d_obs, scale factor). whole_sample: kernel-weighted
        resampling of real atmospheres near the observed values. Returns a NEW Coupled (this one is unchanged) flagged 'conditioned'."""
        for nme in obs:
            if nme not in self.names:
                raise KeyError(f"{nme!r} is not one of the coupled columns {self.names}")
        c = Coupled.__new__(Coupled)
        c.__dict__ = dict(self.__dict__)
        c.flags = list(self.flags) + [f"conditioned-on-{len(obs)}-values"]
        idx = [self.names.index(k) for k in obs]
        vals = np.array([obs[k] for k in obs], float)
        if self.method == "whole_sample":
            sd = self.data[:, idx].std(0) + 1e-12
            w = np.exp(-0.5 * (((self.data[:, idx] - vals) / (0.3 * sd)) ** 2).sum(1)) + 1e-300     # kernel width 0.3 sd
            c._cond = ("weights", w / w.sum())
            return c
        un = [j for j in range(len(self.names)) if j not in idx]
        u_obs = np.array([np.interp(v, self._sorted[:, j], self._probs) for v, j in zip(vals, idx)])
        S = self.corr_lr
        S_oo, S_uo, S_uu = S[np.ix_(idx, idx)], S[np.ix_(un, idx)], S[np.ix_(un, un)]
        gain = S_uo @ np.linalg.inv(S_oo)
        S_c = S_uu - gain @ S_uo.T
        if self.method == "gaussian_copula":
            x_o = norm_ppf(np.clip(u_obs, 1e-6, 1 - 1e-6))
            c._cond = ("gauss", idx, un, gain @ x_o, S_c)
        else:
            g, cdf = _t_table(self.nu)
            x_o = np.interp(np.clip(u_obs, 1e-6, 1 - 1e-6), cdf, g)
            q = float(x_o @ np.linalg.solve(S_oo, x_o))
            nu2 = self.nu + len(idx)
            c._cond = ("t", idx, un, gain @ x_o, S_c, nu2, (self.nu + q) / nu2)
        c._obs = dict(zip(obs, vals))
        return c

    def _draw_conditional(self, n, rng):
        kind = self._cond[0]
        if kind == "weights":
            return self.data[rng.choice(len(self.data), n, p=self._cond[1])]
        _, idx, un, mu, S_c = self._cond[:5]
        L = np.linalg.cholesky(S_c + 1e-10 * np.eye(len(un)))
        z = rng.standard_normal((n, len(un))) @ L.T
        out = np.empty((n, len(self.names)))
        if kind == "gauss":
            out[:, un] = self._to_data(norm_cdf(mu + z))
        else:
            nu2, scale = self._cond[5], self._cond[6]
            t = mu + np.sqrt(scale) * z / np.sqrt(rng.chisquare(nu2, (n, 1)) / nu2)
            g, c = _t_table(self.nu)
            out[:, un] = self._to_data(np.interp(t, g, c))
        for j, v in zip(idx, self._obs.values()):
            out[:, j] = v
        return out

    def adjust(self, shift=None, scale=None):
        """Mean shift (data units, per column) and spread scale about the median. Any adjustment sets the flag 'adjusted-uncalibrated'. Returns a NEW Coupled."""
        c = Coupled.__new__(Coupled)
        c.__dict__ = dict(self.__dict__)
        c.shift = self.shift + (np.zeros(len(self.names)) if shift is None else np.asarray(shift, float))
        c.scale = self.scale * (np.ones(len(self.names)) if scale is None else np.asarray(scale, float))
        c.flags = list(dict.fromkeys(self.flags + ["adjusted-uncalibrated"]))
        return c

    def spec(self):
        """The fitted mathematical specification for external Monte Carlo tools."""
        s = dict(method=self.method, names=self.names, marginals={n: dict(quantile_probs=self._probs.tolist(), quantiles=self._sorted[:, j].tolist()) for j, n in enumerate(self.names)})
        if self.method != "whole_sample":
            w, v = np.linalg.eigh(self.corr_lr)
            o = np.argsort(w)[::-1]
            s.update(correlation=self.corr_lr.tolist(), eigenvalues=w[o].tolist(), eigenvectors=v[:, o].T.tolist(), low_rank_k=self.k)
        if self.nu is not None:
            s["nu"] = self.nu
        return s
