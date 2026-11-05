"""Scenario picker (PHASE4_FORECAST.md 4.7 / G4.7): real whole profiles at chosen percentiles of an outcome.

    scenarios(samples, outcome_fn, pcts=(1, 25, 50, 75, 99))

samples: dict of arrays with the sample index first (as written by output/coupled.py). outcome_fn(samples) -> (n,) scalar per sample
(for example the mean wind speed 0-3 km, the drift of a parachute descent, a landing distance). Returns, per percentile, the INDEX of the
sample whose outcome is nearest that percentile and that sample itself, so a scenario is a real, internally consistent atmosphere,
never an average of several.
"""
import numpy as np


def scenarios(samples, outcome_fn, pcts=(1, 25, 50, 75, 99), weights=None):
    out = np.asarray(outcome_fn(samples), float)
    n = len(out)
    if out.ndim != 1:
        raise ValueError("outcome_fn must return one number per sample")
    if weights is None:
        targets = np.percentile(out, pcts)
    else:  # weighted percentiles (sample weights from the coupled file)
        order = np.argsort(out)
        cw = np.cumsum(np.asarray(weights, float)[order])
        cw = (cw - 0.5 * np.asarray(weights, float)[order]) / cw[-1]
        targets = np.interp(np.asarray(pcts) / 100.0, cw, out[order])
    picks = [int(np.argmin(np.abs(out - t))) for t in targets]
    return [dict(percentile=p, index=i, outcome=float(out[i]), target=float(t), sample={k: v[i] for k, v in samples.items() if hasattr(v, "__len__") and len(v) == n})
            for p, i, t in zip(pcts, picks, targets)]
