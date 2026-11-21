"""Regression checks for the audit fixes (2026-11-21, tempest_arknet_audit.md)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from tempest.generator.sample import rh_from_dpd
from tempest_weather import coherence, distributions, modes
from tempest_weather.coupling.gaussian_copula import GaussianCopula
from tempest_weather.flight import avionics, dryden


def test_1_dryden_mil_constants_in_feet_and_continuous_at_1000ft():
    z = np.array([10.0, 100.0, 304.0, 304.8, 305.6, 609.6, 2000.0])
    T = np.tile(288.0 - 0.0065 * z, (1, 1))
    e = dryden.envelopes(z, np.full((1, z.size), 10.0), np.zeros((1, z.size)), T)
    ratio = e["sigma_u"][0] / e["sigma_w"][0]
    assert np.all(np.diff(ratio) <= 1e-9) and abs(ratio[3] - 1.0) < 1e-3 and ratio[0] > 1.5
    L = e["L_u"][0]
    assert abs(L[2] - L[4]) < 2.0 and abs(L[5] - 533.0) < 1e-6 and L[-1] == 533.0


def test_2_rh_from_dpd_cold_air_stays_low():
    rh = rh_from_dpd(np.array([160.0, 250.0]), np.array([np.log1p(150.0), np.log1p(5.0)]))
    assert np.all(rh <= 100.0) and rh[0] < 1.0


def test_39_baro_altitude_20_to_32_km_layer():
    h = avionics.baro_altitude_msl(np.array([5474.89, 868.02]))
    assert abs(h[0] - 20000.0) < 5.0 and abs(h[1] - 32000.0) < 20.0


def test_13_fractional_offsets_interpolate_and_integers_unchanged():
    rho = np.array([[1.0, 1.0], [0.8, 0.6], [0.5, 0.3]])
    a = coherence._chol_by_column(rho, [0, 1, 2])
    b = coherence._chol_by_column(rho, [0.0, 1.0, 2.0])
    assert np.allclose(a, b)
    c = coherence._chol_by_column(rho, [0.0, 0.5])
    R = c[0] @ c[0].T
    assert abs(R[0, 1] - 0.9) < 1e-6


def test_21_lead_days_accepts_aware_times():
    when = datetime(2026, 7, 2, 0)
    assert modes.lead_days(when, "2026-07-01T00:00:00+00:00") == pytest.approx(1.0)
    assert modes.lead_days(when.replace(tzinfo=timezone.utc), "2026-07-01T00:00:00") == pytest.approx(1.0)


def test_11_copula_constant_column_is_not_fully_correlated():
    rng = np.random.default_rng(0)
    t = np.column_stack([rng.normal(size=200), np.full(200, 3.0), rng.normal(size=200)])
    cop = GaussianCopula(["a", "b", "c"], t, [distributions.describe(t[:, j], True) for j in range(3)])
    assert abs(cop.corr[0, 1]) < 1e-6 and abs(cop.corr[1, 2]) < 1e-6
