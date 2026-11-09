"""IL-164 / roadmap A4: balloon-matched fine-scale shear through the turbulence step. Real balloon shear is about 1.7x ERA5 at every quantile (IL-103); the calibrated model carries about
80 % of it in the free troposphere and 45 % at 0-1 km. Instead of pushing the profile (that fights the ERA5-corrected truth), scale the Dryden turbulence (tempest_weather.flight.dryden,
clear-air term aloft, boundary-layer term below) per height band so that profile + turbulence reproduces the balloon shear quantiles between the model heights.
Balloons: EPZ (72364), MAF (72265), 00Z (12Z is outside the tool's served hours), interpolated to the model heights (data/igra_heights). Tool: climate mode n = 60 per sounding.
Fit the per-band factor on 2021-23 (calibration years), check on 2024-25 (development window). Metric: shear quantiles p50 / p90 / p99 per band, ratio tool / balloon.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il164_turb_shear.py [--n 80]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest.calibrate import station   # noqa: E402
from tempest_weather import _core   # noqa: E402
from tempest_weather.flight import dryden   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402

BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
Q = np.array([0.5, 0.9, 0.99])
TZ = {"USM00072364": "America/Denver", "USM00072265": "America/Chicago"}
SCALES = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0])
H = np.asarray(_core.HEIGHTS, float)
MID = H[1:]


def shear(u, v):
    return np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / (np.diff(H) / 1000.0)


def balloons(sid, y0, y1):
    d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
    sel = np.array([np.argmin(np.abs(d["heights"] - h)) for h in H])
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    keep = (t.year >= y0) & (t.year <= y1) & (t.hour == 0)
    u, v = d["u"][keep][:, sel].astype(float), d["v"][keep][:, sel].astype(float)
    bad = (u == -32768) | (v == -32768)
    u[bad], v[bad] = np.nan, np.nan
    return t[keep], u * 0.1, v * 0.1


def collect(y0, y1, n, rng):
    """-> balloon shear (rows, 43), tool profile shear (rows*m, 43), tool turbulence-included shear per scale {s: (rows*m, 43)}."""
    sb, st, sturb = [], [], {s: [] for s in SCALES}
    for sid in station.STATIONS:
        t, ub, vb = balloons(sid, y0, y1)
        ok = np.flatnonzero(np.isfinite(ub).all(1) & np.isfinite(vb).all(1))
        for k in rng.choice(ok, min(n, len(ok)), replace=False):
            lat, lon = station.STATIONS[sid]
            local = t[k].tz_localize("UTC").tz_convert(TZ[sid]).tz_localize(None)
            try:
                s = Launch(lat, lon, local.strftime("%Y-%m-%d %H:%M"), mode="ai", n=60, units="si", elevation=station.ELEV[sid], tz=TZ[sid], seed=int(k))._ensure_pool()["samples"]
            except Exception:   # noqa: BLE001
                continue
            u, v, T = (np.asarray(s[x], float) for x in ("u", "v", "T"))
            f = dryden.synthesize(H, u, v, T, dz=10.0, seed=int(k), z_top=float(H[-1]))
            ut = np.stack([np.interp(H, f["z"], row) for row in f["u_turb"]])
            vt = np.stack([np.interp(H, f["z"], row) for row in f["v_turb"]])
            sb.append(shear(ub[k][None], vb[k][None]))
            st.append(shear(u, v))
            for sc in SCALES:
                sturb[sc].append(shear(u + sc * ut, v + sc * vt))
    return np.concatenate(sb), np.concatenate(st), {sc: np.concatenate(x) for sc, x in sturb.items()}


def band_q(x, lo, hi):
    m = (MID > lo) & (MID <= hi)
    return np.quantile(x[:, m].ravel(), Q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    fit, test = collect(2021, 2023, a.n, rng), collect(2024, 2025, a.n, rng)
    print(f"soundings: fit 2021-23 {len(fit[0])}, test 2024-25 {len(test[0])} (00Z, EPZ + MAF); tool n = 60 per sounding")
    print("shear quantiles p50 / p90 / p99 (m/s per km), ratio tool / balloon; the turbulence factor per band is fitted on 2021-23 (smallest mean |log ratio| over the three quantiles)")
    for b, lo, hi in BANDS:
        qb_f, qb_t = band_q(fit[0], lo, hi), band_q(test[0], lo, hi)
        err = {sc: np.mean(np.abs(np.log(band_q(fit[2][sc], lo, hi) / qb_f))) for sc in SCALES}
        best = min(err, key=err.get)
        r0, r1, rb = band_q(test[1], lo, hi) / qb_t, band_q(test[2][1.0], lo, hi) / qb_t, band_q(test[2][best], lo, hi) / qb_t
        print(f"  {b:8s} balloon test {qb_t.round(1)} | profile only {r0.round(2)} | + turbulence x1 {r1.round(2)} | + turbulence x{best:g} (fitted) {rb.round(2)}")


if __name__ == "__main__":
    main()
