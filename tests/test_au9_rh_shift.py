"""AU-9 (New_Plan 15.3): the site shift keeps the dew point fully; the height fade acts once, through T (it was applied twice to RH)."""
import numpy as np

from tempest.generator import sample
from tempest_weather import _core


def _phys(nh, heights):
    phys = np.zeros((1, 4 * nh + 3))
    phys[:, 2 * nh:3 * nh] = 280.0
    phys[:, 3 * nh:4 * nh] = 50.0
    phys[:, 4 * nh], phys[:, 4 * nh + 1], phys[:, 4 * nh + 2] = 288.0, 90000.0, 50.0
    return phys


def test_hand_value_at_1500m_both_paths_and_switch_back(monkeypatch):
    h = np.asarray(sample.HEIGHTS, float)
    k = int(np.argmin(abs(h - 1500.0)))
    assert h[k] == 1500.0
    nh = len(h)
    # 500 m higher site: T at 1.5 km falls by 0.0065 * 500 * exp(-1) = 1.196 K; dew point kept -> RH 50 -> 54.30 (hand: 50 * es(280) / es(278.804))
    a = sample.to_site(_phys(nh, h), 1000.0, 1500.0)
    b = _core.site_shift(_phys(nh, h), 500.0)
    assert abs(a[0, 3 * nh + k] - 54.300) < 0.01 and abs(b[0, 3 * nh + k] - 54.300) < 0.01
    assert np.allclose(a[0, 3 * nh:4 * nh], b[0, 3 * nh:4 * nh])                   # the tool and the scorer agree
    monkeypatch.setattr(sample, "RH_SHIFT_BLEND", True)
    monkeypatch.setattr(_core, "RH_SHIFT_BLEND", True)
    a0 = sample.to_site(_phys(nh, h), 1000.0, 1500.0)
    b0 = _core.site_shift(_phys(nh, h), 500.0)
    assert abs(a0[0, 3 * nh + k] - 51.582) < 0.01 and abs(b0[0, 3 * nh + k] - 51.582) < 0.01   # the old double fade
