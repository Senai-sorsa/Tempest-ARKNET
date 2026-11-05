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
