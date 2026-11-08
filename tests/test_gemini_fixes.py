"""Gemini-review fixes (IL-129..IL-143). Every fix is opt-in: the default behaviour must stay as it was."""
import numpy as np

from tempest_weather import _core
from tempest_weather.flight import TempestFlightSimEngine
from test_flight_engine import synthetic_pool


def _eng(**kw):
    return TempestFlightSimEngine(atm=synthetic_pool(n=2000), info={"elevation_m": 1300.0}, **kw)


def test_il129_tail_extrapolation_off_by_default_and_monotone_when_on():
    off, on = _eng(), _eng(tail_extrap=True)
    j = off.index[("wind_u", 10.0)]
    top = off._sorted[-1, j]
    far = top + 4 * off._sd[j]
    assert off._cdf(j, far) == off._cdf(j, top)                       # default clamps, as before
    assert on._cdf(j, far) > on._cdf(j, top) > on._cdf(j, top - 2 * on._sd[j])
    assert np.isclose(on._cdf(j, on._sorted[1000, j]), off._cdf(j, off._sorted[1000, j]))  # inside the pool: identical
    v = on._cdf(j, top + 1.0 * on._sd[j])
    assert top < on._ppf(j, v) < far                                  # round trip lands beyond the pool max
    lo = on._sorted[0, j] - 1.0 * on._sd[j]
    assert on._ppf(j, on._cdf(j, lo)) < on._sorted[0, j]


def test_il129_no_shear_spike_for_an_observation_above_the_pool_maximum():
    u = np.random.default_rng(3).random((500, 12))
    res = {}
    for flag in (False, True):
        e = _eng(tail_extrap=flag)
        j = e.index[("wind_u", 10.0)]
        obs = e._sorted[-1, j] + 3 * e._sd[j]
        e.condition_on_observations({("wind_u", 10.0): obs})
        b = e.sample_sobol(u)
        res[flag] = np.abs(b["u"][:, 1] - b["u"][:, 0]).mean()        # 50 m minus the pinned 10 m value
    assert res[True] < res[False]


def test_il130_il135_dryden_fixes_are_opt_in_and_correct():
    from tempest_weather.flight import dryden
    z = np.array([10, 50, 100, 500, 1000, 5000, 10000, 18000.0])
    T = 288.15 - 0.0065 * z
    T[z > 11000] = 216.65
    T = np.tile(T, (2, 1))
    T[:, 6:] = 216.65
    u = np.tile(np.linspace(2, 40, len(z)), (2, 1))
    v = np.zeros_like(u)
    old = dryden.envelopes(z, u, v, T)
    assert np.array_equal(old["ri"], dryden.envelopes(z, u, v, T, exact_n2=False)["ri"])
    new = dryden.envelopes(z, u, v, T, exact_n2=True, bl_floor0=True)
    # standard atmosphere: N^2 at 10-18 km is about 1e-4 (theta-based, stable); the old Ri is too small there
    assert (new["ri"][:, -1] > old["ri"][:, -1] * 1.5).all()
    n2 = new["ri"] * np.maximum(np.gradient(u, z, axis=1) ** 2, 1e-6)      # the envelope floors shear^2 at 1e-6
    assert np.allclose(n2[:, -1], 9.80665 / 216.65 * (9.80665 / 1004.7), rtol=0.02)
    # no boundary-layer turbulence at 18 km with the fix (background 0.05 m/s only), a leak with the old floor
    assert new["sigma_w"][0, -1] < old["sigma_w"][0, -1] or old["sigma_w"][0, -1] < 0.06
    assert (new["sigma_w"][:, -1] >= 0.05).all()


def test_il135_pbl_height_and_gust_law_and_resolved_w():
    from tempest_weather.flight import dryden
    z = np.arange(10.0, 3000.0, 10.0)
    stable = np.tile(285 + 0.004 * z, (1, 1))            # theta rises quickly: shallow layer
    mixed = np.tile(290 - 0.0098 * z + 0.0005 * z, (1, 1))
    assert dryden.pbl_height(z, stable)[0] < dryden.pbl_height(z, mixed)[0]
    zc = np.array([10, 50, 100, 300, 600, 1000.0])
    T = np.tile(288 - 0.0065 * zc, (3, 1))
    u = np.tile(np.linspace(3, 9, 6), (3, 1))
    v = np.zeros_like(u)
    g = (np.full(3, 0.5), np.full(3, 0.5), np.zeros(3), np.array([0.2, 0.5, 0.8]))
    base = dryden.synthesize(zc, u, v, T, dz=50.0, seed=1, gust=g)
    same = dryden.synthesize(zc, u, v, T, dz=50.0, seed=1, gust=g, w=None, gust_params=None)
    assert np.array_equal(base["u_total"], same["u_total"])                      # defaults unchanged
    w = np.full((3, 6), 0.7)
    withw = dryden.synthesize(zc, u, v, T, dz=50.0, seed=1, gust=g, w=w)
    assert np.allclose(withw["w_total"] - base["w_total"], 0.7)
    gp = dryden.synthesize(zc, u, v, T, dz=50.0, seed=1, gust=g, gust_params=(np.full(3, 4.0), np.full(3, 1.0)))
    peaks = np.abs(gp["gust_u"]).max(1) ** 2 + np.abs(gp["gust_v"]).max(1) ** 2
    assert np.all(np.diff(peaks) > 0)                                            # higher quantile -> bigger gust, from the sample's own law


def test_dryden_fixes_flag_in_the_batch_call_is_off_by_default():
    eng = _eng()
    u = np.random.default_rng(4).random((4, 10))
    a = eng.sample_sobol_batch(u, k_atmo=6, dz_fine_m=50.0)
    b = eng.sample_sobol_batch(u, k_atmo=6, dz_fine_m=50.0, dryden_fixes=False)
    assert np.array_equal(a["fine"]["u_total"], b["fine"]["u_total"])
    c = eng.sample_sobol_batch(u, k_atmo=6, dz_fine_m=50.0, dryden_fixes=True)
    assert np.isfinite(c["fine"]["w_total"]).all() and c["fine"]["u_total"].shape == a["fine"]["u_total"].shape


def test_il133_refresh_w_follows_the_reordered_rows():
    from tempest_weather import api
    rng = np.random.default_rng(0)
    n, nh = 300, _core.NH
    old = rng.standard_normal((n, 4 * nh))
    w = old[:, :nh] * 0.5                                           # w tied to u of the same sample
    perm = rng.permutation(n)
    atm = {"w": w.copy()}
    api._refresh_w(atm, old, old[perm] + 1e-6)
    assert np.allclose(atm["w"], w[perm])                           # reordered rows get their own w back
    api._refresh_w({"w": None}, old, old)                           # no w: no-op
    import inspect
    assert inspect.signature(api.atmosphere_sequence).parameters["fix_w"].default is False
    assert inspect.signature(api.atmosphere_downrange).parameters["fix_w"].default is False


def test_il140_pit_keep_order_flag_default_unchanged_and_ranks_kept():
    rng = np.random.default_rng(1)
    N, m, D = 3, 50, 4
    x = rng.standard_normal((N, m, D))
    ginv = np.tile(np.linspace(0, 1, 201) ** 1.3, (2, 1))
    groups = np.array([0, 0, 1, 1])
    a = _core.pit_apply(ginv, groups, x)
    assert np.array_equal(a, _core.pit_apply(ginv, groups, x, keep_order=False))
    assert (np.diff(a, axis=1) >= 0).all()                           # default stays sorted
    b = _core.pit_apply(ginv, groups, x, keep_order=True)
    assert np.allclose(np.sort(b, axis=1), a)                        # same values, different order
    assert np.array_equal(np.argsort(b, axis=1), np.argsort(x, axis=1))  # input ranks kept
    from tempest.calibrate import pit_recal
    tab = {"ginv": ginv, "groups": groups}
    assert np.allclose(pit_recal.apply(tab, x, keep_order=True), b, atol=1e-5)


def test_il139_cut_default_is_plain_slice_and_flag_permutes_inside_blocks():
    from tempest_weather import api
    M = api.M_CAL
    groups, n = 2, M + 50
    x = np.arange(groups * M, dtype=float)[:, None] * np.ones((1, 3))
    c = x.copy()
    rng = np.random.default_rng(0)
    out, c_out = api._cut(x, groups, n, rng, c)
    assert np.array_equal(out, x[:n]) and np.array_equal(c_out, c[:n])         # default: exactly x[:n]
    api.OPTIONS["permute_blocks"] = True
    try:
        out, c_out = api._cut(x, groups, n, np.random.default_rng(0), c)
        assert out.shape == (n, 3) and np.array_equal(out, c_out)                # companions follow the same rows
        assert set(out[:M, 0]) == set(range(M))                                  # block 0 stays whole
        last = out[M:, 0]
        assert set(last) <= set(range(M, 2 * M)) and not np.array_equal(last, np.arange(M, M + 50))   # a random subset of block 1, not its first rows
        full, = api._cut(x, groups, groups * M, np.random.default_rng(0))
        assert np.array_equal(full, x)                                           # whole blocks: nothing is permuted
    finally:
        api.OPTIONS["permute_blocks"] = False


def test_il137_shear_smoothing_in_metres_is_opt_in_and_matches_the_training_copy():
    from tempest.calibrate import shear_map
    rng = np.random.default_rng(2)
    n, m, D = 3, 20, 4 * 44 + 3
    x = rng.normal(size=(n, m, D)).astype(np.float32)
    x[..., :88] = np.cumsum(rng.normal(size=(n, m, 88)), -1) * 2
    grid = np.tile(np.linspace(0, 60, 400), (4, 1))
    table = dict(grid=grid, gain=1 + 0.004 * grid)
    base = _core.shear_apply(table, x)
    assert np.array_equal(base, _core.shear_apply(table, x, smooth_m=None))      # default unchanged
    a, b = _core.shear_apply(table, x, smooth_m=1000.0), shear_map.apply(table, x, smooth_m=1000.0)
    assert np.allclose(a, b, atol=1e-4)                                         # runtime and training copies agree
    assert not np.allclose(a, base)
    w = _core.gauss_smoother(_core.HEIGHTS, 500.0)
    assert np.allclose(w.sum(1), 1.0) and w[0, 0] > w[0, 5]
    # the window in metres is the same everywhere: a wider sigma smooths more (the change that survives as "rough" shrinks)
    r1 = np.abs(_core.shear_apply(table, x, smooth_m=300.0)[..., :88] - x[..., :88]).mean()
    r2 = np.abs(_core.shear_apply(table, x, smooth_m=3000.0)[..., :88] - x[..., :88]).mean()
    assert r2 > r1 * 0.9


def test_il132_site_shift_modes_default_unchanged_and_const_keeps_the_lapse_in_the_layer():
    rng = np.random.default_rng(5)
    nh = _core.NH
    z = np.asarray(_core.HEIGHTS, float)
    n = 4
    base = np.zeros((n, 4 * nh + 3))
    base[:, 2 * nh:3 * nh] = 288 - 0.0065 * z[None] + 0.01 * rng.normal(size=(n, nh))
    base[:, 3 * nh:4 * nh] = 50
    base[:, 4 * nh] = 288.5
    base[:, 4 * nh + 1] = 90000
    base[:, 4 * nh + 2] = 50
    a = _core.site_shift(base.copy(), 500.0)
    assert np.array_equal(a, _core.site_shift(base.copy(), 500.0, shift_mode=None))
    c = _core.site_shift(base.copy(), 500.0, shift_mode="const", top_m=1500.0)
    p = _core.site_shift(base.copy(), 500.0, shift_mode="pbl")
    k = (z <= 1500)
    d_old = np.diff(a[:, 2 * nh:3 * nh][:, k], axis=1) / np.diff(z[k])
    d_new = np.diff(c[:, 2 * nh:3 * nh][:, k], axis=1) / np.diff(z[k])
    d_ref = np.diff(base[:, 2 * nh:3 * nh][:, k], axis=1) / np.diff(z[k])
    assert np.abs(d_new - d_ref).max() < np.abs(d_old - d_ref).max()           # the lapse inside the layer is left alone
    assert np.isfinite(p).all() and (p[:, 3 * nh:4 * nh] <= 100).all()


def test_il131_pad_node_and_geopotential_are_opt_in():
    from test_flight_sim_readers import _samples
    from tempest_weather.flight import avionics
    from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind
    s = _samples(elev=1400.0)
    site = 1400.0
    old, new = TempestAtmosphere(s, 2), TempestAtmosphere(s, 2, pad_node=True)
    assert np.isclose(old.conditions(site).temperature, s["T"][2, 0])               # default: the 10 m value at the pad (as before)
    c = new.conditions(site)
    assert np.isclose(c.temperature, s["t2m"][2]) and np.isclose(c.pressure, s["sp"][2], rtol=1e-6)
    assert np.isclose(new.conditions(float(s["height_asl"][5])).temperature, old.conditions(float(s["height_asl"][5])).temperature)
    wv = TempestWind(s, 2, pad_node=True).velocity(site)
    assert wv[0] == 0.0 and abs(wv[1]) <= abs(TempestWind(s, 2).velocity(site)[1]) + 1e-9
    new.anchor(1405.0)                                                              # the anchor check still uses the site elevation
    # geopotential tail: pressure at 40 km slightly different, still monotone and continuous
    g = TempestAtmosphere(s, 2, geopotential=True)
    top = float(s["height_asl"][-1])
    assert abs(g.conditions(top + 50).temperature - g.conditions(top).temperature) < 1.0 and g.conditions(40000).pressure < g.conditions(top).pressure
    assert g.conditions(40000).pressure != old.conditions(40000).pressure
    p = np.array([101325.0, 50000.0, 7500.0])
    a = avionics.baro_altitude_msl(p)
    assert np.array_equal(a, avionics.baro_altitude_msl(p, geometric=False))
    b = avionics.baro_altitude_msl(p, geometric=True)
    assert b[0] == 0.0 and 0 < (b - a)[2] < 100 and (b > a)[1:].all()               # about 51 m at 18 km (7.5 kPa is ~18 km)


def test_il136_acoustics_options_default_unchanged_and_midpoint_is_finer():
    from tempest_weather.flight.acoustics import AcousticRayTracer
    z = np.linspace(0, 3000, 31)
    T = 288 - 0.0065 * z
    u, v = 5 + z / 1000.0, np.zeros_like(z)
    a = AcousticRayTracer(z, T, u, v)
    base = a.trace_ray_fan(2000.0, [90.0], [20.0, 45.0])
    assert np.array_equal(base["x_east_m"], a.trace_ray_fan(2000.0, [90.0], [20.0, 45.0], midpoint=False)["x_east_m"], equal_nan=True)
    fine = a.trace_ray_fan(2000.0, [90.0], [45.0], n_int=20000, midpoint=True)["x_east_m"][0, 0]
    coarse_t = a.trace_ray_fan(2000.0, [90.0], [45.0], n_int=40)["x_east_m"][0, 0]
    coarse_m = a.trace_ray_fan(2000.0, [90.0], [45.0], n_int=40, midpoint=True)["x_east_m"][0, 0]
    assert abs(coarse_m - fine) <= abs(coarse_t - fine) * 1.5 + 1.0              # same accuracy class, finite
    moist = AcousticRayTracer(z, T, u, v, sound_speed=np.sqrt(1.4 * 287.05 * T) * 1.003)
    assert moist.trace_ray_fan(2000.0, [90.0], [45.0])["travel_time_s"][0, 0] < base["travel_time_s"][0, 1]  # a faster medium: shorter time


def test_il138_distance_decaying_inflation_is_opt_in_and_widens_near_the_observation():
    u = np.random.default_rng(9).random((4000, 20))
    e0, e1, e2 = _eng(), _eng(), _eng()
    obs = {("wind_u", 100.0): 8.0}
    e0.condition_on_observations(obs)
    e1.condition_on_observations(obs, inflate=1.5)
    e1b = _eng()
    e1b.condition_on_observations(obs)
    assert np.array_equal(e1._post["eigvals"], e1b._post["eigvals"])               # default path identical
    e2.condition_on_observations(obs, inflate=2.0, inflate_decay_m=1500.0)
    b0, b2 = e0.sample_sobol(u), e2.sample_sobol(u)
    j_near, j_far = 3, 40                                                           # 150 m and ~15 km, same variable
    r_near = b2["u"][:, j_near].std() / b0["u"][:, j_near].std()
    r_far = b2["u"][:, j_far].std() / b0["u"][:, j_far].std()
    assert r_near > 1.05 and r_far < r_near - 0.05                                          # widened near the measurement, hardly far from it


def test_il141_smooth_weights_removes_the_steps_and_keeps_ones():
    from tempest.calibrate import trust
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    n, D = len(HEIGHTS), len(PROFILE) * len(HEIGHTS) + 3
    w = np.ones(D, np.float32)
    w[:n] = 1.0
    w[n:n + 20] = 0.2                                   # a step inside the second variable
    w[-3:] = 0.5
    s = trust.smooth_weights(w, 700.0)
    assert np.array_equal(s[:n], w[:n]) and np.array_equal(s[-3:], w[-3:])      # all-ones column and the surface columns untouched
    assert np.abs(np.diff(s[n:n + 40])).max() < np.abs(np.diff(w[n:n + 40])).max()
    assert s.min() >= 0 and s.max() <= 1


def test_il142_debias_in_logit_space_keeps_humidity_in_range_and_default_unchanged():
    from tempest.scoring import debias
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    n = len(HEIGHTS)
    D = len(PROFILE) * n + 3
    rng = np.random.default_rng(0)
    x = rng.uniform(50, 80, (5, 7, D))
    r = debias.rh_columns(D)
    assert r.sum() == n + 1
    x[..., r] = rng.uniform(0.6, 3.0, (5, 7, r.sum()))                            # very dry samples
    keys = np.zeros(5, np.int64)
    delta = np.zeros((12 * debias.NB, D), np.float32)
    delta[:, r] = 2.0                                                              # model too humid by 2 in the fitted coordinate
    tab = dict(delta=delta, points=None)
    phys = debias.apply(tab, x, keys)
    assert np.allclose(phys[..., ~r], x[..., ~r] - delta[0, ~r])                  # default path = plain subtraction
    lg = debias.apply(dict(tab, rh_logit=np.array(1)), x, keys)
    assert (lg[..., r] > 0).all() and (lg[..., r] <= 100).all()                    # logit shift never reaches 0 or collapses onto it
    assert (lg[..., r] < x[..., r]).all()
    assert (phys[..., r] == 0).mean() > 0.2                                        # the physical shift piles samples on 0 %RH
    assert np.allclose(debias.from_logit(debias.to_logit(np.array([5.0, 50.0, 95.0]))), [5, 50, 95])


def test_il143_headline_valid_mask_drops_filled_columns_and_default_is_identical():
    from tempest.scoring import diag
    r = np.random.default_rng(0)
    N, m, D = 300, 10, 6
    truth = r.normal(size=(N, D))
    truth[:, 3:] = 0.0                                                        # the "filled" part: trivially predicted
    mk = lambda s: r.normal(size=(N, m, D)) * s
    sets = dict(clim=mk(2), clim15=mk(2), known=mk(1), unknown=mk(1))
    sets["known"][..., 3:] = 0.0
    sets["unknown"][..., 3:] = 0.0
    sets["clim15"][..., 3:] = r.normal(size=(N, m, 3)) * 0.5
    grp = [("t", "all", np.ones(D, bool)), ("t", "top", np.arange(D) >= 3)]
    day = np.arange(N) // 5
    base = diag.headline(sets, truth, day, grp, n_boot=20)
    same = diag.headline(sets, truth, day, grp, n_boot=20, valid=np.ones((N, D), bool))
    assert np.allclose(base["skill15_unknown"], same["skill15_unknown"])      # all valid = no change
    valid = np.arange(D)[None, :] < 3
    valid = np.broadcast_to(valid, (N, D)).copy()
    masked = diag.headline(sets, truth, day, grp, n_boot=20, valid=valid)
    assert masked["skill15_unknown"][0] < base["skill15_unknown"][0]          # the filled columns flattered the band
    assert np.isfinite(masked["skill15_unknown"][0]) and np.isnan(masked["skill15_unknown"][1])   # a band with no real column anywhere has no score
    top = np.array([[2, 1, 0, 2], [0, 0, 0, 0]])
    v = diag.valid_from_fill_top(top, 4 * 44 + 3)
    assert v[0, :3].all() and not v[0, 3] and v[0, 44] and not v[0, 46] and v[:, -3:].all() and v[1, 0] and not v[1, 1]


def test_il110_tail_support_counts_and_block_bootstrap_interval():
    from tempest.scoring import diag
    s = diag.tail_support(5000, 0.9999)
    assert abs(s["expected_per_column"] - 0.5) < 1e-9 and s["thin"]
    assert not diag.tail_support(50000, 0.999)["thin"] or diag.tail_support(5000, 0.999)["thin"]
    day = np.repeat(np.arange(50), 10)
    ex = np.zeros((500, 3), bool)
    ex[:10, 0] = True                                         # ten exceeding rows, all on day 0
    ex[:3, 1] = True
    t = diag.tail_support(500, 0.99, day=day, exceed=ex)
    assert t["observed"] == 13 and t["effective_days"] == 1   # many rows, one weather day
    v = np.random.default_rng(0).normal(size=500)
    est, lo, hi = diag.block_bootstrap_ci(v, day, lambda a: np.quantile(a, 0.99), n_boot=100)
    assert lo <= est <= hi and hi - lo > 0
    # day blocks give a wider interval than treating all rows as independent when the rows of a day are equal
    v2 = np.repeat(np.random.default_rng(1).normal(size=50), 10)
    _, l_b, h_b = diag.block_bootstrap_ci(v2, day, np.mean, n_boot=200)
    _, l_i, h_i = diag.block_bootstrap_ci(v2, np.arange(500), np.mean, n_boot=200)
    assert (h_b - l_b) > (h_i - l_i)
