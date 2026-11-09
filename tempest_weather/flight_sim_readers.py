"""Readers that give ONE coupled atmosphere (one row of atmosphere_samples.npz) to a simulator, in the interfaces of flight_sim:

    wind = TempestWind(samples, k)            # like flight_sim.environment.wind.WindModel:  velocity(altitude_m) -> np.array([up, east, north]) in m/s
    atm = TempestAtmosphere(samples, k)       # like AtmosphereModel:  conditions(altitude_m) -> AtmosphereConditions(temperature, pressure, air_density, speed_of_sound)
    atm.anchor(launch_altitude_m)             # raises if the sim's launch elevation differs from the samples' site elevation by more than 10 m

`samples` is the dict/npz written by tempest.output.coupled / tempest_weather (arrays with the sample index first). Nothing from flight_sim is imported, so
the folder stays standalone; the classes are duck-typed to match (world frame (up, east, north) as in flight_sim.utilities.dcm.world_direction).
Rules (docs/specs/coupled-atmosphere.md 2a): linear interpolation in height; below the first height (10 m above ground) the 10 m value; above the top
height (18 km) wind is held at its top value (the written "blend to zero" would mean calm air at 20 km, which is unphysical, so it is not done) and temperature and
pressure continue along the US Standard Atmosphere 1976 lapse rates from the top values (no jump). Temperature is interpolated linearly, pressure in log space,
and density and speed of sound are RECOMPUTED from the interpolated temperature, pressure and humidity, so the four stay consistent between grid heights.
"""
import math
from typing import NamedTuple

import numpy as np

from tempest_weather._core import RD, RV, GAMMA, G0, es_liquid, mixing_q


class AtmosphereConditions(NamedTuple):
    temperature: float
    pressure: float
    air_density: float
    speed_of_sound: float


# standard-atmosphere lapse rates above 18 km: (base altitude m, K per m), geopotential ~ geometric to the accuracy needed here
_RE = 6371000.0
_LAYERS = ((11000.0, 0.0), (20000.0, 0.001), (32000.0, 0.0028), (47000.0, 0.0), (51000.0, -0.0028), (71000.0, -0.002), (86000.0, 0.0))


def _lapse(z):
    rate = -0.0065
    for base, r in _LAYERS:
        if z >= base:
            rate = r
    return rate


class _Tail:
    """T and p above the top height, integrated from the top values with standard lapse rates (100 m steps, to 86 km)."""

    def __init__(self, z_top, t_top, p_top, geopotential=True):
        self.z = np.arange(z_top, 86000.0 + 100.0, 100.0)
        # IL-131 (ON by default since 2026-11-08): the standard lapse layers and the hydrostatic step are in GEOPOTENTIAL height; the grid above is geometric (51 m apart at 18 km)
        hp = (lambda z: _RE * z / (_RE + z)) if geopotential else (lambda z: z)
        t, lnp = [t_top], [math.log(p_top)]
        for a, b in zip(self.z[:-1], self.z[1:]):
            ha, hb = hp(a), hp(b)
            tb = t[-1] + _lapse(ha) * (hb - ha)
            lnp.append(lnp[-1] - G0 * (hb - ha) / (RD * 0.5 * (t[-1] + tb)))
            t.append(tb)
        self.t, self.lnp = np.array(t), np.array(lnp)

    def at(self, z):
        z = min(max(z, self.z[0]), self.z[-1])
        return float(np.interp(z, self.z, self.t)), float(math.exp(np.interp(z, self.z, self.lnp)))


class _Sample:
    def __init__(self, samples, k, pad_node=True, pad_wind_factor=0.72):
        g = lambda key: np.asarray(samples[key][k], float)
        self.z = np.asarray(samples["height_asl"], float)
        self.site = float(self.z[0] - float(np.asarray(samples["height_agl"])[0]))
        self.u, self.v, self.T, self.p, self.RH = g("u"), g("v"), g("T"), g("p"), g("RH")
        self.w = g("w") if "w" in samples and np.isfinite(np.asarray(samples["w"][k])).all() else np.zeros_like(self.u)
        self.k = k
        if pad_node and all(key in samples for key in ("t2m", "sp", "rh2m")) and all(np.isfinite(float(np.asarray(samples[key][k]))) for key in ("t2m", "sp", "rh2m")):
            # IL-131 (plain bug, ON by default since 2026-11-08; pad_node=False = old behaviour): a node at the pad (0 m above ground) with the surface state, so conditions(pad) is (t2m, sp, rh2m) and not the 10 m values. Wind there is the 10 m wind
            # reduced by the log-law ratio ln(2 / z0) / ln(10 / z0) = 0.72 (z0 = 3 cm); the vertical wind is zero at the ground.
            f = float(pad_wind_factor)
            self.z = np.concatenate([[self.site], self.z])
            self.u, self.v, self.w = np.concatenate([[self.u[0] * f], self.u]), np.concatenate([[self.v[0] * f], self.v]), np.concatenate([[0.0], self.w])
            self.T = np.concatenate([[float(np.asarray(samples["t2m"][k]))], self.T])
            self.p = np.concatenate([[float(np.asarray(samples["sp"][k]))], self.p])
            self.RH = np.concatenate([[float(np.asarray(samples["rh2m"][k]))], self.RH])


class TempestWind:
    """Wind of sample k: velocity(altitude_m) -> [up, east, north] (m/s). Vertical wind only if the samples carry it."""

    def __init__(self, samples, k, include_vertical=True, pad_node=True):
        self.s = _Sample(samples, k, pad_node)
        self.include_vertical = include_vertical

    def velocity(self, altitude_m):
        s = self.s
        z = min(max(altitude_m, s.z[0]), s.z[-1])             # below 10 m above ground: the 10 m value; above the top: held
        return np.array([float(np.interp(z, s.z, s.w)) if self.include_vertical else 0.0, float(np.interp(z, s.z, s.u)), float(np.interp(z, s.z, s.v))])


class TempestAtmosphere:
    def __init__(self, samples, k, pad_node=True, geopotential=True):
        self.s = _Sample(samples, k, pad_node)
        s = self.s
        self.tail = _Tail(float(s.z[-1]), float(s.T[-1]), float(s.p[-1]), geopotential)

    def anchor(self, launch_altitude_m, tolerance_m=10.0):
        if abs(launch_altitude_m - self.s.site) > tolerance_m:
            raise ValueError(f"launch altitude {launch_altitude_m:.1f} m differs from the atmosphere's site elevation {self.s.site:.1f} m by more than {tolerance_m} m; "
                             "every height would shift: regenerate the atmosphere for the right elevation")

    def conditions(self, altitude_m):
        s = self.s
        if altitude_m <= s.z[-1]:
            z = max(altitude_m, s.z[0])
            t = float(np.interp(z, s.z, s.T))
            p = math.exp(float(np.interp(z, s.z, np.log(s.p))))
            rh = float(np.interp(z, s.z, s.RH))
            q = float(mixing_q(t, rh, p))
        else:
            t, p = self.tail.at(altitude_m)
            q = 0.0                                              # dry air up there
        tv = t * (1 + (RV / RD - 1) * q)
        return AtmosphereConditions(t, p, p / (RD * tv), math.sqrt(GAMMA * RD * tv))
