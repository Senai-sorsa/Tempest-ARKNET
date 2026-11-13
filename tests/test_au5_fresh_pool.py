"""AU-5 step 0 (New_Plan 15.2): fresh leftover pool with fixed lines, and the test-year splice."""
import importlib.util
import pathlib

import numpy as np

from tempest.calibrate import station


def _splice():
    p = pathlib.Path(__file__).parents[1] / "scripts" / "au5_splice.py"
    spec = importlib.util.spec_from_file_location("au5_splice", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.splice


def _pairs(rng, n):
    era = rng.normal(size=(n, 4, 44)).astype(np.float32)
    obs = (1.0 + 0.8 * era + rng.normal(scale=0.3, size=era.shape)).astype(np.float32)
    return era, obs, rng.integers(0, 2, n)


def test_fixed_lines_keep_a_b_and_reproduce_the_pool_of_the_same_data():
    rng = np.random.default_rng(0)
    era, obs, g = _pairs(rng, 900)
    t = station.fit(era, obs, g, 2)
    same = station.fit(era, obs, g, 2, ab=(t["a"], t["b"]))
    for k in ("a", "b", "pool", "n", "cuts"):
        assert np.array_equal(same[k], t[k]), k


def test_fresh_pool_keeps_the_lines_and_takes_its_leftovers_from_the_new_pairs():
    rng = np.random.default_rng(1)
    era, obs, g = _pairs(rng, 900)
    t = station.fit(era, obs, g, 2)
    era2, obs2, g2 = _pairs(rng, 600)
    obs2 = obs2 + 5.0                                    # the new years sit 5 above the old line
    f = station.fit(era2, obs2, g2, 2, ab=(t["a"], t["b"]))
    assert np.array_equal(f["a"], t["a"]) and np.array_equal(f["b"], t["b"])
    for gi in range(2):
        for j in range(3):
            left = f["pool"][gi, j, :f["n"][gi, j]]
            assert abs(left.mean() - 5.0) < 0.1          # leftovers against the OLD line, from the new pairs


def test_splice_keeps_training_years_and_replaces_the_test_years():
    splice = _splice()
    meta = dict(cond_names=np.array(["a"]), target_names=np.array(["x", "y"]), rh_target=np.array("dpd"))
    base = dict(cond=np.arange(6.0)[:, None], target=np.zeros((6, 2)), year=np.array([2020, 2021, 2023, 2024, 2024, 2025]), **meta)
    new = dict(cond=np.full((3, 1), 9.0), target=np.ones((3, 2)), year=np.array([2024, 2025, 2025]), **meta)
    out = splice(base, new, 2024)
    assert list(out["year"]) == [2020, 2021, 2023, 2024, 2025, 2025]
    assert list(out["cond"][:, 0]) == [0, 1, 2, 9, 9, 9] and out["target"][3:].all()


def test_splice_keeps_the_order_of_a_base_laid_out_in_date_blocks():
    splice = _splice()
    meta = dict(cond_names=np.array(["a"]), target_names=np.array(["x"]), rh_target=np.array("dpd"))
    base = dict(cond=np.arange(6.0)[:, None], target=np.zeros((6, 1)), year=np.array([2022, 2023, 2024, 2023, 2024, 2025]), **meta)
    new = dict(cond=np.full((2, 1), 9.0), target=np.ones((2, 1)), year=np.array([2024, 2025]), **meta)
    out = splice(base, new, 2024)
    assert list(out["year"]) == [2022, 2023, 2023, 2024, 2025] and list(out["cond"][:, 0]) == [0, 1, 3, 9, 9]
