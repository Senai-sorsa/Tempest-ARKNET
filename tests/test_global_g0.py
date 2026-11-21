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
