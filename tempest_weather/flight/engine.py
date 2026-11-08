"""Quasi-random atmosphere sampler and measurement conditioning (stage 6, modules 1 and 2).

The engine holds a POOL of coupled atmospheres (from `tempest_weather.api.atmosphere_set`) for one place and time. From it:
* marginals: the empirical distribution of every column (u, v, T, RH at the 44 heights, plus 2 m temperature, surface pressure, 2 m humidity), tails as far as the pool reaches;
* copula: the correlation matrix of the normal scores of the pool ranks, with its eigen-decomposition sorted by size (PCA order).

`sample_sobol(u)` takes the simulator's own uniform numbers: the first k columns drive the k leading eigenmodes (low-discrepancy where the variance is), every other mode is filled by a
seeded pseudo-random draw so the full covariance is kept exactly (the blueprint instead rescaled the truncated modes, which distorts the correlations). With `u=None` it returns the
conditional median profile. `condition_on_observations` is the closed-form Gaussian-copula update (Schur complement): the observed columns are pinned to the measured values, the rest
moves with the learned vertical cross-correlations and its remaining uncertainty shrinks. `observe_by_weights` is the alternative that keeps the non-Gaussian structure of the pool
(importance weights and resampling).
"""
import copy

import numpy as np

from tempest_weather import _core
from tempest_weather.distributions import norm_cdf, norm_ppf

NH = _core.NH
VARS = ("wind_u", "wind_v", "temp_K", "rh_pct")


def feature_names():
    names = [(v, float(h)) for v in VARS for h in _core.HEIGHTS]
    return names + [("temp_K", 2.0), ("pressure_Pa", 0.0), ("rh_pct", 2.0)]


def pool_matrix(atm):
    """atm dict (sample first) -> (n, 179) in feature_names() order."""
    return np.concatenate([atm["u"], atm["v"], atm["T"], atm["RH"], atm["t2m"][:, None], atm["sp"][:, None], atm["rh2m"][:, None]], 1).astype(np.float64)


class TempestFlightSimEngine:
    def __init__(self, lat=None, lon=None, when=None, n_pool=2048, seed=0, assets=None, atm=None, info=None, tail_extrap=False, **kw):
        if atm is None:
            from tempest_weather import api
            atm, info = api.atmosphere_set(lat, lon, when, n=n_pool, seed=seed, assets=assets, **kw)
        self.atm, self.info, self.seed = atm, info or {}, seed
        self.tail_extrap = bool(tail_extrap)   # IL-129: extend the marginals past the pool min/max with the outer-5 % slope (off = clamp, as before)
        self.names = feature_names()
        self.index = {k: i for i, k in enumerate(self.names)}
        self.pool = pool_matrix(atm)
        self.elev = float(self.info.get("elevation_m", 0.0))
        n, P = self.pool.shape
        self._sorted = np.sort(self.pool, axis=0)
        self._probs = (np.arange(n) + 0.5) / n
        scores = norm_ppf((np.argsort(np.argsort(self.pool, axis=0), axis=0) + 0.5) / n)
        c = np.nan_to_num(np.corrcoef(scores, rowvar=False))
        np.fill_diagonal(c, 1.0)
        w, v = np.linalg.eigh(c)
        c = (v * np.maximum(w, 1e-8)) @ v.T
        d = np.sqrt(np.diag(c))
        self.corr = c / np.outer(d, d)
        w, v = np.linalg.eigh(self.corr)
        o = np.argsort(w)[::-1]
        self.eigvals, self.eigvecs = np.maximum(w[o], 0.0), v[:, o]
        self._sd = self.pool.std(0) + 1e-12
        self._post = None

    # ---- marginals
    TAIL_FRAC = 0.05

    def _tail_slopes(self, j):
        """(low, high) slope dz/dx of the normal score against the value over the outer 5 % of the pool column j (0 when flat)."""
        key = ("_ts", j)
        if key not in self.__dict__:
            s, n = self._sorted[:, j], len(self._sorted)
            k = max(int(self.TAIL_FRAC * n), 2)
            zs = norm_ppf(self._probs)
            lo = (zs[k] - zs[0]) / (s[k] - s[0]) if s[k] > s[0] else 0.0
            hi = (zs[-1] - zs[-1 - k]) / (s[-1] - s[-1 - k]) if s[-1] > s[-1 - k] else 0.0
            self.__dict__[key] = (float(lo), float(hi))
        return self.__dict__[key]

    def _cdf(self, j, x):
        if self.tail_extrap:
            s = self._sorted[:, j]
            lo, hi = self._tail_slopes(j)
            if x > s[-1] and hi > 0:
                return float(np.clip(norm_cdf(norm_ppf(self._probs[-1]) + hi * (x - s[-1])), 1e-6, 1 - 1e-6))
            if x < s[0] and lo > 0:
                return float(np.clip(norm_cdf(norm_ppf(self._probs[0]) + lo * (x - s[0])), 1e-6, 1 - 1e-6))
        return float(np.clip(np.interp(x, self._sorted[:, j], self._probs), 1e-6, 1 - 1e-6))

    def _ppf(self, j, v):
        out = np.interp(v, self._probs, self._sorted[:, j])
        if self.tail_extrap:
            s = self._sorted[:, j]
            lo, hi = self._tail_slopes(j)
            v = np.asarray(v, float)
            z = norm_ppf(np.clip(v, 1e-12, 1 - 1e-12))
            if hi > 0:
                out = np.where(v > self._probs[-1], s[-1] + (z - norm_ppf(self._probs[-1])) / hi, out)
            if lo > 0:
                out = np.where(v < self._probs[0], s[0] + (z - norm_ppf(self._probs[0])) / lo, out)
        return out

    # ---- module 2
    def condition_on_observations(self, obs, sensor_sigma=None, inflate=1.5, inflate_decay_m=None):
        """obs: {(variable, height_m): measured value}; variables wind_u, wind_v (m/s), temp_K, rh_pct, pressure_Pa (surface, height 0). Heights must be model heights (10, 50, 100 ... 18000 m)
        or 2 m for temp_K / rh_pct. sensor_sigma: physical standard deviation of the sensors (one number or {variable: sigma}); default: practically exact pins. inflate: factor on the posterior variance of the unobserved columns (1.0 = the pure Schur complement; 1.5 is the default: the check in
        scripts/s6_condition_eval.py found the pure version too sharp: 90 % intervals held 80-86 % of balloons, 88-92 % with 1.5).
        inflate_decay_m (IL-138, opt-in; None = the single scalar): the variance of every unobserved column is multiplied by 1 + (inflate - 1) exp(-d / inflate_decay_m), d = distance in metres from the
        column's height to the nearest observed height: the sharpness the pure update has near a measurement is corrected there, and columns far from every measurement (still close to the prior) are not widened."""
        idx, y = [], []
        for (var, h), val in obs.items():
            k = (var, float(h))
            if k not in self.index:
                near = min((n for n in self.names if n[0] == var), key=lambda n: abs(n[1] - h), default=None)
                raise KeyError(f"{k} is not a model height; nearest for {var}: {near}. Use 2 m for temperature and humidity, 0 for surface pressure, and {list(_core.HEIGHTS)} for the profile")
            idx.append(self.index[k])
            y.append(float(norm_ppf(self._cdf(self.index[k], float(val)))))
        idx, y = np.array(idx, int), np.array(y)
        P = len(self.names)
        un = np.setdiff1d(np.arange(P), idx)
        if sensor_sigma is None:
            lat_sig = np.full(len(idx), 1e-3)
        else:
            sig = np.array([sensor_sigma.get(self.names[i][0], 0.0) if isinstance(sensor_sigma, dict) else float(sensor_sigma) for i in idx])
            lat_sig = np.maximum(sig / self._sd[idx], 1e-3)              # physical sensor sd -> latent units (about the sd of the column)
        C11 = self.corr[np.ix_(idx, idx)] + np.diag(lat_sig ** 2)
        C21 = self.corr[np.ix_(un, idx)]
        gain = np.linalg.solve(C11, C21.T).T
        mu = gain @ y
        S = self.corr[np.ix_(un, un)] - gain @ C21.T
        scale = float(inflate)
        if inflate_decay_m:
            h = np.array([self.names[i][1] if self.names[i][1] > 0 else 0.0 for i in range(P)])    # pressure (height 0) and the 2 m values sit at the surface
            d = np.abs(h[un][:, None] - h[idx][None, :]).min(1)
            f = np.sqrt(1.0 + (float(inflate) - 1.0) * np.exp(-d / float(inflate_decay_m)))
            S = S * f[:, None] * f[None, :]
            scale = 1.0
        w, v = np.linalg.eigh(0.5 * (S + S.T))
        o = np.argsort(w)[::-1]
        self._post = dict(idx=idx, un=un, vals=np.array(list(obs.values()), float), mu=mu, eigvals=np.maximum(w[o], 0.0) * scale, eigvecs=v[:, o])
        return self

    def clear_observations(self):
        self._post = None

    def conditioned(self, obs, sensor_sigma=None, inflate=1.5, inflate_decay_m=None):
        """F6: a NEW engine conditioned on obs; this one is left untouched (condition_on_observations mutates self._post, a hazard when one engine is shared between runs)."""
        new = copy.copy(self)
        new.__dict__ = dict(self.__dict__)
        new._post = None
        return new.condition_on_observations(obs, sensor_sigma, inflate, inflate_decay_m)

    def _blocked_normals(self, stream, run_id, n, d, block=256):
        """F1/F2: (n, d) standard normals where every block of `block` rows has its own generator keyed on (seed, stream, run_id, block index): a run of n rows starts with exactly the rows of a
        shorter run, and a different run_id gives different noise."""
        parts = [np.random.default_rng(np.random.SeedSequence([int(self.seed), int(stream), int(run_id), b0 // block])).standard_normal((min(block, n - b0), d)) for b0 in range(0, n, block)]
        return np.concatenate(parts) if parts else np.empty((0, d))

    # ---- module 1
    def sample_sobol(self, u_matrix=None, exact_residual=True, run_id=None, block=256):
        """u_matrix (N, k) uniforms in (0, 1) from the simulator, or None for the conditional median profile (N = 1). -> dict of arrays (N, ...) like `atmosphere_set` (+ z, p, rho, a).
        The k leading eigenmodes are driven by the columns of u_matrix; the remaining modes use a seeded pseudo-random draw (exact_residual=True) or are left out (False). run_id (opt-in, F1/F2): key that
        draw on (seed, run_id, row block) instead of the fixed seed + 31, so runs differ and the first rows do not depend on N."""
        rng = np.random.default_rng(self.seed + 31)
        P = len(self.names)
        if self._post is None:
            vals, vecs, mu, cols, fixed = self.eigvals, self.eigvecs, np.zeros(P), np.arange(P), None
        else:
            p = self._post
            vals, vecs, mu, cols, fixed = p["eigvals"], p["eigvecs"], p["mu"], p["un"], (p["idx"], p["vals"])
        D = len(cols)
        if u_matrix is None:
            y = mu[None, :]
        else:
            u = np.clip(np.asarray(u_matrix, float), 1e-9, 1 - 1e-9)
            N, k = u.shape
            k = min(k, D)
            load = vecs * np.sqrt(vals)[None, :]
            y = mu[None, :] + norm_ppf(u[:, :k]) @ load[:, :k].T
            if exact_residual and k < D:
                noise = rng.standard_normal((N, D - k)) if run_id is None else self._blocked_normals(31, run_id, N, D - k, block)
                y = y + noise @ load[:, k:].T
        x = np.empty((y.shape[0], P))
        for jj, j in enumerate(cols):
            x[:, j] = self._ppf(j, norm_cdf(y[:, jj]))
        if fixed is not None:
            x[:, fixed[0]] = fixed[1][None, :]
        return self._finish(x, self._nearest(x))

    def observe_by_weights(self, obs, sensor_sigma, n_out=1000, run_id=None):
        """The pool-based alternative: weight every pool atmosphere by the Gaussian likelihood of the observations (sensor_sigma in physical units, one number or {variable: sigma}) and
        resample n_out with replacement. -> (batch, effective sample size). Keeps the non-Gaussian structure but needs a large pool and soft sensors: with hard pins the weights collapse."""
        rng = np.random.default_rng(self.seed + 47) if run_id is None else np.random.default_rng(np.random.SeedSequence([int(self.seed), 47, int(run_id)]))
        ll = np.zeros(len(self.pool))
        for (var, h), val in obs.items():
            j = self.index[(var, float(h))]
            s = sensor_sigma.get(var, 1.0) if isinstance(sensor_sigma, dict) else float(sensor_sigma)
            ll += -0.5 * ((self.pool[:, j] - float(val)) / max(s, 1e-9)) ** 2
        w = np.exp(ll - ll.max())
        w /= w.sum()
        pick = rng.choice(len(self.pool), n_out, p=w)
        return self._finish(self.pool[pick].copy(), pick), float(1.0 / np.sum(w ** 2))

    def _nearest(self, x, chunk=4096):
        """Pool row nearest to each new row (standardised columns): copula rows borrow w and the gust parameters from it.
        shortcut: w/gust are not in the copula, so they follow the nearest pool atmosphere; upgrade by adding them as copula columns."""
        if self.atm.get("w") is None and self.atm.get("gust_mu") is None:
            return None
        sd = np.where(self._sd > 0, self._sd, 1.0)
        P = self.pool / sd
        pp = (P ** 2).sum(1)
        return np.concatenate([np.argmin(pp[None, :] - 2 * (x[i:i + chunk] / sd) @ P.T, 1) for i in range(0, len(x), chunk)])

    def _finish(self, x, rows=None):
        x[:, 3 * NH:4 * NH] = np.clip(x[:, 3 * NH:4 * NH], 0, 100)
        x[:, -1] = np.clip(x[:, -1], 0, 100)
        out = dict(u=x[:, :NH], v=x[:, NH:2 * NH], T=x[:, 2 * NH:3 * NH], RH=x[:, 3 * NH:4 * NH], t2m=x[:, -3], sp=x[:, -2], rh2m=x[:, -1], z=np.asarray(_core.HEIGHTS, float))
        th = _core.thermo_column(_core.HEIGHTS, out["T"], out["RH"], out["sp"], t_sfc=out["t2m"], rh_sfc=out["rh2m"], z_sfc=self.elev)
        out.update(p=th["p"], rho=th["rho"], a=th["a"], elevation_m=self.elev)
        if rows is not None:                                             # vertical wind and gust parameters of the pool atmospheres the rows came from (review 2026-11-07: they were dropped)
            for k in ("w", "gust_mu", "gust_beta"):
                if self.atm.get(k) is not None:
                    out[k] = np.asarray(self.atm[k])[rows]
        return out

    def to_samples(self, batch):
        """F3: a batch from sample_sobol / sample_sobol_batch -> the flat sample schema the flight-sim readers expect (adds height_agl and height_asl, drops the nested fine / avionics dicts)."""
        out = {k: v for k, v in batch.items() if not isinstance(v, dict)}
        z = np.asarray(batch["z"], float)
        out["height_agl"] = z.astype(np.float32)
        out["height_asl"] = (self.elev + z).astype(np.float32)
        out["elevation_m"] = np.float32(self.elev)
        return out

    @staticmethod
    def check_outputs(batch, max_wind=150.0):
        """C3: -> list of problems (empty = ok): NaN/inf, RH outside 0-100, T outside 150-340 K, p <= 0 or not decreasing with height, rho or a <= 0, wind above max_wind."""
        bad = []
        for k, v in batch.items():
            if isinstance(v, np.ndarray) and v.dtype.kind == "f" and not np.isfinite(v).all():
                bad.append(f"{k}: NaN or inf")
        if not ((batch["RH"] >= 0).all() and (batch["RH"] <= 100).all()):
            bad.append("RH outside 0-100")
        if not ((batch["T"] > 150).all() and (batch["T"] < 340).all()):
            bad.append("T outside 150-340 K")
        if not (batch["p"] > 0).all():
            bad.append("p <= 0")
        if not (np.diff(batch["p"], axis=1) <= 0).all():
            bad.append("p not decreasing with height")
        if not (batch["rho"] > 0).all():
            bad.append("rho <= 0")
        if not (batch["a"] > 0).all():
            bad.append("a <= 0")
        if not (np.hypot(batch["u"], batch["v"]) < max_wind).all():
            bad.append(f"wind above {max_wind} m/s")
        return bad

    # ---- the one-call contract (blueprint section "Unified integration")
    def sample_sobol_batch(self, u_sobol_matrix, k_atmo=6, include_dryden_turbulence=True, include_avionics_bias=True, dz_fine_m=2.0, turbulence_seed=0, z0_roughness_m=0.03, dryden_fixes=False, run_id=None, exact_ar=False):
        """One vectorised call for a simulator. u_sobol_matrix (N, >= k_atmo [+ 4]): columns 0 .. k_atmo-1 drive the leading atmosphere modes; if the matrix has 4 more columns they are the
        1-cos gust (altitude, wavelength, direction, magnitude). -> dict with the coarse batch (u, v, T, RH, p, rho, a ... on the 44 heights), `fine` (Dryden fields on dz_fine_m) and
        `avionics` (barometric altitude, altimeter bias, refractivity, radio horizon) when asked for. dryden_fixes=True switches on the Gemini-review fixes IL-130/IL-135 (exact N^2, no
        boundary-layer leak above the layer, resolved w added, layer depth from the profile, gust peak from the sample's own gust law); off (default) = the previous output.
        run_id (F1/F2) keys the atmosphere residual and the Dryden noise on (seed, run_id, row block); exact_ar (S1) uses the exact AR(2) transverse filter. Both off by default."""
        from tempest_weather.flight import avionics, dryden
        u = np.asarray(u_sobol_matrix, float)
        batch = self.sample_sobol(u[:, :k_atmo], run_id=run_id)
        if include_dryden_turbulence:
            gust = tuple(u[:, k_atmo + i] for i in range(4)) if u.shape[1] >= k_atmo + 4 else None
            batch["fine"] = dryden.synthesize(batch["z"], batch["u"], batch["v"], batch["T"], dz=dz_fine_m, seed=turbulence_seed, gust=gust, z0=z0_roughness_m, run_id=run_id, exact_ar=exact_ar,
                                             **(dict(w=batch.get("w"), exact_n2=True, bl_floor0=True, h_pbl_from_profile=True,
                                                     gust_params=(batch["gust_mu"], batch["gust_beta"]) if batch.get("gust_mu") is not None else None) if dryden_fixes else {}))
        if include_avionics_bias:
            z_true = self.elev + np.concatenate([[0.0], batch["z"]])
            p = np.concatenate([batch["sp"][:, None], batch["p"]], 1)
            T = np.concatenate([batch["t2m"][:, None], batch["T"]], 1)
            rh = np.concatenate([batch["rh2m"][:, None], batch["RH"]], 1)
            batch["avionics"] = avionics.compute(z_true, p, T, rh)
        return batch
