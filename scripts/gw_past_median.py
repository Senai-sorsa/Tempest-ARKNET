"""M5d: why is the tool's past-mode ensemble median speed worse than the raw ERA5 10 m speed? For 150 TCS hours (2024-25) compare: ERA5 speed, speed of the median vector, median of the ensemble speeds, mean speed, and the MAE of each against ASOS.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_past_median.py"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ.setdefault("TEMPEST_ERA5_STORE", os.path.join(REPO, "data", "pilot", "profiles.zarr"))      # without it mode "past" silently falls back to the climate generator (A9)
import ground_wind_bench as gw   # noqa: E402
from tempest_weather import api   # noqa: E402
from gw_analog import hours_of   # noqa: E402
from gw_extrapolate_down import load   # noqa: E402

_i = api.atmosphere_set(*gw.STATIONS["TCS"][:2], "2024-06-12T20:00:00+00:00", n=20, mode="past", seed=0, elevation=gw.STATIONS["TCS"][2])[1]
assert _i["mode"] == "past", f"past mode not available: {_i['quality']}"
z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
for st in gw.STATIONS:
    At, ut, vt, Tt = load(z, st, [2024, 2025])
    tt_ = hours_of(z, st, [2024, 2025])
    pick = np.sort(np.random.default_rng(5).choice(len(At), 150, replace=False))
    rows = []
    for j, i in enumerate(pick):
        t = tt_[i].astype("datetime64[s]").astype(datetime).replace(tzinfo=timezone.utc)
        u, v = gw.ensemble(st, t, 100, "past", 21 + j)
        s = np.hypot(u, v)
        rows.append([np.hypot(ut[i, 0], vt[i, 0]), np.hypot(np.median(u), np.median(v)), np.median(s), s.mean(), np.hypot(At[i, 0], At[i, 1]), np.median(u) - ut[i, 0], np.median(v) - vt[i, 0], s.std()])
    r = np.array(rows)
    o = r[:, 4]
    print(f"\n{st}: {len(r)} hours, ASOS mean speed {o.mean():.2f}")
    for name, k in (("ERA5 10 m speed", 0), ("speed of the median vector", 1), ("median of ensemble speeds", 2), ("mean of ensemble speeds", 3)):
        print(f"  {name:28s} mean {r[:, k].mean():.2f}  MAE {np.abs(r[:, k] - o).mean():.3f}  bias {r[:, k].mean() - o.mean():+.2f}")
    print(f"  median-vector shift from ERA5: u {r[:, 5].mean():+.2f} v {r[:, 6].mean():+.2f} (mean), mean |shift| {np.hypot(r[:, 5], r[:, 6]).mean():.2f} m/s; ensemble speed sd {r[:, 7].mean():.2f}")
