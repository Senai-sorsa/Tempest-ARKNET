"""Fine-grid turbulence and a coherent discrete gust on top of a coupled profile (stage 6, module 3).

ERA5-type profiles are grid-cell hourly means: they miss the small eddies of the boundary layer and the clear-air turbulence of jet-stream shear. This module adds, along the vertical
path of an ascending vehicle, Dryden-type turbulence whose intensity and scale come from the profile itself, plus an optional 1-cos discrete gust.

Along a VERTICAL traverse the component along the path is the vertical wind w (the "longitudinal" Dryden component: first-order, exponential correlation exp(-d / L_w)); the two horizontal
components u, v are transverse to the path (second-order Dryden filter, correlation (1 - d / 2L) exp(-d / L)). The blueprint had these two roles the other way round; for a vertical path this
is the consistent assignment.
Intensity (MIL-HDBK-1797 style): sigma_w = 1.3 u* (1 - z / h_pbl)^(3/4) in the boundary layer with u* from the 10 m wind and the roughness z0 (neutral log law; no stability correction, the
profile carries none); sigma_u = sigma_v = sigma_w / (0.177 + 0.000823 z)^0.4 below 305 m. Clear-air turbulence where the gradient Richardson number is below 0.25: sigma_cat = |dV/dz| * ell *
(0.25 - Ri) / 0.25 with a mixing length ell = 20 m (an assumption, set by the caller; the blueprint's expression had the unit 1/s, not m/s). Scales: L_w = z / 2 (to 152 m), L_u = z / (0.177 +
0.000823 z)^1.2 (to 533 m), clamped to [2.5, 533] m.
numpy only. Reproducible: the same seed gives the same field.
"""
import numpy as np

KAPPA, G, CP = 0.40, 9.80665, 1004.7


def pbl_height(z, T, ri_crit_dtheta=1.0, default=1200.0):
    """Per-sample boundary-layer depth (m) from the profile (IL-135): the first height where the potential temperature has risen by `ri_crit_dtheta` K above its lowest-level value
    (dry adiabat, theta = T + g z / cp); clamped to 200 .. 3000 m, `default` if the profile never gets there. T (N, nz) on z (nz,) -> (N,)."""
    theta = T + (G / CP) * z[None, :]
    rise = theta - theta[:, :1]
    hit = rise >= ri_crit_dtheta
    idx = hit.argmax(1)
    h = np.where(hit.any(1), z[idx], default)
    return np.clip(h, 200.0, 3000.0)


def envelopes(z, u, v, T, z0=0.03, h_pbl=1200.0, ell_cat=20.0, exact_n2=False, bl_floor0=False):
    """z (nz,) heights above ground (m); u, v, T (N, nz) on that grid -> dict of (N, nz) arrays: sigma_u, sigma_w, L_u, L_w, ri.
    h_pbl: a number or one value per profile (N,). Opt-in fixes (IL-130): exact_n2 uses N^2 = (g / T)(dT/dz + g / cp) (the linearised theta made N^2 31 % low at 10 km, 45 % at 18 km);
    bl_floor0 lets the boundary-layer factor go to 0 above the layer and adds a 0.05 m/s background (the 0.05 floor leaked surface turbulence up to 18 km)."""
    z_s = np.maximum(z, 2.0)
    speed = np.hypot(u, v)
    v10 = np.array([np.interp(10.0, z_s, s) for s in speed])
    u_star = KAPPA * np.maximum(v10, 0.5) / np.log(10.0 / z0)
    du, dv = np.gradient(u, z_s, axis=1), np.gradient(v, z_s, axis=1)
    shear2 = np.maximum(du ** 2 + dv ** 2, 1e-6)
    if exact_n2:
        n2 = (G / np.maximum(T, 150.0)) * (np.gradient(T, z_s, axis=1) + G / CP)
        ri = n2 / shear2
    else:
        theta = T * (1.0 + 0.0098 * z_s[None, :] / np.maximum(T, 200.0))
        dth = np.gradient(theta, z_s, axis=1)
        ri = (G / np.maximum(theta, 200.0)) * dth / shear2
    cat = np.sqrt(shear2) * ell_cat * np.clip((0.25 - ri) / 0.25, 0.0, 1.0)
    hp = np.asarray(h_pbl, float).reshape(-1, 1) if np.ndim(h_pbl) else float(h_pbl)
    if bl_floor0:
        pbl = np.clip(1.0 - z_s[None, :] / hp, 0.0, 1.0) ** 0.75
        sigma_w = 1.3 * u_star[:, None] * pbl + 0.05 + cat
    else:
        pbl = np.clip(1.0 - z_s[None, :] / hp, 0.05, 1.0) ** 0.75
        sigma_w = 1.3 * u_star[:, None] * pbl + cat
    ratio = np.where(z_s < 305.0, 1.0 / (0.177 + 0.000823 * np.minimum(z_s, 305.0)) ** 0.4, 1.0)
    sigma_u = sigma_w * ratio[None, :]
    L_w = np.clip(np.where(z_s < 305.0, 0.5 * z_s, 152.0), 2.5, 533.0)
    L_u = np.clip(np.where(z_s < 533.0, z_s / (0.177 + 0.000823 * z_s) ** 1.2, 533.0), 2.5, 533.0)
    return dict(sigma_u=sigma_u, sigma_w=sigma_w, L_u=np.broadcast_to(L_u, sigma_u.shape), L_w=np.broadcast_to(L_w, sigma_u.shape), ri=ri)


def _ar2_step(x1, x2, tau, dz, e1, e2):
    """Exact one-step transition of the critically damped Dryden filter x1'' + 2 x1' / tau + x1 / tau^2 = n / tau^2 over dz (S1): [x1, x2] -> Phi [x1, x2] + chol(Q) e, with
    Phi = exp(-dz / tau) [[1 + dz / tau, dz], [-dz / tau^2, 1 - dz / tau]] and Q = P - Phi P Phi^T, P = diag(1 / (4 tau), 1 / (4 tau^3)) the stationary covariance (so the state stays
    stationary for any dz, however coarse). All arrays (N,)."""
    a = dz / tau
    ex = np.exp(-a)
    p1, p2 = 1.0 / (4.0 * tau), 1.0 / (4.0 * tau ** 3)
    f11, f12, f21, f22 = ex * (1 + a), ex * dz, -ex * dz / tau ** 2, ex * (1 - a)
    q11 = p1 - (f11 ** 2 * p1 + f12 ** 2 * p2)
    q12 = -(f11 * f21 * p1 + f12 * f22 * p2)
    q22 = p2 - (f21 ** 2 * p1 + f22 ** 2 * p2)
    l11 = np.sqrt(np.maximum(q11, 1e-300))
    l21 = q12 / l11
    l22 = np.sqrt(np.maximum(q22 - l21 ** 2, 0.0))
    return f11 * x1 + f12 * x2 + l11 * e1, f21 * x1 + f22 * x2 + l21 * e1 + l22 * e2


def one_minus_cos(z, z_start, half_len, peak):
    """Discrete gust shape (m/s): peak / 2 * (1 - cos(pi (z - z_start) / half_len)) from z_start to z_start + 2 half_len, zero elsewhere."""
    inside = (z >= z_start) & (z <= z_start + 2.0 * half_len)
    return np.where(inside, 0.5 * peak * (1.0 - np.cos(np.pi * (z - z_start) / half_len)), 0.0)


def synthesize(z_coarse, u, v, T, dz=2.0, seed=0, gust=None, z0=0.03, h_pbl=1200.0, ell_cat=20.0, nsub=8, z_top=None, w=None, exact_n2=False, bl_floor0=False,
               h_pbl_from_profile=False, gust_params=None, run_id=None, block=256, exact_ar=False, _rng=None, uw_corr=None):
    """Fine-grid fields for N profiles. z_coarse (nz,) heights above ground, u, v, T (N, nz). gust: None or (u_alt, u_len, u_dir, u_mag) uniforms in (0, 1) (scalars or (N,) arrays) for the
    1-cos gust: start altitude over 0 .. 12 km, half-wavelength 15 .. 150 m, direction 0 .. 2 pi, peak 3 .. 15 m/s. -> dict: z, u_total, v_total, w_total (N, nzf), u_turb, v_turb, w_turb,
    gust_u, gust_v, sigma_u, sigma_w.
    Opt-in fixes (all off = the old behaviour): w (N, nz) resolved vertical wind added to w_total (IL-130); exact_n2, bl_floor0 (see `envelopes`); h_pbl_from_profile estimates the layer depth
    per profile (IL-135); run_id (F1/F2, opt-in) keys the noise on (seed, run_id, row block) so different runs get different noise and a run of N rows starts with exactly the rows of a run of fewer (the old
    seed + 0 stream repeated the same noise in every batch and changed with N); block = rows per noise block; exact_ar (S1, opt-in) steps the transverse Dryden filter with its exact discrete
    transition and noise covariance (one step per dz, stationary start, no burn-in, no Euler sub-steps); gust_params = (gust_mu, gust_beta) arrays (N,) draw the 1-cos peak from the sample's own gust law (Gumbel-type, mean mu, scale beta) instead of uniform 3-15 m/s (IL-135)."""
    z_coarse = np.asarray(z_coarse, float)
    u, v, T = (np.atleast_2d(np.asarray(a, float)) for a in (u, v, T))
    N = len(u)
    if run_id is not None and _rng is None and N > block:                       # F2: whole row blocks, each with its own seed, so the first rows do not depend on N
        parts = []
        for b0 in range(0, N, block):
            sl = slice(b0, b0 + block)
            sub = lambda a: np.asarray(a, float)[sl] if np.ndim(a) else a
            g = None if gust is None else tuple(sub(x) for x in gust)
            gp = None if gust_params is None else tuple(sub(x) for x in gust_params)
            parts.append(synthesize(z_coarse, u[sl], v[sl], T[sl], dz, seed, g, z0, sub(h_pbl) if np.ndim(h_pbl) else h_pbl, ell_cat, nsub, z_top, None if w is None else np.asarray(w, float)[sl],
                                    exact_n2, bl_floor0, h_pbl_from_profile, gp, run_id, block, exact_ar, np.random.default_rng(np.random.SeedSequence([int(seed), int(run_id), b0 // block])), uw_corr=uw_corr))
        return {k: (parts[0][k] if k == "z" else np.concatenate([p[k] for p in parts])) for k in parts[0]}
    z_top = z_top or z_coarse[-1]
    zf = np.arange(z_coarse[0], z_top + dz, dz)
    interp = lambda a: np.stack([np.interp(zf, z_coarse, r) for r in a])
    uf, vf, Tf = interp(u), interp(v), interp(T)
    if h_pbl_from_profile:
        h_pbl = pbl_height(zf, Tf)
    env = envelopes(zf, uf, vf, Tf, z0, h_pbl, ell_cat, exact_n2=exact_n2, bl_floor0=bl_floor0)
    rng = _rng if _rng is not None else (np.random.default_rng(np.random.SeedSequence([int(seed), int(run_id), 0])) if run_id is not None else np.random.default_rng(seed))
    nz = len(zf)
    ug, vg, wg = np.zeros((N, nz)), np.zeros((N, nz)), np.zeros((N, nz))
    # along-path component (w): exact first-order recurrence
    phi = np.exp(-dz / env["L_w"])
    eta = rng.standard_normal((N, nz))
    wg[:, 0] = env["sigma_w"][:, 0] * eta[:, 0]
    for i in range(1, nz):
        wg[:, i] = phi[:, i] * wg[:, i - 1] + env["sigma_w"][:, i] * np.sqrt(np.maximum(1 - phi[:, i] ** 2, 0.0)) * eta[:, i]
    # transverse components (u, v): second-order Dryden filter, y = K (x1 + sqrt(3) tau x2), x1'' + 2 x1' / tau + x1 / tau^2 = n / tau^2, K = sigma sqrt(tau); Euler sub-steps
    h = dz / nsub
    for out, key in ((ug, 0), (vg, 1)):
        x1, x2 = np.zeros(N), np.zeros(N)
        tau0 = env["L_u"][:, 0]
        if exact_ar:                                                          # S1: stationary start, exact transition per dz (no burn-in, no sub-steps)
            x1, x2 = rng.standard_normal(N) / np.sqrt(4.0 * tau0), rng.standard_normal(N) / np.sqrt(4.0 * tau0 ** 3)
            tau_prev = tau0
            for i in range(nz):
                tau = env["L_u"][:, i]
                r = tau_prev / tau
                x1, x2 = x1 * np.sqrt(r), x2 * r ** 1.5
                tau_prev = tau
                x1, x2 = _ar2_step(x1, x2, tau, dz, rng.standard_normal(N), rng.standard_normal(N))
                out[:, i] = env["sigma_u"][:, i] * np.sqrt(tau) * (x1 + np.sqrt(3.0) * tau * x2)
            continue
        for _ in range(int(min(60.0 * tau0.max(), 4000.0) / h)):          # burn-in so the state starts stationary
            x2 += h * (-x1 / tau0 ** 2 - 2 * x2 / tau0) + np.sqrt(h) * rng.standard_normal(N) / tau0 ** 2
            x1 += h * x2
        tau_prev = tau0
        for i in range(nz):
            tau = env["L_u"][:, i]
            r = tau_prev / tau                                                  # the length scale changed: rescale the state so its stationary variances (1/(4 tau), 1/(4 tau^3)) follow
            x1, x2 = x1 * np.sqrt(r), x2 * r ** 1.5
            tau_prev = tau
            for _ in range(nsub):
                x2 += h * (-x1 / tau ** 2 - 2 * x2 / tau) + np.sqrt(h) * rng.standard_normal(N) / tau ** 2
                x1 += h * x2
            out[:, i] = env["sigma_u"][:, i] * np.sqrt(tau) * (x1 + np.sqrt(3.0) * tau * x2)
    if uw_corr:                                                               # G6 (opt-in): Reynolds stress. The turbulent vertical wind is anti-correlated with the along-mean-wind horizontal turbulence in the boundary layer
        spd = np.maximum(np.hypot(uf, vf), 1e-6)                              # (u'w' = -rho sigma_u sigma_w, rho about 0.35 at the ground, fading to 0 at the top of the layer); w keeps its variance
        u_par = (ug * uf + vg * vf) / spd
        hp = np.broadcast_to(np.asarray(h_pbl, float).reshape(-1, 1) if np.ndim(h_pbl) else float(h_pbl), (N, nz))
        rho = float(uw_corr) * np.clip(1.0 - zf[None, :] / hp, 0.0, 1.0) ** 1.5
        wg = np.sqrt(1.0 - rho ** 2) * wg - rho * env["sigma_w"] * u_par / np.maximum(env["sigma_u"], 1e-9)
    gu = gv = np.zeros((N, nz))
    if gust is not None:
        ua, ul, ud, um = (np.broadcast_to(np.asarray(g, float), (N,)) for g in gust)
        start = zf[0] + ua * min(zf[-1] - zf[0], 12000.0)
        half = 15.0 + ul * 135.0
        peak = 3.0 + um * 12.0
        if gust_params is not None:                                       # the sample's own gust law: quantile um of a Gumbel with location mu, scale beta
            mu, beta = (np.broadcast_to(np.asarray(g, float), (N,)) for g in gust_params)
            peak = np.maximum(mu - beta * np.log(-np.log(np.clip(um, 1e-6, 1 - 1e-6))), 0.0)
        ang = 2.0 * np.pi * ud
        shape = np.stack([one_minus_cos(zf, start[k], half[k], peak[k]) for k in range(N)])
        gu, gv = shape * np.cos(ang)[:, None], shape * np.sin(ang)[:, None]
    wres = interp(np.atleast_2d(np.asarray(w, float))) if w is not None else 0.0
    return dict(z=zf, u_total=uf + ug + gu, v_total=vf + vg + gv, w_total=wg + wres, u_turb=ug, v_turb=vg, w_turb=wg, gust_u=gu, gust_v=gv,
                sigma_u=env["sigma_u"], sigma_w=env["sigma_w"], L_u=env["L_u"], L_w=env["L_w"], ri=env["ri"])
