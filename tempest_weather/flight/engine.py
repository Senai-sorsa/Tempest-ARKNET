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
    def __init__(self, lat=None, lon=None, when=None, n_pool=2048, seed=0, assets=None, atm=None, info=None, **kw):
        if atm is None:
            from tempest_weather import api
            atm, info = api.atmosphere_set(lat, lon, when, n=n_pool, seed=seed, assets=assets, **kw)
        self.atm, self.info, self.seed = atm, info or {}, seed
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
    def _cdf(self, j, x):
        return float(np.clip(np.interp(x, self._sorted[:, j], self._probs), 1e-6, 1 - 1e-6))

    def _ppf(self, j, v):
        return np.interp(v, self._probs, self._sorted[:, j])

    # ---- module 2
    def condition_on_observations(self, obs, sensor_sigma=None, inflate=1.5):
        """obs: {(variable, height_m): measured value}; variables wind_u, wind_v (m/s), temp_K, rh_pct, pressure_Pa (surface, height 0). Heights must be model heights (10, 50, 100 ... 18000 m)
        or 2 m for temp_K / rh_pct. sensor_sigma: physical standard deviation of the sensors (one number or {variable: sigma}); default: practically exact pins. inflate: factor on the posterior variance of the unobserved columns (1.0 = the pure Schur complement; 1.5 is the default: the check in
        scripts/s6_condition_eval.py found the pure version too sharp: 90 % intervals held 80-86 % of balloons, 88-92 % with 1.5)."""
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
        w, v = np.linalg.eigh(0.5 * (S + S.T))
        o = np.argsort(w)[::-1]
        self._post = dict(idx=idx, un=un, vals=np.array(list(obs.values()), float), mu=mu, eigvals=np.maximum(w[o], 0.0) * float(inflate), eigvecs=v[:, o])
        return self

    def clear_observations(self):
        self._post = None

    # ---- module 1
    def sample_sobol(self, u_matrix=None, exact_residual=True):
        """u_matrix (N, k) uniforms in (0, 1) from the simulator, or None for the conditional median profile (N = 1). -> dict of arrays (N, ...) like `atmosphere_set` (+ z, p, rho, a).
        The k leading eigenmodes are driven by the columns of u_matrix; the remaining modes use a seeded pseudo-random draw (exact_residual=True) or are left out (False)."""
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
                y = y + rng.standard_normal((N, D - k)) @ load[:, k:].T
        x = np.empty((y.shape[0], P))
        for jj, j in enumerate(cols):
            x[:, j] = self._ppf(j, norm_cdf(y[:, jj]))
        if fixed is not None:
            x[:, fixed[0]] = fixed[1][None, :]
        return self._finish(x)

    def observe_by_weights(self, obs, sensor_sigma, n_out=1000):
        """The pool-based alternative: weight every pool atmosphere by the Gaussian likelihood of the observations (sensor_sigma in physical units, one number or {variable: sigma}) and
        resample n_out with replacement. -> (batch, effective sample size). Keeps the non-Gaussian structure but needs a large pool and soft sensors: with hard pins the weights collapse."""
        rng = np.random.default_rng(self.seed + 47)
        ll = np.zeros(len(self.pool))
        for (var, h), val in obs.items():
            j = self.index[(var, float(h))]
            s = sensor_sigma.get(var, 1.0) if isinstance(sensor_sigma, dict) else float(sensor_sigma)
            ll += -0.5 * ((self.pool[:, j] - float(val)) / max(s, 1e-9)) ** 2
        w = np.exp(ll - ll.max())
        w /= w.sum()
        pick = rng.choice(len(self.pool), n_out, p=w)
        return self._finish(self.pool[pick].copy()), float(1.0 / np.sum(w ** 2))

    def _finish(self, x):
        x[:, 3 * NH:4 * NH] = np.clip(x[:, 3 * NH:4 * NH], 0, 100)
        x[:, -1] = np.clip(x[:, -1], 0, 100)
        out = dict(u=x[:, :NH], v=x[:, NH:2 * NH], T=x[:, 2 * NH:3 * NH], RH=x[:, 3 * NH:4 * NH], t2m=x[:, -3], sp=x[:, -2], rh2m=x[:, -1], z=np.asarray(_core.HEIGHTS, float))
        th = _core.thermo_column(_core.HEIGHTS, out["T"], out["RH"], out["sp"], t_sfc=out["t2m"], rh_sfc=out["rh2m"], z_sfc=self.elev)
        out.update(p=th["p"], rho=th["rho"], a=th["a"], elevation_m=self.elev)
        return out

    # ---- the one-call contract (blueprint section "Unified integration")
    def sample_sobol_batch(self, u_sobol_matrix, k_atmo=6, include_dryden_turbulence=True, include_avionics_bias=True, dz_fine_m=2.0, turbulence_seed=0, z0_roughness_m=0.03):
        """One vectorised call for a simulator. u_sobol_matrix (N, >= k_atmo [+ 4]): columns 0 .. k_atmo-1 drive the leading atmosphere modes; if the matrix has 4 more columns they are the
        1-cos gust (altitude, wavelength, direction, magnitude). -> dict with the coarse batch (u, v, T, RH, p, rho, a ... on the 44 heights), `fine` (Dryden fields on dz_fine_m) and
        `avionics` (barometric altitude, altimeter bias, refractivity, radio horizon) when asked for."""
        from tempest_weather.flight import avionics, dryden
        u = np.asarray(u_sobol_matrix, float)
        batch = self.sample_sobol(u[:, :k_atmo])
        if include_dryden_turbulence:
            gust = tuple(u[:, k_atmo + i] for i in range(4)) if u.shape[1] >= k_atmo + 4 else None
            batch["fine"] = dryden.synthesize(batch["z"], batch["u"], batch["v"], batch["T"], dz=dz_fine_m, seed=turbulence_seed, gust=gust, z0=z0_roughness_m)
        if include_avionics_bias:
            z_true = self.elev + np.concatenate([[0.0], batch["z"]])
            p = np.concatenate([batch["sp"][:, None], batch["p"]], 1)
            T = np.concatenate([batch["t2m"][:, None], batch["T"]], 1)
            rh = np.concatenate([batch["rh2m"][:, None], batch["RH"]], 1)
            batch["avionics"] = avionics.compute(z_true, p, T, rh)
        return batch
