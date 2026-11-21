"""NOW2 nowcast (opt-in): predict() and Launch.observe_nowcast. Climate mode, no network, dates in 2027."""
from datetime import datetime, timezone

import numpy as np
import pytest

from tempest_weather_v2 import Launch, nowcast as NC

T = datetime(2027, 6, 16, 9, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMPEST_CACHE", str(tmp_path))


def _hist(st, u=2.0, v=1.0):
    return {s: [(u, v)] * 6 for s in [st, *NC._asset()[f"{st}_nbrs"]]}


def test_predict_shape_and_refusals():
    NC._selfcheck()
    p = NC.predict("TCS", T, _hist("TCS"), 3)
    assert p["u"][1] > 0 and p["v"][1] > 0 and 0.02 <= p["gain"] <= 1.0
    with pytest.raises(ValueError, match="lead"):
        NC.predict("TCS", T, _hist("TCS"), 4)
    with pytest.raises(ValueError, match="not one of"):
        NC.predict("XXX", T, _hist("TCS"), 3)
    short = _hist("TCS")
    short["TCS"] = short["TCS"][:3]
    with pytest.raises(ValueError, match="needs 6"):
        NC.predict("TCS", T, short, 3)
    bad = _hist("TCS")
    bad["TCS"][-1] = (float("nan"), 0.0)
    with pytest.raises(ValueError, match="finite"):
        NC.predict("TCS", T, bad, 3)


def test_predict_persistence():
    """A steady strong westerly pushes the nowcast mean above the climatological mean and by more at +1 h than at +6 h."""
    hi = {s: [(12.0, 0.0)] * 6 for s in _hist("TCS")}
    a, b = NC.predict("TCS", T, hi, 1), NC.predict("TCS", T, hi, 6)
    assert a["anomaly"][0] > b["anomaly"][0] > 0 and a["u"][1] < b["u"][1] * 1.2


def test_observe_nowcast_conditions_and_is_off_by_default():
    base = Launch("spaceport_america", "2027-06-16 06:00", mode="ai", n=300, seed=3)
    q = base.observe_nowcast("TCS", T, {s: [(12.0, 0.0)] * 6 for s in _hist("TCS")})   # launch 3 h after the last report
    a, b = base.weather(all=True), q.weather(all=True)
    assert base._obs is None or "_source" not in base._obs
    assert q._obs["_source"].startswith("nowcast TCS +3h") and b.wind_speed != a.wind_speed
    with pytest.raises(ValueError, match="covers"):
        Launch("spaceport_america", "2027-06-16 14:00", mode="ai", n=64).observe_nowcast("TCS", T, _hist("TCS"))
    with pytest.raises(ValueError, match="not one of"):
        base.observe_nowcast("XXX", T, _hist("TCS"))
