"""AU-10: above_top="climatology" is a deliberate alias of "hold". AU-17: Launch.stale takes a naive time as UTC."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np

from tempest.output import coupled
from tempest.profiles.to_heights import HEIGHTS
from tempest_weather_v2.launch import Launch
from tempest_weather_v2.readers import Atmosphere


def _samples(n=4, elev=1400.0):
    rng = np.random.default_rng(0)
    nh = len(HEIGHTS)
    T = np.linspace(305, 215, nh) + rng.normal(0, 1, (n, nh))
    u = rng.normal(4, 3, (n, 1)) + np.linspace(0, 20, nh)
    ph = np.concatenate([u, rng.normal(0, 2, (n, nh)), T, np.clip(rng.normal(30, 10, (n, nh)), 1, 99),
                         np.stack([T[:, 0] + 1, np.full(n, 86000.0), np.full(n, 30.0)], 1)], 1)
    return coupled.build(ph, elev, np.zeros((n, 5)))[0]


def test_climatology_above_top_is_the_same_as_hold():
    s = _samples()
    top = float(s["height_asl"][-1])
    z = np.array([top - 500, top, top + 100, top + 5000, top + 30000])
    h, c = Atmosphere(s, 1, above_top="hold"), Atmosphere(s, 1, above_top="climatology")
    assert np.array_equal(h.air_many(z), c.air_many(z)) and np.array_equal(h.wind_many(z), c.wind_many(z))


def test_stale_takes_a_naive_now_as_utc():
    created = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
    obj = SimpleNamespace(created=created)
    assert Launch.stale(obj, datetime(2026, 11, 12, 13)) is False
    assert Launch.stale(obj, datetime(2026, 11, 12, 19)) is True
    assert Launch.stale(obj, created + timedelta(hours=7)) is True
