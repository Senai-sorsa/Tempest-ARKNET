"""omega -> w conversion: sign, magnitude, surface boundary condition, interpolation."""
import numpy as np

from tempest.generator.build_wdata import omega_to_w
from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS

LEVELS = np.array([5000, 10000, 15000, 20000, 25000, 30000, 40000, 50000, 60000, 70000, 85000, 92500, 100000.0])


def _column():
    z = HEIGHTS.astype(float)
    T = np.tile(np.linspace(300, 215, len(z)), (2, 1))
    th = thermo.column(z, T, np.full(T.shape, 30.0), np.array([87000.0, 87000.0]), z_sfc=1400.0)
    return th


def test_rising_motion_is_positive_and_sized_right():
    th = _column()
    om = np.full((2, 13), -0.1)                                  # Pa/s, upward motion
    w = omega_to_w(om, LEVELS, np.array([87000.0, 87000.0]), th["p"], th["rho"])
    mid = w[:, 20]                                                # a free-atmosphere height
    expect = 0.1 / (th["rho"][:, 20] * 9.80665)
    assert (mid > 0).all() and np.allclose(mid, expect, rtol=0.05)
    assert np.all(np.abs(w[:, 0]) < np.abs(mid))                  # tends to zero toward the ground


def test_underground_levels_do_not_leak_and_sinking_is_negative():
    th = _column()
    om = np.full((2, 13), 0.05)
    om[:, -2:] = 9.0                                              # 925 and 1000 hPa are below the 870 hPa ground: garbage
    w = omega_to_w(om, LEVELS, np.array([87000.0, 87000.0]), th["p"], th["rho"])
    assert np.isfinite(w).all() and (w[:, 20] < 0).all() and np.abs(w).max() < 0.2
