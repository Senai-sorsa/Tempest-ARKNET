import numpy as np
import pandas as pd

from tempest.generator.build_dataset import target_names
from tempest.ingest import indices
from tempest.profiles.to_heights import HEIGHTS, G0, interp_columns, liquid_rh, magnus_rh, profiles_from_levels


def test_interp_linear_unsorted_nan_and_out_of_range():
    h = np.array([[300.0, np.nan, 100.0, 200.0]])
    x = np.array([[30.0, 999.0, 10.0, 20.0]])
    out = interp_columns(h, x, np.array([50.0, 100.0, 150.0, 300.0, 400.0]))
    assert np.isnan(out[0, 0]) and np.isnan(out[0, 4])
    assert np.allclose(out[0, 1:4], [10, 15, 30])


def test_interp_log_below():
    out = interp_columns(np.array([[10.0, 100.0]]), np.array([[1.0, 2.0]]), np.array([np.sqrt(1000.0)]), log_below=100)
    assert np.isclose(out[0, 0], 1.5)  # halfway in ln(h)


def test_magnus_saturated():
    assert np.isclose(magnus_rh(np.float64(290.0), np.float64(290.0)), 100.0)


def test_profiles_from_levels_shapes_and_underground_dropped():
    # 3 levels: one underground (agl < 0), two above; constant fields so every target reads the level value
    zs = np.array([1000.0 * G0])
    z = np.array([[500.0, 3000.0, 21000.0]]) * G0
    one = np.ones((1, 3))
    prof, rh2m = profiles_from_levels(z, 5 * one, 5 * one, 250 * one, 50 * one, zs,
                                      *(np.array([5.0]),) * 4, np.array([250.0]), np.array([250.0]))
    assert prof["u"].shape == (1, 44) and rh2m.shape == (1,)
    assert np.allclose(prof["u"][0], 5) and np.allclose(prof["T"][0], 250)  # top level 20 km AGL covers 18 km
    assert np.isclose(rh2m[0], 100)


def test_indices_parsers(tmp_path):
    (tmp_path / "oni.txt").write_text(" SEAS  YR   TOTAL   ANOM\n  DJF 1991  27.0  0.50\n  JFM 1991  27.0  0.40\n")
    qbo = ("30 mb\n  ORIGINAL DATA\n\nYEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC\n"
           "1991" + "".join(f"{v:7.2f}" for v in range(1, 12)) + "-999.90\n\n30 mb\n  ANOMALY\n")
    (tmp_path / "qbo_u30.txt").write_text(qbo)
    (tmp_path / "qbo_u50.txt").write_text(qbo)
    (tmp_path / "wwv.txt").write_text("Warm Water Volume\n\n date Volume Anomaly\n199101 0.2E+16 0.3E+14\n")
    t = indices.load(str(tmp_path))
    v = indices.at(t, pd.to_datetime(["1991-01-15 12:00", "1991-12-01 00:00"]))
    assert np.allclose(v[0], [0.5, 1.0, 1.0, 3e13]) and np.isnan(v[1, 1])  # Dec QBO missing


def test_target_names_match_layout():
    assert len(target_names()) == 4 * len(HEIGHTS) + 3


def test_liquid_rh_unchanged_when_warm_and_lower_when_cold():
    assert np.isclose(liquid_rh(np.float64(280.0), np.float64(60.0)), 60.0)
    cold = liquid_rh(np.float64(220.0), np.float64(100.0))  # ice saturation at -53 C is ~60 % over water
    assert 55 < cold < 65


def test_liquid_rh_is_continuous_and_monotone_across_the_mixed_phase_range():
    t = np.linspace(240.0, 280.0, 4001)
    r = liquid_rh(t, np.full_like(t, 80.0))
    assert np.isfinite(r).all() and np.abs(np.diff(r)).max() < 0.05  # no jump at 250.16 K or 273.16 K
    assert (np.diff(r) >= -1e-9).all() and np.allclose(r[t >= 273.16], 80.0, atol=1e-6)
