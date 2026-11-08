"""Schaake shuffle (IL-82/IL-83): keep each column's samples, change which sample goes with which across columns.

For one row, `x` holds m samples of every column (sorted or not) and `template` holds m REAL profiles that stand for the dependence structure we want (same lead
for forecast errors, same grid point / month / hour bin for climate). Each column of x is sorted and its values are handed out in the rank order of the template
column, so every marginal is exactly what it was (CRPS, coverage, PIT per column are unchanged) while the joint behaviour across heights and variables is the
real one. Off by default (score --shuffle).
"""
import numpy as np


def apply(x, template, w=1.0):
    """x, template (N, m, D) -> x with the template's rank structure along the m axis.
    w < 1 (IL-161): blended ranks. Each column's ranks are w x the template's rank + (1 - w) x the rank the sample already has in x (the network's own order), re-ranked within the column,
    so the marginals are still exactly those of x and w = 1 is the plain Schaake shuffle."""
    r_t = np.argsort(np.argsort(template, axis=1), axis=1)
    if w >= 1.0:
        return np.take_along_axis(np.sort(x, axis=1), r_t, axis=1)
    r_x = np.argsort(np.argsort(x, axis=1), axis=1)
    blend = float(w) * r_t + (1.0 - float(w)) * r_x
    ranks = np.argsort(np.argsort(blend, axis=1, kind="stable"), axis=1, kind="stable")
    return np.take_along_axis(np.sort(x, axis=1), ranks, axis=1)


def cell_keys(keys, cell, n_lon=29):
    """Scoring-group keys (point id x 144 + month x 12 + hour bin; point ids run n_lon per latitude row, southern row first) -> keys of block x month x hour bin, blocks of cell x cell points."""
    k_ = np.asarray(keys)
    pid = k_ // 144
    return ((pid // n_lon // cell) * 100 + (pid % n_lon) // cell) * 144 + k_ % 144


def grid_n_lon(cond):
    """Longitudes per latitude row of the grid in `cond` (as score.group_keys numbers its points), or 0 if the points are not a full regular grid."""
    from tempest.generator.features import FEATURES
    ll = np.unique(np.round(np.asarray(cond)[:, [FEATURES.index("lat"), FEATURES.index("lon")]], 3), axis=0)
    n_lat, n_lon = len(np.unique(ll[:, 0])), len(np.unique(ll[:, 1]))
    return n_lon if n_lat * n_lon == len(ll) else 0


def group_template(target, keys, year, idx, m, rng, before_year, pooled=False, cell=0, n_lon=29):
    """Real profiles as dependence template: for each row idx, m training-year rows (year < before_year) of the same scoring group (grid point x month x hour bin).
    target: dataset target array, keys: group keys for all rows, year: year per row. n_lon: grid_n_lon of the dataset (L3-35: 29 was
    hard-wired, which cut the 9 x 9 Denver grid into mixed strips); 0 = not a regular grid, so cell falls back to per-point templates.
    Returns (len(idx), m, D) physical profiles."""
    from tempest.generator.sample import to_physical
    if pooled:                                           # IL-94: templates by month x 2-hour bin only (all grid points together): small enough to ship with the tool
        keys = np.asarray(keys) % 144
    elif cell and n_lon:                                 # IL-95: templates per block of `cell` x `cell` grid points (0.25 degree steps; point ids run n_lon per row of latitude) x month x 2-hour bin
        keys = cell_keys(keys, cell, n_lon)
    elif cell:
        print("shuffle: points are not a regular grid, --template-cell ignored (per-point templates)", flush=True)
    tr = np.flatnonzero(year < before_year)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[idx], "left"), np.searchsorted(keys[tr], keys[idx], "right")
    pick = tr[np.minimum(lo[:, None] + (rng.random((len(idx), m)) * np.maximum(hi - lo, 1)[:, None]).astype(np.int64), len(tr) - 1)]
    return to_physical(np.asarray(target[pick.ravel()])).reshape(len(idx), m, -1)
