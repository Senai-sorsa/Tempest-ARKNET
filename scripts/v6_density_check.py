"""V6: air density and pressure against balloons. Density feeds the drag (apogee), pressure the altimeter and the density; 1 hPa is about 8 m of altitude.
Truth: IGRA2 derived soundings at Santa Teresa (EPZ) and Midland (MAF), 00Z 2024-25 (development window), MEASURED pressure and temperature, humidity -> virtual temperature,
density = p / (Rd Tv), at fixed heights above the launch point (log-pressure interpolation). Tool: climate mode (mode 'ai', the Monte Carlo source) for that date and hour, n = 400,
seed per case. Baseline: the 1976 US standard atmosphere at the same height above sea level (what many flight simulators use when no weather is given).
Per height: bias of the median (%), MAE of the median (%), CRPS (% of the mean truth), 90 % interval coverage; standard atmosphere: bias and MAE.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/v6_density_check.py [--n 150]
"""
import argparse
import io
import os
import sys
import zipfile

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.calibrate import station   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402
from tempest_weather import _core   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402

RD, EPS = 287.05, 0.622
Z_AGL = np.array([0.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0, 7000.0, 10000.0])
TZ = {"USM00072364": "America/Denver", "USM00072265": "America/Chicago"}


def es_hpa(t_k):
    return 6.1094 * np.exp(17.625 * (t_k - 273.15) / (t_k - 273.15 + 243.04))


def read_soundings(path, y0, y1):
    """-> list of (UTC time, p (Pa), T (K), RH (%), height above the launch point (m)) for nominal 00Z soundings."""
    out = []
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
        lines = io.TextIOWrapper(f, "ascii", errors="replace")
        for line in lines:
            if not line.startswith("#"):
                continue
            year, hour, n = int(line[13:17]), int(line[24:26]), int(line[31:36])
            block = [next(lines) for _ in range(n)]
            if not (y0 <= year <= y1 and hour == 0) or n < 10:
                continue
            a = np.array([[int(r[8 * i:8 * i + 7]) for i in (0, 2, 3, 12)] for r in block], float)
            a[a <= -9999] = np.nan
            p, gph, t, rh = a.T
            ok = np.isfinite(p) & np.isfinite(gph) & np.isfinite(t)
            if ok.sum() < 10 or not ok[0]:
                continue
            h = station.geometric_height(gph * station.G0) - station.geometric_height(gph[0] * station.G0)
            out.append((pd.Timestamp(f"{line[13:17]}-{line[18:20]}-{line[21:23]}T00:00"), p[ok], t[ok] / 10, np.nan_to_num(rh[ok] / 10, nan=0.0), h[ok]))
    return out


def balloon_at(p, t, rh, h, z):
    """pressure and density of the balloon at heights z above the launch point (NaN above the top)."""
    if h.max() < z.max():
        return None
    o = np.argsort(h)
    h, p, t, rh = h[o], p[o], t[o], rh[o]
    lp = np.interp(z, h, np.log(p))
    tz, rz = np.interp(z, h, t), np.interp(z, h, rh)
    pz = np.exp(lp)
    e = np.clip(rz, 0, 100) / 100 * es_hpa(tz) * 100.0
    q = EPS * e / (pz - (1 - EPS) * e)
    tv = tz * (1 + 0.61 * q)
    return pz, pz / (RD * tv)


def standard_atmosphere(z_asl):
    z = np.asarray(z_asl, float)
    t = np.where(z < 11000, 288.15 - 0.0065 * z, 216.65)
    p = np.where(z < 11000, 101325 * (t / 288.15) ** 5.25588, 22632.1 * np.exp(-9.80665 * (z - 11000) / (RD * 216.65)))
    return p, p / (RD * t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    cases = []
    for sid in station.STATIONS:
        for c in read_soundings(os.path.join(REPO, "data", "raw", "igra_2026", f"{sid}-drvd.txt.zip"), 2024, 2025):
            cases.append((sid,) + c)
    pick = rng.choice(len(cases), min(a.n, len(cases)), replace=False)
    H = np.asarray(_core.HEIGHTS, float)
    rows = []
    for k in pick:
        sid, t_utc, p, t, rh, h = cases[k]
        b = balloon_at(p, t, rh, h, Z_AGL)
        if b is None:
            continue
        lat, lon = station.STATIONS[sid]
        local = t_utc.tz_localize("UTC").tz_convert(TZ[sid]).tz_localize(None)
        try:
            s = Launch(lat, lon, local.strftime("%Y-%m-%d %H:%M"), mode="ai", n=400, units="si", elevation=station.ELEV[sid], tz=TZ[sid], seed=int(k))._ensure_pool()["samples"]
        except Exception:   # noqa: BLE001  (an hour outside the served window is skipped)
            continue
        tp = np.stack([np.interp(Z_AGL, H, row) for row in np.asarray(s["p"], float)])
        tr = np.stack([np.interp(Z_AGL, H, row) for row in np.asarray(s["rho"], float)])
        tp[:, 0] = np.asarray(s["sp"], float)          # at the ground: the surface pressure (the profile starts at 10 m; density at 10 m is used for 0 m, 0.1 % off)
        sp_, sr_ = standard_atmosphere(station.ELEV[sid] + Z_AGL)
        rows.append((sid, b[0], b[1], tp, tr, sp_, sr_))
    print(f"{len(rows)} soundings (00Z, 2024-25, EPZ {sum(r[0] == 'USM00072364' for r in rows)}, MAF {sum(r[0] == 'USM00072265' for r in rows)})")
    for name, ib, it, isd in (("pressure", 1, 3, 5), ("density", 2, 4, 6)):
        print(f"\n{name}: height AGL | tool: bias of median %, MAE of median %, CRPS % of truth, cov90 | standard atmosphere: bias %, MAE %")
        for j, z in enumerate(Z_AGL):
            y = np.array([r[ib][j] for r in rows])
            ens = np.stack([r[it][:, j] for r in rows])
            med = np.median(ens, 1)
            lo, hi = np.percentile(ens, 5, 1), np.percentile(ens, 95, 1)
            crps = crps_ensemble(ens[..., None], y[:, None])[:, 0]
            sa = np.array([r[isd][j] for r in rows])
            print(f"  {z:7.0f} m | {100 * np.mean((med - y) / y):+6.2f}  {100 * np.mean(np.abs(med - y) / y):5.2f}  {100 * crps.mean() / y.mean():5.2f}  {np.mean((y >= lo) & (y <= hi)):.2f} | "
                  f"{100 * np.mean((sa - y) / y):+6.2f}  {100 * np.mean(np.abs(sa - y) / y):5.2f}")


if __name__ == "__main__":
    main()
