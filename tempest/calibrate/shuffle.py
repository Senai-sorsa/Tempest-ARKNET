"""Schaake shuffle (IL-82/IL-83): keep each column's samples, change which sample goes with which across columns.

For one row, `x` holds m samples of every column (sorted or not) and `template` holds m REAL profiles that stand for the dependence structure we want (same lead
for forecast errors, same grid point / month / hour bin for climate). Each column of x is sorted and its values are handed out in the rank order of the template
column, so every marginal is exactly what it was (CRPS, coverage, PIT per column are unchanged) while the joint behaviour across heights and variables is the
real one. Off by default (score --shuffle).
"""
import numpy as np


def apply(x, template):
    """x, template (N, m, D) -> x with the template's rank structure along the m axis."""
    ranks = np.argsort(np.argsort(template, axis=1), axis=1)
    return np.take_along_axis(np.sort(x, axis=1), ranks, axis=1)


def group_template(target, keys, year, idx, m, rng, before_year, pooled=False, cell=0):
    """Real profiles as dependence template: for each row idx, m training-year rows (year < before_year) of the same scoring group (grid point x month x hour bin).
    target: dataset target array, keys: group keys for all rows, year: year per row. Returns (len(idx), m, D) physical profiles."""
    from tempest.generator.sample import to_physical
    if pooled:                                           # IL-94: templates by month x 2-hour bin only (all grid points together): small enough to ship with the tool
        keys = np.asarray(keys) % 144
    elif cell:                                           # IL-95: templates per block of `cell` x `cell` grid points (0.25 degree steps; point ids run 29 per row of latitude) x month x 2-hour bin
        k_ = np.asarray(keys)
        pid = k_ // 144
        keys = ((pid // 29 // cell) * 100 + (pid % 29) // cell) * 144 + k_ % 144
    tr = np.flatnonzero(year < before_year)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[idx], "left"), np.searchsorted(keys[tr], keys[idx], "right")
    pick = tr[np.minimum(lo[:, None] + (rng.random((len(idx), m)) * np.maximum(hi - lo, 1)[:, None]).astype(np.int64), len(tr) - 1)]
    return to_physical(np.asarray(target[pick.ravel()])).reshape(len(idx), m, -1)
