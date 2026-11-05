"""Thermals: sub-grid vertical wind in the convective boundary layer (PHASED_PLAN 3.3, atmosphere-outputs.md section 3).

Per sample: boundary-layer height zi (ERA5 blh) and surface sensible heat flux H (upward positive, W/m2) give the
convective velocity scale  w* = (g / T * H / (rho cp) * zi)^(1/3)  (0 when H <= 0: stable air, no thermals), and the
standard deviation of vertical wind through the layer follows Lenschow et al. (1980):
    sigma_w^2 = 1.8 w*^2 (z/zi)^(2/3) (1 - 0.8 z/zi)^2     for 0 < z < zi.
NOTE: Code-Modifications/atmosphere-outputs.md writes this as sigma_w = w* * 1.8 * ..., which drops the square root
(sigma_w = w* sqrt(1.8) ...); with it, thermals come out 34 % too strong. The variance form is used here.
Thermals are skewed (narrow strong updrafts, broad weak downdrafts) and span the layer, so each sample gets ONE thermal
regime (updraft with probability `updraft_area`, else downdraft) and one standard-normal draw shared by all heights,
plus a small per-height part (`z_corr` = correlation between heights).
STATUS: the physics is unit-tested; the coefficients still have to be checked against high-resolution balloon rise
rates (not downloaded yet, see Code-Modifications/ASK_LATER.md) and sshf (ERA5 sensible heat) is not in the Earthmover
store, it needs a CDS pull. Until then the module is off by default everywhere.
"""
import numpy as np

G0, CP = 9.80665, 1004.0


def sensible_heat_up(sshf_accum_j_m2, hours=1.0):
    """ERA5 sshf (J/m2 accumulated over `hours`, downward positive) -> H in W/m2 with upward heat positive."""
    return -np.asarray(sshf_accum_j_m2, float) / (3600.0 * hours)


def w_star(h_up, zi, t_air, rho):
    """Convective velocity scale (m/s); zero where H <= 0 or zi <= 0."""
    h = np.maximum(np.asarray(h_up, float), 0.0)
    return (G0 / np.asarray(t_air, float) * h / (np.asarray(rho, float) * CP) * np.maximum(np.asarray(zi, float), 0.0)) ** (1.0 / 3.0)


def sigma_w(z_agl, zi, wstar, floor=0.0):
    """Standard deviation of vertical wind (m/s) at heights z_agl (n,) for boundary-layer heights zi (...,) and w* (...,)
    -> (..., n). Zero (or `floor`) above the layer."""
    z = np.asarray(z_agl, float)
    zi = np.asarray(zi, float)[..., None]
    r = z / np.maximum(zi, 1.0)
    inside = (r > 0) & (r < 1)
    s = np.sqrt(1.8) * np.asarray(wstar, float)[..., None] * np.where(inside, r, 0.0) ** (1 / 3) * (1 - 0.8 * np.where(inside, r, 0.0))
    return np.where(inside, np.maximum(s, floor), floor)


def draw(sigma, rng, updraft_area=0.35, between_share=0.8, z_corr=0.8):
    """sigma (n, H) -> one thermal profile per row (n, H): zero mean, standard deviation sigma at every height, positive
    skew, strongly correlated through the layer (one regime and one common normal per row)."""
    n, nh = sigma.shape
    a, f = updraft_area, between_share
    delta = np.sqrt(f / (a * (1 - a)))                 # separation of the two regimes in units of sigma
    up = rng.random(n) < a
    centre = np.where(up, (1 - a) * delta, -a * delta)  # regime mean (a*mu_up + (1-a)*mu_down = 0)
    eps = z_corr * rng.standard_normal((n, 1)) + np.sqrt(1 - z_corr ** 2) * rng.standard_normal((n, nh))
    return sigma * (centre[:, None] + np.sqrt(1 - f) * eps)
