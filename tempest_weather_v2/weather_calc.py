"""Launch-site numbers from atmospheres (spec 1.1-1.3): altimeter setting, station pressure, MSLP, density altitude, dew point, drift-equivalent uniform wind, shear, jet wind, magnetic declination.

All functions are vectorised over samples (first axis) and use SI inside; conversions to US units are in `units.py`. numpy only.
"""
import math

import numpy as np

__all__ = ["altimeter_setting_hpa", "station_pressure_hpa", "mslp_hpa", "density_altitude_m", "dew_point_k", "drift_wind", "max_shear", "upper_wind_max", "declination_deg",
           "wind_from_deg", "cardinal", "FLIGHT_DEFAULT"]

N_ALT = 0.190284
G0, RD, L_STD, T0, P0_HPA, RHO0 = 9.80665, 287.05287, 0.0065, 288.15, 1013.25, 1.225
FLIGHT_DEFAULT = dict(apogee_m=10000 * 0.3048, main_m=1000 * 0.3048, v_drogue=75 * 0.3048, v_main=20 * 0.3048)   # the reference flight of spec 1.2


def altimeter_setting_hpa(p_station_hpa, elevation_m):
    """Altimeter setting (what METARs call barometric pressure, 'A3002'): station pressure reduced to sea level through the standard atmosphere (NWS formula, spec 1.1)."""
    p = np.asarray(p_station_hpa, float) - 0.3
    k = (P0_HPA ** N_ALT) * L_STD / T0
    return p * (1.0 + k * np.asarray(elevation_m, float) / p ** N_ALT) ** (1.0 / N_ALT)


def station_pressure_hpa(altimeter_hpa, elevation_m):
    """Exact inverse of `altimeter_setting_hpa`: pad pressure from a sea-level altimeter setting through the standard atmosphere."""
    a = np.asarray(altimeter_hpa, float)
    k = (P0_HPA ** N_ALT) * L_STD / T0
    return (a ** N_ALT - k * np.asarray(elevation_m, float)) ** (1.0 / N_ALT) + 0.3


def mslp_hpa(p_station_hpa, t_station_k, elevation_m):
    """Mean sea-level pressure, reduced with the actual temperature (hypsometric, mean column temperature from the standard lapse rate)."""
    h = np.asarray(elevation_m, float)
    tmean = np.asarray(t_station_k, float) + L_STD * h / 2.0
    return np.asarray(p_station_hpa, float) * np.exp(G0 * h / (RD * tmean))


def density_altitude_m(rho):
    """Standard-atmosphere altitude (m) at which the air density equals `rho` (kg/m3); troposphere formula, valid to 11 km."""
    r = np.asarray(rho, float) / RHO0
    expo = G0 / (RD * L_STD) - 1.0
    return T0 / L_STD * (1.0 - r ** (1.0 / expo))


def dew_point_k(t_k, rh_pct):
    """Dew point from temperature and relative humidity (Magnus, over water)."""
    t = np.asarray(t_k, float) - 273.15
    a, b = 17.62, 243.12
    g = np.log(np.clip(np.asarray(rh_pct, float), 0.01, 100.0) / 100.0) + a * t / (b + t)
    return b * g / (a - g) + 273.15


def wind_from_deg(u, v):
    """Meteorological direction the wind blows FROM (0 = north, 90 = east) from east/north components."""
    return (np.degrees(np.arctan2(-np.asarray(u, float), -np.asarray(v, float))) + 360.0) % 360.0


_CARD = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def cardinal(deg):
    return _CARD[int((float(deg) % 360.0) / 22.5 + 0.5) % 16]


def drift_wind(u, v, z_agl, apogee_m=FLIGHT_DEFAULT["apogee_m"], main_m=FLIGHT_DEFAULT["main_m"], v_drogue=FLIGHT_DEFAULT["v_drogue"], v_main=FLIGHT_DEFAULT["v_main"]):
    """Drift-equivalent uniform wind (spec 1.2): the time-weighted VECTOR mean of the wind from the ground to apogee, weight 1 / v_descent(z) (fast under drogue above `main_m`, slow under the
    main below it). u, v (N, nz) east/north on heights z_agl (nz,). -> (speed (N,), from_deg (N,), u_mean, v_mean). The wind above the top height is held; apogee above 18 km is the caller's flag."""
    z = np.asarray(z_agl, float)
    grid = np.arange(0.0, apogee_m + 5.0, 10.0)
    uu = np.stack([np.interp(grid, z, r) for r in np.atleast_2d(u)])
    vv = np.stack([np.interp(grid, z, r) for r in np.atleast_2d(v)])
    wgt = np.where(grid > main_m, 1.0 / v_drogue, 1.0 / v_main)
    um, vm = (uu * wgt).sum(1) / wgt.sum(), (vv * wgt).sum(1) / wgt.sum()
    return np.hypot(um, vm), wind_from_deg(um, vm), um, vm


def max_shear(u, v, z_agl):
    """Largest vertical vector wind shear |du/dz| over the column and the height AGL (layer midpoint) where it happens. -> (shear s^-1 (N,), height (N,))."""
    z = np.asarray(z_agl, float)
    du, dv, dz = np.diff(u, axis=1), np.diff(v, axis=1), np.diff(z)
    s = np.hypot(du, dv) / dz[None, :]
    j = s.argmax(1)
    return s.max(1), 0.5 * (z[j] + z[j + 1])


def upper_wind_max(u, v, z_agl, lo_m=5000.0):
    """Peak wind speed above `lo_m` AGL (the jet-stream corridor) and its height. -> (speed (N,), height (N,))."""
    z = np.asarray(z_agl, float)
    sel = z >= lo_m
    s = np.hypot(u[:, sel], v[:, sel])
    j = s.argmax(1)
    return s.max(1), z[sel][j]


# ---------------------------------------------------------------------- magnetic declination (low-degree IGRF, good to a few degrees)
# IGRF-13, epoch 2020.0 (nT) and secular variation (nT/yr), degree <= 4. Declination from a degree-4 field is accurate to about 1-3 deg over the contiguous US; sites.toml stores exact values.
_G = {(1, 0): (-29404.8, 5.7), (1, 1): (-1450.9, 7.4), (2, 0): (-2499.6, -11.0), (2, 1): (2982.0, -7.0), (2, 2): (1677.0, -2.1), (3, 0): (1363.2, 2.2), (3, 1): (-2381.2, -5.9),
      (3, 2): (1236.2, 3.1), (3, 3): (525.7, -12.0), (4, 0): (903.0, -1.2), (4, 1): (809.5, -1.6), (4, 2): (86.3, -5.9), (4, 3): (-309.4, 5.2), (4, 4): (48.0, -5.1)}
_H = {(1, 1): (4652.5, -25.9), (2, 1): (-2991.6, -30.2), (2, 2): (-734.6, -22.4), (3, 1): (-82.1, 6.0), (3, 2): (241.9, -1.1), (3, 3): (-543.4, 0.5), (4, 1): (281.9, -0.1),
      (4, 2): (-158.4, 6.5), (4, 3): (199.7, 3.6), (4, 4): (-349.7, -5.0)}


def _schmidt(nmax, theta):
    """Schmidt semi-normalised P_n^m(cos theta) and dP/dtheta for n <= nmax (recursion)."""
    ct, st = math.cos(theta), math.sin(theta)
    P = {(0, 0): 1.0}
    dP = {(0, 0): 0.0}
    for n in range(1, nmax + 1):
        for m in range(0, n + 1):
            if n == m:
                f = 1.0 if n == 1 else math.sqrt((2.0 * n - 1.0) / (2.0 * n))
                P[(n, n)] = f * st * P[(n - 1, n - 1)]
                dP[(n, n)] = f * (st * dP[(n - 1, n - 1)] + ct * P[(n - 1, n - 1)])
            else:
                if n == 1:
                    P[(1, 0)], dP[(1, 0)] = ct, -st
                    continue
                den = math.sqrt(n * n - m * m)
                k = math.sqrt(max((n - 1.0) ** 2 - m * m, 0.0))
                p2, d2 = (P[(n - 2, m)], dP[(n - 2, m)]) if n - 2 >= m else (0.0, 0.0)
                P[(n, m)] = ((2.0 * n - 1.0) * ct * P[(n - 1, m)] - k * p2) / den
                dP[(n, m)] = ((2.0 * n - 1.0) * (ct * dP[(n - 1, m)] - st * P[(n - 1, m)]) - k * d2) / den
    return P, dP


def declination_deg(lat, lon, year=2026.0):
    """Magnetic declination (degrees east of true north) at the surface from the degree-4 IGRF-13 field; secular variation to `year`. Geocentric latitude from geodetic (WGS84)."""
    phi = math.radians(lat)
    lat_c = math.atan((1.0 - 6.694380e-3) * math.tan(phi))
    theta, lam, dt = math.pi / 2.0 - lat_c, math.radians(lon), year - 2020.0
    P, dP = _schmidt(4, theta)
    st = math.sin(theta)
    br = bt = bp = 0.0
    for n in range(1, 5):
        for m in range(0, n + 1):
            g = _G[(n, m)][0] + _G[(n, m)][1] * dt
            h = (_H[(n, m)][0] + _H[(n, m)][1] * dt) if (n, m) in _H else 0.0
            c, s = math.cos(m * lam), math.sin(m * lam)
            br += (n + 1) * (g * c + h * s) * P[(n, m)]
            bt -= (g * c + h * s) * dP[(n, m)]
            bp += m * (g * s - h * c) * P[(n, m)] / st
    # at the Earth's surface r = a: B_r = sum (n+1) ..., B_theta = - dV/dtheta, B_phi = -(1 / sin theta) dV/dphi
    north, east = -bt, bp
    return math.degrees(math.atan2(east, north))
