"""Shear patches: p = 0 leaves samples untouched, patched samples gain shear only in the wind columns, the fit raises the tail of too-calm samples."""
import numpy as np

from tempest.calibrate import shear_tail as st

N = st.N


def _x(rng, S=300, m=20, D=4 * N + 3, scale=1.0):
    x = rng.normal(0, 1, (S, m, D)).astype(np.float32)
    x[..., :2 * N] = np.cumsum(rng.normal(0, 0.05 * scale, (S, m, 2 * N)), -1)   # smooth-ish winds
    return x


def test_p_zero_is_identity_and_only_wind_changes():
    rng = np.random.default_rng(0)
    x = _x(rng)
    assert np.array_equal(st.apply(dict(p=0.0, sigma=np.ones(4)), x, rng), x)
    y = st.apply(dict(p=0.5, sigma=np.full(4, 2.0)), x, rng)
    assert np.array_equal(y[..., 2 * N:], x[..., 2 * N:]) and not np.array_equal(y[..., :N], x[..., :N])


def test_fit_raises_a_too_light_tail_and_is_bounded():
    rng = np.random.default_rng(1)
    calm, wild = _x(rng, scale=1.0), _x(rng, scale=3.0)
    sig, target = st.fit_sigma(calm, wild[:, 0], 0.05, rng)
    after = st.band_shear_q(st.apply(dict(p=0.05, sigma=sig), calm, rng), 99.9)
    before = st.band_shear_q(calm, 99.9)
    assert (after >= before - 1e-6).all() and (sig > 0).any() and (sig <= 8).all()


def test_fixed_bands_stay_zero():
    rng = np.random.default_rng(2)
    calm, wild = _x(rng, scale=1.0), _x(rng, scale=3.0)
    sig, _ = st.fit_sigma(calm, wild[:, 0], 0.05, rng, free=(False, False, True, False))
    assert sig[0] == sig[1] == sig[3] == 0.0 and sig[2] > 0
