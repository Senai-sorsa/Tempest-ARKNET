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


def test_past_wind_spread_flag_and_widening():
    from tempest_weather import _core
    from tempest_weather_v2.launch import widen_near_surface
    rng = np.random.default_rng(1)
    x = rng.normal(5.0, 2.0, size=(4000, len(_core.HEIGHTS)))
    y = widen_near_surface(x, 1.2, _core.HEIGHTS)
    assert np.allclose(np.median(y, 0), np.median(x, 0))
    assert y[:, 0].std() / x[:, 0].std() == pytest.approx(1.2, abs=1e-6)
    hi = np.asarray(_core.HEIGHTS) > 300
    assert np.allclose(y[:, hi], x[:, hi])
    assert np.allclose(widen_near_surface(x, 1.0, _core.HEIGHTS), x)
    with pytest.raises(ValueError):
        Launch("spaceport_america", "2027-06-16 10:00", past_wind_spread=9)
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=64, past_wind_spread=1.2)
    assert L.with_(units="si").past_wind_spread == 1.2
    assert "past-wind-spread-widened" not in L.weather(all=True).flags               # climate mode: not applied


def test_domain_inside_edge_outside():
    d = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=64).domain()
    assert d["status"] in ("inside", "edge") and d["region"] and d["edge_km"] > 0
    assert Launch(32.5, -104.5, "2027-06-16 10:00", mode="ai", n=64).domain()["status"] == "inside"
    e = Launch(31.05, -104.5, "2027-06-16 10:00", mode="ai", n=64)
    assert e.domain()["status"] == "edge" and "edge of the trained area" in e.domain()["reason"] and "edge of what the model was trained on" in e.trust
    far = Launch(32.5, -104.5, "2027-06-16 10:00", mode="ai", n=64, elevation=3500, units="si").domain()
    assert far["status"] == "edge" and "model grid height" in far["reason"]
    out = Launch(45.0, -90.0, "2027-06-16 10:00", mode="ai", n=64).domain()                                  # no asset set covers it
    assert out["status"] == "outside" and out["region"] is None


def test_trust_line_says_atmosphere_only_and_gives_climate_advice():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=64, units="si")
    t = L.trust
    assert "atmosphere only" in t and "not of the rocket" in t and "observe_latest" in t


def test_observation_guards_refuse_impossible_values_and_keep_real_extremes():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200, units="si", seed=2)
    for kw, text in ((dict(wind_10m="95 m/s", wind_from_deg=200), None), (dict(wind_10m="-5 m/s", wind_from_deg=200), "outside"), (dict(wind_10m="130 m/s", wind_from_deg=200), "outside"),
                     (dict(temperature="-95 C"), "outside"), (dict(temperature="70 C"), "outside"), (dict(station_pressure="400 hPa"), None), (dict(station_pressure="2000 hPa"), "outside"),
                     (dict(wind_10m="5 m/s", wind_from_deg=400), "outside"), (dict(wind_10m=float("nan"), wind_from_deg=10), "finite"), (dict(altimeter="500 hPa"), "outside")):
        if text is None:
            L.observe(**kw)
        else:
            with pytest.raises(ValueError, match=text):
                L.observe(**kw)
    with pytest.raises(ValueError, match="cannot be negative"):
        L.observe(wind_10m="3 m/s", wind_from_deg=10, age_hours=-1.0)
    storm = L.observe(wind_10m="35 m/s", wind_from_deg=250)                 # a real storm wind is inside the limits: accepted, trusted, flagged as far from the climate prior
    r = storm.weather(all=True)
    assert abs(r.wind_10m - 35.0) < 1.0 and any(f.startswith("observation-far-outside-the-prior") for f in r.flags)
    heat = L.observe(temperature="45 C").weather(all=True)
    assert abs(heat.temperature - 45.0) < 0.5
    ok = L.observe(wind_10m="4 m/s", wind_from_deg=200, temperature="28 C").weather(all=True)
    assert not any(f.startswith("observation-far-outside") for f in ok.flags)


def test_percentile_window_is_symmetric_near_the_edges_and_advice_by_date():
    import numpy as np
    from datetime import datetime as _dt, timezone as _tz
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=1024, units="si", seed=3)
    pool = L._ensure_pool()
    d = L._derive(pool["samples"], pool["launch_times"])
    ws = d["wind_speed"]
    rank = (np.argsort(np.argsort(ws)) + 0.5) / len(ws)
    for p in (1, 99):
        r = L.weather(percentile=p, all=True)
        sel_rank = np.abs(rank - p / 100.0) <= max(min(max(0.05, 12.5 / len(ws)), p / 100.0, 1 - p / 100.0), 6.0 / len(ws))
        assert abs(np.median(rank[sel_rank]) - p / 100.0) < 0.004            # the companion fields now describe the p-th percentile day, not a day 2 points inside
    past = Launch("spaceport_america", "2020-06-16 10:00", mode="ai", n=64, units="si").trust
    assert "in the past" in past and "mode='past'" in past
    soon = Launch("spaceport_america", "2026-11-12 10:00", mode="ai", n=64, units="si", now=_dt(2026, 11, 9, 12, 0)).trust
    assert "days away" in soon and "forecast" in soon
    far = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=64, units="si").trust
    assert "in the past" not in far and "days away" not in far


def test_ground_wind_profile_rows():
    import numpy as np
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=300, units="si", seed=4)
    g = L.ground_wind_profile()
    assert g["units"] == "m/s" and g["heights_m"][0] == 10.0 and g["heights_m"][-1] == 200.0 and len(g["speed"][50]) == len(g["heights_m"])
    assert all(a <= b <= c for a, b, c in zip(g["speed"][10], g["speed"][50], g["speed"][90])) and g["mean_0_200m"][10] <= g["mean_0_200m"][50] <= g["mean_0_200m"][90]
    s = L._ensure_pool()["samples"]
    assert g["speed"][50][0] == pytest.approx(float(np.median(np.hypot(s["u"][:, 0], s["v"][:, 0]))))
    us = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=300, units="us", seed=4).ground_wind_profile()
    assert us["units"] == "mph" and us["speed"][50][0] == pytest.approx(g["speed"][50][0] / 0.44704, rel=1e-6)
    assert len(g["weibull_shape"]) == len(g["weibull_scale"]) == len(g["calm_share"]) == len(g["heights_m"])          # W9 shape rows
    assert all(1.0 < x < 5.0 for x in g["weibull_shape"]) and all(0.0 <= x <= 1.0 for x in g["calm_share"])
    assert us["weibull_scale"][0] == pytest.approx(g["weibull_scale"][0] / 0.44704, rel=1e-6) and us["weibull_shape"] == g["weibull_shape"]
    assert g["speed"][10][0] < g["weibull_scale"][0] < g["speed"][90][0] * 1.2


def test_speed_distributions_are_positive_families_weibull_or_lognormal():
    L = Launch("spaceport_america", "2027-07-16 10:00", mode="ai", n=1024, units="si", seed=3)
    d = L.distribution(["wind_speed", "wind_10m", "wind_3km", "gust"])
    for k, r in d.items():
        assert r["type"] in ("weibull", "lognormal"), (k, r["type"])               # wind_speed and wind_3km used to pick a Gumbel, which allows negative speeds
    w = d["wind_10m"]
    if w["type"] == "weibull":
        assert 1.2 < w["params"]["shape"] < 4.0
    t = L.distribution(["temperature"])["temperature"]
    assert t["type"] is not None                                                   # other variables are untouched


def test_gust_law_follows_the_observed_wind():
    """Gemini bug 3: after observe(wind_10m=25 m/s) the gust law must be evaluated at the new wind, not left at the prior's value."""
    base = Launch(32.94, -106.91, "2027-06-16 10:00", tz="America/Denver", seed=3, n=60)
    pool0 = base._ensure_pool()["samples"]
    if "gust_mu" not in pool0:
        pytest.skip("no gust law in these assets")
    hot = base.observe(wind_10m="25 m/s", wind_from_deg=270)
    mu_hot = np.asarray(hot._ensure_pool()["samples"]["gust_mu"])
    assert mu_hot.mean() > np.asarray(pool0["gust_mu"]).mean() + 3.0


def test_sequence_keeps_samples_coherent_over_hours():
    """G2 / M11: sample j is one weather system through the hours (the ordinary pool draws every sample independently)."""
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=150, seed=1)
    seq = L.sequence((0, 1), n=150)
    z = L.elevation_info()[0] + 1500.0
    a = [np.array([s[i].wind(z)[1] for i in range(150)]) for s in seq]
    assert len(seq) == 2 and len(seq[0]) == 150
    assert np.corrcoef(a[0], a[1])[0, 1] > 0.4


def test_calibrate_site_rescales_ground_wind_and_fades_aloft():
    """M6 / W5 wiring: a ratio calibration of 0.8 lowers the 10 m speed by 20 %, nothing at 300 m and above; the original Launch is unchanged."""
    from tempest_weather_v2.sitecal import fit_site
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200, seed=3)
    ref = np.linspace(1, 8, 300)
    cal = fit_site(ref, 0.8 * ref, method="ratio")
    C = L.calibrate_site(cal)
    a, b = L._ensure_pool()["samples"], C._ensure_pool()["samples"]
    sp = lambda s, j: np.hypot(s["u"][:, j], s["v"][:, j])
    assert abs(sp(b, 0).mean() / sp(a, 0).mean() - 0.8) < 0.01
    z = np.asarray(a["height_agl"])
    j = int(np.argmin(np.abs(z - 500)))
    assert np.allclose(sp(b, j), sp(a, j), rtol=1e-4)
    assert "ground-wind-site-calibrated-ratio" in C._ensure_pool()["flags"] and "ground-wind-site-calibrated-ratio" not in L._ensure_pool()["flags"]


def test_past_era5_anchor_flag_reaches_atmosphere_set_only_when_on(monkeypatch):
    """M5c: the opt-in flag adds era5_anchor=1.0 to the call; default adds nothing (the call is unchanged)."""
    from tempest_weather import api
    seen = []
    real = api.atmosphere_set

    def spy(*a, **k):
        seen.append(dict(k))
        return real(*a, **k)
    monkeypatch.setattr(api, "atmosphere_set", spy)
    Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=30, seed=1)._ensure_pool()
    Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=30, seed=1, past_era5_anchor=True)._ensure_pool()
    assert "era5_anchor" not in seen[0] and seen[1].get("era5_anchor") == 1.0


def test_measured_wind_gust_law_matches_station_gust_factors():
    """W8c: after observe(wind_10m=...) the gust uses the law fitted on MEASURED winds: no gust group most hours at light wind, gust factor about 1.3-1.4 in strong wind (stations 1.36-1.43),
    held above 20 m/s; the model-wind law fed the same wind gave factors of 2.4-4.8 above 16 m/s."""
    import numpy as np
    from tempest_weather import api
    rng = np.random.default_rng(0)

    def draws(ws):
        mu, beta = api._gust_params_measured(np.full(4000, ws), 172, 18.0, 1.0)
        return np.maximum(mu - beta * np.log(-np.log(rng.random(4000).clip(1e-12, 1 - 1e-12))), ws)
    light, strong, storm = draws(3.0), draws(14.0), draws(30.0)
    assert (light == 3.0).mean() > 0.85                                          # stations: about 95 % of 2-5 m/s hours have no gust group
    assert 1.2 < np.median(strong) / 14.0 < 1.5 and 1.15 < np.median(storm) / 30.0 < 1.6
    assert np.all(np.isfinite(storm)) and np.percentile(storm, 99) / 30.0 < 2.2   # a storm never produces an impossible gust
    base = Launch(32.94, -106.91, "2027-06-16 10:00", tz="America/Denver", seed=3, n=200)
    if "gust_mu" not in base._ensure_pool()["samples"]:
        pytest.skip("no gust law in these assets")
    obs = base.observe(wind_10m="18 m/s", wind_from_deg=270)
    d = obs._derive(obs._ensure_pool()["samples"])
    assert np.median(d["gust"] / d["wind_10m"]) < 1.6
    from tempest_weather_v2 import launch as LM
    old, LM.MEASURED_GUST_LAW = LM.MEASURED_GUST_LAW, False
    try:
        o2 = base.observe(wind_10m="18 m/s", wind_from_deg=270)
        d2 = o2._derive(o2._ensure_pool()["samples"])
    finally:
        LM.MEASURED_GUST_LAW = old
    assert np.median(d2["gust"] / d2["wind_10m"]) > np.median(d["gust"] / d["wind_10m"]) + 0.2       # the switch restores the model-wind law
