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

__all__ = ["VehiclePriors", "run", "MCResult", "calibrate_vehicle_sigma", "latin_hypercube", "AdaptiveConformal"]


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
    def __init__(self, values, params, atm_index, atm_metrics=None):
        self.atm_metrics = atm_metrics or {}          # name -> per-atmosphere number (pad air density, mean wind below 200 m / 3 km); filled by run()
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
        for name, m in self.atm_metrics.items():                           # Gemini bug 1: the sample index is not a physical quantity (its rank correlation with the apogee is chance); the physical metrics are
            x = np.asarray(m, float)[self.atm_index]
            out[f"atmosphere: {name}"] = float(np.corrcoef(np.argsort(np.argsort(x)), y)[0, 1] ** 2) if np.std(x) > 0 else 0.0
        return out

    def explained(self):
        """Joint rank regression of the result on all vehicle parameters (r2_vehicle) and on vehicle parameters plus the physical atmosphere metrics (r2_all); atmosphere_gain = r2_all - r2_vehicle is the part
        of the variance the atmosphere adds once the vehicle is accounted for (the first-order shares of `contributions` can overlap). Needs atmosphere metrics (set by run())."""
        y = np.argsort(np.argsort(self.values)).astype(float)
        rk = lambda x: np.argsort(np.argsort(x)).astype(float)
        names = list(self.params[0]) if self.params else []
        veh = [rk(np.array([p[n] for p in self.params], float)) for n in names if np.std([p[n] for p in self.params]) > 0]
        atm = [rk(np.asarray(m, float)[self.atm_index]) for m in self.atm_metrics.values() if np.std(np.asarray(m, float)[self.atm_index]) > 0]

        def r2(cols):
            if not cols or len(y) <= len(cols) + 2:
                return 0.0
            X = np.column_stack([np.ones(len(y))] + cols)
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            res = y - X @ beta
            return float(1.0 - res.var() / y.var())
        rv, ra = r2(veh), r2(veh + atm)
        return dict(r2_vehicle=rv, r2_all=ra, atmosphere_gain=max(ra - rv, 0.0))

    def summary(self):
        v = self.values
        return dict(n=int(len(v)), mean=float(v.mean()), sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0, p5=self.interval(90)[0], p50=float(np.median(v)), p95=self.interval(90)[1])


def atmosphere_metrics(atm):
    """Physical summary numbers of one reader: air density at the pad, mean wind speed from the pad to 200 m and to 3 km (in the reader's units); None when the reader cannot give them."""
    try:
        z0 = float(atm.elevation_m)
        rho = float(np.asarray(atm.air(z0 + 1.0))[2])
        sp = lambda top: float(np.mean(np.linalg.norm(np.asarray(atm.wind_many(z0 + np.linspace(10.0, top, 24))), axis=-1)))
        return dict(pad_air_density=rho, mean_wind_0_200m=sp(200.0), mean_wind_0_3km=sp(3000.0))
    except Exception:  # noqa: BLE001  (a custom reader without these attributes: the index-based share remains)
        return None


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
    per = [atmosphere_metrics(atmospheres[k]) for k in range(m)]
    metrics = {key: np.array([d[key] for d in per]) for key in per[0]} if all(d is not None for d in per) else {}
    return MCResult(vals, params, idx, metrics)


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


class AdaptiveConformal:
    """M10: adaptive conformal calibration of a central quantile interval of an ensemble (online conformal inference, Gibbs and Candes 2021, in its padding form as used for AI weather ensembles). The interval is the
    ensemble's central (1 - alpha) interval stretched about its centre by a factor s_t that moves after every verified case: s_t+1 = s_t + gamma (miss_t - alpha), miss_t = 1 when the observation fell outside the
    stretched interval. The long-run share of misses converges to alpha WHATEVER the ensemble's own calibration (distribution-free, marginal over time, not conditional on the case). A quantile re-levelling would saturate at
    the ensemble's min / max when the ensemble is too narrow; the stretch does not.
    Use: ac = AdaptiveConformal(0.10); lo, hi = ac.interval(samples); ... later ac.update(observed, (lo, hi)). For the 10 m wind (past-mode coverage 0.79) and for the total apogee interval of `run`.
    gamma: step size (0.01-0.1); larger adapts faster but jitters. s is kept in [0.05, 20]."""

    def __init__(self, alpha=0.10, gamma=0.05):
        if not 0.0 < alpha < 1.0 or gamma <= 0:
            raise ValueError("alpha must be in (0, 1) and gamma positive")
        self.alpha, self.gamma, self.stretch = float(alpha), float(gamma), 1.0
        self.n, self.misses = 0, 0

    def interval(self, samples):
        x = np.asarray(samples, float)
        lo, hi = np.quantile(x, self.alpha / 2.0), np.quantile(x, 1.0 - self.alpha / 2.0)
        c, h = 0.5 * (lo + hi), 0.5 * (hi - lo)
        return float(c - self.stretch * h), float(c + self.stretch * h)

    def update(self, observed, interval):
        miss = 0.0 if interval[0] <= observed <= interval[1] else 1.0
        self.stretch = float(min(max(self.stretch + self.gamma * (miss - self.alpha), 0.05), 20.0))
        self.n += 1
        self.misses += int(miss)
        return bool(miss)

    @property
    def coverage(self):
        return 1.0 - self.misses / self.n if self.n else float("nan")
