"""Seasonal width factors: s = 1 is the identity, the fitted factor reaches the target coverage, ranks are kept."""
import numpy as np

from tempest.calibrate import seasonal


def test_identity_and_rank_preservation():
    rng = np.random.default_rng(0)
    x = rng.normal(280, 3, (30, 199, 179)).astype(np.float32)
    out = seasonal.apply(dict(scale=np.ones((12, 179), np.float32)), x, np.full(30, 6))
    assert np.allclose(out[..., 5], x[..., 5], atol=1e-3)
    wide = seasonal.apply(dict(scale=np.full((12, 179), 1.3, np.float32)), x, np.full(30, 6))
    assert np.array_equal(np.argsort(wide[..., 7], 1), np.argsort(x[..., 7], 1))     # ranks unchanged
    assert (wide[..., 7].std(1) > x[..., 7].std(1) * 1.25).all()


def test_fit_scale_reaches_target_and_does_not_shrink_below_floor():
    rng = np.random.default_rng(1)
    n, c = 4000, 5
    sig = 1.15                                     # truths are 15 % wider than the samples' spread
    x = rng.normal(0, 1, (n, 199, c))
    y = rng.normal(0, sig, (n, c))
    lo, med, hi = x.min(1), np.median(x, 1), x.max(1)
    s = seasonal.fit_scale(lo, med, hi, y)
    cov = ((y >= med - s * (med - lo)) & (y <= med + s * (hi - med))).mean()
    assert 1.05 < s < 1.30 and cov >= 0.989
    y2 = rng.normal(0, 0.8, (n, c))                # samples already too wide: the factor stops at the floor, not at 0
    assert seasonal.fit_scale(lo, med, hi, y2) == seasonal.S_MIN


def test_month_smoothing_is_circular():
    s = np.ones((12, 1)); s[0, 0] = 1.3
    sm = seasonal.smooth_months(s)
    assert sm[11, 0] > 1 and sm[1, 0] > 1 and np.isclose(sm.mean(), s.mean())


def test_restrict_keeps_only_chosen_variables():
    from tempest.scoring.score import band_masks
    tab = dict(scale=np.full((12, len(band_masks()[0][2])), 0.9, np.float32))
    r = seasonal.restrict(tab, {"RH"})
    rh = np.zeros(tab["scale"].shape[1], bool)
    for v, _, sel in band_masks():
        if v == "RH":
            rh |= sel
    assert np.allclose(r["scale"][:, rh], 0.9) and np.allclose(r["scale"][:, ~rh], 1.0)
