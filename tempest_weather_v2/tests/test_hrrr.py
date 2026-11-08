"""C3: HRRR 10 m wind anchor (offline fake of the Open-Meteo reply)."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tempest_weather_v2 import Launch, hrrr as H

NOW = datetime(2027, 6, 16, 18, 0, tzinfo=timezone.utc)


def fake_for(speed, deg, key="2027-06-16T16:00"):
    def f(url):
        assert "ncep_hrrr_conus" in url and "wind_speed_10m" in url
        return {"hourly": {"time": [key], "wind_speed_10m": [speed], "wind_direction_10m": [deg]}}
    return f


def test_fetch_wind_components_and_endpoints():
    u, v, note = H.fetch_wind(32.99, -106.97, datetime(2027, 6, 16, 16, 20, tzinfo=timezone.utc), now=NOW, fetch=fake_for(8.0, 270.0))
    assert u == pytest.approx(8.0, abs=1e-6) and v == pytest.approx(0.0, abs=1e-6) and "archive" not in note and "live" in note   # within 2 days of now: live run
    old = datetime(2027, 6, 1, 16, 0, tzinfo=timezone.utc)
    seen = []
    H.fetch_wind(32.99, -106.97, old, now=NOW, fetch=lambda url: seen.append(url) or fake_for(3.0, 180.0, "2027-06-01T16:00")(url))
    assert "historical-forecast-api" in seen[0]
    with pytest.raises(LookupError, match="two days"):
        H.fetch_wind(32.99, -106.97, NOW + timedelta(days=5), now=NOW, fetch=fake_for(1, 1))
    with pytest.raises(LookupError, match="no value"):
        H.fetch_wind(32.99, -106.97, datetime(2027, 6, 16, 17, 0, tzinfo=timezone.utc), now=NOW, fetch=fake_for(1, 1))


def test_observe_hrrr_moves_ground_wind_median_and_shrinks_spread_only_near_the_ground():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=600, units="si", seed=3)            # 10:00 MDT = 16:00 UTC
    A = L.observe_hrrr(fetch=fake_for(8.0, 270.0), now=NOW)
    base, new = L.atmospheres(600), A.atmospheres(600)
    s0, s1 = L._ensure_pool()["samples"], A._ensure_pool()["samples"]
    assert np.median(s1["u"][:, 0]) == pytest.approx(8.0, abs=0.05) and np.median(s1["v"][:, 0]) == pytest.approx(0.0, abs=0.05)
    assert s1["u"][:, 0].std() == pytest.approx(0.8 * s0["u"][:, 0].std(), rel=0.02)
    assert np.allclose(s1["u"][:, -1], s0["u"][:, -1]) and np.allclose(s1["T"], s0["T"])           # high levels and temperature untouched
    assert "ground-wind-anchored-to-HRRR" in A.weather(all=True).flags and "HRRR" in A.trust and "HRRR" not in L.trust
    assert A.with_(units="us")._hrrr == A._hrrr                                                      # survives with_
    with pytest.raises(ValueError):
        Launch("spaceport_america", ("2027-06-16 08:00", "2027-06-16 12:00"), mode="ai", n=64).observe_hrrr(fetch=fake_for(1, 1), now=NOW)
