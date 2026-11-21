"""Audit 2026-11-14: forecast-mode top heights over high ground, the bilinear block split, the final-test model check."""
import json
import os
import re
import warnings

import numpy as np
import pytest

from tempest_weather import _core, api, forecast as TF

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENVER = os.path.join(os.path.dirname(api.__file__), "assets_denver")


def test_blend_rows_serves_the_bilinear_weights_on_average():
    pts, wts = np.array([10, 11, 20, 21]), np.array([0.035, 0.005, 0.845, 0.115])        # Spaceport America's weights
    n, groups = 1024, int(np.ceil(1024 / api.M_CAL))
    served = np.zeros(4)
    R = 2000
    for s in range(R):
        rows = api._blend_rows(pts, wts, groups, np.random.default_rng(s))
        assert len(rows) == groups * api.M_CAL
        served += [(rows[:n] == p).mean() for p in pts]
    assert np.abs(served / R - wts).max() < 0.01                                        # old split: 0.972 / 0.028 for the two main points


def test_blend_rows_single_and_whole_blocks():
    rows = api._blend_rows(np.array([5]), np.array([1.0]), 3, np.random.default_rng(0))
    assert (rows == 5).all() and len(rows) == 3 * api.M_CAL
    rows = api._blend_rows(np.array([1, 2]), np.array([0.5, 0.5]), 4, np.random.default_rng(1))
    assert (rows == 1).sum() == (rows == 2).sum() == 2 * api.M_CAL


def test_fill_forecast_top_fills_only_a_top_gap():
    nh = _core.NH
    prof = {k: np.linspace(1, 2, nh) for k in ("u", "v", "T", "RH")}
    prof["T"][-2:] = np.nan                                                             # top gap: filled
    prof["u"][5] = np.nan                                                               # interior gap: left alone
    h = api._fill_forecast_top(prof)
    assert h == float(_core.HEIGHTS[-2])
    assert np.isfinite(prof["T"]).all() and (prof["T"][-2:] == prof["T"][-3]).all()
    assert np.isnan(prof["u"][5])
    assert api._fill_forecast_top({k: np.ones(nh) for k in ("u", "v", "T", "RH")}) is None


def _std_height(p):
    return 44330.77 * (1 - (p / 1013.25) ** 0.190263) if p >= 226.32 else 11000.0 + 6341.62 * np.log(226.32 / p)


def _canned(elev, cold=0.0):
    sp = 1013.25 * (1 - elev / 44330.77) ** 5.2559
    tt = lambda z: (15.0 - 6.5e-3 * z if z < 11000 else -56.5)

    def f(lat, lon, day, **kw):
        n = 24
        hr = {"time": [f"{day}T{h:02d}:00" for h in range(n)], "temperature_2m": [tt(elev)] * n, "dew_point_2m": [tt(elev) - 15.0] * n,
              "wind_speed_10m": [5.0] * n, "wind_direction_10m": [250.0] * n, "surface_pressure": [sp] * n}
        for p in TF.LEVELS_SERVED:
            zh = _std_height(p) + (cold if p <= 100 else 0.0)
            hr[f"temperature_{p}hPa"], hr[f"relative_humidity_{p}hPa"] = [tt(zh)] * n, [35.0] * n
            hr[f"wind_speed_{p}hPa"], hr[f"wind_direction_{p}hPa"], hr[f"geopotential_height_{p}hPa"] = [8.0 + 20.0 * (1 - p / 1000.0)] * n, [265.0] * n, [zh] * n
        return {"hourly": hr, "elevation": elev}
    return f


def _has_denver_modef():
    try:
        return json.load(open(os.path.join(DENVER, "manifest.json"), encoding="utf-8")).get("modef_included", False)
    except OSError:
        return False


@pytest.mark.skipif(not _has_denver_modef(), reason="no Denver assets with the forecast network")
@pytest.mark.parametrize("cold", [0.0, -2000.0])
def test_forecast_mode_has_no_nan_over_high_ground(cold):
    g = api._assets(DENVER)["grid"]
    p = int(np.argmax(g["elev"]))                                                       # 3375 m: 18 km above it is above the 50 hPa level
    lat, lon, el = float(g["lat"][p]), float(g["lon"][p]), float(g["elev"][p])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        atm, info = api.atmosphere_set(lat, lon, "2026-11-08T17:00", n=398, now="2026-11-05T00:00", fetch=_canned(el, cold), assets=DENVER)
    assert info["mode"] == "forecast"
    for k in ("u", "v", "T", "RH", "p", "rho", "a", "t2m", "sp", "rh2m"):
        assert np.isfinite(np.asarray(atm[k], float)).all(), k
    assert any(q.startswith("forecast-top-heights-filled") for q in info["quality"])


def test_final_test_scores_the_shipped_model():
    txt = open(os.path.join(HERE, "scripts", "final_test_2026h2.sh"), encoding="utf-8").read()
    assert re.search(r"^N=models/s25/c4wx4r_s0 ", txt, re.M) and "source_sha256" in txt and "exit 6" in txt  # 28.5 freeze model (manifest model_source)
    assert txt.index("source_sha256") < txt.index("FINAL_TEST_2026H2_DONE\n") or txt.index("source_sha256") < txt.index('echo "started')
