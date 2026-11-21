"""Regression checks for the Gemini review fixes (2026-11-20)."""
import numpy as np

from tempest_weather_v2 import launch as L
from tempest_weather_v2.stats import Coupled


def test_coupled_conditional_uses_each_columns_own_marginal():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 4000)
    data = np.c_[a, 1000 + 50 * rng.normal(size=4000), 5 * a + rng.normal(size=4000)]    # col 1 lives near 1000, col 2 near 0
    c = Coupled(data, ["a", "b", "c"], method="gaussian_copula").condition({"a": 0.0})
    x = c.draw(4000, seed=1)
    assert abs(np.median(x[:, 1]) - 1000) < 20                                         # was drawn from column 0's marginal (near 0) before the fix
    assert abs(np.median(x[:, 2])) < 1.0


def test_level_factor_caps_aloft_but_keeps_10m():
    z = np.asarray(L._core.HEIGHTS, float)
    f = L._level_factor(np.array([50.0, 0.01, 1.0]), z)
    assert f[0, 0] == 50.0 and f[1, 0] == 0.01                                         # the observed 10 m speed is honoured exactly
    assert f[0, 1:].max() <= L.SPEED_K_MAX and f[1, 1:].min() >= 1.0 / L.SPEED_K_MAX  # but not blown up aloft
    assert np.allclose(f[2], 1.0)
    top = z >= L.SPEED_TOP_M
    assert np.allclose(f[:, top], 1.0)
