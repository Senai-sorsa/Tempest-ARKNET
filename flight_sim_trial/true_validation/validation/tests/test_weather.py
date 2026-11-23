"""The profile arithmetic and IGRA parsing; nothing here touches the network."""
import pytest

from fsval.weather import _igra_level, geometric_m, isa_altitude_m, join_profile, standard_pressure


def test_isa_altitude_inverts_the_standard_atmosphere():
    assert float(isa_altitude_m(101325.0)) == pytest.approx(0.0, abs=0.01)
    assert float(isa_altitude_m(standard_pressure(8000.0))) == pytest.approx(8000.0, abs=1.0)
    assert float(isa_altitude_m(5474.9)) == pytest.approx(20000.0, abs=15.0)


def test_geometric_exceeds_geopotential_as_the_earth_curves_away():
    assert geometric_m(0.0) == 0.0
    assert geometric_m(30000.0) == pytest.approx(30141.9, abs=0.5)


def test_join_drops_buried_levels_and_sorts_upward():
    levels = {"level_hpa": [100.0, 500.0, 1000.0], "geopotential": [160000.0, 55000.0, 500.0], "temperature": [210.0, 260.0, 300.0],
              "specific_humidity": [0.0, 0.001, 0.01], "u_component_of_wind": [20.0, 10.0, 1.0], "v_component_of_wind": [0.0, 5.0, 0.0]}
    surface = {"temperature_k": 310.0, "pressure_pa": 95000.0, "relative_humidity": 0.1, "east_m_s": 2.0, "north_m_s": -1.0}
    p = join_profile(levels, surface, 1000.0)
    assert p["pressure_pa"] == [95000.0, 50000.0, 10000.0]
    assert p["z_m"][0] == 1000.0 and p["z_m"] == sorted(p["z_m"])
    assert p["east_m_s"] == [2.0, 10.0, 20.0]
    assert p["virtual_temperature_k"][2] == 210.0
    assert 310.0 < p["virtual_temperature_k"][0] < 312.0


def test_igra_level_reads_the_fixed_columns_and_skips_missing():
    assert _igra_level("21 -9999  85000A 1560B  152B") == {"pressure_pa": 85000.0, "height_m": 1560.0, "temperature_k": pytest.approx(288.35)}
    assert _igra_level("21 -9999  85000A-9999   152B") is None
