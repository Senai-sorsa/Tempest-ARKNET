"""IL-166 (from V6): is the mid-troposphere temperature (and so density) spread too narrow against balloons, and does one spread factor per height fitted on balloons fix it?
Balloons EPZ + MAF 00Z: fit on 2021-23 (calibration years), test on 2024-25 (development window). Tool climate mode n = 400 per sounding. Per height (0.5-10 km AGL): factor s that
scales the deviations of the pool from its median so the 90 % interval holds 90 % of the 2021-23 balloons (bisection); then on 2024-25: coverage and CRPS of T and of density,
before and after (density rebuilt from the scaled T with the pool's own pressure and humidity, first order: rho ~ 1 / T).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il166_t_spread.py [--n 150]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from v6_density_check import RD, TZ, balloon_at, read_soundings   # noqa: E402
from tempest.calibrate import station   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import _core   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402

Z = np.array([500.0, 1000.0, 2000.0, 3000.0, 5000.0, 7000.0, 10000.0])


def collect(y0, y1, n, rng):
    cases = []
    for sid in station.STATIONS:
        for c in read_soundings(os.path.join(REPO, "data", "raw", "igra_2026", f"{sid}-drvd.txt.zip"), y0, y1):
            cases.append((sid,) + c)
    H = np.asarray(_core.HEIGHTS, float)
    out = []
    for k in rng.choice(len(cases), min(n, len(cases)), replace=False):
        sid, t_utc, p, t, rh, h = cases[k]
        b = balloon_at(p, t, rh, h, Z)
        if b is None:
            continue
        o = np.argsort(h)
        tb = np.interp(Z, h[o], t[o])
        lat, lon = station.STATIONS[sid]
        local = t_utc.tz_localize("UTC").tz_convert(TZ[sid]).tz_localize(None)
        try:
            s = Launch(lat, lon, local.strftime("%Y-%m-%d %H:%M"), mode="ai", n=400, units="si", elevation=station.ELEV[sid], tz=TZ[sid], seed=int(k) + 7)._ensure_pool()["samples"]
        except Exception:   # noqa: BLE001
            continue
        T = np.stack([np.interp(Z, H, row) for row in np.asarray(s["T"], float)])
        R = np.stack([np.interp(Z, H, row) for row in np.asarray(s["rho"], float)])
        out.append((tb, b[1], T, R))
    return out


def cover(ens, y):
    lo, hi = np.percentile(ens, 5, 1), np.percentile(ens, 95, 1)
    return float(np.mean((y >= lo) & (y <= hi)))


def scale(ens, s):
    med = np.median(ens, 1, keepdims=True)
    return med + s * (ens - med)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    fit, test = collect(2021, 2023, a.n, rng), collect(2024, 2025, a.n, rng)
    print(f"fit 2021-23: {len(fit)} soundings; test 2024-25: {len(test)} soundings (00Z, EPZ + MAF)")
    print(" height | factor (fit) | T test: cov90 before -> after, CRPS K before -> after | density test: cov90 before -> after, CRPS % before -> after")
    for j, z in enumerate(Z):
        yf = np.array([c[0][j] for c in fit])
        ef = np.stack([c[2][:, j] for c in fit])
        lo_s, hi_s = 0.5, 3.0
        for _ in range(30):
            mid = 0.5 * (lo_s + hi_s)
            lo_s, hi_s = (mid, hi_s) if cover(scale(ef, mid), yf) < 0.90 else (lo_s, mid)
        s = 0.5 * (lo_s + hi_s)
        yt, et = np.array([c[0][j] for c in test]), np.stack([c[2][:, j] for c in test])
        rt, er = np.array([c[1][j] for c in test]), np.stack([c[3][:, j] for c in test])
        et2 = scale(et, s)
        er2 = er * et / et2                                   # density at fixed pressure and humidity scales as 1 / T
        c0, c1 = crps_ensemble(et[..., None], yt[:, None])[:, 0].mean(), crps_ensemble(et2[..., None], yt[:, None])[:, 0].mean()
        d0, d1 = crps_ensemble(er[..., None], rt[:, None])[:, 0].mean(), crps_ensemble(er2[..., None], rt[:, None])[:, 0].mean()
        print(f" {z:6.0f} | {s:5.2f}        | {cover(et, yt):.2f} -> {cover(et2, yt):.2f}, {c0:.3f} -> {c1:.3f} | {cover(er, rt):.2f} -> {cover(er2, rt):.2f}, {100 * d0 / rt.mean():.3f} -> {100 * d1 / rt.mean():.3f}")


if __name__ == "__main__":
    main()
