"""G0 locks and encoders (docs/plans/GLOBAL_PLAN.md G0)."""
import numpy as np
import pytest

from tempest.geo import holdout
from tempest.geo.sh import sh


def test_holdout_refuses_places_and_window(monkeypatch):
    monkeypatch.delenv("TEMPEST_FINAL_GLOBAL", raising=False)
    holdout.check([35.0, -10.0], [-106.0, 60.0], np.array(["2025-12-31T23", "2026-06-30T12"], "datetime64[h]"))  # Denver-ish, ocean: fine
    with pytest.raises(holdout.HoldoutError):
        holdout.check([37.9], [-75.0])                                 # Wallops (0.4 deg away)
    with pytest.raises(holdout.HoldoutError):
        holdout.check([8.0], [167.7 - 360])                            # Kwajalein across the date line
    lat, lon, r = holdout.places()
    assert len(lat) == 11 and r == 1.0                                 # 4 sites + 7 IGRA stations
    with pytest.raises(holdout.HoldoutError):
        holdout.check(lat[4:5], lon[4:5])                              # a held IGRA station
    with pytest.raises(holdout.HoldoutError):
        holdout.check(times=np.array(["2026-07-01"], "datetime64[D]"))
    monkeypatch.setenv("TEMPEST_FINAL_GLOBAL", "1")
    holdout.check([37.9], [-75.5], np.array(["2026-08-01"], "datetime64[D]"))  # G6 only


def test_sh_finite_at_poles():
    y = sh(np.array([90.0, -90.0, 90.0]), np.array([0.0, 0.0, 123.0]), 10)
    assert np.isfinite(y).all() and np.allclose(y[0], y[2])            # the pole value does not depend on longitude


def test_statics_sane():
    import os
    from tempest.geo import statics
    if not os.path.exists(statics.INV):
        pytest.skip("ERA5 invariants not on disk")
    s = statics.statics([27.99, 0.0, 39.74, 39.74], [86.93, -30.0, -104.99, -104.99 + 360])  # Everest, mid-Atlantic, Denver twice
    assert s["oro_m"][0] > 4000 and s["lsm"][1] == 0 and s["coast_km"][1] < -500 < 0 < s["coast_km"][2]
    assert all(np.allclose(v[2], v[3]) for v in s.values())             # longitude wrap
    assert all(np.isfinite(v).all() for v in s.values())


def test_clim_recovers_known_cycle():
    from tempest.geo import clim
    rng = np.random.default_rng(0)
    t = np.datetime64("2001-01-01T00") + rng.integers(0, 24 * 365 * 15, 20000).astype("timedelta64[h]")
    X = clim.basis(t, -105.0)
    doy, lst = np.arctan2(X[:, 10], X[:, 5]), np.arctan2(X[:, 2], X[:, 1])  # sin/cos of annual h1 and diurnal h1
    mu = 10 + 8 * np.cos(doy) + 3 * np.sin(lst)
    sd = 2 + np.cos(doy)
    y = np.stack([mu + sd * rng.standard_normal(len(t)), np.full(len(t), 5.0)], 1)
    c = clim.fit(t, -105.0, y)
    m, s = clim.predict(c, t, -105.0)
    assert np.abs(m[:, 0] - mu).max() < 0.3 and np.abs(s[:, 0] / sd - 1).mean() < 0.06 and np.allclose(m[:, 1], 5, atol=1e-6)
    with pytest.raises(ValueError):
        clim.fit(np.array(["2026-01-01"] * 200, "datetime64[h]"), 0.0, np.zeros(200))
