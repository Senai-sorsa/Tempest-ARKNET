"""IL-162 lapse-rate quantile map: identity below the median, tail moved toward the truth, rank order of layers kept, smooth temperature profile kept."""
import numpy as np

from tempest.calibrate import lapse_map as LM


def make(n, m, spread, seed):
    rng = np.random.default_rng(seed)
    D = 4 * LM.NH + 3
    x = np.zeros((n, m, D))
    t0 = 288.0 - 6.5 * LM.HEIGHTS / 1000.0                                  # standard lapse
    noise = np.cumsum(rng.normal(scale=spread, size=(n, m, LM.NH)) * np.sqrt(np.diff(LM.HEIGHTS, prepend=0.0)) / 30.0, axis=-1)
    x[..., LM.T0:LM.T0 + LM.NH] = t0 + noise
    return x


def test_map_pulls_a_too_rough_tail_toward_the_truth_and_keeps_the_rest():
    samples, truth = make(40, 60, 1.6, 0), make(40, 60, 1.0, 1)[:, 0]
    table = LM.fit(samples, truth)
    after = LM.apply(table, samples)
    q = lambda x: np.quantile(LM.lapse(x)[..., LM.BAND_OF_LAYER == 0], 0.99)
    assert abs(q(after) - q(truth)) < abs(q(samples) - q(truth)) * 0.6                   # the 99th percentile of the lowest band moves most of the way
    L0, L1 = LM.lapse(samples), LM.lapse(after)
    r0, r1 = np.argsort(np.argsort(L0, axis=-1), axis=-1), np.argsort(np.argsort(L1, axis=-1), axis=-1)
    assert np.corrcoef(r0.ravel(), r1.ravel())[0, 1] > 0.9                                # the order of the layers within a sample is kept (the high-pass step allows small swaps)
    t0, t1 = samples[..., LM.T0:LM.T0 + LM.NH], after[..., LM.T0:LM.T0 + LM.NH]
    assert np.abs(np.median(t1, axis=1) - np.median(t0, axis=1)).max() < 3.0              # smooth part and medians stay
    other = np.delete(np.arange(samples.shape[-1]), np.arange(LM.T0, LM.T0 + LM.NH))
    assert np.array_equal(after[..., other], samples[..., other])                         # only temperature columns are touched


def test_identity_when_samples_already_match_truth_and_file_roundtrip(tmp_path):
    samples = make(30, 50, 1.0, 2)
    truth = samples[:, 0]
    table = LM.fit(samples, np.concatenate([truth] * 1))
    after = LM.apply(table, samples)
    assert np.abs(after - samples).max() < 0.8                                            # a map fitted on itself changes little
    np.savez(tmp_path / "m.npz", **table)
    again = dict(np.load(tmp_path / "m.npz"))
    assert np.allclose(LM.apply(again, samples), after)


def test_lowest_level_is_not_moved():
    """Gemini bug 5: the high-pass in the map must leave the surface level (index 0) alone."""
    samples, truth = make(40, 60, 1.6, 0), make(40, 60, 1.0, 1)[:, 0]
    after = LM.apply(LM.fit(samples, truth), samples)
    assert np.allclose(after[..., LM.T0], samples[..., LM.T0], atol=1e-4)


def test_runtime_lapse_apply_matches_the_training_side_map():
    """L21b: tempest_weather._core.lapse_apply (numpy, shipped) equals tempest.calibrate.lapse_map.apply within 1e-5 K on samples with a rough tail."""
    from tempest_weather import _core
    samples, truth = make(20, 40, 1.6, 3), make(20, 40, 1.0, 4)[:, 0]
    table = LM.fit(samples, truth)
    a = LM.apply(table, samples)
    b = _core.lapse_apply({k: np.asarray(v) for k, v in table.items()}, samples)
    assert np.abs(a - b).max() < 1e-5
    assert np.abs(a - samples).max() > 0.1                                                # the map did something, so the parity is not trivial
