"""AU-6 (New_Plan 15.2): sonde --partial keeps soundings with complete low levels and fills missing climatology columns."""
import numpy as np

from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.sonde import fill_invalid, low_complete

N_H = len(HEIGHTS)
D = len(PROFILE) * N_H + 3


def _col(var, h):
    return PROFILE.index(var) * N_H + int(np.argmin(np.abs(np.asarray(HEIGHTS) - h)))


def test_low_complete_keeps_upper_gaps_and_drops_low_wind_or_surface_gaps():
    phys = np.ones((5, D))
    phys[1, _col("u", 15000)] = np.nan              # upper wind lost: kept
    phys[2, _col("v", 1000)] = np.nan               # low wind lost: dropped
    phys[3, -1] = np.nan                            # a surface field lost: dropped
    if "RH" in PROFILE:
        phys[4, _col("RH", 2000)] = np.nan          # humidity is not in the low-level rule: kept
    assert low_complete(phys).tolist() == [True, True, False, False, True]


def test_fill_invalid_is_untouched_without_gaps_and_fills_only_from_valid_soundings():
    rng = np.random.default_rng(0)
    phys = rng.normal(size=(40, D))
    pool = np.arange(40)
    x = phys[rng.integers(0, 40, (6, 5))]
    r1, r2 = np.random.default_rng(3), np.random.default_rng(3)
    same = fill_invalid(x.copy(), phys, pool, r1)
    assert np.array_equal(same, x) and r1.integers(1 << 30) == r2.integers(1 << 30)   # no gaps: no random numbers used
    j = _col("u", 15000)
    phys[:30, j] = np.nan                            # only soundings 30-39 have this column
    x = phys[rng.integers(0, 40, (6, 5))]
    out = fill_invalid(x, phys, pool, rng)
    assert np.isfinite(out).all()
    assert np.isin(out[..., j], phys[30:, j]).all()
