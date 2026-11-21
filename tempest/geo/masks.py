"""G0 below-ground mask: ERA5 pressure levels with p > surface pressure are extrapolated, not real air.

    below_ground(levels_hpa, sp_pa) -> bool (..., n_levels); sp_pa (...,) decoded surface pressure in Pa.
"""
import numpy as np


def below_ground(levels_hpa, sp_pa):
    return np.asarray(levels_hpa, float) * 100.0 > np.asarray(sp_pa, float)[..., None]
