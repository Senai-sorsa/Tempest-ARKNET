"""M5d part 2: anchor the past-mode 10 m wind ensemble on the raw ERA5 10 m wind. For each hour the tool's (u, v) ensemble is re-centred so its median vector equals the ERA5 10 m vector (weight w), and its spread about the median is scaled by s;
score the speed CRPS / MAE / 90 % coverage against ASOS. 250 random 2024-25 daytime hours per station, m = 100 (fit nothing: w, s on a small grid, so read the grid, not the best cell).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_past_anchor.py"""
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
from tempest.scoring.score import crps_ensemble   # noqa: E402

_i = api.atmosphere_set(*gw.STATIONS["TCS"][:2], "2024-06-12T20:00:00+00:00", n=20, mode="past", seed=0, elevation=gw.STATIONS["TCS"][2])[1]
assert _i["mode"] == "past", f"past mode not available: {_i['quality']}"
z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
for st in gw.STATIONS:
    At, ut, vt, Tt = load(z, st, [2024, 2025])
    tt_ = hours_of(z, st, [2024, 2025])
    pick = np.sort(np.random.default_rng(3).choice(len(At), 250, replace=False))      # the same hours as gw_tool_vs_analog.py
    U, V = [], []
    for j, i in enumerate(pick):
        t = tt_[i].astype("datetime64[s]").astype(datetime).replace(tzinfo=timezone.utc)
        u, v = gw.ensemble(st, t, 100, "past", 11 + j)
        U.append(u), V.append(v)
    U, V = np.array(U), np.array(V)
    obs = np.hypot(At[pick, 0], At[pick, 1])
    eu, ev = ut[pick, 0][:, None], vt[pick, 0][:, None]
    mu_, mv_ = np.median(U, 1, keepdims=True), np.median(V, 1, keepdims=True)
    cr = lambda e: float(crps_ensemble(e[:, :, None], obs[:, None])[:, 0].mean())
    cov = lambda e: float(np.mean((obs >= np.quantile(e, 0.05, axis=1)) & (obs <= np.quantile(e, 0.95, axis=1))))
    print(f"\n{st}: {len(pick)} hours; w = weight of the re-centring on ERA5 (0 = tool as is), s = spread scale")
    print("   w     s   speed CRPS  MAE(median)  cov90   mean speed (obs %.2f)" % obs.mean())
    for w in (0.0, 0.5, 1.0):
        for s in (1.0, 0.8, 0.6):
            cu, cv = mu_ + w * (eu - mu_), mv_ + w * (ev - mv_)
            sp = np.hypot(cu + s * (U - mu_), cv + s * (V - mv_))
            print(f"  {w:.1f}  {s:.1f}   {cr(sp):.3f}      {np.abs(np.median(sp, 1) - obs).mean():.3f}     {cov(sp):.2f}   {sp.mean():.2f}")
