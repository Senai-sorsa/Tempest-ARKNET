"""AV13 port (New_Plan 28.11 item 8): with a region gust law, _gust_params uses it at / above GUST_SWITCH_WS model wind and the built-in law below; the option restores the region law everywhere."""
import numpy as np

from tempest_weather import api


def test_gust_speed_switch():
    g = dict(phys_model=dict(theta=np.array(api.GUST_PHYS_MODEL["theta"]) + 1.0, phi=api.GUST_PHYS_MODEL["phi"]), phys_model_cap=api.GUST_PHYS_MODEL_CAP, station=0.0)
    ws = np.array([1.0, 4.99, 5.0, 8.0, 15.0])
    hi = ws >= api.GUST_SWITCH_WS
    b = api._gust_params(None, ws, 120, 18.0, 1.0)
    r = api._gust_physical(g["phys_model"], g["phys_model_cap"], ws, 120, 18.0, 0.0)
    s = api._gust_params(g, ws, 120, 18.0, 1.0)
    for k in range(2):
        assert np.array_equal(s[k][~hi], b[k][~hi]) and np.array_equal(s[k][hi], r[k][hi])
    try:
        api.OPTIONS["gust_speed_switch"] = False
        e = api._gust_params(g, ws, 120, 18.0, 1.0)
    finally:
        api.OPTIONS["gust_speed_switch"] = True
    assert all(np.array_equal(e[k], r[k]) for k in range(2))
