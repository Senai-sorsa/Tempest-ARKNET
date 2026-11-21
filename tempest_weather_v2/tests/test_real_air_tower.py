"""New_Plan 28.11 item 8 ports: RA 1a real-air gap (api.real_air_gap, Launch.real_air) and the DP tower wrapper (Launch.observe_tower = observe_radar with the kit b67 settings)."""
import numpy as np

from tempest_weather import _core, api
from tempest_weather_v2.launch import Launch


def test_real_air_gap_adds_the_band_variance_only():
    z = np.asarray(_core.HEIGHTS, float)
    u = np.zeros((40000, len(z)))
    a, b = api.real_air_gap(u, u + 3.0, z, seed=1)
    want = {10.0: 1.54, 1000.0: 1.63, 2000.0: 1.49, 5000.0: 1.49, 8000.0: 1.83, 15000.0: 1.98, 18000.0: 1.98}
    for h, sd in want.items():
        k = int(np.where(z == h)[0][0])
        assert abs(a[:, k].std() - sd) < 0.03 and abs((b[:, k] - 3.0).std() - sd) < 0.03 and abs(a[:, k].mean()) < 0.03
    assert np.all(u == 0)                                     # input untouched
    assert abs(np.corrcoef(a[:, 0], b[:, 0])[0, 1]) < 0.03    # u and v independent


def test_launch_real_air_leaves_atmospheres_unchanged():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200, units="si")
    s0 = L.atmospheres().samples
    u0 = np.array(s0["u"], copy=True)
    r = L.real_air().samples
    assert np.array_equal(L.atmospheres().samples["u"], u0) and np.array_equal(r["T"], s0["T"])
    d = np.asarray(r["u"], float) - u0
    assert 1.3 < d[:, 0].std() < 1.8 and not np.array_equal(r["v"], s0["v"])


def test_observe_tower_is_observe_radar_with_the_kit_settings():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=200, units="si")
    h, u, v = [10.0, 60.0, 120.0, 200.0], [3.0, 5.0, 6.0, 7.0], [1.0, 1.5, 2.0, 2.5]
    T = L.observe_tower(h, u, v)
    elev = float(L.elevation_info()[0])
    R = L.observe_radar(site="tower", profile=dict(heights_asl_m=[elev + x for x in h], u=u, v=v, site="tower", time=""), levels_m=(10.0, 50.0, 100.0, 150.0, 200.0), sigma_ms=0.5)
    assert T._obs["_radar"] == R._obs["_radar"] and T._obs["_radar_sigma"] == 0.5 and sorted(T._obs["_radar"]) == [10.0, 50.0, 100.0, 150.0, 200.0]
    assert np.array_equal(T.atmospheres().samples["u"], R.atmospheres().samples["u"])
