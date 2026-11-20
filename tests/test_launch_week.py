"""O3 launch-week factor port (New_Plan 28.11 item 12): Launch.launch_week matches the b4 / b38 replay rule (decaying average, alpha 1/30, IL-207b start)."""
from datetime import datetime, timezone

import numpy as np

from tempest_weather_v2 import obs as O, sitecal
from tempest_weather_v2.launch import Launch


def _tool_mean(lat, lon, elev, t):
    seed = int(t.replace(tzinfo=timezone.utc).timestamp()) % 100000
    L = Launch(lat, lon, t.strftime("%Y-%m-%d %H:%M"), tz="UTC", n=200, seed=seed, units="si", elevation=elev, mode="ai", site_cal=None)
    s = L._ensure_pool()["samples"]
    return float(np.hypot(np.asarray(s["u"])[:, 0], np.asarray(s["v"])[:, 0]).mean())


def test_launch_week_matches_b4_rule():
    lat, lon, elev = O.STATIONS["MAF"]                                   # away from TCS: start 1.0
    L = Launch(lat, lon, "2024-05-10 19:00", tz="UTC", n=200, seed=1, units="si", elevation=elev, mode="ai")
    h1, h2 = datetime(2024, 5, 8, 18), datetime(2024, 5, 9, 22)          # 13 / 17 local (CDT), two and one days before
    rd = {h1: 9.0, h2: 3.0, datetime(2024, 5, 10, 15): 20.0, datetime(2024, 4, 30, 18): 20.0}   # launch day and 10 days back: ignored
    f = L.launch_week(rd)._site_cal
    ref = 1.0
    for t, y in ((h1, 9.0), (h2, 3.0)):
        ref += (y / _tool_mean(lat, lon, elev, t) - ref) / 30.0
    assert f["method"] == "ratio" and abs(f["ratio"] - ref) < 1e-12


def test_launch_week_starts_from_il207b():
    lat, lon, elev = O.STATIONS["TCS"]
    L = Launch(lat, lon, "2024-07-10 20:00", tz="UTC", n=200, seed=1, units="si", elevation=elev, mode="ai")
    f = L.launch_week({})._site_cal["ratio"]
    assert f == float(sitecal.tcs_speed_factor(datetime(2024, 7, 10, 20))["hourly"][20]) and f != 1.0
