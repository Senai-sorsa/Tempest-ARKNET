"""Ensemble -> 44 heights: a synthetic column is reproduced, underground levels are dropped, members stay separate."""
import numpy as np

from tempest.nearterm import ensemble as en
from tempest.profiles.to_heights import G0, HEIGHTS, R_EARTH


def _doc(members=3, hours=4, elev=1400.0, sp_hpa=860.0, ws_surface=4.0):
    """A column with temperature falling 6.5 K/km from 300 K at the ground, wind speed 4 m/s + 2 m/s per km from the west."""
    h = {"time": [f"2026-11-05T{i:02d}:00" for i in range(hours)]}

    def put(var, fn):
        for m in range(members):
            h[var if m == 0 else f"{var}_member{m:02d}"] = [fn(m)] * hours
    # geopotential height of each pressure level above sea level for this synthetic atmosphere (hypsometric, scale height 8 km)
    z_of_p = lambda p: 8000.0 * np.log(1013.25 / p)
    put("temperature_2m", lambda m: 300.0 - 273.15 + 0.2 * m)
    put("relative_humidity_2m", lambda m: 30.0)
    put("surface_pressure", lambda m: sp_hpa)
    put("wind_speed_10m", lambda m: ws_surface)
    put("wind_direction_10m", lambda m: 270.0)
    for p in en.LEVELS:
        z = z_of_p(p)
        agl = z - elev
        put(f"geopotential_height_{p}hPa", lambda m, z=z: z)
        put(f"temperature_{p}hPa", lambda m, agl=agl: 300.0 - 273.15 - 0.0065 * max(agl, 0) + 0.2 * m)
        put(f"relative_humidity_{p}hPa", lambda m: 40.0)
        put(f"wind_speed_{p}hPa", lambda m, agl=agl: 4.0 + 0.002 * max(agl, 0))
        put(f"wind_direction_{p}hPa", lambda m: 270.0)
    return {"hourly": h, "elevation": elev}


def test_shapes_wind_direction_and_members():
    prof = en.to_profiles(_doc())
    assert prof["u"].shape == (3, 4, 44) and prof["T"].shape == (3, 4, 44)
    # wind from the west (270 deg) blows toward the east: u > 0, v ~ 0
    ok = np.isfinite(prof["u"][0, 0])
    assert (prof["u"][0, 0][ok] > 0).all() and np.abs(prof["v"][0, 0][ok]).max() < 1e-6
    assert np.allclose(prof["T"][1, 0] - prof["T"][0, 0], 0.2, atol=1e-3, equal_nan=True)  # members keep their offsets


def test_temperature_follows_the_lapse_rate_above_ground():
    prof = en.to_profiles(_doc())
    T = prof["T"][0, 0]
    sel = (HEIGHTS >= 1000) & (HEIGHTS <= 5000)
    assert np.isfinite(T[sel]).all()
    assert np.allclose(T[sel], 300.0 - 0.0065 * HEIGHTS[sel], atol=0.6)  # interpolation error of a few tenths between levels


def test_underground_levels_are_dropped():
    doc = _doc(elev=1400.0, sp_hpa=860.0)
    # make the 1000 and 925 hPa values garbage (they are below the 860 hPa ground): the profile must not change
    clean = en.to_profiles(doc)
    for p in (1000, 925):
        for k in [k for k in doc["hourly"] if k.startswith(f"temperature_{p}hPa")]:
            doc["hourly"][k] = [99.0] * len(doc["hourly"][k])
    dirty = en.to_profiles(doc)
    assert np.allclose(clean["T"], dirty["T"], equal_nan=True)
