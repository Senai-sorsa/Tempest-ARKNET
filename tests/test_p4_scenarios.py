"""Scenario picker: picked outcomes sit at the percentiles, and the profile returned is one real sample."""
import numpy as np

from tempest.forecast.scenarios import scenarios


def _samples(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    u = rng.normal(5, 3, (n, 44))
    return dict(u=u, T=rng.normal(280, 5, (n, 44)), t2m=rng.normal(300, 4, n))


def test_outcomes_match_percentiles_and_samples_are_whole_rows():
    s = _samples()
    fn = lambda d: np.abs(d["u"][:, :10]).mean(1)
    res = scenarios(s, fn, (1, 25, 50, 75, 99))
    out = fn(s)
    for r in res:
        assert abs(r["outcome"] - np.percentile(out, r["percentile"])) < 0.05 * out.std()
        assert np.array_equal(r["sample"]["u"], s["u"][r["index"]]) and np.array_equal(r["sample"]["T"], s["T"][r["index"]])
        assert r["sample"]["t2m"] == s["t2m"][r["index"]]
    assert [r["index"] for r in res] == sorted({r["index"] for r in res}, key=lambda i: fn(s)[i])  # ordered by outcome


def test_weights_move_the_median():
    s = _samples()
    fn = lambda d: d["t2m"]
    w = np.where(s["t2m"] > np.median(s["t2m"]), 5.0, 1.0)
    plain, weighted = scenarios(s, fn, (50,))[0]["outcome"], scenarios(s, fn, (50,), weights=w)[0]["outcome"]
    assert weighted > plain
