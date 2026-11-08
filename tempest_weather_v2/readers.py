"""Readers v2 (spec F7, S2, F12, F3): one coupled atmosphere (row k of a sample set) as fast wind / air lookups for a simulator.

    atm = Atmosphere(samples, k, frame="une", units="si", reference="asl", direction="to", above_top="hold")
    atm.wind(alt) -> (up, east, north) array          atm.air(alt) -> (T, p, rho, a)       atm.conditions(alt) -> namedtuple (flight_sim's AtmosphereConditions)
    atm.wind_many(alts) / atm.air_many(alts)          vectorised; no Python loop

* S2: at construction the piecewise-linear profile (the 44 model heights plus a node at the pad with the surface state) is expanded once onto a 10 m grid in float32. Every model
  height is a multiple of 10 m, so linear interpolation on the 10 m grid reproduces the piecewise-linear profile exactly (tested). Pressure is interpolated in ln p, and density and speed of
  sound are computed from T, p and humidity when the table is built.
* F7: `frame` ("une" = up/east/north, the flight_sim world frame; "enu"; "ned"), `units` ("si" or "us": ft, ft/s, degF, inHg, slug/ft3), `reference` ("asl" or "agl" altitude input) and
  `direction` ("to" = velocity of the air, "from" = reversed vector) are applied once, so lookups cost nothing extra.
* F12: above the top height (18 km, a parameter) `above_top` is "hold" (wind held; T and p continue along the 1976 standard lapse rates, no jump), "decay" (wind falls off with a 5 km scale),
  "climatology" (standard atmosphere T and p, wind held) or "raise" (AboveTopError). Below the pad node the pad values are held.
* F3: the sample schema is height_agl (44,), height_asl (44,), elevation_m, u, v, T, RH, p (N, 44), optional w, t2m, sp, rh2m (N,). `to_samples` of the engine and `atmosphere_set` outputs
  are accepted (see `normalise_samples`, which adds the missing height keys).
Stdlib + numpy only. Nothing from the flight simulator is imported; the classes are duck-typed to its interfaces.
"""
import math
from typing import NamedTuple

import numpy as np

from tempest_weather import _core
from tempest_weather._core import GAMMA, G0, RD, RV, mixing_q

__all__ = ["Atmosphere", "AtmosphereConditions", "AboveTopError", "normalise_samples"]

GRID_M = 10.0
FT, INHG, SLUG_FT3 = 0.3048, 3386.389, 515.378819
_LAYERS = ((11000.0, 0.0), (20000.0, 0.001), (32000.0, 0.0028), (47000.0, 0.0), (51000.0, -0.0028), (71000.0, -0.002), (86000.0, 0.0))
_RE = 6371000.0
_POLICIES = ("hold", "decay", "climatology", "raise")
_FRAMES = {"une": (0, 1, 2, (1, 1, 1)), "enu": (1, 2, 0, (1, 1, 1)), "ned": (2, 1, 0, (1, 1, -1))}   # output = (v[a], v[b], v[c]) * signs from (up, east, north)


class AboveTopError(ValueError):
    """The request is above the top height and above_top="raise"."""


class AtmosphereConditions(NamedTuple):
    temperature: float
    pressure: float
    air_density: float
    speed_of_sound: float


def normalise_samples(samples, elevation_m=None):
    """F3: accept the producers' dicts (z / elevation_m, or height_agl / height_asl) and return the canonical schema (a new dict; arrays are not copied)."""
    s = dict(samples)
    agl = s.get("height_agl", s.get("z"))
    if agl is None:
        raise KeyError("samples need height_agl (or z)")
    s["height_agl"] = np.asarray(agl, float)
    elev = float(elevation_m if elevation_m is not None else s.get("elevation_m", float(np.asarray(s["height_asl"])[0]) - float(s["height_agl"][0]) if "height_asl" in s else np.nan))
    if not np.isfinite(elev):
        raise KeyError("samples need elevation_m (or height_asl)")
    s["elevation_m"] = elev
    s["height_asl"] = elev + s["height_agl"]
    for k in ("u", "v", "T", "RH", "p"):
        if k not in s:
            raise KeyError(f"samples need {k}")
    s.setdefault("w", None)
    return s


def _lapse(h):
    rate = -0.0065
    for base, r in _LAYERS:
        if h >= base:
            rate = r
    return rate


def _tail(z_top, t_top, p_top, z_max=86000.0, step=100.0):
    """T and ln p above the top along the 1976 standard lapse rates (geopotential steps, hydrostatic), z geometric -> (z, T, lnp)."""
    z = np.arange(z_top, z_max + step, step)
    t, lnp = [t_top], [math.log(p_top)]
    hp = lambda zz: _RE * zz / (_RE + zz)
    for a, b in zip(z[:-1], z[1:]):
        ha, hb = hp(a), hp(b)
        tb = t[-1] + _lapse(ha) * (hb - ha)
        lnp.append(lnp[-1] - G0 * (hb - ha) / (RD * 0.5 * (t[-1] + tb)))
        t.append(tb)
    return z, np.array(t), np.array(lnp)


class _Table:
    """The 10 m float32 tables of one atmosphere in SI, altitude measured above the pad (agl)."""

    def __init__(self, s, k, pad_node, pad_wind_factor, above_top, decay_scale_m):
        agl = np.asarray(s["height_agl"], float)
        row = lambda key: None if s.get(key) is None else np.asarray(s[key], float)[k]
        u, v, T, RH, p = (np.asarray(s[x], float)[k] for x in ("u", "v", "T", "RH", "p"))
        w = row("w") if row("w") is not None and np.isfinite(row("w")).all() else np.zeros_like(u)
        z = agl
        if pad_node and all(s.get(x) is not None for x in ("t2m", "sp", "rh2m")) and np.isfinite([float(np.asarray(s[x])[k]) for x in ("t2m", "sp", "rh2m")]).all():
            f = float(pad_wind_factor)
            z = np.concatenate([[0.0], agl])
            u, v, w = np.concatenate([[u[0] * f], u]), np.concatenate([[v[0] * f], v]), np.concatenate([[0.0], w])
            T = np.concatenate([[float(np.asarray(s["t2m"])[k])], T])
            p = np.concatenate([[float(np.asarray(s["sp"])[k])], p])
            RH = np.concatenate([[float(np.asarray(s["rh2m"])[k])], RH])
        self.z0, self.top = float(z[0]), float(z[-1])
        n = int(round((self.top - self.z0) / GRID_M)) + 1
        g = self.z0 + GRID_M * np.arange(n)
        self.g_top = g[-1]
        lerp = lambda y: np.interp(g, z, y).astype(np.float32)
        lnp = np.interp(g, z, np.log(p))
        t_g, rh_g = np.interp(g, z, T), np.clip(np.interp(g, z, RH), 0, 100)
        self.u, self.v, self.w, self.T, self.lnp = lerp(u), lerp(v), lerp(w), t_g.astype(np.float32), lnp.astype(np.float32)
        q = mixing_q(t_g, rh_g, np.exp(lnp))
        tv = t_g * (1 + (RV / RD - 1) * q)
        self.rho = (np.exp(lnp) / (RD * tv)).astype(np.float32)
        self.a = np.sqrt(GAMMA * RD * tv).astype(np.float32)
        self.top_vals = (float(u[-1]), float(v[-1]), float(w[-1]), float(T[-1]), float(p[-1]))
        self.policy, self.scale = above_top, decay_scale_m
        self._tail = None
        self._lists = None

    def lists(self):
        """Plain Python lists of the tables, built on the first scalar lookup (scalar access is several times faster on lists than on numpy arrays)."""
        if self._lists is None:
            self._lists = tuple(a.tolist() for a in (self.u, self.v, self.w, self.T, self.lnp, self.rho, self.a))
        return self._lists

    def tail(self, elev):
        if self._tail is None:
            zt, tt, lp = _tail(self.top + elev, self.top_vals[3], self.top_vals[4])
            self._tail = (zt - elev, tt, lp)
        return self._tail


class Atmosphere:
    """Row k of a sample set as wind and air lookups (see the module docstring)."""

    def __init__(self, samples, k, *, frame="une", units="si", reference="asl", direction="to", above_top="hold", pad_node=True, pad_wind_factor=0.72,
                 decay_scale_m=5000.0, elevation_m=None, launch_time=None, index=None):
        if frame not in _FRAMES:
            raise ValueError(f"frame must be one of {sorted(_FRAMES)}, not {frame!r}")
        if units not in ("si", "us"):
            raise ValueError("units must be 'si' or 'us'")
        if reference not in ("asl", "agl"):
            raise ValueError("reference must be 'asl' or 'agl'")
        if direction not in ("to", "from"):
            raise ValueError("direction must be 'to' or 'from'")
        if above_top not in _POLICIES:
            raise ValueError(f"above_top must be one of {_POLICIES}, not {above_top!r}")
        s = normalise_samples(samples, elevation_m)
        self.elevation_m = s["elevation_m"]
        self.index, self.launch_time = (k if index is None else index), launch_time
        self.frame, self.units, self.reference, self.direction, self.above_top = frame, units, reference, direction, above_top
        self._t = _Table(s, k, pad_node, pad_wind_factor, above_top, decay_scale_m)
        a, b, c, signs = _FRAMES[frame]
        self._perm, self._sign = (a, b, c), np.asarray(signs, np.float32) * (-1.0 if direction == "from" else 1.0)
        self._ft = units == "us"
        self._n = len(self._t.u)
        self._sgn = tuple(float(x) for x in self._sign)

    # ---- coordinate handling
    def _agl(self, alt):
        z = np.asarray(alt, np.float64) * (FT if self._ft else 1.0)
        return z - self.elevation_m if self.reference == "asl" else z

    def _check_top(self, z):
        if self.above_top == "raise" and np.any(z > self._t.g_top + 1e-6):
            raise AboveTopError(f"altitude above the top of the profile ({self._t.g_top + (self.elevation_m if self.reference == 'asl' else 0):.0f} m); set above_top to 'hold', 'decay' or 'climatology'")

    def _pos(self, z):
        t = self._t
        return np.clip((z - t.z0) / GRID_M, 0.0, len(t.u) - 1.0)

    def _interp(self, arr, pos):
        i0 = np.minimum(pos.astype(np.int64), len(arr) - 2) if len(arr) > 1 else np.zeros_like(pos, np.int64)
        f = (pos - i0).astype(np.float32)
        return arr[i0] * (1.0 - f) + arr[np.minimum(i0 + 1, len(arr) - 1)] * f

    # ---- scalar fast path (S2): pure Python, no numpy calls; valid from the pad up to the top of the profile
    def _fast(self, alt):
        """-> (up, east, north, T, p, rho, a) in SI above-the-pad coordinates, or None when the altitude is above the top (the caller then uses the numpy path)."""
        t = self._t
        z = alt * (FT if self._ft else 1.0)
        if self.reference == "asl":
            z -= self.elevation_m
        if z > t.g_top:
            return None
        pos = (z - t.z0) * 0.1
        if pos <= 0.0:
            i, f = 0, 0.0
        else:
            i = int(pos)
            f = pos - i
            if i >= self._n - 1:
                i, f = self._n - 2, 1.0
        L = t.lists()
        g = lambda arr: arr[i] + (arr[i + 1] - arr[i]) * f
        return g(L[2]), g(L[0]), g(L[1]), g(L[3]), math.exp(g(L[4])), g(L[5]), g(L[6])

    # ---- wind
    def wind_many(self, alts):
        z = self._agl(alts)
        self._check_top(z)
        pos = self._pos(z)
        t = self._t
        up, e, n = self._interp(t.w, pos), self._interp(t.u, pos), self._interp(t.v, pos)
        vec = np.stack([up, e, n], -1)
        if self.above_top == "decay":
            over = np.maximum(z - t.g_top, 0.0)
            vec = vec * np.exp(-over / t.scale).astype(np.float32)[..., None]
        out = vec[..., list(self._perm)] * self._sign
        return out / np.float32(FT) if self._ft else out

    def wind(self, alt):
        if np.ndim(alt) == 0 and self.above_top != "decay":
            r = self._fast(float(alt))
            if r is not None:
                vec = (r[0], r[1], r[2])
                k = 1.0 / FT if self._ft else 1.0
                a, b, c = self._perm
                return np.array((vec[a] * self._sgn[0] * k, vec[b] * self._sgn[1] * k, vec[c] * self._sgn[2] * k))
        return self.wind_many(np.asarray(alt, np.float64))

    # ---- air
    def air_many(self, alts):
        z = self._agl(alts)
        self._check_top(z)
        t = self._t
        pos = self._pos(z)
        T, lnp = self._interp(t.T, pos).astype(np.float64), self._interp(t.lnp, pos).astype(np.float64)
        rho, a = self._interp(t.rho, pos).astype(np.float64), self._interp(t.a, pos).astype(np.float64)
        above = z > t.g_top
        if np.any(above):
            zt, tt, lp = t.tail(self.elevation_m)
            zc = np.minimum(z, zt[-1])
            T2, lnp2 = np.interp(zc, zt, tt), np.interp(zc, zt, lp)
            tv = T2                                                    # dry air up there
            T, lnp = np.where(above, T2, T), np.where(above, lnp2, lnp)
            rho = np.where(above, np.exp(lnp2) / (RD * tv), rho)
            a = np.where(above, np.sqrt(GAMMA * RD * tv), a)
        p = np.exp(lnp)
        if self._ft:
            return np.stack([(T - 273.15) * 1.8 + 32.0, p / INHG, rho / SLUG_FT3, a / FT], -1)
        return np.stack([T, p, rho, a], -1)

    def air(self, alt):
        if np.ndim(alt) == 0:
            r = self._fast(float(alt))
            if r is not None:
                T, p, rho, a = r[3], r[4], r[5], r[6]
                if self._ft:
                    return ((T - 273.15) * 1.8 + 32.0, p / INHG, rho / SLUG_FT3, a / FT)
                return (T, p, rho, a)
        return self.air_many(np.asarray(alt, np.float64))

    def conditions(self, alt):
        """Flight_sim's AtmosphereModel interface (SI only, altitude above sea level)."""
        z = float(alt) - self.elevation_m
        t = self._t
        if z <= t.g_top:
            pos = (z - t.z0) * 0.1
            if pos <= 0.0:
                i, f = 0, 0.0
            else:
                i = int(pos)
                f = pos - i
                if i >= self._n - 1:
                    i, f = self._n - 2, 1.0
            L = t.lists()
            return AtmosphereConditions(L[3][i] + (L[3][i + 1] - L[3][i]) * f, math.exp(L[4][i] + (L[4][i + 1] - L[4][i]) * f),
                                        L[5][i] + (L[5][i + 1] - L[5][i]) * f, L[6][i] + (L[6][i + 1] - L[6][i]) * f)
        saved = (self._ft, self.reference)
        self._ft, self.reference = False, "asl"
        try:
            T, p, rho, a = self.air_many(float(alt))
        finally:
            self._ft, self.reference = saved
        return AtmosphereConditions(float(T), float(p), float(rho), float(a))

    def velocity(self, alt):
        """Flight_sim's WindModel interface (SI, world frame up/east/north, altitude above sea level)."""
        z = float(alt) - self.elevation_m
        t = self._t
        if z <= t.g_top and self.above_top != "decay":
            pos = (z - t.z0) * 0.1
            if pos <= 0.0:
                i, f = 0, 0.0
            else:
                i = int(pos)
                f = pos - i
                if i >= self._n - 1:
                    i, f = self._n - 2, 1.0
            L = t.lists()
            return np.array((L[2][i] + (L[2][i + 1] - L[2][i]) * f, L[0][i] + (L[0][i + 1] - L[0][i]) * f, L[1][i] + (L[1][i + 1] - L[1][i]) * f))
        saved = (self._ft, self.reference, self._perm, self._sign)
        self._ft, self.reference, self._perm, self._sign = False, "asl", (0, 1, 2), np.ones(3, np.float32)
        try:
            return self.wind_many(float(alt)).astype(np.float64)
        finally:
            self._ft, self.reference, self._perm, self._sign = saved

    def anchor(self, launch_altitude_m, tolerance_m=10.0, on_mismatch="raise"):
        """Check (or, with on_mismatch="shift", adopt) the simulator's pad elevation (F10)."""
        if abs(launch_altitude_m - self.elevation_m) <= tolerance_m:
            return self
        if on_mismatch == "shift":
            self.elevation_m = float(launch_altitude_m)
            return self
        raise ValueError(f"launch altitude {launch_altitude_m:.1f} m differs from the atmosphere's site elevation {self.elevation_m:.1f} m by more than {tolerance_m} m; "
                         "give the pad elevation when you generate the atmosphere, or anchor(..., on_mismatch='shift')")

    def to_openrocket_csv(self, path, step_m=100.0):
        """Tabular atmosphere for OpenRocket (spec 4): altitude_m, temp_K, pressure_Pa, wind_speed_ms, wind_from_deg (heights above sea level)."""
        saved = (self._ft, self.reference, self._perm, self._sign)
        self._ft, self.reference, self._perm, self._sign = False, "asl", (0, 1, 2), np.ones(3, np.float32)
        try:
            top = self._t.g_top + self.elevation_m
            alts = np.arange(self.elevation_m, top + 0.1, step_m)
            T, p, _, _ = self.air_many(alts).T
            vec = self.wind_many(alts)
        finally:
            self._ft, self.reference, self._perm, self._sign = saved
        spd = np.hypot(vec[:, 1], vec[:, 2])
        frm = (np.degrees(np.arctan2(-vec[:, 1], -vec[:, 2])) + 360.0) % 360.0
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("altitude_m,temp_K,pressure_Pa,wind_speed_ms,wind_from_deg\n")
            for row in zip(alts, T, p, spd, frm):
                f.write("{:.1f},{:.2f},{:.1f},{:.2f},{:.1f}\n".format(*row))
        return path
