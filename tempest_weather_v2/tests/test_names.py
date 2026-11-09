"""Plain names, aliases, typo suggestions, quantity parsing and unit round trips."""
import pytest

from tempest_weather_v2 import names as N


def test_aliases_and_typo_suggestions():
    assert N.resolve_name("temperature") == "temperature" and N.resolve_name("t2m_c") == "temperature" and N.resolve_name("wind_speed@100") == "wind_10m"
    with pytest.raises(ValueError, match="did you mean wind_speed"):
        N.resolve_name("wind_sped")
    with pytest.raises(ValueError, match="unknown variable"):
        N.resolve_name("zzzzzz")


def test_parse_quantity_units_and_defaults():
    assert N.parse_quantity("4600 ft", "length") == pytest.approx(1402.08)
    assert N.parse_quantity("1.4 km", "length") == pytest.approx(1400.0)
    assert N.parse_quantity("14 mph", "speed") == pytest.approx(6.2586, abs=1e-3)
    assert N.parse_quantity("82 F", "temperature") == pytest.approx(27.7778, abs=1e-3)
    assert N.parse_quantity("300 K", "temperature") == pytest.approx(26.85)
    assert N.parse_quantity("1013 hPa", "pressure") == pytest.approx(1013.0)
    assert N.parse_quantity("29.92 inHg", "pressure") == pytest.approx(1013.2, abs=0.2)
    assert N.parse_quantity(1000, "length", "si") == 1000.0 and N.parse_quantity(1000, "length", "us") == pytest.approx(304.8)
    assert N.parse_quantity("240", "angle") == 240.0
    with pytest.raises(ValueError, match="cannot read"):
        N.parse_quantity("fast", "speed")
    with pytest.raises(ValueError, match="not a speed unit"):
        N.parse_quantity("5 ft", "speed")


def test_unit_round_trips_and_labels():
    for name, v in (("elevation", 1400.6), ("temperature", 31.0), ("pressure", 1013.25), ("wind_speed", 4.2), ("density", 1.05), ("max_wind_shear", 0.012)):
        assert N.from_units(name, N.to_units(name, v, "us"), "us") == pytest.approx(v)
        assert N.to_units(name, v, "si") == v
    assert N.to_units("temperature", 0.0) == 32.0 and N.to_units("pressure", 1013.25) == pytest.approx(29.92, abs=0.01)
    assert N.to_units("max_wind_shear", 0.01) == pytest.approx(0.01 * 304.8 / 0.44704)
    assert N.unit_label("temperature") == "°F" and N.unit_label("temperature", "si") == "°C" and N.unit_label("pressure") == "inHg"
    assert N.format_value("wind_from_deg", 245.4) == "245" and N.format_value("pressure", 1013.25, "us") == "29.92"
