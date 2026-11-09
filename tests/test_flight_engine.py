"""Stage 6, modules 1 and 2: Sobol-driven eigen sampler and measurement conditioning, on a synthetic pool with known structure."""
import numpy as np
import pytest

from tempest_weather import _core
from tempest_weather.flight import TempestFlightSimEngine

NH = _core.NH


def synthetic_pool(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    z = np.asarray(_core.HEIGHTS, float)
    drive = rng.standard_normal((n, 3))
    u = 5 + 3 * drive[:, :1] * np.exp(-z / 6000)[None] + 0.3 * rng.standard_normal((n, NH))
    v = 1 + 2 * drive[:, 1:2] * np.exp(-z / 6000)[None] + 0.3 * rng.standard_normal((n, NH))
    T = 288 - 0.0065 * z[None] + 2 * drive[:, 2:3] + 0.2 * rng.standard_normal((n, NH))
    RH = np.clip(40 + 10 * drive[:, 2:3] + 3 * rng.standard_normal((n, NH)), 1, 99)
    return dict(u=u, v=v, T=T, RH=RH, t2m=T[:, 0] + 0.3, sp=95000 - 300 * drive[:, 0], rh2m=RH[:, 0])


def test_sobol_modes_keep_marginals_and_correlation_and_are_reproducible():
    qmc = pytest.importorskip("scipy.stats.qmc")
    eng = TempestFlightSimEngine(atm=synthetic_pool(), info={"elevation_m": 1300.0})
    u = qmc.Sobol(8, scramble=True, seed=1).random(4096)
    b = eng.sample_sobol(u)
    assert np.allclose(b["T"].mean(0), eng.atm["T"].mean(0), atol=0.15) and np.allclose(b["T"].std(0), eng.atm["T"].std(0), rtol=0.1)
    c_pool = np.corrcoef(eng.atm["u"][:, 0], eng.atm["u"][:, 20])[0, 1]
    c_gen = np.corrcoef(b["u"][:, 0], b["u"][:, 20])[0, 1]
    assert abs(c_pool - c_gen) < 0.05
    assert np.array_equal(b["u"], eng.sample_sobol(u)["u"])                            # same uniforms -> same profiles
    assert np.isfinite(b["rho"]).all() and (b["RH"] >= 0).all() and (b["RH"] <= 100).all()


def test_conditioning_pins_observations_moves_the_rest_and_shrinks_the_spread():
    eng = TempestFlightSimEngine(atm=synthetic_pool(), info={"elevation_m": 1300.0})
    u = np.random.default_rng(2).random((3000, 12))
    free = eng.sample_sobol(u)
    eng.condition_on_observations({("wind_u", 10.0): 9.0, ("temp_K", 2.0): 292.0})
    b = eng.sample_sobol(u)
    assert np.allclose(b["u"][:, 0], 9.0) and np.allclose(b["t2m"], 292.0)             # observed values pinned exactly
    assert b["u"][:, 10].mean() > free["u"][:, 10].mean() + 1.0                          # a strong wind at 10 m raises the wind above it (shared driver)
    assert b["u"][:, 10].std() < 0.7 * free["u"][:, 10].std()                            # and the spread shrinks
    assert np.allclose(eng.sample_sobol(None)["u"][0, 0], 9.0)
    with pytest.raises(KeyError):
        eng.condition_on_observations({("wind_u", 12.0): 1.0})                          # not a model height


def test_weights_alternative_reports_effective_sample_size():
    eng = TempestFlightSimEngine(atm=synthetic_pool(), info={"elevation_m": 1300.0})
    _, ess_soft = eng.observe_by_weights({("wind_u", 10.0): 5.0}, 2.0, 500)
    _, ess_hard = eng.observe_by_weights({("wind_u", 10.0): 5.0, ("temp_K", 2.0): 290.0, ("wind_v", 10.0): 1.0}, 0.05, 500)
    assert ess_soft > 20 * ess_hard and ess_hard < 30


def test_one_call_contract_returns_coarse_fine_and_avionics_columns():
    eng = TempestFlightSimEngine(atm=synthetic_pool(n=1500), info={"elevation_m": 1400.0})
    u = np.random.default_rng(4).random((6, 10))
    b = eng.sample_sobol_batch(u, k_atmo=6, dz_fine_m=20.0)
    assert b["u"].shape == (6, NH) and b["fine"]["u_total"].shape[0] == 6 and b["fine"]["z"][1] - b["fine"]["z"][0] == 20.0
    assert np.abs(b["fine"]["gust_u"]).max() + np.abs(b["fine"]["gust_v"]).max() > 0          # the last four columns placed a gust
    a = b["avionics"]
    assert a["altimeter_bias_m"].shape == (6, NH + 1) and np.isfinite(a["refractivity_N"]).all()


def test_localisation_taper_is_opt_in_and_limits_the_reach_of_an_observation():
    """G1: off = unchanged; on = a pinned 10 m wind moves levels near it as before and far levels much less."""
    from tempest_weather.flight.engine import _gaspari_cohn
    assert _gaspari_cohn(0.0, 1000.0) == 1.0 and _gaspari_cohn(2500.0, 1000.0) == 0.0 and 0 < _gaspari_cohn(1000.0, 1000.0) < 1
    pool = synthetic_pool()
    u = np.random.default_rng(2).random((3000, 12))
    obs = {("wind_u", 10.0): 9.0}
    a = TempestFlightSimEngine(atm=pool, info={"elevation_m": 1300.0}).condition_on_observations(obs).sample_sobol(u)
    a2 = TempestFlightSimEngine(atm=pool, info={"elevation_m": 1300.0}).condition_on_observations(obs, localize_m=None).sample_sobol(u)
    b = TempestFlightSimEngine(atm=pool, info={"elevation_m": 1300.0}).condition_on_observations(obs, localize_m=500.0).sample_sobol(u)
    assert np.array_equal(a["u"], a2["u"])
    free = TempestFlightSimEngine(atm=pool, info={"elevation_m": 1300.0}).sample_sobol(u)
    far = 20
    assert abs(b["u"][:, far].mean() - free["u"][:, far].mean()) < 0.3 * abs(a["u"][:, far].mean() - free["u"][:, far].mean())
    assert np.allclose(b["u"][:, 0], 9.0)


def test_dryden_reynolds_stress_is_opt_in_and_keeps_the_vertical_variance():
    """G6: uw_corr anticorrelates w' with the along-wind u' near the ground, fading with height; default unchanged."""
    from tempest_weather.flight import dryden
    z = np.array([10, 50, 100, 200, 500, 1000, 2000.0])
    N = 800
    u, v, T = np.tile(8 + 0 * z, (N, 1)), np.zeros((N, 7)), np.tile(290 - 0.0065 * z, (N, 1))
    a = dryden.synthesize(z, u, v, T, seed=1)
    a0 = dryden.synthesize(z, u, v, T, seed=1, uw_corr=None)
    b = dryden.synthesize(z, u, v, T, seed=1, uw_corr=0.35)
    assert np.array_equal(a["w_turb"], a0["w_turb"])
    i50, i1500 = np.searchsorted(b["z"], 50), np.searchsorted(b["z"], 1500)
    c = lambda r, i: np.corrcoef(r["u_turb"][:, i], r["w_turb"][:, i])[0, 1]
    assert c(b, i50) < -0.2 and abs(c(a, i50)) < 0.15 and abs(c(b, i1500)) < 0.15
    assert abs(b["w_turb"][:, i50].std() / a["w_turb"][:, i50].std() - 1) < 0.1
