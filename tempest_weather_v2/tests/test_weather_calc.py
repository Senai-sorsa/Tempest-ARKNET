"""Launch-site physics: altimeter setting round trip, density altitude, dew point, drift-equivalent wind, shear / jet, declination against known values."""
import numpy as np
import pytest

from tempest_weather_v2 import weather_calc as W


def test_altimeter_setting_round_trips_and_matches_the_standard_atmosphere():
    for h in (0.0, 300.0, 1400.6, 2500.0, 4000.0):
        p_isa = 1013.25 * (1 - 0.0065 * h / 288.15) ** 5.25588            # a standard day: altimeter setting must be 1013.25 hPa
        a = W.altimeter_setting_hpa(p_isa, h)
        assert abs(a - 1013.25) < 0.5                                       # the NWS formula has a 0.3 hPa offset built in (a standard day reads about 1012.9)
    p = np.array([850.0, 859.5, 870.0])
    a = W.altimeter_setting_hpa(p, 1400.6)
    assert np.allclose(W.station_pressure_hpa(a, 1400.6), p, atol=0.01)       # acceptance test of spec 1.1: round trip within 0.01 hPa
    assert 29.5 < a[1] * 0.02953 < 30.5                                      # inHg is a plausible altimeter setting


def test_mslp_is_higher_for_a_colder_column_and_density_altitude_inverts_the_standard_density():
    assert W.mslp_hpa(860.0, 250.0, 1400.0) > W.mslp_hpa(860.0, 310.0, 1400.0)
    for h in (0.0, 1400.0, 3000.0, 8000.0):
        T = 288.15 - 0.0065 * h
        rho = 101325 * (T / 288.15) ** 5.25588 / (287.05287 * T)
        assert abs(W.density_altitude_m(rho) - h) < 2.0
    assert W.density_altitude_m(1.0) > 1400.0                                # a hot day at altitude: density altitude above the elevation


def test_dew_point_and_directions():
    assert abs(W.dew_point_k(300.0, 100.0) - 300.0) < 1e-6
    assert abs(W.dew_point_k(303.15, 50.0) - (273.15 + 18.4)) < 0.3         # 30 C at 50 % RH: dew point about 18.4 C
    assert W.wind_from_deg(0.0, -5.0) == pytest.approx(0.0)                  # wind blowing toward the south comes from the north
    assert W.wind_from_deg(-5.0, 0.0) == pytest.approx(90.0)                 # blowing west = from the east
    assert W.wind_from_deg(5.0, 0.0) == pytest.approx(270.0)
    assert W.cardinal(245) == "WSW" and W.cardinal(0) == "N" and W.cardinal(359) == "N"


def test_drift_wind_weights_the_descent_and_cancels_turning_winds():
    z = np.arange(0.0, 18001.0, 100.0)
    u = np.full((1, len(z)), 6.0)
    v = np.zeros((1, len(z)))
    spd, frm, um, vm = W.drift_wind(u, v, z)
    assert spd[0] == pytest.approx(6.0, abs=1e-6) and frm[0] == pytest.approx(270.0)       # constant westerly... blowing east, from the west
    # wind only below the main deployment height counts much more than the same wind in the drogue phase (slow descent = long time)
    low = np.where(z < 300.0, 10.0, 0.0)[None]
    high = np.where((z > 2000.0) & (z < 2300.0), 10.0, 0.0)[None]
    assert W.drift_wind(low, v, z)[0][0] > 3 * W.drift_wind(high, v, z)[0][0]
    # a wind that turns through 180 degrees with height nearly cancels (vector mean), unlike a scalar mean of speeds
    ut = np.where(z < 1500.0, 8.0, -8.0)[None]
    assert W.drift_wind(ut, v, z)[0][0] < 8.0 * 0.9


def test_shear_and_jet_diagnostics():
    z = np.array([10.0, 100.0, 1000.0, 5000.0, 9000.0, 12000.0, 18000.0])
    u = np.array([[1.9, 2.0, 5.0, 12.0, 30.0, 60.0, 20.0]])
    v = np.zeros_like(u)
    s, h = W.max_shear(u, v, z)
    assert s[0] == pytest.approx(30.0 / 3000.0) and h[0] == pytest.approx(10500.0)          # 30 m/s over 3 km between 9 and 12 km
    jet, hj = W.upper_wind_max(u, v, z)
    assert jet[0] == 60.0 and hj[0] == 12000.0


@pytest.mark.parametrize("name,lat,lon,expect", [("Spaceport America", 32.99, -106.97, 7.9), ("Midland TX", 31.94, -102.19, 5.7), ("Boston", 42.36, -71.06, -14.4),
                                                  ("Seattle", 47.6, -122.3, 15.0), ("London", 51.5, -0.1, 1.0), ("Sydney", -33.9, 151.2, 12.7), ("Anchorage", 61.2, -149.9, 14.5)])
def test_declination_against_known_values_within_a_few_degrees(name, lat, lon, expect):
    assert abs(W.declination_deg(lat, lon, 2026.5) - expect) < 3.0, name
