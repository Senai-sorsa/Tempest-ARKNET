"""IL-183: a region's own physical gust law in its assets is used instead of the built-in NM/TX constants; without one, the result is exactly the built-in law (NM/TX unchanged)."""
import numpy as np

from tempest_weather import api


def test_region_law_overrides_and_default_is_unchanged():
    ws, doy, hour = np.array([2.0, 6.0, 8.5]), 172, 18.0                                       # below the 9 m/s cap (above it the gust factor is held)
    g_plain = dict(theta=np.zeros(8), phi=np.zeros(8))
    mu0, b0 = api._gust_params(g_plain, ws, doy, hour, 1.0)
    mu_ref, b_ref = api._gust_physical(api.GUST_PHYS_MODEL, api.GUST_PHYS_MODEL_CAP, ws, doy, hour, 1.0)
    assert np.allclose(mu0, mu_ref) and np.allclose(b0, b_ref)                                  # no regional law: the built-in one
    law = dict(theta=np.array([1.0, 1.2, 0, 0, 0, 0, 0, 0.5]), phi=np.array([-1.0, 0, 0, 0, 0, 0, 0, 0]))
    g = dict(g_plain, phys_model=law, phys_model_cap=9.0, phys_measured=law, phys_measured_cap=20.0, station=0.0)
    sw = api.OPTIONS["gust_speed_switch"]
    try:
        api.OPTIONS["gust_speed_switch"] = False                                               # the region law everywhere (AV13 switch off)
        mu1, b1 = api._gust_params(g, ws, doy, hour, 1.0)
    finally:
        api.OPTIONS["gust_speed_switch"] = sw
    assert np.allclose(mu1, 1.0 + 1.2 * ws) and np.allclose(b1, np.exp(-1.0))                   # the region's law, with ITS station flag (0), not the caller's 1
    mu3, _ = api._gust_params(g, ws, doy, hour, 1.0)                                            # AV13 switch on (default): region law only at >= 5 m/s
    hi = ws >= api.GUST_SWITCH_WS
    assert np.allclose(mu3[hi], 1.0 + 1.2 * ws[hi]) and np.allclose(mu3[~hi], mu_ref[~hi])
    mu2, _ = api._gust_params_measured(ws, doy, hour, 1.0, g=g)
    assert np.allclose(mu2, 1.0 + 1.2 * ws)
    assert np.allclose(api._gust_params_measured(ws, doy, hour, 1.0)[0], api._gust_physical(api.GUST_PHYS_MEASURED, api.GUST_MEASURED_WS_CAP, ws, doy, hour, 1.0)[0])
