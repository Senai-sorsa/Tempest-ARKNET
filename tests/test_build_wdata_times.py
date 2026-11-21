"""IL-177: build_wdata.row_times recovers each row's UTC time from its own features (day of year, solar hour, longitude, year), including the leap day, day 366 and hour 0."""
import numpy as np
import pandas as pd

from tempest.generator.build_dataset import solar_hour
from tempest.generator.build_wdata import row_times
from tempest.generator.features import FEATURES, features


def test_row_times_round_trip():
    times = pd.DatetimeIndex(["2020-02-29T07:00", "2020-12-31T23:00", "2021-01-01T00:00", "2019-12-31T05:00", "2024-07-04T12:00", "2025-06-16T08:00"])
    lons = np.array([-108.0, -101.0, -104.75, -106.25, -102.5, -107.0])
    lats = np.full(len(times), 32.0)
    sh = np.array([solar_hour(times[i:i + 1], np.array([lons[i]]))[0][0] for i in range(len(times))])
    cond = features(lats, lons, np.zeros(len(times)), np.zeros(len(times)), times.dayofyear.to_numpy(), sh, times.year.to_numpy(),
                    np.zeros(len(times)), np.zeros(len(times)), np.zeros(len(times)), np.zeros(len(times)))
    assert cond.shape[1] >= len([k for k in FEATURES if k in ("lat", "lon", "doy_sin", "doy_cos", "hour_sin", "hour_cos", "year")])
    assert list(row_times(cond)) == list(times)
