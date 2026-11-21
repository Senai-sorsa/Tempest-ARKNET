"""Regression checks for the Gemini review fixes (2026-11-20)."""
import numpy as np

from tempest_weather.flight import dryden


def test_dryden_w_std_follows_sigma_w():
    z = np.array([0.0, 100.0, 300.0, 1000.0, 2000.0, 3000.0])
    n = 4000
    u = np.tile(np.array([3.0, 8.0, 10.0, 12.0, 14.0, 15.0]), (n, 1))
    T = np.tile(288.0 - 0.0065 * z, (n, 1))
    out = dryden.synthesize(z, u, np.zeros_like(u), T, seed=3)
    zf, sw = out["z"], out["sigma_w"]
    for h in (50.0, 400.0, 1500.0, 2500.0):
        i = int(np.argmin(abs(zf - h)))
        target = np.sqrt(np.mean(sw[:, i] ** 2))
        assert abs(out["w_turb"][:, i].std() / target - 1) < 0.1, (h, out["w_turb"][:, i].std(), target)
