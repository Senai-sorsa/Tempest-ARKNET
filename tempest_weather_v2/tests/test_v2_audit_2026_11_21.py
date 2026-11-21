"""Regression checks for the v2 audit fixes (2026-11-21, tempest_arknet_audit.md)."""
import numpy as np
import pytest

from tempest_weather_v2 import _net
from tempest_weather_v2.montecarlo import MCResult
from tempest_weather_v2.sitecal import apply_site, fit_site
from tempest_weather_v2.stats import fit_best


def test_41_fit_best_empty_input_gives_nan_quantiles():
    out = fit_best([])
    assert out["n"] == 0 and out["type"] is None and all(np.isnan(v) for v in out["quantiles"].values())


def test_41_constant_result_has_zero_contributions():
    r = MCResult(np.full(50, 3.0), [dict(mass=float(i)) for i in range(50)], np.arange(50) % 5)
    assert all(v == 0.0 for v in r.contributions().values())


def test_26_fit_site_counts_finite_pairs():
    r = np.r_[np.linspace(1, 10, 50), np.full(200, np.nan)]
    with pytest.raises(ValueError):
        fit_site(r, r * 1.1, method="ratio")


def test_26_tied_top_knots_extrapolate_by_ratio():
    cal = dict(method="quantile", src=np.array([1.0, 5.0, 5.0]), dst=np.array([1.2, 6.0, 6.0]))
    assert apply_site(cal, np.array([10.0]))[0] == pytest.approx(12.0)


def test_41_elevation_info_restores_the_offline_setting(monkeypatch):
    from tempest_weather_v2 import Launch
    from tempest_weather_v2 import launch as L

    def boom(lat, lon):
        assert _net.is_offline()
        raise RuntimeError("no service")
    monkeypatch.setattr(L.E, "lookup", boom)
    _net.set_offline(False)
    try:
        Launch(40.0, -105.0, "2026-07-01T12:00", offline=True).elevation_info()
        assert _net._offline is False
    finally:
        _net.set_offline(None)
