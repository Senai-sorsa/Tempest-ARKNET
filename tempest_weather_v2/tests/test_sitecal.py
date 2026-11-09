"""M6 site calibration (measure-correlate-predict)."""
import numpy as np
import pytest

from tempest_weather_v2.sitecal import apply_site, fit_site


def make(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    hours = np.arange(n) % 24
    ref = rng.weibull(2.0, n) * 4.0 + 0.2
    true_factor = 0.6 + 0.8 * (np.sin((hours - 9) / 24 * 2 * np.pi) > 0)         # the site is calmer at night than the reference, windier by day
    site = ref * true_factor * (1 + rng.normal(0, 0.1, n))
    return ref, site, hours, true_factor


def test_ratio_hourly_and_quantile_remove_the_bias_and_hourly_wins_on_error():
    ref, site, hours, tf = make()
    ref2, site2, hours2, _ = make(seed=5)
    err = {}
    for m in ("ratio", "hourly", "quantile"):
        cal = fit_site(ref, site, hours, method=m)
        c = apply_site(cal, ref2, hours2)
        err[m] = (np.abs(c - site2).mean(), (c - site2).mean())
        assert abs((c - site2).mean()) < 0.25                                   # bias small
    assert err["hourly"][0] < err["ratio"][0] * 0.8                             # the day/night structure is learned
    cal = fit_site(ref, site, hours, method="hourly")
    assert cal["hourly"].shape == (24,) and abs(cal["hourly"][3] - 0.6) < 0.1 and abs(cal["hourly"][15] - 1.4) < 0.1


def test_quantile_map_is_monotone_and_validation():
    ref, site, hours, _ = make()
    cal = fit_site(ref, site, method="quantile")
    x = np.linspace(0, 20, 200)
    y = apply_site(cal, x)
    assert (np.diff(y) >= -1e-9).all()
    with pytest.raises(ValueError):
        fit_site(ref, site, method="bogus")
    with pytest.raises(ValueError):
        fit_site(ref, site, method="hourly")                                    # hours missing
    with pytest.raises(ValueError):
        fit_site(ref[:50], site[:50], hours[:50])
    with pytest.raises(ValueError):
        apply_site(fit_site(ref, site, hours, method="hourly"), ref)
