"""Joint band: s = 1 is the plain min/max range; the fitted multiplier reaches the target whole-profile coverage."""
import numpy as np

from tempest.calibrate import joint


def _toy(n=3000, m=199, h=44, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, m, h)).astype(np.float32)
    y = rng.normal(size=(n, h)).astype(np.float32)  # truth drawn like the samples: each height is calibrated alone
    return x, y


def test_scale_one_is_min_max_range():
    x, _ = _toy(n=20)
    lo, hi = joint.band(x, 1.0)
    assert np.allclose(lo, x.min(1)) and np.allclose(hi, x.max(1))


def test_plain_range_undercovers_whole_profiles_and_fit_fixes_it():
    x, y = _toy()
    per_height = ((y >= x.min(1)) & (y <= x.max(1))).mean()
    assert abs(per_height - 0.99) < 0.003  # each height alone is right
    whole = joint.inside(x, y, 1.0).mean()
    assert whole < 0.8  # 44 heights at once: far fewer
    s = joint.fit_scale(x, y, 0.99)
    assert s > 1.0 and joint.inside(x, y, s).mean() >= 0.99


def test_apply_shapes():
    x = np.random.default_rng(1).normal(size=(5, 20, 179)).astype(np.float32)
    lo, hi = joint.apply(np.array([1.0, 1.2, 1.0, 1.5]), x)
    assert lo.shape == hi.shape == (5, 176) and (hi >= lo).all()
