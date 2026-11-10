"""G3: with several template sets in the assets (export --post-template-sets K), each block of 199 atmospheres gets its own copula (set g mod K): the rank patterns of blocks 0 and 1 no longer repeat,
while the marginals are unchanged."""
import numpy as np
import pytest

from tempest_weather import api


def test_blocks_do_not_repeat_one_copula():
    A = api._assets(None)
    if "rank_extra" not in (A.get("post") or {}):
        pytest.skip("bundled assets carry one template set")
    a, _ = api.atmosphere_set(32.99, -106.97, "2025-07-15T15:00", n=995, seed=4)
    u = np.asarray(a["u"])[:, :20].reshape(5, 199, 20)
    r = np.argsort(np.argsort(u, axis=1), axis=1)
    assert np.mean(r[0] == r[1]) < 0.05 and np.mean(r[0] == r[2]) < 0.05     # chance level is 1/199
