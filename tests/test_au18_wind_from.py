"""AU-18: profiles_from_levels(wind_from=150) ignores a pressure level 100-150 m above ground for the wind; default unchanged."""
import numpy as np

from tempest.profiles.to_heights import HEIGHTS, profiles_from_levels

G0 = 9.80665


def _column(level_agl):
    agl = np.array([level_agl, 1000.0, 3000.0])
    z = (agl * G0)[None]                                       # ground at 0 m: geopotential of each level
    u = np.array([[20.0, 12.0, 15.0]])                         # a fast level just above 100 m makes the false step
    zero = np.zeros(1)
    args = (z, u, np.zeros_like(u), np.full_like(u, 280.0), np.full_like(u, 50.0), zero, np.full(1, 5.0), zero,
            np.full(1, 10.0), zero, np.full(1, 285.0), np.full(1, 275.0))
    return args


def test_wind_from_150_skips_the_level_near_the_anchor():
    i100, i150 = int(np.flatnonzero(HEIGHTS == 100)[0]), int(np.flatnonzero(HEIGHTS == 150)[0])
    old = profiles_from_levels(*_column(120.0))[0]["u"][0]
    new = profiles_from_levels(*_column(120.0), wind_from=150.0)[0]["u"][0]
    assert old[i100] == new[i100] == 10.0
    assert old[i150] > 19.0                                   # the 120 m level pulls 150 m almost to 20 m/s
    assert abs(new[i150] - (10.0 + 2.0 * 50 / 900)) < 0.05    # line from the 100 m anchor to the 1000 m level
    # a column with no level in 100-150 m is identical either way
    a = profiles_from_levels(*_column(400.0))[0]
    b = profiles_from_levels(*_column(400.0), wind_from=150.0)[0]
    assert all(np.array_equal(a[k], b[k], equal_nan=True) for k in a)
