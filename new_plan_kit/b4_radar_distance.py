"""New_Plan 10.2 O2: radar over distance. Score the Holloman radar (HDX, ~145 km from the Santa Teresa balloon) and the El Paso radar (EPZ,
beside the balloon) on the SAME 00Z balloon days (radar volume near 23:30 UTC the day before; files cached in data/raw/nexrad_nvw), both with
the shipped conditioning (u, v at 500 / 1000 / 1500 / 2000 m, inflation 1.5) at sensor sigma 3.0, and HDX also at 4.5 / 6.0 / 8.0 m/s.
Measurement only (no adoption): gain = CRPS skill vs free (%) at 2.5-5 km and 5-12 km, with a day-block interval on CRPS(radar) - CRPS(free),
and 90 % coverage. If HDX at 3.0 covers < 0.85 at 2.5-5 km, the smallest sigma that restores >= 0.85 is the distance term for observe_radar.
Caveat: all hours are 23 UTC (afternoon, deep mixed layer).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_radar_distance.py --seed 0     # ~40 min
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b4_radar_distance.py --n 3
Result: docs/results/logs/kit_b4_radar_distance.log
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K
from b4_radar_thinned import BANDS, H, SHIPPED, obs_at, summary
import glob

from p3_vad_vs_balloon import OUT as NVW, parse
from tempest.calibrate import station
from tempest.scoring.score import crps_ensemble
from tempest_weather.flight import TempestFlightSimEngine

BALLOON = "USM00072364"
ARMS = {"EPZ s3.0": ("EPZ", 3.0)}
ARMS.update({f"HDX s{s}": ("HDX", s) for s in (3.0, 4.5, 6.0, 8.0)})


def cached(day, radar):
    """The cached 23 UTC volume p3_vad_vs_balloon.fetch would pick (same key rule), or None: no network, only the files on disk."""
    fs = glob.glob(os.path.join(NVW, f"{radar}_NVW_{day:%Y_%m_%d}_23*"))
    return min(fs, key=lambda f: abs(int(f[-8:-6]) * 60 + int(f[-5:-3]) - 30)) if fs else None


def restoring_sigma(cov):
    """cov: {sigma: HDX 2.5-5 km coverage} -> the smallest sigma with coverage >= 0.85, or None."""
    ok = [s for s, c in sorted(cov.items()) if c >= 0.85]
    return ok[0] if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="max common days")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    K.ram_gate(3.0)
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", BALLOON + ".npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    keep = np.flatnonzero((t.year >= 2015) & (t.year <= 2025) & (t.hour == 0))
    assert not (t[keep].year >= 2026).any()
    lat, lon = station.STATIONS[BALLOON]
    elev = station.ELEV[BALLOON]
    rows, done = [], 0
    for k in np.random.default_rng(a.seed).permutation(keep):
        if done >= a.n:
            break
        ub, vb = d["u"][k][sel].astype(float), d["v"][k][sel].astype(float)
        if ((ub == -32768) | (vb == -32768)).any():
            continue
        ub, vb = ub * 0.1, vb * 0.1
        day0 = t[k] - pd.Timedelta(days=1)
        try:
            rad = {}
            for r_id in ("EPZ", "HDX"):
                p = cached(day0, r_id)
                rad[r_id] = parse(p, elev) if p else None
            if any(v is None for v in rad.values()):
                continue
            eng = TempestFlightSimEngine(lat, lon, t[k].tz_localize("UTC").isoformat(), n_pool=1024, seed=int(k) + 100000 * a.seed, elevation=elev)
        except Exception:   # noqa: BLE001  (a day without both radar files or an engine pool is skipped)
            continue
        U = np.random.default_rng(1 + a.seed).random((400, 12))
        out = {"free": eng.sample_sobol(U)}
        for name, (r_id, sig) in ARMS.items():
            obs = obs_at(SHIPPED, *rad[r_id])
            if not obs:
                break
            eng.condition_on_observations(obs, sensor_sigma={"wind_u": sig, "wind_v": sig}, inflate=1.5)
            out[name] = eng.sample_sobol(U)
            eng.clear_observations()
        if len(out) != len(ARMS) + 1:
            continue
        done += 1
        for name, b in out.items():
            for band, lo_, hi_ in BANDS:
                m = (H >= lo_) & (H < hi_)
                cr, cv = [], []
                for key, y in (("u", ub), ("v", vb)):
                    x = b[key][:, m]
                    cr.append(crps_ensemble(x[None], y[m][None])[0].mean())
                    q = np.quantile(x, [0.05, 0.95], axis=0)
                    cv.append(((y[m] >= q[0]) & (y[m] <= q[1])).mean())
                rows.append(dict(day=str(t[k].date()), method=name, band=band, crps=float(np.mean(cr)), cov90=float(np.mean(cv))))
    df = pd.DataFrame(rows)
    lines = [f"O2 radar over distance: seed {a.seed}, {done} common EPZ + HDX days (00Z Santa Teresa balloon, radar 23 UTC), shipped 4 levels 0.5-2 km, inflation 1.5"]
    if df.empty:
        lines.append("no common days")
        K.report("b4_radar_distance", lines)
        return
    s = summary(df)
    for band, _, _ in BANDS:
        piv = df[df.band == band].pivot_table(index="day", columns="method", values="crps")
        for m in ["free"] + list(ARMS):
            c, cv, sk = s[(band, m)]
            row = f"  {band:8s} {m:9s} CRPS {c:5.2f} ({sk:+5.1f} % vs free)  cov90 {cv:.2f}"
            if m != "free":
                dm, dlo, dhi = K.block_boot((piv[m] - piv["free"]).to_numpy(), list(piv.index), draws=1000)
                row += f"  minus free {dm:+.3f} [{dlo:+.3f}, {dhi:+.3f}]"
            lines.append(row)
    cov = {ARMS[m][1]: s[("2.5-5 km", m)][1] for m in ARMS if m.startswith("HDX")}
    if cov[3.0] >= 0.85:
        lines.append(f"HDX at sigma 3.0 covers {cov[3.0]:.2f} at 2.5-5 km (>= 0.85): no distance term needed.")
    else:
        rs = restoring_sigma(cov)
        lines.append(f"HDX at sigma 3.0 covers {cov[3.0]:.2f} at 2.5-5 km (< 0.85): " + (f"sigma {rs} restores >= 0.85 -> the distance term for observe_radar at ~145 km" if rs else "no tested sigma restores 0.85"))
    lines.append("Measurement only (pre-set): no adoption from this run.")
    K.report("b4_radar_distance", lines)


def _selfcheck():
    assert restoring_sigma({3.0: 0.80, 4.5: 0.86, 6.0: 0.9}) == 4.5 and restoring_sigma({3.0: 0.7}) is None


_selfcheck()
if __name__ == "__main__":
    main()
