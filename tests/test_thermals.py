"""Thermals: Lenschow profile, no thermals in stable air, skewed draws with the right spread and height coupling."""
import numpy as np

from tempest.output import thermals as th


def test_w_star_values_and_stable_air():
    # H = 300 W/m2, zi = 2000 m, T = 305 K, rho = 1.0: w* ~ 3.0-3.5 m/s (textbook desert afternoon)
    ws = th.w_star(300.0, 2000.0, 305.0, 1.0)
    assert 2.5 < ws < 4.0
    assert th.w_star(-20.0, 2000.0, 285.0, 1.1) == 0.0


def test_sigma_w_profile_shape_and_peak():
    z = np.array([10, 100, 300, 500, 1000, 1500, 1999, 2500, 5000.0])
    s = th.sigma_w(z, 2000.0, 3.0)
    assert s[-2:].tolist() == [0.0, 0.0]                      # above the layer
    peak = np.argmax(th.sigma_w(np.linspace(10, 1990, 400), 2000.0, 1.0))
    zpk = np.linspace(10, 1990, 400)[peak] / 2000.0
    assert 0.15 < zpk < 0.35                                    # the maximum sits about a quarter of the way up
    assert abs(th.sigma_w(np.array([500.0]), 2000.0, 1.0)[0] - np.sqrt(1.8) * 0.25 ** (1 / 3) * (1 - 0.2)) < 1e-9
    assert 0.55 < th.sigma_w(np.array([500.0]), 2000.0, 1.0)[0] < 0.95  # about 0.6-0.9 w*, not the 1.4 w* of the unrooted form


def test_draw_has_requested_sigma_zero_mean_positive_skew_and_height_coupling():
    rng = np.random.default_rng(0)
    sig = np.tile(th.sigma_w(np.linspace(100, 1800, 12), 2000.0, 3.0), (60000, 1))
    w = th.draw(sig, rng)
    assert np.allclose(w.mean(0), 0, atol=0.03)
    assert np.allclose(w.std(0) / sig[0], 1.0, atol=0.03)
    skew = ((w - w.mean(0)) ** 3).mean(0) / w.std(0) ** 3
    assert (skew > 0.3).all()                                    # narrow strong updrafts
    c = np.corrcoef(w[:, 2], w[:, 8])[0, 1]
    assert c > 0.6                                                # thermals span the layer
    assert (th.draw(np.zeros((5, 12)), rng) == 0).all()          # no thermals where sigma is zero


def test_sensible_heat_sign():
    assert th.sensible_heat_up(-3.6e6) == 1000.0                  # ERA5 stores upward heat as negative accumulations
