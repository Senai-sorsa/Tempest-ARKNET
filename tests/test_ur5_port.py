"""WD1 / UR5 tool port (New_Plan 28.11 item 12): the sequence step changes the wind below 300 m only (10 m change faded out by 300 m), only with a table, and switches off cleanly."""
import numpy as np

from tempest_weather import _core, api


def _table(map_gain):
    x = np.linspace(0, 60, 100)
    return dict(lat=np.array([31.5]), lon=np.array([-107.5]), xt=np.tile(x, (1, 12, 24, 1)), xe=np.tile(x * map_gain, (1, 12, 24, 1)),
                ok=np.ones((1, 12, 24), bool), rho=np.tile([0.7, 0.9, 4.0], (1, 12, 24, 1)), s=np.ones(2))


def test_ur5_sequence_low_wind_only():
    A = api._assets()
    post = A["post"]
    kw = dict(offsets=(0, 1, 2), n=398, seed=3)
    try:
        A["post"] = {k: v for k, v in (post or {}).items() if k != "ur5"}
        a0, _ = api.atmosphere_sequence(32.0, -106.0, "2013-04-15T18:00:00+00:00", **kw)
        A["post"]["ur5"] = _table(0.5)
        api.OPTIONS["ur5_sequence"] = False
        a2, _ = api.atmosphere_sequence(32.0, -106.0, "2013-04-15T18:00:00+00:00", **kw)
        api.OPTIONS["ur5_sequence"] = True
        a1, i1 = api.atmosphere_sequence(32.0, -106.0, "2013-04-15T18:00:00+00:00", **kw)
    finally:
        A["post"], api.OPTIONS["ur5_sequence"] = post, True
    assert "sequence-10m-wind:ur5-wd1" in i1[0]["quality"]
    for k in range(3):
        assert np.array_equal(a0[k]["u"], a2[k]["u"])
        hi = np.asarray(_core.HEIGHTS) >= 300
        assert np.array_equal(a0[k]["u"][:, hi], a1[k]["u"][:, hi]) and np.array_equal(a0[k]["T"], a1[k]["T"])
    du0, du1 = a1[0]["u"][:, 0] - a0[0]["u"][:, 0], a1[0]["u"][:, 1] - a0[0]["u"][:, 1]
    w = 1 - (_core.HEIGHTS[1] - _core.HEIGHTS[0]) / (300.0 - _core.HEIGHTS[0])
    assert np.allclose(du1, w * du0, atol=1e-3)                                 # 50 m gets the tapered share of the 10 m change
    s0, s1 = np.hypot(a0[0]["u"][:, 0], a0[0]["v"][:, 0]), np.hypot(a1[0]["u"][:, 0], a1[0]["v"][:, 0])
    assert np.allclose(np.sort(s1), np.sort(s0) * 0.5, atol=1e-3)   # hour 0: map only (s = 1), order kept
    assert np.allclose(s1, s0 * 0.5, atol=1e-3)
