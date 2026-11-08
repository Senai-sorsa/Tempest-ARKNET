"""Readers: exact values at grid heights, consistency between them, the 10 m / above-top rules, the anchor check, the same sample index everywhere."""
import numpy as np
import pytest

from tempest.output import coupled
from tempest.profiles.to_heights import HEIGHTS
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind


def _samples(n=6, elev=1400.0, seed=0):
    rng = np.random.default_rng(seed)
    nh = len(HEIGHTS)
    T = np.linspace(305, 215, nh) + rng.normal(0, 1, (n, nh))
    u = rng.normal(4, 3, (n, 1)) + np.linspace(0, 20, nh)
    ph = np.concatenate([u, rng.normal(0, 2, (n, nh)), T, np.clip(rng.normal(30, 10, (n, nh)), 1, 99), np.stack([T[:, 0] + 1, np.full(n, 86000.0), np.full(n, 30.0)], 1)], 1)
    a, _ = coupled.build(ph, elev, np.zeros((n, 5)))
    return a


def test_values_at_grid_heights_are_exact_and_between_them_consistent():
    s = _samples()
    atm, wind = TempestAtmosphere(s, 3), TempestWind(s, 3)
    for j in (0, 10, 30, 43):
        z = float(s["height_asl"][j])
        c = atm.conditions(z)
        assert np.isclose(c.temperature, s["T"][3, j]) and np.isclose(c.pressure, s["p"][3, j], rtol=1e-6)
        assert np.isclose(c.air_density, s["rho"][3, j], rtol=2e-3) and np.isclose(c.speed_of_sound, s["a"][3, j], rtol=2e-3)
        v = wind.velocity(z)
        assert np.isclose(v[1], s["u"][3, j]) and np.isclose(v[2], s["v"][3, j])
    z = float(0.5 * (s["height_asl"][20] + s["height_asl"][21]))
    c = atm.conditions(z)
    assert np.isclose(c.air_density * 287.05 * c.temperature, c.pressure, rtol=0.01)          # ideal gas holds between heights
    assert np.isclose(c.speed_of_sound, np.sqrt(1.4 * 287.05 * c.temperature), rtol=0.01)


def test_below_first_and_above_top_rules():
    s = _samples()
    atm, wind = TempestAtmosphere(s, 0, pad_node=False), TempestWind(s, 0, pad_node=False)      # pad_node=False = the original rule; IL-131 (default) adds a pad node with the surface state
    assert np.allclose(wind.velocity(1400.0), wind.velocity(float(s["height_asl"][0])))         # at the ground: the 10 m value
    top = float(s["height_asl"][-1])
    assert np.allclose(wind.velocity(top + 5000), wind.velocity(top))                            # held above the top
    c_top, c_up = atm.conditions(top), atm.conditions(top + 100)
    assert abs(c_up.temperature - c_top.temperature) < 1.0 and c_up.pressure < c_top.pressure    # no jump, falling pressure
    assert atm.conditions(60000.0).pressure < atm.conditions(30000.0).pressure < c_top.pressure


def test_anchor_and_sample_index():
    s = _samples(elev=1400.0)
    atm = TempestAtmosphere(s, 1)
    atm.anchor(1405.0)
    with pytest.raises(ValueError, match="site elevation"):
        atm.anchor(1430.0)
    a, w = TempestAtmosphere(s, 2), TempestWind(s, 2)
    assert a.s.k == w.s.k == 2 and np.isclose(a.conditions(float(s["height_asl"][5])).temperature, s["T"][2, 5])
