"""Atmosphere builder: time conversions (the rest needs the trained model and data files)."""
import pandas as pd

from tempest.output.atmosphere import solar_time


def test_naive_time_is_local_solar_time():
    utc, sh = solar_time("2027-06-16 15:00", -105.0)           # 105 W is 7 h behind UTC in solar time
    assert sh == 15.0 and utc == pd.Timestamp("2027-06-16 22:00")


def test_aware_time_converts_to_solar_hour():
    utc, sh = solar_time("2027-06-16T22:00:00+00:00", -105.0)
    assert utc == pd.Timestamp("2027-06-16 22:00") and abs(sh - 15.0) < 1e-9
    utc2, sh2 = solar_time("2027-06-16T16:00:00-06:00", -105.0)  # same instant written in a local offset
    assert utc2 == utc and abs(sh2 - 15.0) < 1e-9
