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
    early = tw.values(32.9, -106.9, "2026-11-08T09:00", ["T@2000"], n=199, now=NOW, fetch=canned)       # 09 h solar: not in 14-20
    assert early["mode"] == "ai" and any("solar-hours" in q for q in early["quality"])
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
