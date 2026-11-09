"""Acoustic ray tracing through a coupled profile: where does sound from a source at altitude reach the ground, when, and where is the shadow zone (stage 6, module 4).

Method: the effective sound speed c_eff(z, psi) = c(z) + V(z) . e_psi along the horizontal direction psi of propagation (the standard stratified-medium approximation; valid for rays that
stay close to the vertical plane of propagation). Snell's law in a stratified medium conserves a = cos(theta) / c_eff, with theta the ray angle from the horizontal. A ray leaving the source at
depression angle beta has a = cos(beta) / c_eff(source). It continues down while a c_eff(z) < 1 and TURNS upward where a c_eff(z) reaches 1 (then it never reaches the ground: shadow zone).
Horizontal range along psi: x = integral cot(theta) dz, time: t = integral dz / (c_eff sin(theta)) (path length over effective speed). The cross-wind component advects the wave by V_perp * t
(first-order). Not modelled: absorption, nonlinear steepening of a boom, ground reflection, 3D refraction by a cross-wind gradient, turbulence scattering.
The blueprint's ray parameter p = cos / (c + V cos) and its q-formula mixed the wind projection in a way that does not conserve a for a wind-free medium; this version reduces exactly to
straight rays for constant c and to the textbook circular arc for a constant c_eff gradient (both tested).
"""
import numpy as np

GAMMA_R = 1.4 * 287.05287


class AcousticRayTracer:
    def __init__(self, z_m, temp_K, wind_u_mps, wind_v_mps, sound_speed=None):
        """sound_speed (IL-136, opt-in): the moist speed of sound on the same heights (the batch's `a`), instead of the dry-air value from the temperature."""
        self.z = np.asarray(z_m, float)
        self.c = np.sqrt(GAMMA_R * np.asarray(temp_K, float)) if sound_speed is None else np.asarray(sound_speed, float)
        self.u, self.v = np.asarray(wind_u_mps, float), np.asarray(wind_v_mps, float)

    def trace_ray_fan(self, source_alt_m, azimuths_deg, depression_angles_deg, n_int=400, midpoint=False):
        """Rays from (0, 0, source_alt_m) to the ground. azimuths: direction of propagation, degrees clockwise from north; depression: degrees below the horizontal.
        midpoint=True (IL-136, opt-in) evaluates the integrands at the middle of every height step instead of the trapezoid on its ends, which is finite where a ray nearly turns.
        -> dict of (n_az, n_dep) arrays: x_east_m, y_north_m, travel_time_s, reaches_ground (False where the ray turns upward or has no downward start), turning_height_m."""
        z = np.linspace(0.0, float(source_alt_m), n_int)
        zi = 0.5 * (z[1:] + z[:-1]) if midpoint else z                  # where the integrands are read
        c, u, v = (np.interp(zi, self.z, a) for a in (self.c, self.u, self.v))
        c_src, u_src, v_src = (float(np.interp(source_alt_m, self.z, a)) for a in (self.c, self.u, self.v))
        az, dep = np.deg2rad(np.asarray(azimuths_deg, float)), np.deg2rad(np.asarray(depression_angles_deg, float))
        shape = (len(az), len(dep))
        x, y, t = (np.full(shape, np.nan) for _ in range(3))
        ok, turn = np.zeros(shape, bool), np.full(shape, np.nan)
        for i, psi in enumerate(az):
            e_h = np.array([np.sin(psi), np.cos(psi)])
            v_par = u * e_h[0] + v * e_h[1]
            v_perp = u * e_h[1] - v * e_h[0]
            c_eff = c + v_par
            c_eff_src = c_src + u_src * e_h[0] + v_src * e_h[1]
            for j, beta in enumerate(dep):
                a = np.cos(beta) / c_eff_src
                s = a * c_eff                                              # cos(theta) along the ray
                bad = s >= 1.0 - 1e-9
                if bad.any():
                    turn[i, j] = zi[np.flatnonzero(bad)[-1]]               # the highest height below the source where the ray would be horizontal
                    continue
                sin_t = np.sqrt(1.0 - s ** 2)
                dxdz = s / sin_t
                dtdz = 1.0 / (c_eff * sin_t)
                if midpoint:
                    dz = np.diff(z)
                    x_par, tt, drift = float((dxdz * dz).sum()), float((dtdz * dz).sum()), float((v_perp * dtdz * dz).sum())
                else:
                    x_par = np.trapezoid(dxdz, z) if hasattr(np, "trapezoid") else np.trapz(dxdz, z)
                    tt = np.trapezoid(dtdz, z) if hasattr(np, "trapezoid") else np.trapz(dtdz, z)
                    drift = (np.trapezoid(v_perp * dtdz, z) if hasattr(np, "trapezoid") else np.trapz(v_perp * dtdz, z))
                x[i, j] = x_par * e_h[0] + drift * e_h[1]
                y[i, j] = x_par * e_h[1] - drift * e_h[0]
                t[i, j], ok[i, j] = tt, True
        return dict(x_east_m=x, y_north_m=y, travel_time_s=t, reaches_ground=ok, turning_height_m=turn)
