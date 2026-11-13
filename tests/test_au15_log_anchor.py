"""AU-15 (New_Plan 15.3): near-term ensemble wind between the 10 m anchor and the first pressure level follows ln(height), not a line above 100 m."""
import numpy as np

from tempest.profiles.to_heights import HEIGHTS, interp_columns


def test_log_profile_between_10m_and_first_level_within_02():
    hw = np.array([[10.0, 400.0, 1500.0, 3000.0]])
    prof = lambda z: 2.0 * np.log(z / 0.05)                     # neutral log law, u* / kappa = 2 m/s, z0 = 5 cm: 10.6 m/s at 10 m, 18.0 at 400 m
    x = prof(hw)
    new = interp_columns(hw, x, HEIGHTS, 100, log_first=True)[0]
    old = interp_columns(hw, x, HEIGHTS, 100)[0]
    H = np.asarray(HEIGHTS, float)
    for z in (100.0, 150.0, 200.0, 300.0):
        j = int(np.flatnonzero(H == z)[0])
        assert abs(new[j] - prof(z)) < 0.2
    j = int(np.flatnonzero(H == 200.0)[0])
    assert prof(200.0) - old[j] > 1.0                          # the old line read low there
    k = H > 400.0                                              # above the first level nothing changes
    assert np.allclose(new[k], old[k], equal_nan=True)
