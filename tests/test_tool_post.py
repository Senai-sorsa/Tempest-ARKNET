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
