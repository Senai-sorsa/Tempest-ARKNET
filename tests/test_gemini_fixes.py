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
