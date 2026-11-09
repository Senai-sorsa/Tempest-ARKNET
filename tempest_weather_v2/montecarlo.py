"""A1 (docs/plans/ROADMAP_RATINGS.md): a total-uncertainty Monte Carlo harness. The atmosphere pool alone is the uncertainty of the AIR only (flight-sim test, 2026-11-08: the measured apogee fell outside the whole sampled
distribution in 18 of 20 cases because the rocket model's own error is 2-4 times the atmosphere effect). This harness samples the atmosphere AND the vehicle parameters together, runs your simulator, and returns the apogee (or
any scalar) distribution, how much of its variance each input explains, and whether a measured value is inside it.

    from tempest_weather_v2 import Launch
    from tempest_weather_v2.montecarlo import run, VehiclePriors, calibrate_vehicle_sigma

    def simulate(atmosphere, drag_scale=1.0, impulse_scale=1.0, mass_scale=1.0):       # your simulator: atmosphere is a reader with .wind(alt) / .air(alt); return one number (apogee)
        ...
    priors = VehiclePriors(drag_scale=("lognormal", 0.05), impulse_scale=("lognormal", 0.03), mass_scale=("normal", 0.02))      # (kind, relative sd)   kinds: normal, lognormal, uniform (half-width)
    res = run(simulate, Launch("spaceport_america", "2027-06-16 10:00").atmospheres(200), priors, n=200, seed=1)
    print(res.summary(), res.interval(90), res.coverage(measured))

Stdlib + numpy only; the simulator is any callable. Vehicle parameters are scale factors around 1 (a relative sd), sampled by Latin hypercube (default) or at random; atmosphere k and vehicle sample k are paired by a random permutation.
`calibrate_vehicle_sigma` turns past flights (apogee error in %, atmosphere-only spread in %) into the vehicle share of the error: sigma_vehicle^2 = mean(error^2) - atmosphere_sd^2.
"""
import math

import numpy as np

__all__ = ["VehiclePriors", "run", "MCResult", "calibrate_vehicle_sigma", "latin_hypercube"]


def latin_hypercube(n, d, rng):
    """(n, d) stratified uniform samples in (0, 1): each column has exactly one point in every 1/n stratum."""
    u = (np.arange(n)[:, None] + rng.random((n, d))) / n
    for j in range(d):
        u[:, j] = u[rng.permutation(n), j]
    return u


def _ppf_normal(p):
    """Standard normal quantile (Acklam's rational approximation, |relative error| < 1.2e-9)."""
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    out = np.empty_like(p)
    lo, hi = p < 0.02425, p > 1 - 0.02425
    mid = ~(lo | hi)
    q = p[mid] - 0.5
    r = q * q
    out[mid] = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    for mask, sign in ((lo, 1.0), (hi, -1.0)):
        if mask.any():
            qq = np.sqrt(-2 * np.log(p[mask] if sign > 0 else 1 - p[mask]))
            x = (((((c[0] * qq + c[1]) * qq + c[2]) * qq + c[3]) * qq + c[4]) * qq + c[5]) / ((((d[0] * qq + d[1]) * qq + d[2]) * qq + d[3]) * qq + 1)
            out[mask] = sign * x
    return out


class VehiclePriors:
    """Named scale factors around 1: VehiclePriors(drag_scale=("lognormal", 0.05), mass_scale=("normal", 0.02), rail_friction=("uniform", 0.3))."""
    KINDS = ("normal", "lognormal", "uniform")

    def __init__(self, **spec):
        for k, (kind, sd) in spec.items():
            if kind not in self.KINDS:
                raise ValueError(f"{k}: kind must be one of {self.KINDS}, not {kind!r}")
            if not sd > 0:
                raise ValueError(f"{k}: the relative sd (or uniform half-width) must be positive")
            if kind == "uniform" and sd >= 1:
                raise ValueError(f"{k}: a uniform half-width of {sd} would reach zero or below")
        self.spec = dict(spec)

    def __len__(self):
        return len(self.spec)

    def sample(self, n, rng, method="lhs"):
        names = list(self.spec)
        if not names:
            return [dict() for _ in range(n)]
        u = latin_hypercube(n, len(names), rng) if method == "lhs" else rng.random((n, len(names)))
        cols = {}
        for j, name in enumerate(names):
            kind, sd = self.spec[name]
            z = _ppf_normal(u[:, j])
            cols[name] = 1.0 + sd * z if kind == "normal" else np.exp(sd * z - 0.5 * sd * sd) if kind == "lognormal" else 1.0 + sd * (2.0 * u[:, j] - 1.0)
        return [{name: float(cols[name][i]) for name in names} for i in range(n)]


class MCResult:
    def __init__(self, values, params, atm_index):
        self.values = np.asarray(values, float)
        self.params = params
        self.atm_index = np.asarray(atm_index, int)

    def interval(self, percent=90.0):
        lo = (100.0 - percent) / 2.0
        return tuple(float(x) for x in np.percentile(self.values, [lo, 100.0 - lo]))

    def coverage(self, measured, percent=90.0):
        """True when the measured value lies inside the central `percent` interval; also see `rank`."""
        lo, hi = self.interval(percent)
        return bool(lo <= measured <= hi)

    def rank(self, measured):
        """Share of the sampled values below the measured one (0 or 1 = outside the whole sample)."""
        return float(np.mean(self.values < measured))

    def contributions(self):
        """First-order share of the variance explained by each vehicle parameter and by the atmosphere (rank regression, one input at a time; the shares do not have to sum to 1)."""
        out = {}
        y = np.argsort(np.argsort(self.values)).astype(float)
        for name in (self.params[0] if self.params else {}):
            x = np.array([p[name] for p in self.params], float)
            out[name] = float(np.corrcoef(np.argsort(np.argsort(x)), y)[0, 1] ** 2) if np.std(x) > 0 else 0.0
        a = self.atm_index.astype(float)
        out["atmosphere (by its sample index; use varying atmospheres)"] = 0.0 if np.std(a) == 0 else float(np.corrcoef(np.argsort(np.argsort(a)), y)[0, 1] ** 2)
        return out

    def summary(self):
        v = self.values
        return dict(n=int(len(v)), mean=float(v.mean()), sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0, p5=self.interval(90)[0], p50=float(np.median(v)), p95=self.interval(90)[1])


def run(simulate, atmospheres, priors=None, n=None, seed=0, method="lhs"):
    """Call simulate(atmosphere, **vehicle_parameters) n times with atmosphere k and a sampled vehicle parameter set; return an MCResult.
    atmospheres: any indexable sequence of readers (Launch.atmospheres(n)); n defaults to its length. When n is larger than the sequence the atmospheres are reused in a random order."""
    priors = priors or VehiclePriors()
    m = len(atmospheres)
    if m == 0:
        raise ValueError("no atmospheres")
    n = int(n or m)
    rng = np.random.default_rng(seed)
    idx = np.concatenate([rng.permutation(m) for _ in range(math.ceil(n / m))])[:n]
    params = priors.sample(n, rng, method)
    vals = []
    for k in range(n):
        v = float(simulate(atmospheres[int(idx[k])], **params[k]))
        if not math.isfinite(v):
            raise ValueError(f"the simulator returned {v} for atmosphere {int(idx[k])} and parameters {params[k]}")
        vals.append(v)
    return MCResult(vals, params, idx)


def calibrate_vehicle_sigma(errors_pct, atmosphere_sd_pct):
    """From flights with a measured apogee: errors_pct = (simulated median / measured - 1) in percent for each flight, atmosphere_sd_pct = the spread of the atmosphere-only pool for that flight in percent.
    -> dict(vehicle_rms_pct, vehicle_scatter_pct, bias_pct, n): vehicle_rms^2 = mean(error^2) - mean(atmosphere sd^2) (bias included, floored at 0); bias_pct = the mean signed error (a vehicle bias to correct
    first); vehicle_scatter^2 = var(error) - mean(atmosphere sd^2) (what is left around the bias: the sigma to put in the vehicle priors once the bias is corrected). With fewer than 5 flights the result is
    flagged as not reliable."""
    e = np.asarray(errors_pct, float)
    a = np.asarray(atmosphere_sd_pct, float)
    if e.shape != a.shape or e.size == 0:
        raise ValueError("errors and atmosphere spreads need the same, non-zero length")
    atm = float(np.mean(a ** 2))
    return dict(vehicle_rms_pct=math.sqrt(max(float(np.mean(e ** 2)) - atm, 0.0)), vehicle_scatter_pct=math.sqrt(max(float(np.var(e)) - atm, 0.0)), bias_pct=float(e.mean()), n=int(e.size), reliable=bool(e.size >= 5))
