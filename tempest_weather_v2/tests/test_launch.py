"""Launch end to end on the real NM/TX model assets (climate mode, no network). Dates in 2027 so no past data is touched."""
import numpy as np
import pytest

from tempest_weather_v2 import Launch, Window
from tempest_weather_v2.readers import Atmosphere

WHEN = "2027-06-16 10:00"


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))


@pytest.fixture(scope="module")
def launch():
    return Launch("spaceport_america", WHEN, mode="ai", n=400)


def test_weather_numbers_units_and_printout(launch):
    r = launch.weather()
    assert abs(r.elevation - 4595.0) < 1.0 and 60 < r.temperature < 105               # degF, a June morning at 1,400 m
    assert 28.5 < r.pressure < 31.0 and 0 <= r.wind_speed < 25 and 0 <= r.wind_from_deg <= 360   # inHg altimeter setting, mph
    si = Launch("spaceport_america", WHEN, mode="ai", n=400, units="si").weather()
    assert abs(si.elevation - 1400.6) < 0.1 and abs(si.temperature - (r.temperature - 32) / 1.8) < 0.3 and abs(si.pressure - r.pressure * 33.8639) < 0.6
    text = str(r)
    assert "elevation" in text and "°F" in text and "inHg" in text and "mph" in text and "Climate estimate" in text and "10,000 ft flight" in text
    full = launch.weather(all=True)
    for k in ("station_pressure", "mslp", "wind_from_deg", "wind_10m", "gust", "humidity", "dew_point", "density", "density_ratio", "max_wind_shear", "upper_wind_max"):
        assert hasattr(full, k), k
    assert "True (" in str(full) and "Mag" in str(full)                                  # wind direction with the magnetic bearing
    assert full.station_pressure < full.pressure                                         # inHg: pad pressure is below the sea-level altimeter setting
    with pytest.raises(AttributeError, match="did you mean wind_speed"):
        r.wind_sped


def test_pressure_chain_station_altimeter_inverse(launch):
    from tempest_weather_v2 import weather_calc as W
    f = launch.weather(all=True)
    back = float(W.station_pressure_hpa(f.si("pressure"), 1400.6))
    assert abs(back - f.si("station_pressure")) < 1.0                                    # median-of-each-field vs per-sample: still within a hPa


def test_percentiles_are_coupled_and_ordered(launch):
    lo, mid, hi = launch.weather(ras_profiles=True)
    assert lo.si("wind_speed") <= mid.si("wind_speed") <= hi.si("wind_speed") and hi.si("wind_speed") > lo.si("wind_speed")
    assert "10th percentile of wind_speed" in lo.label and "NOT one consistent day" not in lo.label
    m = launch.weather(percentile=90, marginal=True)
    assert "marginal-percentiles" in m.flags and "NOT one consistent day" in m.label
    with pytest.raises(ValueError, match="between 0 and 100"):
        launch.weather(percentile=120)
    with pytest.raises(ValueError, match="by="):
        launch.weather(percentile=50, by="nope")


def test_immutable_reproducible_and_with_():
    a = Launch("spaceport_america", WHEN, mode="ai", n=300, seed=3)
    b = Launch("spaceport_america", WHEN, mode="ai", n=300, seed=3)
    assert a.weather().to_dict() == b.weather().to_dict()
    with pytest.raises(AttributeError, match="immutable"):
        a.seed = 4
    c = a.with_(seed=4)
    assert c.seed == 4 and a.seed == 3 and c.weather().to_dict() != a.weather().to_dict()
    d = a.with_(units="si")
    assert d.units == "si" and d.lat == a.lat
    with pytest.raises(TypeError):
        Launch("spaceport_america")
    with pytest.raises(KeyError, match="did you mean"):
        Launch("spaceport_amerca", WHEN)
    with pytest.raises(ValueError, match="units"):
        Launch("spaceport_america", WHEN, units="metric")


def test_coordinates_use_lookup_then_fall_back_to_the_model_grid_flagged(monkeypatch):
    from tempest_weather_v2 import elevation as E
    monkeypatch.setattr(E, "lookup", lambda lat, lon, **k: (_ for _ in ()).throw(E.ElevationUnavailable("offline")))
    L = Launch(32.99, -106.97, WHEN, mode="ai", n=200)
    r = L.weather()
    assert "elevation-from-model-grid" in r.flags and 4500 < r.elevation < 5200 and "time-zone-guessed-from-position" in r.flags
    monkeypatch.setattr(E, "lookup", lambda lat, lon, **k: E.Elevation(1401.3, "usgs-3dep", 10.0, ""))
    L2 = Launch(32.99, -106.97, WHEN, mode="ai", n=200)
    assert abs(L2.weather().si("elevation") - 1401.3) < 1e-6
    L3 = Launch(32.99, -106.97, WHEN, mode="ai", n=200, elevation="4600 ft")
    assert abs(L3.weather().si("elevation") - 1402.08) < 1e-3                             # the user's value always wins


def test_window_draws_several_hours_and_reports_it():
    w = Window(WHEN, earliest="08:00", latest="2027-06-16 14:00")
    L = Launch("spaceport_america", w, mode="ai", n=300)
    r = L.weather()
    assert "window-hours-independent" in r.flags and "triangular" in r.label
    pool = L._ensure_pool()
    assert len({int(t.astype("datetime64[h]").astype("int64")) for t in pool["launch_times"]}) >= 4
    atms = L.atmospheres(20)
    assert len(atms) == 20 and atms[3].launch_time is not None
    one = Launch("spaceport_america", WHEN, mode="ai", n=100)
    assert "10:00 MDT" in one.local_time_note and "solar" in one.local_time_note


def test_distribution_and_couple(launch):
    d = launch.distribution(["wind_speed", "temperature"])
    assert d["wind_speed"]["type"] in ("normal", "lognormal", "weibull", "gumbel", "beta") and len(d["temperature"]["quantiles"]) == 9
    assert d["temperature"]["units"] == "°F" and 50 < d["temperature"]["quantiles_display"][0.5] < 105
    with pytest.raises(ValueError, match="did you mean temperature"):
        launch.distribution(["temprature"])
    c = launch.couple(["temperature", "wind_speed"], method="t_copula")
    x = c.draw(500)
    assert x.shape == (500, 2) and c.nu is not None
    ws = launch.couple(["temperature", "wind_speed"])
    assert ws.draw(50).shape == (50, 2) and ws.method == "whole_sample"


def test_atmosphere_sequence_feeds_the_readers(launch):
    atms = launch.atmospheres(50)
    assert len(atms) == 50 and isinstance(atms[0], Atmosphere) and len(atms[:10]) == 10 and atms[-1].index == 49
    n = 0
    for a in atms:
        T, p, rho, c = a.air(1400.6 + 500.0)
        assert 250 < T < 330 and 70000 < p < 90000 and 0.8 < rho < 1.2
        n += 1
    assert n == 50
    with pytest.raises(IndexError):
        atms[50]


def test_save_and_load_roundtrip(tmp_path, launch):
    p = launch.save(str(tmp_path / "june16.tempest"))
    L2 = Launch.load(p)
    a, b = launch.weather().to_dict(), L2.weather().to_dict()
    for k in a:
        assert a[k] == pytest.approx(b[k], rel=1e-5, abs=1e-5), k
    assert len(L2.atmospheres(10)) == 10 and L2.provenance["package_version"]


def test_engine_and_observe_condition_on_launch_day_measurements(launch):
    eng = launch.engine()
    assert eng is launch.engine()                                                   # cached
    cond = launch.observe(wind_10m="14 mph", wind_from_deg=240, temperature="82 F")
    assert cond is not launch and launch._obs == {} and len(cond._obs) == 3
    r0, r1 = launch.weather(all=True), cond.weather(all=True)
    assert abs(r1.wind_10m - 14.0) < 0.6 and abs(r1.wind_10m_from_deg - 240.0) < 3.0 and abs(r1.temperature - 82.0) < 0.6
    assert "conditioned on 3 measurements (not yet validated)" in r1.trust
    assert abs(r0.wind_10m - 14.0) > 1.0
    with pytest.raises(NotImplementedError):
        launch.observe(sounding="auto")
    with pytest.raises(ValueError, match="needs a wind speed"):
        launch.observe(wind_from_deg=90)
    with pytest.raises(ValueError, match="at least one"):
        launch.observe()


def test_exports(launch):
    r = launch.weather(all=True)
    ras = r.to_ras()
    assert "RASAero" in ras and "(ft)" in ras and "inHg" in ras and "mph" in ras and "4595" in ras
    orr = r.to_openrocket()
    assert "mbar" in orr and "Wind direction" in orr and "turbulence intensity" in orr
    assert r.to_dict(units="si")["elevation"] == pytest.approx(1400.6, abs=0.1)


def test_past_mode_without_a_store_warns_loudly_and_a_store_path_is_accepted(monkeypatch):
    import os
    monkeypatch.delenv("TEMPEST_ERA5_STORE", raising=False)
    with pytest.warns(UserWarning, match="fell back to the climate generator"):
        L = Launch("spaceport_america", "2022-06-24 09:17", mode="past", n=100)
        r = L.weather()
    assert "fallback-mode" in r.flags and "not available" in r.trust
    store = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pilot", "profiles.zarr")
    if os.path.exists(store):
        ok = Launch("spaceport_america", "2022-06-24 09:17", mode="past", n=100, era5_store=store).weather()
        assert "fallback-mode" not in ok.flags and "Past date" in ok.trust


def test_observe_accepts_pad_pressure_and_altimeter_setting(launch):
    from tempest_weather_v2 import weather_calc as W
    base = launch.weather(all=True)
    cond = launch.observe(station_pressure="25.00 inHg")                              # about 0.4 inHg below the median pad pressure
    r = cond.weather(all=True)
    assert abs(r.station_pressure - 25.00) < 0.05 and r.station_pressure < base.station_pressure - 0.2
    a_hpa = float(W.altimeter_setting_hpa(base.si("station_pressure") - 8.0, 1400.6))   # an altimeter setting 8 hPa lower than the median
    c2 = launch.observe(altimeter=f"{a_hpa:.2f} hPa")
    assert abs(c2.weather(all=True).si("station_pressure") - (base.si("station_pressure") - 8.0)) < 0.6
    with pytest.raises(ValueError, match="not both"):
        launch.observe(station_pressure="25 inHg", altimeter="29.9 inHg")
    assert "conditioned on 1 measurements" in cond.trust


def test_launches_many_times_at_once():
    from tempest_weather_v2 import Launches
    runs = Launches.over_times("spaceport_america", times=["2027-06-16 08:00", "2027-06-16 12:00"], mode="ai", n=64, units="si")
    assert len(runs) == 2 and len(runs.weather()) == 2
    t = runs.table("wind_speed")
    assert t.shape == (2, 3) and (t[:, 1] <= t[:, 0]).all() and (t[:, 0] <= t[:, 2]).all()
    with pytest.raises(ValueError):
        Launches([])
