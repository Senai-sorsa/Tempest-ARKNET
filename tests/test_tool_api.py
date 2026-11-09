"""The four calls of tempest_weather, on the exported assets (skipped when they are not present)."""
import json
import os
import shutil

import numpy as np
import pytest

from tempest_weather import api, coupling, outputs, ranking, registry

ASSETS = "tempest_weather/assets"
needs_assets = pytest.mark.skipif(not os.path.exists(os.path.join(ASSETS, "manifest.json")), reason="assets not exported")
WHEN = "2027-06-16 15:00"


@needs_assets
def test_atmosphere_percentiles_are_ordered_worst_to_best_and_complete():
    res = api.atmosphere(32.99, -106.97, WHEN, (15, 50, 85), extras=("gust10", "rho_sfc"), n=400, seed=1, elevation=1400.0)
    assert [r["meta"]["percentile"] for r in res] == [15, 50, 85]
    sc = [r["meta"]["flight_score"] for r in res]
    assert sc[0] > sc[1] > sc[2]                                              # 15 is worse than 50 is worse than 85
    d = res[1]
    assert d["launch_elevation_m"] == 1400.0 and 250 < d["launch_temperature_K"] < 330 and 70000 < d["barometric_pressure_Pa"] < 95000
    assert 0 <= d["relative_humidity"] <= 1 and set(d["extras"]) == {"gust10", "rho_sfc"}
    toml = outputs.to_toml(d, "test")
    assert "[atmosphere]" in toml and "UniformWind" in toml and 'launch_elevation = "1400.0 m"' in toml
    assert "temperature" in outputs.to_text(d) and "relative humidity" in outputs.to_text(d) and json.loads(outputs.to_json(d))["meta"]["percentile"] == 50


@needs_assets
def test_values_order_and_units_and_errors():
    r = api.values(32.99, -106.97, WHEN, ["wind_speed@100", "t2m_c", "sp"], n=300)
    assert list(r["values"]) == ["wind_speed@100", "t2m_c", "sp"] and r["units"]["sp"] == "Pa" and r["mode"] == "ai"
    with pytest.raises(ValueError, match="unknown variable"):
        api.values(32.99, -106.97, WHEN, ["not_a_variable"], n=300)
    with pytest.raises(ValueError, match="outside the trained area"):
        api.values(40.0, -100.0, WHEN, ["t2m"], n=300)
    with pytest.raises(ValueError, match="solar time"):
        api.values(32.99, -106.97, "2027-06-16 03:00", ["t2m"], n=300)


@needs_assets
def test_distribution_settings_pick_standard_or_empirical():
    v = ["t2m_c", "wind_speed@100", "rh2m_frac", "gust10"]
    d0 = api.distribution(32.99, -106.97, WHEN, v, setting=0, n=400)
    d1 = api.distribution(32.99, -106.97, WHEN, v, setting=1, n=400)
    d2 = api.distribution(32.99, -106.97, WHEN, v, setting=2, n=400)
    assert all(s["type"] != "empirical" or "no standard type" in s["note"] for s in d0["variables"].values())
    assert all(s["type"] == "empirical" for s in d2["variables"].values())
    assert d0["kind"] == "uncertainty" and d1["kind"] == "predicted"
    # without model error the predicted set is narrower than the uncertainty set
    s0 = api.distribution(32.99, -106.97, WHEN, ["wind_speed@100"], setting=2, n=400, samples=True)["variables"]["wind_speed@100"]["samples"]
    s3 = api.distribution(32.99, -106.97, WHEN, ["wind_speed@100"], setting=3, n=400, samples=True)["variables"]["wind_speed@100"]["samples"]
    assert np.std(s3) < np.std(s0)


@needs_assets
def test_couple_whole_sample_rows_are_real_and_copula_keeps_rank_correlation():
    c = api.couple(32.99, -106.97, WHEN, ["t2m", "sp", "wind_speed@100"], n=400)
    idx, rows = c.draw(50, np.random.default_rng(0))
    assert np.array_equal(rows, c.table[idx]) and c.info["mode"] == "ai"
    g = api.couple(32.99, -106.97, WHEN, ["t2m", "sp", "wind_speed@100"], method="gaussian_copula", n=400)
    assert g.spec()["method"] == "gaussian_copula" and g.draw(10)[1].shape == (10, 3)


def test_tampered_assets_are_refused(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"model.npz": "0" * 64}, "model_source": "x"}))
    (tmp_path / "model.npz").write_bytes(b"not the model")
    with pytest.raises(RuntimeError, match="manifest hash"):
        api._assets(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        api._assets(str(tmp_path / "missing"))


def test_ranking_picks_by_position_and_registry_validates():
    score = np.array([3.0, 1.0, 2.0, 5.0, 4.0])
    assert ranking.pick(score, 0) == 3 and ranking.pick(score, 100) == 1 and ranking.pick(score, 50) == 0
    with pytest.raises(ValueError):
        ranking.pick(score, 120)
    with pytest.raises(ValueError, match="valid"):
        registry.evaluate({"t2m": np.ones(3)}, ["bogus"])


STORE = "data/pilot/profiles80.zarr"
needs_store = pytest.mark.skipif(not (os.path.exists(STORE) and os.path.exists(os.path.join(ASSETS, "manifest.json"))), reason="local ERA5 store / assets not present")


@needs_store
def test_past_mode_follows_era5_and_is_narrower_than_the_climate_model():
    when = "2025-06-16T00:00:00+00:00"
    past = api.values(31.95, -102.19, when, ["t2m", "wind_speed@100", "T@5000"], n=398, elevation=None, era5_store=STORE)
    assert past["mode"] == "past" and "nominal" in past["quality"] and past["source"].startswith("ERA5")
    clim = api.values(31.95, -102.19, when, ["t2m", "wind_speed@100", "T@5000"], n=398, mode="ai")
    assert clim["mode"] == "ai"
    d_past = api.distribution(31.95, -102.19, when, ["T@5000"], setting=2, n=398, samples=True, era5_store=STORE)["variables"]["T@5000"]["samples"]
    d_clim = api.distribution(31.95, -102.19, when, ["T@5000"], setting=2, n=398, samples=True, mode="ai")["variables"]["T@5000"]["samples"]
    assert np.std(d_past) < 0.5 * np.std(d_clim)                   # knowing the day shrinks the spread a lot
    nm = api.distribution(31.95, -102.19, when, ["T@5000"], setting=3, n=100, samples=True, era5_store=STORE)["variables"]["T@5000"]
    assert nm["type"] == "constant"                                # without model error the past is the ERA5 value itself


@needs_store
def test_night_hours_are_refused_before_the_store_is_read():
    with pytest.raises(ValueError, match="solar time"):
        api.values(31.95, -102.19, "2025-06-16T08:00:00+00:00", ["t2m"], n=199, era5_store=STORE)


def test_modes_without_a_source_fall_back_and_say_so():
    from tempest_weather import modes
    assert modes.choose(3.0) == ("ai", ["fallback-mode", "week-source-not-available"])
    assert modes.choose(-30.0, available={"past"}) == ("past", ["nominal"])
    assert modes.choose(400.0) == ("ai", ["nominal"])
    with pytest.raises(ValueError):
        modes.choose(1.0, "nonsense")
