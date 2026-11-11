"""A3-fix B (ASK_LATER 23): a neighbour report uses the distance gain as rho in the speed-space step; an own-station report is unchanged."""
import numpy as np
import pytest

from tempest_weather_v2 import launch as LM


def _speed(L):
    s = L._ensure_pool()["samples"]
    return np.hypot(np.asarray(s["u"])[:, 0], np.asarray(s["v"])[:, 0])


@pytest.fixture
def base():
    from tempest_weather_v2 import obs as O
    lat, lon, elev = O.STATIONS["TCS"]
    try:
        L = LM.Launch(lat, lon, "2023-05-10 20:00", tz="UTC", n=200, seed=7, units="si", elevation=elev, mode="ai")
        L._ensure_pool()
    except Exception as e:   # noqa: BLE001  (model assets or the ERA5 store not on this machine)
        pytest.skip(f"tool not servable here: {e!r}")
    return L


def _obs(L, km):
    return _speed(L.observe(wind_10m="14 m/s", wind_from_deg=240.0, age_hours=1.0, distance_km=km, elevation_diff_m=0.0, source="X"))


def test_own_station_unchanged_and_neighbour_trusted_less(base, monkeypatch):
    prior = np.median(_speed(base))
    monkeypatch.setattr(LM, "NEIGHBOUR_RHO_FROM_GAIN", False)
    own_off, far_off = _obs(base, 0.0), _obs(base, 150.0)
    monkeypatch.setattr(LM, "NEIGHBOUR_RHO_FROM_GAIN", True)
    own_on, far_on = _obs(base, 0.0), _obs(base, 150.0)
    assert np.array_equal(own_off, own_on)
    # a report 150 km away pulls the median toward 14 m/s less than the age-only rho did, and the spread stays wider
    assert abs(np.median(far_on) - prior) < abs(np.median(far_off) - prior)
    assert np.std(far_on) > np.std(far_off)
