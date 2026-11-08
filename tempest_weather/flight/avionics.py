"""Barometric altimeter bias and radio refractivity (stage 6, module 5, without the gaseous-attenuation part).

* Barometric altitude: what a flight computer that inverts the static pressure with the 1976 International Standard Atmosphere reads, in the troposphere
  z = (T0 / L) (1 - (p / p0)^(R L / g)) and above 11 km z = 11000 - (R T11 / g) ln(p / p11); referenced to the pad (pressure at the first level), which is how dual-deploy altimeters zero
  their AGL altitude. The bias is z_baro_agl - z_true_agl: negative on a warm day (warm air keeps the pressure higher at a given height, so the computer reads too low) and positive on a cold day; it is
  what moves the drogue / main deployment away from the setting.
* Radio refractivity N = 77.6 p / T + 3.73e5 e / T^2 (p, e in hPa, T in K; ITU-R P.453), its vertical gradient, the effective Earth radius factor k = 1 / (1 + R_E dN/dz 1e-6) and the radio
  horizon sqrt(2 k R_E h).
Not implemented: the ITU-R P.676 gaseous attenuation (needs the line tables; it is small below 10 GHz and would be a guess without them).
"""
import numpy as np

T0, P0, L = 288.15, 101325.0, 0.0065
RD, G0, RE = 287.05287, 9.80665, 6371000.0
P11, T11 = 22632.06, 216.65
EXP = RD * L / G0


def baro_altitude_msl(p, geometric=False):
    """ISA altitude (m) of the static pressure p (Pa). The ISA formulas give GEOPOTENTIAL height; geometric=True (IL-131, opt-in) converts to geometric height z = Re H / (Re - H)
    (the two differ by 51 m at 18 km)."""
    p = np.asarray(p, float)
    tropo = (T0 / L) * (1.0 - (np.clip(p, 1.0, None) / P0) ** EXP)
    strato = 11000.0 - (RD * T11 / G0) * np.log(np.clip(p, 1.0, None) / P11)
    h = np.where(p >= P11, tropo, strato)
    return RE * h / (RE - h) if geometric else h


def saturation_vapour_hpa(T):
    t = np.asarray(T, float) - 273.15
    return 6.1121 * np.exp((18.678 - t / 234.5) * (t / (257.14 + t)))


def compute(z_true_m, pressure_Pa, temp_K, rh_pct=None, geometric=True):
    """Profiles (nz,) or (N, nz) from the first level up (the first level is the pad). -> dict: z_true_agl_m, z_baro_msl_m, z_baro_agl_m, altimeter_bias_m, refractivity_N, dN_dz_per_km,
    k_factor, radio_horizon_km."""
    z = np.asarray(z_true_m, float)
    p = np.atleast_2d(np.asarray(pressure_Pa, float))
    T = np.atleast_2d(np.asarray(temp_K, float))
    z_agl = z - z[0]
    zb = baro_altitude_msl(p, geometric)
    zb_agl = zb - zb[:, :1]
    e = np.zeros_like(T) if rh_pct is None else np.clip(np.atleast_2d(np.asarray(rh_pct, float)), 0, 100) / 100.0 * saturation_vapour_hpa(T)
    N = 77.6 * (p / 100.0) / T + 3.73e5 * e / T ** 2
    dN = np.gradient(N, z, axis=1)                                                                           # per metre
    k = 1.0 / (1.0 + RE * dN * 1e-6)
    horizon = np.sqrt(2.0 * np.clip(k, 0.2, 20.0) * RE * np.maximum(z_agl, 0.0)[None, :]) / 1000.0
    return dict(z_true_agl_m=z_agl, z_baro_msl_m=zb, z_baro_agl_m=zb_agl, altimeter_bias_m=zb_agl - z_agl[None, :], refractivity_N=N, dN_dz_per_km=dN * 1000.0, k_factor=k, radio_horizon_km=horizon)
