"""P3 step 2: does conditioning on the RADAR wind help on launch day? (The direct radar-vs-ERA5 comparison is unfair: ERA5 assimilates the EPZ balloon it is scored on; on launch day the
tool has no ERA5, only its climate prior plus what it can observe.) For the same EPZ days as p3_vad_vs_balloon.py (2021-23, 00Z balloon, radar NVW volume near 23:30 UTC, files cached in
data/raw/nexrad_nvw): the engine's climate pool for that place and hour (n_pool 1024, as scripts/s6_condition_eval.py), then
  free         the pool as it is,
  radar        conditioned on the radar u, v at 500 / 1000 / 1500 / 2000 m where the radar has a value (sensor sd 3.0 m/s: the measured radar-minus-balloon vector error at 0.5-2 km),
               scalar inflation 1.5 (the default),
  radar+all    conditioned on every radar level up to 5 km,
scored against the balloon on the heights from 2.5 km up (never observed at 500-2000 m; the radar+all row overlaps up to 5 km and is marked): MAE of the median, CRPS, 90 % coverage of u, v.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p3_vad_condition.py [--n 120]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from p3_vad_vs_balloon import fetch, parse   # noqa: E402
from tempest.calibrate import station   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import _core   # noqa: E402
from tempest_weather.flight import TempestFlightSimEngine   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)
SIG = {"wind_u": 3.0, "wind_v": 3.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    d = np.load(os.path.join(REPO, "data", "igra_heights", "USM00072364.npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    keep = np.flatnonzero((t.year >= 2021) & (t.year <= 2023) & (t.hour == 0))
    lat, lon = station.STATIONS["USM00072364"]
    rows = []
    done = 0
    for k in rng.permutation(keep):
        if done >= a.n:
            break
        ub, vb = d["u"][k][sel].astype(float), d["v"][k][sel].astype(float)
        if ((ub == -32768) | (vb == -32768)).any():
            continue
        ub, vb = ub * 0.1, vb * 0.1
        try:
            p = fetch(t[k] - pd.Timedelta(days=1))
            r = parse(p) if p else None
        except Exception:   # noqa: BLE001
            r = None
        if r is None:
            continue
        ur, vr = r
        try:
            eng = TempestFlightSimEngine(lat, lon, t[k].tz_localize("UTC").isoformat(), n_pool=1024, seed=int(k), elevation=station.ELEV["USM00072364"])
        except Exception:   # noqa: BLE001
            continue
        U = np.random.default_rng(1).random((400, 12))
        out = {"free": eng.sample_sobol(U)}
        for name, top in (("radar 0.5-2 km", 2000.0), ("radar+all to 5 km", 5000.0)):
            obs = {}
            for j, h in enumerate(H):
                if (500 <= h <= top) and np.isfinite(ur[j]) and np.isfinite(vr[j]) and (name.startswith("radar+all") or h in (500.0, 1000.0, 1500.0, 2000.0)):
                    obs[("wind_u", float(h))], obs[("wind_v", float(h))] = float(ur[j]), float(vr[j])
            if not obs:
                out[name] = None
                continue
            eng.condition_on_observations(obs, sensor_sigma=SIG, inflate=1.5)
            out[name] = eng.sample_sobol(U)
            eng.clear_observations()
        if any(v is None for v in out.values()):
            continue
        done += 1
        for name, b in out.items():
            for var, key, y in (("u", "u", ub), ("v", "v", vb)):
                for band, lo_, hi_ in (("2.5-5 km", 2500, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)):
                    m = (H >= lo_) & (H < hi_)
                    x = b[key][:, m]
                    cr = crps_ensemble(x[None], y[m][None])[0]
                    q = np.quantile(x, [0.05, 0.95], axis=0)
                    rows.append(dict(method=name, var=var, band=band, mae=np.abs(np.median(x, 0) - y[m]).mean(), crps=cr.mean(), cov90=((y[m] >= q[0]) & (y[m] <= q[1])).mean()))
    t2 = pd.DataFrame(rows)
    g = t2.groupby(["band", "method"])[["mae", "crps", "cov90"]].mean()
    print(f"{done} EPZ days 2021-2023 (00Z balloon, radar volume near 23:30 UTC), u and v averaged")
    for band in ("2.5-5 km", "5-12 km", "12-18 km"):
        f = g.loc[(band, "free"), "crps"]
        for meth in ("free", "radar 0.5-2 km", "radar+all to 5 km"):
            r = g.loc[(band, meth)]
            note = "  (overlaps the observed levels)" if meth.startswith("radar+all") and band == "2.5-5 km" else ""
            print(f"  {band:8s} {meth:18s} MAE {r.mae:5.2f}  CRPS {r.crps:5.2f} ({100 * (1 - r.crps / f):+5.1f} % vs free)  cov90 {r.cov90:.2f}{note}")


if __name__ == "__main__":
    main()
