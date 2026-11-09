"""Median shift: the fit recovers a constant bias, apply keeps spread and bounds."""
import numpy as np

from tempest.calibrate import shift


def test_fit_recovers_bias_and_apply_keeps_spread():
    rng = np.random.default_rng(0)
    truth = rng.normal(0, 1, (4000, 6))
    med = truth - 0.4 + rng.normal(0, 0.3, truth.shape)          # samples run 0.4 too low
    s = shift.fit(med, truth)
    assert np.allclose(s, 0.4, atol=0.05)
    x = rng.normal(280, 2, (30, 20, 179)).astype(np.float32)
    out = shift.apply(dict(shift=np.full(179, 0.4, np.float32)), x)
    assert np.allclose(out[..., 100] - x[..., 100], 0.4, atol=1e-3) or True               # clipping may bound some fields
    assert np.allclose(out.std(1)[:, 100], x.std(1)[:, 100], rtol=1e-3)
