"""End to end: the tool answers from a forecast inside its tested window, and falls back (flagged) outside it or when the fetch fails."""
import json
import os

import numpy as np
import pytest

import tempest_weather as tw
from tempest_weather import forecast as TF

ASSETS = os.path.join(os.path.dirname(tw.__file__), "assets")


def _has_modef():
    try:
        return json.load(open(os.path.join(ASSETS, "manifest.json"))).get("modef_included", False)
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _has_modef(), reason="assets without the forecast network (run tempest.export_tool --modef)")


def canned(lat, lon, day):
    hr = {"time": [f"{day}T{h:02d}:00" for h in range(24)]}
    n = 24
    hr["temperature_2m"] = [14.0] * n
    hr["dew_point_2m"] = [-4.0] * n
    hr["wind_speed_10m"] = [5.0] * n
    hr["wind_direction_10m"] = [250.0] * n
    hr["surface_pressure"] = [850.0] * n
    for p in TF.LEVELS_SERVED:
        zh = 44330 * (1 - (p / 1013.25) ** 0.1903)
        hr[f"temperature_{p}hPa"] = [15.0 - 0.0065 * zh] * n
        hr[f"relative_humidity_{p}hPa"] = [35.0] * n
        hr[f"wind_speed_{p}hPa"] = [8.0 + 20.0 * (1 - p / 1000.0)] * n
        hr[f"wind_direction_{p}hPa"] = [265.0] * n
        hr[f"geopotential_height_{p}hPa"] = [zh] * n
    return {"hourly": hr}


NOW = "2026-11-05T00:00"
WHEN = "2026-11-08T17:00"        # naive = local solar time: 3 days ahead, late afternoon


def test_forecast_mode_answers_inside_the_window():
    out = tw.values(32.9, -106.9, WHEN, ["T@2000", "u@5000", "wind_speed@100"], n=398, now=NOW, fetch=canned)
    assert out["mode"] == "forecast" and "nominal" in out["quality"]
    assert any(q.startswith("forecast-source") for q in out["quality"]) and all(np.isfinite(list(out["values"].values())))
    assert 250 < out["values"]["T@2000"] < 310


def test_fallback_outside_the_tested_hours_and_leads_and_on_fetch_failure():
    late = tw.values(32.9, -106.9, "2026-11-08T20:30", ["T@2000"], n=199, now=NOW, fetch=canned)       # 20.5 h solar: outside the forecast window 02-20 h, inside the climate model's 06-21 h
    assert late["mode"] == "ai" and any("solar-hours" in q for q in late["quality"])
    morning = tw.values(32.9, -106.9, "2026-11-08T09:00", ["T@2000"], n=199, now=NOW, fetch=canned)    # F-V2: 09 h solar is served by forecast mode since 2026-11-10 (tested at 05 / 11 / 17 h)
    assert morning["mode"] == "forecast"
    far = tw.values(32.9, -106.9, "2026-11-20T17:00", ["T@2000"], n=199, now=NOW, fetch=canned)         # 15 days ahead
    assert far["mode"] == "ai" and any("lead-outside" in q for q in far["quality"])

    def boom(lat, lon, day):
        raise OSError("no network")
    fail = tw.values(32.9, -106.9, WHEN, ["T@2000"], n=199, now=NOW, fetch=boom)
    assert fail["mode"] == "ai" and any("forecast-fetch-failed" in q for q in fail["quality"])


def test_forecast_distribution_is_calibrated_width_and_coherent():
    c = tw.couple(32.9, -106.9, WHEN, ["T@2000", "T@2500"], n=398, now=NOW, fetch=canned)
    k, rows = c.draw(398, np.random.default_rng(0)) if c.draw.__code__.co_argcount > 2 else c.draw(398)
    assert rows.shape[1] == 2 and np.corrcoef(rows.T)[0, 1] > 0.5       # neighbouring heights move together (real error profiles reorder the samples)


def test_ensemble_features_are_opt_in_and_checked():
    """ASK_LATER 21: ens_features must be 24 finite values (spreads >= 0); assets without the ensemble network refuse them instead of silently answering HRES-only."""
    ens = {k: (1.0 if k.endswith("sd") else 3.0) for k in TF.ENS_FEATURES}
    assert TF.ens_vector(ens).shape == (24,) and TF.ens_vector(list(ens.values()))[1] == 1.0
    for bad in ([1.0] * 23, {**ens, "v10_sd": -0.5}, {**ens, "t2m_mean": float("nan")}):
        with pytest.raises(ValueError):
            TF.ens_vector(bad)
    if not json.load(open(os.path.join(ASSETS, "manifest.json"))).get("modef_ens_included", False):
        with pytest.raises(ValueError, match="no ensemble mode F"):
            tw.values(32.9, -106.9, WHEN, ["T@2000"], n=50, now=NOW, fetch=canned, ens_features=ens)


@pytest.mark.parametrize("single", [True, False])
def test_forecast_mode_moves_every_sample_by_one_grid_shift(monkeypatch, single):   # AU-2 (New_Plan 15.1)
    from tempest_weather import _core, api
    seen, real = [], _core.site_shift
    monkeypatch.setattr(_core, "site_shift", lambda phys, dz: (seen.append(np.array(dz, float)), real(phys, dz))[1])
    monkeypatch.setitem(api.OPTIONS, "forecast_single_shift", single)
    atm, info = api.atmosphere_set(32.99, -106.97, WHEN, n=1024, elevation=1401, now=NOW, fetch=canned)
    assert info["mode"] == "forecast" and len(seen) == 1
    want = info["elevation_m"] - info["grid_elevation_m"]
    if single:
        assert np.allclose(seen[0], want)
    else:                                                         # the old line: rows keep their own blend point's height (two values at Spaceport America)
        assert len(np.unique(seen[0])) > 1


@pytest.mark.parametrize("fix", [True, False])
def test_surface_values_from_another_height_are_moved_to_the_grid_once(monkeypatch, fix):   # AU-3 (New_Plan 15.1)
    from tempest_weather import _core, api
    monkeypatch.setitem(api.OPTIONS, "forecast_grid_elevation", fix)
    run = lambda f: api.atmosphere_set(32.99, -106.97, WHEN, n=4, predicted=True, elevation=1401, now=NOW, fetch=f)
    plain, info = run(canned)
    zg = info["grid_elevation_m"]
    low, info2 = run(lambda la, lo, d: dict(canned(la, lo, d), elevation=zg - 90.0))        # same numbers, said to be 90 m below the grid
    moved = any(q.startswith("forecast-surface-values-moved-from-source-height") for q in info2["quality"])
    if not fix:
        assert not moved and np.allclose(low["sp"], plain["sp"]) and np.allclose(low["t2m"], plain["t2m"])
        return
    assert moved and not any(q.startswith("forecast-surface-values-moved") for q in info["quality"])
    t0 = 14.0 + 273.15
    assert np.allclose(low["t2m"] - plain["t2m"], -_core.LAPSE * 90.0, atol=1e-4)
    assert np.allclose(low["sp"] / plain["sp"], np.exp(-_core.G0 * 90.0 / (_core.RD * (t0 - _core.LAPSE * 45.0))), rtol=1e-4)   # float32 and the site step's t2m dependence: ~2 Pa of a 914 Pa shift


def test_default_request_asks_for_the_grid_height():   # AU-3
    from tempest_weather.sources import openmeteo
    assert "elevation=1495.5" in openmeteo.url(32.99, -106.97, "2026-11-08", elevation=1495.46) and "elevation" not in openmeteo.url(32.99, -106.97, "2026-11-08")
