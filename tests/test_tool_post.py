"""The tool's optional shape post-processing: marginals stay, order across columns follows the template, missing assets leave samples alone."""
import numpy as np

from tempest_weather import api


def test_post_process_keeps_marginals_and_skips_without_assets():
    rng = np.random.default_rng(0)
    x = (rng.normal(size=(2, 30, 179)) * 3 + 50).astype(np.float32)
    assert api._post_process({"post": None}, x, 190, 15.0) is x
    tpl = np.zeros((144, 199, 179), np.float16)
    month, hb = int(190 / 365.25 * 12) % 12, int(15.0 / 2) % 12
    tpl[month * 12 + hb, :30] = rng.normal(size=(30, 179))
    tpl[month * 12 + hb, 30:] = rng.normal(size=(169, 179))
    y = api._post_process({"post": {"tpl": tpl[:, :30]}}, x, 190, 15.0)
    assert np.allclose(np.sort(y, axis=1), np.sort(x, axis=1))                         # every column keeps its values
    assert not np.array_equal(y, x)
    empty = api._post_process({"post": {"tpl": np.zeros((144, 30, 179), np.float16)}}, x, 190, 15.0)
    assert np.array_equal(empty, x)                                                   # an empty template bin changes nothing


def test_rank_templates_equal_value_templates():
    from tempest_weather import _core
    rng = np.random.default_rng(3)
    x = rng.normal(size=(2, 40, 12))
    tpl = rng.normal(size=(2, 40, 12))
    ranks = np.argsort(np.argsort(tpl, axis=1), axis=1).astype(np.uint8)
    assert np.array_equal(_core.shuffle_apply_ranks(x, ranks), _core.shuffle_apply(x, tpl))


def test_bias_gate_and_wind_rescale():
    from tempest_weather import bias
    st = {"site": "x", "model": "m", "lat": 32.0, "lon": -102.0, "updated": "2026-01-01",
          "temperature_2m": {"1": {"b": [1.0] * 24, "n": [30] * 12 + [5] * 12, "se": [0.1] * 24}},
          "wind_speed_10m": {"1": {"b": [-1.0] * 24, "n": [30] * 24, "se": [0.1] * 12 + [5.0] * 12}}}
    assert bias.correction(st, "temperature_2m", 1.2, 3) == 1.0                  # enough updates, bias well above its error
    assert bias.correction(st, "temperature_2m", 1.2, 15) == 0.0                 # too few updates
    assert bias.correction(st, "wind_speed_10m", 1.0, 20) == 0.0                 # bias inside two standard errors
    f = dict(t2m=290.0, u10=3.0, v10=4.0)
    dT, dW = bias.apply_to_fields(f, st, 1.0, 3)
    assert abs(f["t2m"] - 289.0) < 1e-9 and abs(np.hypot(f["u10"], f["v10"]) - 6.0) < 1e-9 and abs(f["u10"] / f["v10"] - 0.75) < 1e-9
    assert bias.find(None, 32.0, -102.0) is None


def test_wind_widening_scales_low_levels_only_and_keeps_ranks():
    from tempest_weather import bias
    rng = np.random.default_rng(0)
    nh = 44
    h = np.r_[10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000, np.arange(2500, 18001, 500)].astype(float)
    phys = np.zeros((500, 4 * nh + 3))
    phys[:, :nh] = 5 + rng.normal(0, 1.0, (500, 1)) * np.ones(nh)
    phys[:, nh:2 * nh] = 2 + rng.normal(0, 1.0, (500, 1)) * np.ones(nh)
    before = phys.copy()
    st = {"wind_speed_10m": {"2": {"b": [0.0] * 24, "n": [40] * 24, "se": [0.1] * 24, "sd": [2.5] * 24}}}
    k0 = bias.widen_wind(phys, st, 2.0, 12, nh, heights=h)
    assert 1.5 < k0 <= 2.2
    assert phys[:, 0].std() > 1.5 * before[:, 0].std()                             # 10 m widened
    assert np.allclose(phys[:, -8:-3], before[:, -8:-3])                           # nothing but the wind blocks touched
    assert abs(phys[:, nh - 1].std() - before[:, nh - 1].std()) < 0.01 * before[:, nh - 1].std() + 1e-6      # 18 km unchanged
    assert np.array_equal(np.argsort(phys[:, 0]), np.argsort(before[:, 0])) or np.corrcoef(phys[:, 0], before[:, 0])[0, 1] > 0.999
    assert bias.widen_wind(phys.copy(), st, 2.0, 12, nh, heights=h) >= 1.0
    assert bias.widen_wind(before.copy(), {"wind_speed_10m": {"2": {"n": [5] * 24, "sd": [9.0] * 24}}}, 2.0, 12, nh, heights=h) == 1.0   # too few updates: nothing


def test_hourly_coherence_keeps_marginals_and_hits_the_lag_correlation():
    from tempest_weather import coherence
    rng = np.random.default_rng(0)
    n, D, offs = 4000, 6, [-3, 0, 1, 4]
    rho = np.tile(np.array([1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3])[:, None], (1, D))
    samples = [rng.normal(m, s, (n, D)) for m, s in ((0, 1), (5, 2), (-3, 0.5), (1, 3))]
    out = coherence.sequence(samples, offs, rho, rng)
    for s, o in zip(samples, out):
        assert np.allclose(np.sort(s, 0).mean(0), np.sort(o, 0).mean(0), atol=0.05) and np.allclose(s.std(0), o.std(0), rtol=0.05)      # every hour keeps its marginal
    for (i, a), (k, b) in (((0, offs[0]), (1, offs[1])), ((1, offs[1]), (2, offs[2])), ((0, offs[0]), (3, offs[3]))):
        want = rho[abs(a - b), 0]
        got = np.corrcoef(norm_scores(out[i][:, 0]), norm_scores(out[k][:, 0]))[0, 1]
        assert abs(got - want) < 0.04, (a, b, got, want)


def norm_scores(x):
    from tempest_weather.distributions import norm_ppf
    return norm_ppf((np.argsort(np.argsort(x)) + 0.5) / len(x))


def test_coherence_nugget_lowers_the_correlation_between_hours_only():
    from tempest_weather import coherence
    rng = np.random.default_rng(5)
    n, D = 6000, 3
    rho = np.tile(np.array([1.0, 0.9, 0.8])[:, None], (1, D))
    s = [rng.normal(0, 1, (n, D)) for _ in range(2)]
    out = coherence.sequence(s, [0, 2], rho, rng, kappa=np.full(D, 0.8))
    got = np.corrcoef(norm_scores(out[0][:, 0]), norm_scores(out[1][:, 0]))[0, 1]
    assert abs(got - 0.8 * 0.8) < 0.04
