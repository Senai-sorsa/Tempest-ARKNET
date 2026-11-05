"""Tool forecast converter vs the training-side converter, and the Open-Meteo field reader."""
import os

import numpy as np
import pytest

from tempest_weather import forecast as TF

HRES = "data/raw/wb2_hres/2018.nc"


@pytest.mark.skipif(not os.path.exists(HRES), reason="needs the HRES archive")
def test_numpy_converter_matches_training_converter():
    import xarray as xr

    from tempest.forecast import modeF
    h = xr.open_dataset(HRES)
    bl = dict(ratio=np.array([1.7, 1.67, 1.59, 1.47, 1.28]), dpd_a=6.75, dpd_b=0.757)
    c, j, la, lo, zs = 10, 1, 5, 12, 1500.0
    ref = modeF.forecast_profiles(h, np.array([c]), np.array([j]), np.array([la]), np.array([lo]), np.array([zs * 9.80665]), bl)
    g = lambda n: h[n].values[c, j, :, la, lo]
    lev = h.level.values.astype(float)
    fields = dict(t=g("t"), u=g("u"), v=g("v"), z=g("z"), r=TF.rh_from_q(g("q"), g("t"), lev * 100.0), t2m=float(h.t2m.values[c, j, la, lo]),
                  u10=float(h.u10.values[c, j, la, lo]), v10=float(h.v10.values[c, j, la, lo]), sp=float(h.sp.values[c, j, la, lo]))
    out = TF.forecast_profile(fields, zs, bl)
    for k in ("u", "v", "T", "RH"):
        a, b = out[k], ref[k][0]
        ok = np.isfinite(a) & np.isfinite(b)
        assert (np.isfinite(a) == np.isfinite(b)).all() and np.allclose(a[ok], b[ok], atol=0.05), k


def test_openmeteo_fields_and_condition_row():
    L = TF.LEVELS_SERVED
    hr = {"time": ["2026-11-08T00:00"], "temperature_2m": [12.0], "dew_point_2m": [-2.0], "wind_speed_10m": [4.0], "wind_direction_10m": [270.0], "surface_pressure": [850.0]}
    for p in L:
        hr[f"temperature_{p}hPa"] = [15.0 - 0.0065 * (1000 - p) * 8]
        hr[f"relative_humidity_{p}hPa"] = [40.0]
        hr[f"wind_speed_{p}hPa"] = [10.0]
        hr[f"wind_direction_{p}hPa"] = [270.0]
        hr[f"geopotential_height_{p}hPa"] = [44330 * (1 - (p / 1013.25) ** 0.1903)]
    f = TF.fields_from_openmeteo({"hourly": hr}, 0)
    assert np.allclose(f["u"], 10.0) and np.allclose(f["v"], 0.0, atol=1e-9)             # wind from the west blows towards the east: u > 0
    assert f["sp"] == 85000.0 and f["t2m"] == pytest.approx(285.15)
    bl = dict(ratio=np.full(5, 1.4), dpd_a=0.0, dpd_b=1.0)
    prof = TF.forecast_profile(f, 1500.0, bl)
    assert prof["u"].shape == (44,) and np.isfinite(prof["T"][:20]).all() and 0 <= prof["rh2m"] <= 100
    row = TF.condition(prof, 32.9, -106.9, 1500.0, 312, 3.0, 4)
    assert row.shape == (6 + 4 * 11,) and row[5] == pytest.approx(3.0 / 7.0)
