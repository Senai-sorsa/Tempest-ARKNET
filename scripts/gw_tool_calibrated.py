"""M5c: the like-for-like test. The tool's past-mode 10 m speed ensemble (m = 100, mode asserted 'past'), alone and with (a) the ERA5 anchor (era5_anchor = 1), (b) spread widening about the median x1.2 / x1.4 (C4a style), (c) a site calibration of the speed ('ratio', 'hourly', 'quantile' from sitecal, fitted on 2015-23 ERA5 10 m speed against ASOS speed at the same hours and applied to every ensemble member), and combinations, against the analog ensemble of gw_analog.py, on the SAME 250 random 2024-25 daytime hours per station
(speed CRPS, MAE of the median, 90 % coverage).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_tool_calibrated.py"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ.setdefault("TEMPEST_ERA5_STORE", os.path.join(REPO, "data", "pilot", "profiles.zarr"))
import ground_wind_bench as gw   # noqa: E402
from gw_analog import feats, hours_of   # noqa: E402
from gw_extrapolate_down import load   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402
from tempest_weather_v2 import sitecal   # noqa: E402

lat0, lon0, el0 = gw.STATIONS["TCS"]
_i = api.atmosphere_set(lat0, lon0, "2024-06-12T20:00:00+00:00", n=20, mode="past", seed=0, elevation=el0)[1]
assert _i["mode"] == "past", f"past mode not available: {_i['quality']}"
z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
K = 40
W = np.array([1.0, 1.0, 1.0, 1.0, 0.6, 1.2, 1.2, 0.8, 0.8])
sp = lambda x: np.hypot(x[..., 0], x[..., 1])


def widen(U, V, s):
    mu_, mv_ = np.median(U, 1, keepdims=True), np.median(V, 1, keepdims=True)
    return mu_ + s * (U - mu_), mv_ + s * (V - mv_)


for st in gw.STATIONS:
    lat, lon, el = gw.STATIONS[st]
    Al, ul, vl, Tl = load(z, st, list(range(2015, 2024)))
    At, ut, vt, Tt = load(z, st, [2024, 2025])
    tl, tt_ = hours_of(z, st, list(range(2015, 2024))), hours_of(z, st, [2024, 2025])
    Xl, Xt = feats(ul, vl, Tl, tl), feats(ut, vt, Tt, tt_)
    mu, sd = Xl.mean(0), Xl.std(0) + 1e-9
    Zl, Zt = (Xl - mu) / sd * W, (Xt - mu) / sd * W
    pick = np.sort(np.random.default_rng(3).choice(len(Zt), 250, replace=False))
    d2 = (Zt[pick] ** 2).sum(1)[:, None] + (Zl ** 2).sum(1)[None, :] - 2 * Zt[pick] @ Zl.T
    an = sp(Al[np.argpartition(d2, K, axis=1)[:, :K]])
    obs = sp(At[pick])
    hod_l = (tl.astype("datetime64[h]").astype(np.int64) % 24)
    hod_t = (tt_[pick].astype("datetime64[h]").astype(np.int64) % 24)
    era_l = np.hypot(ul[:, 0], vl[:, 0])
    cals = {m: sitecal.fit_site(era_l, sp(Al), hod_l, method=m) for m in ("ratio", "hourly", "quantile")}
    ens = {}
    for tag, anchor in (("tool", 0.0), ("tool+anchor", 1.0)):
        U, V = [], []
        for j, i in enumerate(pick):
            t = tt_[i].astype("datetime64[s]").astype(datetime).replace(tzinfo=timezone.utc)
            atm, _ = api.atmosphere_set(lat, lon, t.isoformat(), n=100, mode="past", seed=11 + j, elevation=el, era5_anchor=anchor)
            U.append(np.asarray(atm["u"][:, 0], float)), V.append(np.asarray(atm["v"][:, 0], float))
        ens[tag] = (np.array(U), np.array(V))
    rows = {}
    for tag, (U, V) in ens.items():
        for s in (1.0, 1.2, 1.4):
            Uw, Vw = widen(U, V, s)
            base = np.hypot(Uw, Vw)
            nm = f"{tag}" + (f" widen x{s:g}" if s != 1.0 else "")
            rows[nm] = base
            for m, cal in cals.items():
                rows[nm + f" + site:{m}"] = np.stack([sitecal.apply_site(cal, base[k], np.full(base.shape[1], hod_t[k])) for k in range(len(base))])
    rows["analog ensemble (needs the station record)"] = an
    cr = lambda e: float(crps_ensemble(e[:, :, None], obs[:, None])[:, 0].mean())
    cov = lambda e: float(np.mean((obs >= np.quantile(e, 0.05, axis=1)) & (obs <= np.quantile(e, 0.95, axis=1))))
    print(f"\n{st}: 250 hours (2024-25), ASOS mean {obs.mean():.2f} m/s; raw ERA5 10 m MAE {np.abs(np.hypot(ut[pick, 0], vt[pick, 0]) - obs).mean():.3f}")
    print(f"  {'variant':50s} CRPS   MAE(med)  cov90  mean")
    for nm, e in sorted(rows.items(), key=lambda kv: cr(kv[1])):
        print(f"  {nm:50s} {cr(e):.3f}  {np.abs(np.median(e, 1) - obs).mean():.3f}    {cov(e):.2f}   {e.mean():.2f}")
