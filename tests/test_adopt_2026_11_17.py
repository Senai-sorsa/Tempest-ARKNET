"""Adoption of 2026-11-17: AV35 aloft shear map in the tool's post step."""
import numpy as np

from tempest_weather import _core, api


def test_amap_changes_only_5km_and_up():
    rng = np.random.default_rng(0)
    nh = _core.NH
    x = np.zeros((2, 50, 179), np.float32)
    x[..., :2 * nh] = np.cumsum(rng.normal(0, 1.5, (2, 50, 2 * nh)), axis=-1)
    gain = np.ones((4, 20)) * 1.0
    gain[2:] = 1.3
    post = dict(amap=dict(grid=np.tile(np.linspace(0, 100, 20), (4, 1)), gain=gain))
    y = api._post_process(dict(post=post), x, 100.0, 12.0)
    low = np.flatnonzero(_core.HEIGHTS < 5000.0)
    cols = np.concatenate([low, nh + low])
    assert np.array_equal(y[..., cols], x[..., cols])
    assert not np.allclose(y[..., :2 * nh], x[..., :2 * nh])
    assert np.array_equal(y[..., 2 * nh:], x[..., 2 * nh:])
