"""Elevation lookup: service order, fallbacks, no-data handling, verification, cache and the offline DEM. No network: services are monkeypatched."""
import numpy as np
import pytest

from tempest_weather_v2 import elevation as E


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))
    monkeypatch.delenv("TEMPEST_DEM", raising=False)
    E._DEM_CACHE.clear()


def fake(values):
    """values: name -> metres or an Exception; returns the call log."""
    log = []
    for name, (fn, res, cover) in list(E.SERVICES.items()):
        def f(lat, lon, timeout, _n=name):
            log.append(_n)
            v = values.get(_n, RuntimeError("offline"))
            if isinstance(v, Exception):
                raise v
            return E._valid(v)
        E.SERVICES[name] = (f, res, cover)
    return log


@pytest.fixture(autouse=True)
def restore():
    saved = dict(E.SERVICES)
    yield
    E.SERVICES.clear()
    E.SERVICES.update(saved)


def test_first_service_wins_and_feet():
    log = fake({"usgs-3dep": 1401.27, "opentopodata-ned10m": 1400.0})
    e = E.lookup(32.99, -106.97)
    assert e.source == "usgs-3dep" and e.m == pytest.approx(1401.27) and e.ft == pytest.approx(1401.27 * 3.28084)
    assert log == ["usgs-3dep"]


def test_fallback_order_and_nodata_sentinel_including_strings():
    log = fake({"usgs-3dep": "No data", "opentopodata-ned10m": -1000000, "open-meteo-glo90": 1398.0})
    e = E.lookup(32.99, -106.97)
    assert e.source == "open-meteo-glo90" and log == ["usgs-3dep", "opentopodata-ned10m", "open-meteo-glo90"]


def test_outside_us_skips_us_services():
    log = fake({"open-meteo-glo90": 12.0})
    assert E.lookup(-33.0, 73.0).source == "open-meteo-glo90" and log == ["open-meteo-glo90"]


def test_cache_means_one_call_per_site():
    log = fake({"usgs-3dep": 875.0})
    E.lookup(31.94, -102.19)
    E.lookup(31.94, -102.19)
    assert log == ["usgs-3dep"]


def test_verify_flags_disagreement_and_is_not_cached():
    log = fake({"usgs-3dep": 1401.0, "opentopodata-ned10m": 1450.0})
    e = E.lookup(32.99, -106.97, verify=True)
    assert "check the coordinates" in e.note and log == ["usgs-3dep", "opentopodata-ned10m"]
    E.lookup(32.99, -106.97, verify=True)
    assert len(log) == 4


def test_offline_dem_bilinear_and_all_fail(tmp_path):
    fake({})
    lat, lon = np.array([32.0, 33.0]), np.array([-107.0, -106.0])
    p = tmp_path / "dem.npz"
    np.savez(p, lat=lat, lon=lon, elev=np.array([[1000.0, 1200.0], [1400.0, 1600.0]]))
    e = E.lookup(32.5, -106.5, offline_dem=str(p))
    assert e.source == "offline-dem" and e.m == pytest.approx(1300.0)
    with pytest.raises(E.ElevationUnavailable):
        E.lookup(10.0, 10.0, cache=False)


def test_bad_coordinates():
    with pytest.raises(ValueError):
        E.lookup(95.0, 0.0)



def test_goes_through_the_shared_network_layer_and_offline_mode_blocks_it(monkeypatch):
    from tempest_weather_v2 import _net
    calls = []
    monkeypatch.setattr(_net, "fetch", lambda url, **kw: calls.append((url, kw.get("service"))) or b'{"value": 1401.3}')
    assert abs(E.usgs_3dep(32.99, -106.97) - 1401.3) < 1e-9 and calls[0][1] == "usgs-epqs"
    monkeypatch.undo()
    _net.set_offline(True)
    try:
        with pytest.raises(_net.OfflineError):
            E.usgs_3dep(32.99, -106.97)
    finally:
        _net.set_offline(None)
