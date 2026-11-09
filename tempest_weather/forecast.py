"""Forecast mode (mode F in the plans): a forecast turned into a distribution of the 44-height profile. numpy only (copies of the conversions in tempest.profiles.to_heights
and tempest.forecast.modeF; tests/test_tool_forecast.py checks that both give the same numbers).

    fields = fields_from_openmeteo(doc, hour_index)                          # pressure-level fields of one hour from an Open-Meteo response
    prof   = forecast_profile(fields, z_sfc_m, bl)                           # dict u, v, T, RH (44,) + t2m, sp, rh2m, using the boundary-layer tables `bl`
    cond   = condition(prof, lat, lon, z_sfc_m, doy, lead_days, coarse)      # the network's input row
Valid where it was trained: 00 UTC starts of the IFS at leads of 1, 3, 5 and 7 days, valid near 17:00 local solar time (AUTOPILOT F-8a); the caller applies those limits.
"""
import numpy as np

from tempest_weather import _core

G0, R_EARTH = 9.80665, 6371000.0
EPS = 287.0597 / 461.5250
T0, TICE = 273.16, 250.16
LAPSE_BINS = np.array([0.0, 4.0, 7.0, 9.0])
HEIGHTS = _core.HEIGHTS
NH = _core.NH
LEVELS_SERVED = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]


def geometric_height(z):
    zh = z / G0
    return R_EARTH * zh / (R_EARTH - zh)


def magnus_rh(t, td):
    t, td = t - 273.15, td - 273.15
    return 100 * np.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))


def td_from_rh(t, rh):
    tc = t - 273.15
    rh = np.clip(rh, 1.0, 100.0) / 100.0
    g = np.log(rh) + 17.625 * tc / (243.04 + tc)
    return 243.04 * g / (17.625 - g) + 273.15


def liquid_rh(t, r):
    es_l = 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))
    es_i = 611.21 * np.exp(22.587 * (t - 273.16) / (t + 0.7))
    a = np.clip((t - 250.16) / 23.0, 0, 1) ** 2
    return r * (a * es_l + (1 - a) * es_i) / es_l


def rh_from_q(q, t, p_pa):
    """IFS mixed-phase relative humidity (%) from specific humidity (only used to test against the archive; the live feed gives RH directly)."""
    e = p_pa * q / (EPS + (1 - EPS) * q)
    alpha = np.where(t >= T0, 1.0, np.where(t <= TICE, 0.0, np.clip(((t - TICE) / (T0 - TICE)) ** 2, 0, 1)))
    es = alpha * 611.21 * np.exp(17.502 * (t - T0) / (t - 32.19)) + (1 - alpha) * 611.21 * np.exp(22.587 * (t - T0) / (t + 0.7))
    return np.clip(100 * e / es, 0, 100)


def interp_columns(h, x, targets, log_below=None):
    h = np.where(np.isfinite(h) & np.isfinite(x), h, np.inf)
    order = np.argsort(h, axis=-1)
    h, x = np.take_along_axis(h, order, -1), np.take_along_axis(x, order, -1)
    n_valid = np.isfinite(h).sum(-1, keepdims=True)
    out = np.full(h.shape[:-1] + (len(targets),), np.nan, np.float32)
    for j, t in enumerate(targets):
        k = (h <= t).sum(-1, keepdims=True) - 1
        ok = (k >= 0) & (k + 1 < n_valid)
        k0, k1 = np.clip(k, 0, h.shape[-1] - 2), np.clip(k + 1, 1, h.shape[-1] - 1)
        h0, h1 = np.take_along_axis(h, k0, -1), np.take_along_axis(h, k1, -1)
        x0, x1 = np.take_along_axis(x, k0, -1), np.take_along_axis(x, k1, -1)
        with np.errstate(invalid="ignore", divide="ignore"):
            if log_below is not None and t < log_below:
                w = (np.log(t) - np.log(h0)) / (np.log(h1) - np.log(h0))
            else:
                w = (t - h0) / (h1 - h0)
        exact = (h0 == t) & (k >= 0)
        val = np.where(exact, x0, x0 + w * (x1 - x0))
        out[..., j] = np.where(ok | exact, val, np.nan)[..., 0]
    return out


def profiles_from_levels(z, u, v, t, r, z_sfc, u10, v10, u100, v100, t2m, d2m):
    """Pressure-level arrays (..., L) and surface fields -> dict of (..., 44) profiles (levels at or below the ground dropped; wind below 100 m from the 10 / 100 m anchors)."""
    agl = geometric_height(z) - geometric_height(z_sfc)[..., None]
    agl = np.where(agl > 0, agl, np.nan)
    agl_w = np.where(agl > 100, agl, np.nan)
    shape = agl.shape[:-1] + (1,)
    hw = np.concatenate([np.full(shape, 10.0), np.full(shape, 100.0), agl_w], -1)
    ht = np.concatenate([np.full(shape, 2.0), agl], -1)
    rh2m = np.clip(magnus_rh(t2m, d2m), 0, 100)
    return dict(u=interp_columns(hw, np.concatenate([u10[..., None], u100[..., None], u], -1), HEIGHTS, 100),
                v=interp_columns(hw, np.concatenate([v10[..., None], v100[..., None], v], -1), HEIGHTS, 100),
                T=interp_columns(ht, np.concatenate([t2m[..., None], t], -1), HEIGHTS),
                RH=interp_columns(ht, np.concatenate([rh2m[..., None], np.clip(liquid_rh(t, r), 0, 100)], -1), HEIGHTS)), rh2m


def boundary_inputs(t, r, z, t2m, z_sfc):
    """Lapse rate (K/km) from 2 m to the lowest level above ground and that level's dewpoint depression (K). Arrays (n, L) / (n,); z and z_sfc geopotential."""
    agl = z / G0 - (z_sfc / G0)[:, None]
    low = np.where(agl > 0, agl, np.inf).argmin(1)
    ar = np.arange(len(t))
    t_low, agl_low = t[ar, low], agl[ar, low]
    return (t2m - t_low) / np.maximum(agl_low / 1000.0, 0.05), t_low - td_from_rh(t_low, np.clip(r[ar, low], 1.0, 100.0))


def forecast_profile(fields, z_sfc_m, bl):
    """fields: dict t (K), u, v (m/s), r (% as the IFS defines it), z (m2/s2), all (L,), and t2m (K), u10, v10 (m/s), sp (Pa); z_sfc_m: surface height of the grid point (m).
    bl: dict ratio (5,), dpd_a, dpd_b (the tables fitted with the network). -> dict u, v, T, RH (44,), t2m, sp, rh2m."""
    a = lambda k: np.atleast_2d(np.asarray(fields[k], float))
    t, u, v, r, z = a("t"), a("u"), a("v"), a("r"), a("z")
    t2m, u10, v10 = (np.atleast_1d(np.asarray(fields[k], float)) for k in ("t2m", "u10", "v10"))
    zs = np.atleast_1d(np.asarray(z_sfc_m, float)) * G0
    lapse, dpd_low = boundary_inputs(t, r, z, t2m, zs)
    ratio = np.asarray(bl["ratio"])[np.digitize(lapse, LAPSE_BINS)]
    d2m = t2m - np.clip(float(bl["dpd_a"]) + float(bl["dpd_b"]) * dpd_low, 0.0, 60.0)
    prof, rh2m = profiles_from_levels(z, u, v, t, r, zs, u10, v10, ratio * u10, ratio * v10, t2m, d2m)
    out = {k: x[0] for k, x in prof.items()}
    out.update(t2m=float(t2m[0]), sp=float(np.asarray(fields["sp"]).ravel()[0]), rh2m=float(rh2m[0]))
    return out


def flat(prof):
    return np.concatenate([prof["u"], prof["v"], prof["T"], prof["RH"]]).astype(np.float32)


def condition(prof, lat, lon, z_sfc_m, doy, lead_days, coarse=4):
    """The network input row, as tempest.forecast.modeF.cond_matrix: lat, lon, z_sfc / 1e4, doy harmonics, lead / 7, and every `coarse`-th height of u, v, T, RH."""
    a = 2 * np.pi * doy / 365.25
    head = [lat, lon, z_sfc_m / 1e4, np.sin(a), np.cos(a), lead_days / 7.0]
    body = np.concatenate([prof[k][::coarse] for k in ("u", "v", "T", "RH")])
    return np.concatenate([head, body]).astype(np.float32)


def fields_from_openmeteo(doc, i):
    """Open-Meteo hourly response (pressure-level variables for LEVELS_SERVED, wind in m/s, temperatures in C, geopotential height in m) -> the `fields` dict of hour index i."""
    h = doc["hourly"]
    lev = LEVELS_SERVED
    g = lambda base: np.array([h[f"{base}_{p}hPa"][i] for p in lev], float)
    ws, wd = g("wind_speed"), np.radians(g("wind_direction"))
    ws10, wd10 = float(h["wind_speed_10m"][i]), np.radians(float(h["wind_direction_10m"][i]))
    return dict(level_hpa=np.array(lev, float), t=g("temperature") + 273.15, r=g("relative_humidity"), z=g("geopotential_height") * G0,
                u=-ws * np.sin(wd), v=-ws * np.cos(wd), t2m=float(h["temperature_2m"][i]) + 273.15, u10=-ws10 * np.sin(wd10), v10=-ws10 * np.cos(wd10),
                sp=float(h["surface_pressure"][i]) * 100.0)
