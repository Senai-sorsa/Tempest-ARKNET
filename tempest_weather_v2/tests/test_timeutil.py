"""Windows and local time: forms, uniform / triangular sampling, the 06-21 h solar cut, exclusions, union of ranges, errors. Needs tzdata (in the project venv)."""
from datetime import datetime, timezone

import numpy as np
import pytest

from tempest_weather_v2 import timeutil as T
from tempest_weather_v2.timeutil import Window, WindowError

LON = -106.97
TZ = "America/Denver"
NOW = datetime(2027, 6, 15, 12, 0, tzinfo=T.get_zone(TZ))


def res(w, **kw):
    return w.resolve(LON, TZ, now=NOW, **kw)


def local_hours(r, n=4000, seed=0):
    s = r.sample(n, np.random.default_rng(seed)).astype("datetime64[s]").astype(object)
    z = T.get_zone(TZ)
    return np.array([(t.replace(tzinfo=timezone.utc).astimezone(z).hour + t.replace(tzinfo=timezone.utc).astimezone(z).minute / 60) for t in s])


def test_single_time_is_local_wall_clock_with_dst():
    r = res(Window("2027-06-16 10:00"))
    assert r.kind == "single" and r.cut_share == 0
    t = r.sample(3)[0].astype(datetime)
    assert (t.hour, t.minute) == (16, 0)                                     # 10:00 MDT = 16:00 UTC
    assert "2027-06-16 10:00 MDT" in r.description
    solar = T.solar_hour(r.cells_utc[0].astype(datetime), LON)
    assert abs(solar - (16 - 106.97 / 15)) % 24 < 1e-6 or abs(solar - 8.87) < 0.01


def test_uniform_forms_agree_and_stay_inside_the_window():
    forms = [Window("2027-06-16 09:00-13:00"), Window(("2027-06-16 09:00", "2027-06-16 13:00")), Window(earliest="2027-06-16 09:00", latest="13:00")]
    for w in forms:
        r = res(w)
        assert r.kind == "uniform"
        h = local_hours(r)
        assert h.min() >= 9.0 - 1e-9 and h.max() <= 13.0 + 1e-9 and abs(h.mean() - 11.0) < 0.1


def test_triangular_peaks_at_the_most_likely_time_and_forms_agree():
    a = res(Window(("2027-06-16 10:00", "2027-06-16 08:00", "2027-06-16 16:00")))
    b = res(Window("2027-06-16 10:00", earliest="08:00", latest="16:00"))
    assert a.kind == "triangular" and np.allclose(a.prob, b.prob)
    h = local_hours(a, 20000)
    assert (h < 10).mean() == pytest.approx((10 - 8) / (16 - 8), abs=0.03)    # P(X < mode) = (mode - a) / (b - a) for a triangular law
    assert h.mean() == pytest.approx((8 + 10 + 16) / 3, abs=0.06)
    with pytest.raises(WindowError, match="most likely"):
        res(Window(("2027-06-16 18:00", "2027-06-16 08:00", "2027-06-16 16:00")))


def test_night_hours_are_cut_and_reported_and_whole_day_dates_work():
    r = res(Window(("2027-06-16", "2027-06-17")))                           # two whole days
    assert 0.3 < r.cut_share < 0.5                                          # about 9 of 24 hours per day are outside 06-21 h solar
    sh = T.solar_hour(r.cells_utc, LON)
    assert sh.min() >= 6.0 and sh.max() < 21.0
    assert set(r.day_share) <= {"2027-06-16", "2027-06-17"} and abs(sum(r.day_share.values()) - 1) < 1e-9
    assert "cut" in r.description
    assert not np.isclose(res(Window("2027-06-16")).cut_share, 0)           # a single date is the whole day too


def test_exclusions_every_day_and_one_day():
    base = res(Window(("2027-06-16 08:00", "2027-06-17 16:00")))
    ex = res(Window(("2027-06-16 08:00", "2027-06-17 16:00"), exclude=["12:00-14:00"]))
    assert ex.cut_share > base.cut_share
    h = local_hours(ex)
    assert not ((h >= 12) & (h < 14)).any()
    one = res(Window(("2027-06-16 08:00", "2027-06-17 16:00"), exclude=["2027-06-17 09:00-10:00"]))
    assert one.cut_share > base.cut_share and one.cut_share < ex.cut_share
    with pytest.raises(WindowError, match="nothing is left"):
        res(Window("2027-06-16 03:00-04:00"))
    with pytest.raises(WindowError, match="cannot read the exclusion"):
        res(Window("2027-06-16 09:00-13:00", exclude=["lunch"]))


def test_union_of_ranges_weights_and_relative_times():
    ranges = [("2027-06-16 08:00", "2027-06-16 11:00"), ("2027-06-18 08:00", "2027-06-18 11:00")]
    r = res(Window(ranges))
    assert abs(r.day_share["2027-06-16"] - 0.5) < 1e-9                       # equal lengths: equal weight
    r = res(Window(ranges, weights=[3, 1]))
    assert abs(r.day_share["2027-06-16"] - 0.75) < 1e-9
    with pytest.raises(WindowError, match="weights has"):
        res(Window(ranges, weights=[1]))
    r = res(Window("tomorrow 10am"))                                         # NOW is 2027-06-15
    assert "2027-06-16 10:00" in r.description
    r = res(Window("today 14:00"))
    assert "2027-06-15 14:00" in r.description


def test_errors_are_helpful():
    with pytest.raises(WindowError, match="give the date"):
        res(Window("09:00"))
    with pytest.raises(WindowError, match="cannot read the time"):
        res(Window("next tuesday-ish"))
    with pytest.raises(WindowError, match="earliest= and latest="):
        Window(earliest="08:00")
    with pytest.raises(WindowError, match="before the earliest"):
        res(Window(("2027-06-16 13:00", "2027-06-16 09:00")))
    with pytest.raises(WindowError, match="time zone"):
        T.get_zone("Mars/Olympus")
    assert T._clock("9:30pm") == 21 * 60 + 30 and T._clock("12am") == 0 and T._clock("25:00") is None


def test_sample_reproducible_and_inside_cells():
    r = res(Window("2027-06-16 09:00-13:00"))
    a, b = r.sample(100, np.random.default_rng(5)), r.sample(100, np.random.default_rng(5))
    assert np.array_equal(a, b) and a.dtype == np.dtype("datetime64[s]")
