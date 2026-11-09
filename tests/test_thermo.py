"""thermo.py: isothermal column exact, US Standard Atmosphere 1976 within 0.1 %, humidity effect, shapes."""
import numpy as np

from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS


def _std_atm(z):
    """US Standard Atmosphere 1976 T (K) and p (Pa) at geometric height z (m), up to 20 km."""
    r0 = 6356766.0
    h = r0 * z / (r0 + z)  # geopotential height (m)
    t = np.where(h <= 11000, 288.15 - 0.0065 * h, 216.65)
    p11 = 101325 * (216.65 / 288.15) ** (9.80665 / (287.053 * 0.0065))
    p = np.where(h <= 11000, 101325 * (288.15 / np.maximum(t, 1)) ** (-9.80665 / (287.053 * 0.0065)),
                 p11 * np.exp(-9.80665 * (h - 11000) / (287.053 * 216.65)))
    return t, p


def test_isothermal_dry_column_matches_closed_form():
    z = HEIGHTS.astype(float)
    T = np.full(len(z), 250.0)
    out = thermo.column(z, T, np.zeros(len(z)), 100000.0, t_sfc=250.0, rh_sfc=0.0)
    # ln(p/ps) = -(g0 R^2 / (Rd T)) (1/R - 1/(R+z)), exact for g falling with height
    R = thermo.R_EARTH
    exact = 100000.0 * np.exp(-(thermo.G0 * R ** 2 / (thermo.RD * 250.0)) * (1 / R - 1 / (R + z)))
    assert np.allclose(out["p"], exact, rtol=1e-5)


def test_standard_atmosphere_within_a_tenth_of_a_percent():
    z = HEIGHTS.astype(float)
    t, p = _std_atm(z)
    t0, p0 = _std_atm(np.array([0.0]))
    out = thermo.column(z, t, np.zeros(len(z)), float(p0[0]), t_sfc=float(t0[0]), rh_sfc=0.0)
    rel = np.abs(out["p"] / p - 1)
    assert rel.max() < 1e-3, rel.max()
    # density from the ideal gas law at the standard values
    assert np.allclose(out["rho"], p / (287.05 * t), rtol=2e-3)


def test_speed_of_sound_at_sea_level_standard():
    out = thermo.column(np.array([10.0]), np.array([288.15]), np.array([0.0]), 101325.0, t_sfc=288.15, rh_sfc=0.0)
    assert abs(out["a"][0] - 340.3) < 0.5


def test_moist_air_is_lighter_and_virtual_t_is_warmer():
    z = HEIGHTS.astype(float)
    T = np.linspace(300, 220, len(z))
    dry = thermo.column(z, T, np.zeros(len(z)), 90000.0)
    wet = thermo.column(z, T, np.full(len(z), 90.0), 90000.0)
    assert (wet["tv"] > dry["tv"]).all()
    assert (wet["rho"][:5] < dry["rho"][:5]).all()
    assert (np.diff(wet["p"]) < 0).all()  # pressure falls with height


def test_batch_shapes_and_site_elevation():
    z = HEIGHTS.astype(float)
    T = np.tile(np.linspace(290, 215, len(z)), (5, 3, 1))
    out = thermo.column(z, T, np.full(T.shape, 40.0), np.full((5, 3), 87000.0), z_sfc=1400.0)
    assert out["p"].shape == T.shape and np.isfinite(out["rho"]).all()
