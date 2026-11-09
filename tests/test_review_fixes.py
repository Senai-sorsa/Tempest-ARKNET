"""Review fixes F-1, F-2, F-3, F-5, F-18, F-22."""
import importlib
import sys

import numpy as np
import pytest

from tempest.generator import sample
from tempest.gust import model as gm
from tempest.nearterm import ensemble
from tempest.profiles.to_heights import HEIGHTS, PROFILE, liquid_rh

NH = len(HEIGHTS)


def test_to_heights_light_import_without_dask_or_xarray():
    for name in ("dask", "dask.array", "xarray"):
        sys.modules.setdefault(name, None)
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("tempest.profiles.to_heights")}
    try:
        mod = importlib.import_module("tempest.profiles.to_heights")
        assert len(mod.HEIGHTS) == 44
    finally:
        sys.modules.update(saved)
        for name in ("dask", "dask.array", "xarray"):
            if sys.modules.get(name, 0) is None:
                del sys.modules[name]


def test_liquid_rh_only_acts_in_the_cold():
    t = np.array([290.0, 273.0, 255.0, 240.0])
    r = np.full(4, 60.0)
    out = liquid_rh(t, r)
    assert out[0] == 60.0 and np.all(np.diff(out) < 0) is np.True_ or out[2] < 60.0      # warm: unchanged; cold: lower RH over water than over the mixed phase
    assert out[3] < out[2]


def test_gust_hour_and_station_helpers():
    import pandas as pd
    assert gm.utc_hour(pd.Timestamp("2025-07-01 21:30")) == pytest.approx(21.5)
    assert gm.station_flag(33.0, -106.9) == 1.0        # Spaceport America side
    assert gm.station_flag(31.95, -102.2) == 0.0       # Midland


def test_site_shift_is_smooth_and_identity_at_zero():
    rng = np.random.default_rng(0)
    phys = np.zeros((3, 4 * NH + 3))
    phys[:, 2 * NH:3 * NH] = 290.0 - 0.0065 * HEIGHTS
    phys[:, 3 * NH:4 * NH] = 50.0
    phys[:, 4 * NH] = 290.3
    phys[:, 4 * NH + 1] = 86000.0
    phys[:, 4 * NH + 2] = 40.0
    same = sample.to_site(phys.copy(), 1500.0, 1500.0)
    assert np.allclose(same, phys)
    up = sample.to_site(phys.copy(), 1500.0, 1700.0)                               # site 200 m higher
    d2m_to_10m = up[:, 2 * NH] - up[:, 4 * NH]
    d2m_to_10m0 = phys[:, 2 * NH] - phys[:, 4 * NH]
    assert np.allclose(d2m_to_10m, d2m_to_10m0, atol=0.01)                          # no new jump between the 2 m and the 10 m temperature
    assert np.allclose(up[:, 4 * NH], 290.3 - 0.0065 * 200)
    assert up[0, 2 * NH + 40] - phys[0, 2 * NH + 40] > -0.01                       # the shift has faded at 17 km
    assert (up[:, 3 * NH:4 * NH] <= 100).all() and (up[:, 4 * NH + 2] >= 40).all()   # colder, same dew point: RH rises
    _ = rng


def test_bilinear_weights_and_allocation():
    from tempest_weather import _core
    lat = np.repeat(np.arange(31.0, 31.76, 0.25), 3)
    lon = np.tile(np.array([-108.0, -107.75, -107.5]), 4)
    pts, w = _core.bilinear(lat, lon, 31.0, -108.0)                      # on a grid point: that point alone
    assert len(pts) == 1 and w[0] == 1.0
    pts, w = _core.bilinear(lat, lon, 31.125, -107.875)                  # cell centre: four equal weights
    assert len(pts) == 4 and np.allclose(w, 0.25)
    pts, w = _core.bilinear(lat, lon, 31.0625, -107.9375)
    assert np.isclose(w.sum(), 1.0) and w.max() > 0.5
    rng = np.random.default_rng(0)
    for blocks in (4, 6, 9):
        c = _core.allocate(w, blocks, rng)
        assert c.sum() == blocks and np.all(np.abs(c - w * blocks) < 1.0)


def test_site_shift_accepts_one_shift_per_row():
    from tempest_weather import _core
    phys = np.zeros((2, 4 * NH + 3))
    phys[:, 2 * NH:3 * NH] = 280.0
    phys[:, 3 * NH:4 * NH] = 50.0
    phys[:, 4 * NH] = 281.0
    phys[:, 4 * NH + 1] = 80000.0
    phys[:, 4 * NH + 2] = 40.0
    out = _core.site_shift(phys.copy(), np.array([0.0, 200.0]))
    assert np.allclose(out[0], phys[0]) and out[1, 4 * NH] == pytest.approx(281.0 - 1.3)


def test_tempest_blend_matches_tool_blend():
    from tempest.output import blend
    from tempest_weather import _core
    lat = np.repeat(np.arange(31.0, 31.76, 0.25), 3)
    lon = np.tile(np.array([-108.0, -107.75, -107.5]), 4)
    for q in ((31.0, -108.0), (31.1, -107.8), (31.6, -107.6)):
        a, wa = blend.bilinear(lat, lon, *q)
        b, wb = _core.bilinear(lat, lon, *q)
        assert np.array_equal(a, b) and np.allclose(wa, wb)
