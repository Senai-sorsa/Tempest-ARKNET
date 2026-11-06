"""Stage 6 check of module 2: does conditioning on launch-day measurements improve the profile above them, on real balloons?

For N held-out 00Z soundings (Santa Teresa and Midland, 2024-25) the engine builds a pool for that place and date with the climate generator (no forecast, as for a day-of query that has
only climatology plus the measurements), then three versions of the atmosphere are compared with the balloon above the measured part:
  free      the pool as it is,
  schur     Gaussian-copula conditioning (condition_on_observations, observed values pinned),
  weights   importance weights and resampling of the pool (observe_by_weights).
Measurements taken from the balloon itself: 2 m temperature (surface value), 10 m wind, surface pressure, and a partial sounding of u, v, T at 500, 1000, 1500, 2000 m, with sensor noise
(T 0.3 K, wind 0.8 m/s, pressure 50 Pa) added. Scored on the heights from 2.5 km up (never measured): MAE of the median and CRPS, per variable and band, plus the share of the 90 %
interval that holds the balloon.
    PYTHONPATH=. python scripts/s6_condition_eval.py [--n 150]"""
import argparse

import numpy as np
import pandas as pd

from tempest.calibrate import station
from tempest.profiles.to_heights import HEIGHTS
from tempest.scoring.score import crps_ensemble
from tempest_weather import api
from tempest_weather.flight import TempestFlightSimEngine

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=150)
ap.add_argument("--assets", default=None)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--inflate", type=float, nargs="*", default=[1.0, 1.5, 2.0])
a = ap.parse_args()
rng = np.random.default_rng(a.seed)
NH = len(HEIGHTS)
obs_h = [500.0, 1000.0, 1500.0, 2000.0]
SIG = {"wind_u": 0.8, "wind_v": 0.8, "temp_K": 0.3, "pressure_Pa": 50.0}
cases = []
for sid, (lat, lon) in station.STATIONS.items():
    t, prof, sfc = station.read_igra(f"data/raw/igra_2026/{sid}-drvd.txt.zip", 2024, 2025)
    ok = np.isfinite(prof).all((1, 2)) & (t.hour == 0)
    for i in np.flatnonzero(ok):
        cases.append((sid, lat, lon, t[i], prof[i], sfc[i]))
pick = rng.choice(len(cases), min(a.n, len(cases)), replace=False)
rows = []
for k in pick:
    sid, lat, lon, tt, prof, sfc = cases[k]
    try:
        eng = TempestFlightSimEngine(lat, lon, tt.tz_localize("UTC").isoformat(), n_pool=1024, seed=int(k), assets=a.assets, elevation=station.ELEV[sid])
    except Exception as e:  # noqa: BLE001 - a case outside the served window is skipped
        continue
    truth = prof                                              # (4, 44): u, v, T, RH above the launch point
    obs = {("wind_u", 10.0): truth[0, 0], ("wind_v", 10.0): truth[1, 0], ("temp_K", 2.0): sfc[0], ("pressure_Pa", 0.0): sfc[1]}
    for h in obs_h:
        j = int(np.argmin(np.abs(HEIGHTS - h)))
        obs[("wind_u", float(HEIGHTS[j]))], obs[("wind_v", float(HEIGHTS[j]))], obs[("temp_K", float(HEIGHTS[j]))] = truth[0, j], truth[1, j], truth[2, j]
    noisy = {key: val + rng.normal(0, SIG[key[0]]) for key, val in obs.items()}
    u = np.random.default_rng(1).random((400, 12))
    free = eng.sample_sobol(u)
    schur = {}
    for infl in a.inflate:
        eng.condition_on_observations(noisy, sensor_sigma=SIG, inflate=infl)
        schur[f"schur x{infl:g}"] = eng.sample_sobol(u)
    eng.clear_observations()
    wts, ess = eng.observe_by_weights(noisy, SIG, 400)
    sel = HEIGHTS >= 2500
    for name, b in [("free", free), *schur.items(), ("weights", wts)]:
        for vi, (var, key) in enumerate((("u", "u"), ("v", "v"), ("T", "T"))):
            x = b[key][:, sel]                                 # (400, nh)
            y = truth[vi][sel]
            cr = crps_ensemble(x[None], y[None])[0]
            lo, hi = np.quantile(x, [0.05, 0.95], axis=0)
            rows.append(dict(method=name, var=var, band="2.5-12 km", mae=np.abs(np.median(x, 0) - y)[HEIGHTS[sel] <= 12000].mean(), crps=cr[HEIGHTS[sel] <= 12000].mean(), cov90=((y >= lo) & (y <= hi))[HEIGHTS[sel] <= 12000].mean(), ess=ess if name == "weights" else np.nan))
            rows.append(dict(method=name, var=var, band="12-18 km", mae=np.abs(np.median(x, 0) - y)[HEIGHTS[sel] > 12000].mean(), crps=cr[HEIGHTS[sel] > 12000].mean(), cov90=((y >= lo) & (y <= hi))[HEIGHTS[sel] > 12000].mean(), ess=np.nan))
t = pd.DataFrame(rows)
g = t.groupby(["var", "band", "method"])[["mae", "crps", "cov90"]].mean()
free = g.xs("free", level="method")
out = []
for (var, band, m), r in g.iterrows():
    out.append(dict(var=var, band=band, method=m, mae=r.mae, crps=r.crps, crps_vs_free=f"{(1 - r.crps / free.loc[(var, band), 'crps']) * 100:+.1f} %", cov90=r.cov90))
print(f"{len(t) // (6 * (len(a.inflate) + 2))} soundings scored; effective sample size of the weights: median {t.ess.median():.1f} of 1024")
print(pd.DataFrame(out).round(3).to_string(index=False))
