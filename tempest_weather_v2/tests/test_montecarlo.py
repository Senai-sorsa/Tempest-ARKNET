"""A1: total-uncertainty harness with a toy simulator."""
import math

import numpy as np
import pytest

from tempest_weather_v2 import Launch
from tempest_weather_v2.montecarlo import MCResult, VehiclePriors, calibrate_vehicle_sigma, latin_hypercube, run


def test_latin_hypercube_has_one_point_per_stratum():
    u = latin_hypercube(50, 3, np.random.default_rng(0))
    for j in range(3):
        assert sorted(int(x * 50) for x in u[:, j]) == list(range(50))


def test_priors_sample_means_and_validation():
    p = VehiclePriors(a=("normal", 0.05), b=("lognormal", 0.1), c=("uniform", 0.2))
    s = p.sample(4000, np.random.default_rng(1))
    for k, sd in (("a", 0.05), ("b", 0.1)):
        x = np.array([d[k] for d in s])
        assert abs(x.mean() - 1.0) < 0.005 and abs(x.std() - sd) < 0.006               # mean 1 (the lognormal is mean-corrected), relative sd as asked
    c = np.array([d["c"] for d in s])
    assert 0.8 <= c.min() and c.max() <= 1.2
    with pytest.raises(ValueError):
        VehiclePriors(a=("beta", 0.1))
    with pytest.raises(ValueError):
        VehiclePriors(a=("normal", 0.0))
    with pytest.raises(ValueError):
        VehiclePriors(a=("uniform", 1.0))
    assert VehiclePriors().sample(3, np.random.default_rng(0)) == [{}, {}, {}]


def test_run_total_uncertainty_is_wider_than_atmosphere_alone_and_attributes_it():
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=120, units="si", seed=2)
    atms = L.atmospheres(120)

    def simulate(atm, drag_scale=1.0, impulse_scale=1.0):
        wind = abs(atm.wind(1401.0 + 100.0)[1]) + abs(atm.wind(1401.0 + 100.0)[2])          # a stand-in: apogee falls with the ground wind, rises with impulse, falls with drag
        return 4000.0 * impulse_scale / drag_scale - 12.0 * wind
    atm_only = run(simulate, atms, VehiclePriors(), n=120, seed=3)
    total = run(simulate, atms, VehiclePriors(drag_scale=("lognormal", 0.06), impulse_scale=("lognormal", 0.04)), n=120, seed=3)
    assert total.summary()["sd"] > 2.0 * atm_only.summary()["sd"]
    c = total.contributions()
    assert c["drag_scale"] > 0.1 and c["impulse_scale"] > 0.05 and c["drag_scale"] <= 1.0
    lo, hi = total.interval(90)
    assert lo < total.summary()["p50"] < hi and total.coverage(total.summary()["p50"]) and not total.coverage(hi + 1000.0)
    assert total.rank(total.values.min() - 1.0) == 0.0 and total.rank(total.values.max() + 1.0) == 1.0 and abs(total.rank(lo) - 0.05) < 0.02
    same = run(simulate, atms, VehiclePriors(drag_scale=("lognormal", 0.06)), n=30, seed=5)
    again = run(simulate, atms, VehiclePriors(drag_scale=("lognormal", 0.06)), n=30, seed=5)
    assert np.array_equal(same.values, again.values)                                      # reproducible
    longer = run(simulate, atms[:10], VehiclePriors(), n=25, seed=1)                      # n larger than the pool: atmospheres are reused
    assert len(longer.values) == 25


def test_run_refuses_a_non_finite_result_and_empty_input():
    with pytest.raises(ValueError, match="returned"):
        run(lambda atm: float("nan"), [object()] * 3, n=3)
    with pytest.raises(ValueError, match="no atmospheres"):
        run(lambda atm: 1.0, [], n=3)


def test_calibrate_vehicle_sigma_from_flights():
    r = calibrate_vehicle_sigma([7.7, 5.5, -2.5], [1.4, 0.9, 0.5])                        # the three testable flights (error %, atmosphere sd %)
    assert r["n"] == 3 and not r["reliable"] and abs(r["bias_pct"] - 3.567) < 0.01 and 5.4 < r["vehicle_rms_pct"] < 5.7 and 4.0 < r["vehicle_scatter_pct"] < 4.7
    assert calibrate_vehicle_sigma([0.1, -0.1], [1.0, 1.0])["vehicle_rms_pct"] == 0.0     # atmosphere spread alone explains it
    with pytest.raises(ValueError):
        calibrate_vehicle_sigma([1.0], [1.0, 2.0])


def test_adaptive_conformal_restores_coverage_of_an_overconfident_ensemble():
    from tempest_weather_v2.montecarlo import AdaptiveConformal
    rng = np.random.default_rng(0)
    raw_miss, ac = 0, AdaptiveConformal(0.10, gamma=0.02)
    n = 3000
    for _ in range(n):
        centre = rng.normal(0, 2.0)
        ens = centre + rng.normal(0, 1.0, 100)              # the ensemble spread (sd 1) is half the real error (sd 2): coverage of the central 90 % would be about 0.63
        y = centre + rng.normal(0, 2.0)
        lo, hi = np.quantile(ens, [0.05, 0.95])
        raw_miss += not (lo <= y <= hi)
        i = ac.interval(ens)
        ac.update(y, i)
    assert 1 - raw_miss / n < 0.75                          # the raw interval is over-confident
    assert abs(ac.coverage - 0.90) < 0.02 and ac.stretch > 2.0       # adaptive stretching brings it back (the ensemble is about 2x too narrow)
    with pytest.raises(ValueError):
        AdaptiveConformal(1.5)


def test_physical_atmosphere_metrics_explain_a_wind_driven_result():
    """Gemini bug 1: the share of the variance due to the atmosphere is measured with physical quantities, not the sample index."""
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=150, units="si", seed=4)
    atms = L.atmospheres(150)
    z0 = atms[0].elevation_m

    def simulate(atm, drag_scale=1.0):
        w = atm.wind(z0 + 100.0)
        return 4000.0 / drag_scale - 40.0 * float(np.hypot(w[1], w[2]))
    r = run(simulate, atms, VehiclePriors(drag_scale=("normal", 0.02)), n=300, seed=1)
    assert set(r.atm_metrics) == {"pad_air_density", "mean_wind_0_200m", "mean_wind_0_3km"}
    c = r.contributions()
    assert c["atmosphere: mean_wind_0_200m"] > 0.3 and c["atmosphere: mean_wind_0_200m"] > c["atmosphere (by its sample index; use varying atmospheres)"]
    e = r.explained()
    assert e["atmosphere_gain"] > 0.3 and e["r2_all"] >= e["r2_vehicle"]


def test_sobol_sampling_indices_and_bootstrap_band():
    """M8: scrambled Sobol sampling keeps the priors' mean / sd; Sobol indices recover a known additive model; the bootstrap band contains the estimate."""
    from tempest_weather_v2.montecarlo import bootstrap_percentile, sobol_indices
    p = VehiclePriors(a=("normal", 0.1), b=("normal", 0.1))
    s = p.sample(1024, np.random.default_rng(0), "sobol")
    x = np.array([d["a"] for d in s])
    assert abs(x.mean() - 1) < 0.005 and abs(x.std() - 0.1) < 0.005

    class Atm:                                    # a toy atmosphere reader: its number is its index scaled
        def __init__(self, k):
            self.k = k
    atms = [Atm(k / 31.0) for k in range(32)]
    sim = lambda atm, a=1.0, b=1.0: 4.0 * (a - 1.0) + 1.0 * (b - 1.0) + 0.2 * (atm.k - 0.5)            # additive: variances 0.16, 0.01, 0.2^2/12 = 0.0033
    res = sobol_indices(sim, atms, p, n=512, seed=1, n_boot=60)
    tot = 0.16 + 0.01 + 0.2 ** 2 / 12
    assert abs(res["a"]["first"] - 0.16 / tot) < 0.06 and res["a"]["first"] > 0.8
    assert abs(res["a"]["total"] - res["a"]["first"]) < 0.08                                           # additive: no interaction
    assert res["atmosphere"]["first"] < 0.08 and res["b"]["first"] < 0.12
    est, lo, hi = bootstrap_percentile(np.random.default_rng(0).normal(size=400), 95)
    assert lo < est < hi and hi - lo < 0.6


def test_wind_persistence_increment_widens_the_wind_dependent_result():
    """M2: with wind_age (rho < 1) the result spread grows by the persistence increment; rho = 1 changes nothing in the spread."""
    L = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=150, units="si", seed=4)
    atms = L.atmospheres(150)
    z0 = atms[0].elevation_m

    def sim(atm):
        w = atm.wind(z0 + 300.0)
        return float(w[1])
    nh = len(atms.samples["height_agl"])
    base = run(sim, atms, n=300, seed=1)
    same = run(sim, atms, n=300, seed=1, wind_age=np.ones(nh), conditioned=True)
    wide = run(sim, atms, n=300, seed=1, wind_age=np.full(nh, 0.7), conditioned=True)
    with pytest.raises(ValueError):
        run(sim, atms, n=10, seed=1, wind_age=np.full(nh, 0.7))                  # not declared conditioned: refused
    assert abs(same.values.std() / base.values.std() - 1) < 0.02
    assert wide.values.std() > 1.2 * base.values.std()
