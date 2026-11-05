"""Forecast logger: the validator accepts a complete file and rejects truncated, short or out-of-range ones."""
import copy

from tempest.ops import logger as L

MODEL = "ecmwf_ifs025"


def _doc(model=MODEL, steps=384):
    n = L.MODELS[model]
    h = {"time": [f"t{i}" for i in range(steps)]}
    for var in L.HOURLY:
        lo, hi = next(((a, b) for p, a, b in L.RANGES if var.startswith(p)), (0, 1))
        mid = (lo + hi) / 2
        h[var] = [mid] * steps
        for k in range(1, n):
            h[f"{var}_member{k:02d}"] = [mid] * steps
    return {"hourly": h}


def test_complete_file_passes():
    ok, msg = L.validate(_doc(), MODEL)
    assert ok, msg


def test_truncated_time_axis_is_rejected():
    ok, _ = L.validate(_doc(steps=100), MODEL)
    assert not ok


def test_missing_members_are_rejected():
    d = _doc()
    del d["hourly"]["wind_speed_500hPa_member07"]
    assert not L.validate(d, MODEL)[0]


def test_nulls_in_first_days_are_rejected():
    d = _doc()
    for m in [k for k in d["hourly"] if k.startswith("temperature_500hPa")]:
        d["hourly"][m] = [None] * 384
    assert not L.validate(d, MODEL)[0]


def test_out_of_range_member_tolerated_only_below_ten_percent():
    d = _doc()
    d["hourly"]["temperature_500hPa_member01"][5] = 500  # 1 of 51 bad: tolerated
    assert L.validate(copy.deepcopy(d), MODEL)[0]
    for k in range(1, 10):
        d["hourly"][f"temperature_500hPa_member{k:02d}"][5] = 500  # 9 of 51 bad: over 10 %
    assert not L.validate(d, MODEL)[0]


def test_optional_variables_of_weathernext_are_not_required():
    d = _doc("google_weathernext2_ensemble")
    for k in [k for k in d["hourly"] if k.startswith(("relative_humidity_2m", "wind_gusts_10m"))]:
        d["hourly"][k] = [None] * 384
    assert L.validate(d, "google_weathernext2_ensemble")[0]


def test_slot_is_stable_within_half_day():
    from datetime import datetime, timezone
    a = L.slot(datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc))
    b = L.slot(datetime(2026, 11, 5, 11, 59, tzinfo=timezone.utc))
    c = L.slot(datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc))
    assert a == b == "20261105_00z" and c == "20261105_12z"


def test_ec46_validator_accepts_complete_and_rejects_short_or_missing_members():
    from tempest.ops import logger_p4 as P4
    d = {"time": [f"d{i}" for i in range(46)]}
    for var in P4.DAILY:
        d[var] = [1.0] * 46
        for k in range(1, P4.MEMBERS):
            d[f"{var}_member{k:02d}"] = [1.0] * 46
    assert P4.validate({"daily": d})[0]
    short = {k: (v[:20] if isinstance(v, list) else v) for k, v in d.items()}
    assert not P4.validate({"daily": short})[0]
    del d["precipitation_sum_member07"]
    assert not P4.validate({"daily": d})[0]
