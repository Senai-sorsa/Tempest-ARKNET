"""METAR parsing and the observe_metar / --metar paths."""
import pytest

from tempest_weather_v2 import Launch, metar
from tempest_weather_v2.cli import main


def test_parse_common_groups():
    m = metar.parse("KTCS 241553Z 19002KT 10SM CLR 23/12 A3012 RMK AO2 SLP199")
    assert (m.station, m.day, m.hour, m.minute) == ("KTCS", 24, 15, 53)
    assert m.wind_from_deg == 190 and m.wind_speed_ms == pytest.approx(2 * 0.514444) and m.gust_ms is None
    assert m.temp_c == 23.0 and m.dew_c == 12.0 and m.altimeter_hpa == pytest.approx(30.12 * 33.8639, abs=0.01) and not m.variable
    g = metar.parse("METAR KMAF 011753Z 24015G25KT 10SM FEW080 M02/M05 Q1013")
    assert g.wind_from_deg == 240 and g.gust_ms == pytest.approx(25 * 0.514444) and g.temp_c == -2.0 and g.dew_c == -5.0 and g.altimeter_hpa == 1013.0
    mps = metar.parse("EDDF 121020Z 27004MPS 9999 18/10 Q1020")
    assert mps.wind_speed_ms == 4.0
    assert metar.parse("KXXX 011200Z 00000KT 10SM CLR 20/10 A2992").wind_speed_ms == 0.0


def test_variable_wind_and_unusable_text():
    m = metar.parse("KTCS 241553Z VRB03KT 10SM CLR 23/12 A3012")
    assert m.variable and m.wind_from_deg is None
    kw = m.observation_kwargs()
    assert "wind_10m" not in kw and kw["temperature"] == "23.00 C" and kw["altimeter"].endswith("hPa")       # the speed is dropped: no direction to condition with
    assert metar.parse("KTCS 241553Z 00000KT 10SM CLR 23/12 A3012").observation_kwargs()["wind_10m"] == "0 m/s"
    with pytest.raises(metar.MetarError, match="cannot find"):
        metar.parse("hello world")
    only_wind = metar.parse("KTCS 241553Z VRB03KT")
    assert only_wind.observation_kwargs() == {}


def test_observe_metar_conditions_a_launch():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=300, units="si")
    c = L.observe_metar("KTCS 161553Z 24010KT 10SM CLR 31/05 A3010")
    r = c.weather(all=True)
    assert abs(r.wind_10m - 10 * 0.514444) < 0.4 and abs(r.wind_10m_from_deg - 240) < 4 and abs(r.temperature - 31.0) < 0.5
    assert "conditioned on 3 measurements" in c.trust or "conditioned on 4 measurements" in c.trust
    with pytest.raises(ValueError, match="nothing usable"):
        L.observe_metar("KTCS 161553Z VRB03KT")


def test_cli_metar_option(capsys):
    rc = main(["weather", "spaceport_america", "2027-06-16 10:00", "--mode", "ai", "--n", "300", "--units", "si", "--metar", "KTCS 161553Z 24010KT 10SM CLR 31/05 A3010", "--all"])
    out = capsys.readouterr().out
    assert rc == 0 and "conditioned on" in out and "31." in out
