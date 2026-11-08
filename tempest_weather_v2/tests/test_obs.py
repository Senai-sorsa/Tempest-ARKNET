"""Observation ingestion: nearest stations, age / distance weights, IEM parsing (offline fake), observe with weights, observe_latest end to end."""
from datetime import datetime, timezone

import pytest

from tempest_weather_v2 import Launch, obs as O


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))


CSV = (b"station,valid,metar\n"
       b"TCS,2027-06-16 13:53,KTCS 161353Z 20004KT 10SM CLR 22/10 A3015\n"
       b"TCS,2027-06-16 14:53,KTCS 161453Z 22006KT 10SM CLR 25/09 A3016 RMK AO2\n"
       b"TCS,2027-06-16 15:53,KTCS 161553Z 24012KT 10SM CLR 28/08 A3016\n")     # the last one is after the launch time


def fake(url):
    assert "data=metar" in url and "format=onlycomma" in url
    return CSV if "station=TCS" in url else b"station,valid,metar\n"           # only TCS has reports in this fake world


def test_nearest_stations_and_weights():
    near = O.nearest(32.94, -106.91)
    assert near[0][0] == "TCS" and 40 < near[0][1] < 60 and len(near) == 3
    assert O.nearest(32.94, -106.91, max_km=10) == []
    g1, g3, g6 = O.persistence_gain(1.0), O.persistence_gain(3.0), O.persistence_gain(6.0)
    assert 0.80 <= g1 <= 0.88 and 0.60 <= g3 <= 0.66 and g6 < 0.4                      # GW-1: 0.80-0.88 at 1 h, 0.63-0.66 at 3 h
    assert O.persistence_gain(0.0) == 1.0 and O.representativeness_gain(0.0, 0.0) == 1.0
    assert O.representativeness_gain(100.0, 80.0) < O.representativeness_gain(10.0, 80.0) < 1.0
    assert O.effective_gain(0, 0, 0) == 1.0 and O.effective_gain(100, 1000, 3000) == 0.02            # floor
    assert O.observation_sigma(2.0, 1.0) < 0.01 and O.observation_sigma(2.0, 0.5) == pytest.approx(2.0) and O.observation_sigma(2.0, 0.2) > 2.0 * 1.9


def test_latest_report_picks_the_newest_not_after_the_launch_time():
    when = datetime(2027, 6, 16, 15, 17, tzinfo=timezone.utc)
    t, m = O.latest_report("TCS", when, fetch=fake)
    assert t == datetime(2027, 6, 16, 14, 53, tzinfo=timezone.utc) and m.wind_from_deg == 220 and m.temp_c == 25.0
    assert O.latest_report("TCS", datetime(2027, 6, 16, 12, 0, tzinfo=timezone.utc), fetch=fake) == (None, None)
    assert O.latest_report("TCS", when, fetch=lambda u: b"station,valid,metar\n") == (None, None)


def test_observe_with_weights_moves_the_median_less_than_an_exact_pin():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=400, units="si")
    prior = L.weather(all=True).wind_10m
    pin = L.observe(wind_10m="9 m/s", wind_from_deg=240).weather(all=True).wind_10m
    old = L.observe(wind_10m="9 m/s", wind_from_deg=240, age_hours=3.0).weather(all=True).wind_10m
    far = L.observe(wind_10m="9 m/s", wind_from_deg=240, age_hours=3.0, distance_km=120, elevation_diff_m=80).weather(all=True).wind_10m
    assert abs(pin - 9.0) < 0.5
    assert abs(old - prior) > 0.2 and abs(pin - prior) > abs(old - prior) > abs(far - prior) - 1e-9     # exact pin > 3 h old > 3 h old and far away
    assert abs(far - prior) < abs(old - prior)


def test_observe_latest_end_to_end_and_errors():
    L = Launch("spaceport_america", "2027-06-16 09:17", mode="ai", n=300, units="si")          # 09:17 MDT = 15:17 UTC
    c = L.observe_latest(fetch=fake)
    assert "METAR TCS 16 14:53Z" in c.trust and "km from the pad" in c.trust and "h old" in c.trust and "weights assumed" in c.trust
    r = c.weather(all=True)
    assert "observation-from-METAR TCS 16 14:53Z" in r.flags
    assert 0 < r.wind_10m < 12 and abs(r.temperature - 25.0) < 4.0                                # pulled towards 22 deg / 6 kt, not exactly pinned
    assert c._obs["_age_h"] == pytest.approx(24 / 60 + 0, abs=0.5)
    with pytest.raises(LookupError, match="no usable METAR"):
        L.observe_latest(fetch=lambda u: b"station,valid,metar\n")
    now = datetime(2027, 6, 16, 14, 0, tzinfo=timezone.utc)                                       # the real clock is before the 14:53 report: it cannot exist yet
    with pytest.raises(LookupError):
        L.observe_latest(fetch=fake, now=now.replace(hour=13, minute=0))
