"""Open-Meteo client with recorded fixtures: caching, staleness, graceful degradation, error handling. No network."""
import json

import pytest

from tempest.ingest import openmeteo as om

DOC = {"hourly": {"time": ["2026-11-05T00:00"], "temperature_2m": [10.0]}, "elevation": 871.0}


def _setup(monkeypatch, tmp_path, responses):
    calls = []

    def fake(url, **_):
        calls.append(url)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return json.dumps(r).encode()
    monkeypatch.setattr(om, "fetcher", fake)
    return calls, str(tmp_path)


def test_cache_hit_avoids_second_request(monkeypatch, tmp_path):
    calls, d = _setup(monkeypatch, tmp_path, [DOC])
    a = om.ensemble(31.94, -102.19, "ecmwf_ifs025", ["temperature_2m"], 3, max_age_hours=None, cache_dir=d)
    b = om.ensemble(31.94, -102.19, "ecmwf_ifs025", ["temperature_2m"], 3, max_age_hours=None, cache_dir=d)
    assert a == b == DOC and len(calls) == 1
    assert "models=ecmwf_ifs025" in calls[0] and "hourly=temperature_2m" in calls[0] and "wind_speed_unit=ms" in calls[0]


def test_stale_entry_is_refreshed_and_failure_degrades_to_the_stale_copy(monkeypatch, tmp_path):
    calls, d = _setup(monkeypatch, tmp_path, [DOC, RuntimeError("down")])
    om.ensemble(31.94, -102.19, "m", ["t"], 3, max_age_hours=None, cache_dir=d)           # stored
    out = om.ensemble(31.94, -102.19, "m", ["t"], 3, max_age_hours=0, cache_dir=d)         # stale at once -> request fails -> stale copy
    assert out["_stale"] is True and len(calls) == 2


def test_failure_without_cache_raises_and_api_errors_are_not_cached(monkeypatch, tmp_path):
    calls, d = _setup(monkeypatch, tmp_path, [RuntimeError("down"), {"error": True, "reason": "bad"}])
    with pytest.raises(RuntimeError):
        om.seasonal(31.94, -102.19, ["temperature_2m_mean"], cache_dir=d)
    with pytest.raises(RuntimeError, match="bad"):
        om.seasonal(31.94, -102.19, ["temperature_2m_mean"], cache_dir=d)
    assert not list(tmp_path.glob("*.json"))


def test_elevation_parses(monkeypatch, tmp_path):
    calls, d = _setup(monkeypatch, tmp_path, [{"elevation": [1400.0]}])
    assert om.elevation(32.99, -106.97, cache_dir=d) == 1400.0
