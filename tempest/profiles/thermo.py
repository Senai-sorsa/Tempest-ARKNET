"""Pressure, density and speed of sound along a profile, derived (not learned) from T, RH and surface pressure.

    from tempest.profiles.thermo import column
    out = column(HEIGHTS, T, RH, sp, t2m, rh2m, z_sfc)   # dict of p (Pa), rho (kg/m3), a (m/s), q (kg/kg), tv (K)

Decision (docs/PLAN.md): pressure is derived by hypsometric integration of the sampled T and RH, so a sampled
profile is hydrostatically consistent by construction. The generator does not learn pressure aloft.
Layer by layer from the surface: ln p_top = ln p_bottom - g dz / (Rd Tv), with Tv the mean virtual temperature of the
layer and g(z) = g0 (R/(R+z))^2 at the layer mid-height above sea level. Humidity needs p, and p needs Tv, so
q is computed twice (one fixed-point pass; the second pass changes p by under 0.01 %).
RH is over liquid water, the same convention as the profiles (to_heights.liquid_rh). All arrays broadcast over leading
dimensions; heights are metres above ground.
"""
import numpy as np

RD, RV, G0, R_EARTH, GAMMA = 287.05, 461.5, 9.80665, 6371000.0, 1.4
EPS = RD / RV


def es_liquid(t):
    """Saturation vapour pressure over liquid water (Pa), T in K (same formula as to_heights.liquid_rh)."""
    return 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))


def mixing_q(t, rh, p):
    """Specific humidity (kg/kg) from T (K), RH over liquid water (%), p (Pa)."""
    e = np.clip(rh, 0, 100) / 100.0 * es_liquid(t)
    return EPS * e / (p - (1 - EPS) * e)


def virtual_t(t, q):
    return t * (1 + (RV / RD - 1) * q)


def gravity(z_asl):
    """Gravity (m/s2) at geometric height above sea level (m)."""
    return G0 * (R_EARTH / (R_EARTH + z_asl)) ** 2


def column(z_agl, T, rh, ps, t_sfc=None, rh_sfc=None, z_sfc=0.0):
    """Heights above ground (n,), T (..., n) K, RH (..., n) %, surface pressure ps (...) Pa ->
    dict(p, rho, a, q, tv), each (..., n). The first layer runs from the surface (t_sfc, rh_sfc; default the first
    level's values) to z_agl[0]. z_sfc (m, scalar or (...)) is the site elevation, used only for gravity."""
    z_agl = np.asarray(z_agl, np.float64)
    T, rh, ps = (np.asarray(x, np.float64) for x in (T, rh, ps))
    t0 = T[..., 0] if t_sfc is None else np.asarray(t_sfc, np.float64)
    r0 = rh[..., 0] if rh_sfc is None else np.asarray(rh_sfc, np.float64)
    zs = np.asarray(z_sfc, np.float64)
    z_edges = np.concatenate([[0.0], z_agl])                       # (n+1,)
    dz = np.diff(z_edges)
    g = gravity(zs[..., None] + 0.5 * (z_edges[1:] + z_edges[:-1]))  # (..., n) mid-layer gravity
    t_all = np.concatenate([t0[..., None], T], -1)                 # (..., n+1) layer edges
    r_all = np.concatenate([r0[..., None], rh], -1)
    # pass 1: dry-virtual guess (Tv = T) with the pressure it gives; pass 2: the humidity from that pressure
    p = None
    tv = t_all
    for _ in range(2):
        inc = g * dz / (RD * 0.5 * (tv[..., 1:] + tv[..., :-1]))
        p_all = ps[..., None] * np.exp(-np.concatenate([np.zeros_like(inc[..., :1]), np.cumsum(inc, -1)], -1))
        q_all = mixing_q(t_all, r_all, p_all)
        tv = virtual_t(t_all, q_all)
    p, q, tvl = p_all[..., 1:], q_all[..., 1:], tv[..., 1:]
    return dict(p=p, rho=p / (RD * tvl), a=np.sqrt(GAMMA * RD * tvl), q=q, tv=tvl)
