"""L2 / C1 stage 1: how much of a neighbouring station's wind anomaly is seen at another station? Fit the observation weights from data.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/obs_loso.py

Stations: the ASOS sites in tempest_weather_v2.obs.STATIONS with data in data/raw/asos (fetch with scripts/fetch_asos_extra.py). For every ordered pair (source S, target T) and every age a (source report a hours BEFORE the
target hour) the gain g = sum(aS * aT) / sum(aS^2) over u and v anomalies (month x UTC-hour climatology removed; fit years 2015-2022). Then ln g = c - d/L - |dz|/H - a/tau is fitted separately for local day (solar 08-17 h)
and night (20-05 h) (night is the stable, decoupled regime). Test years 2023-2025: variance explained when the target anomaly is predicted from the source anomaly with (a) the assumed scales of obs.py (150 km, 400 m, 6.3 h),
(b) the fitted scales, (c) the best gain per pair (an upper bound). Writes data/obs_scales.json.
"""
import json
import os
import sys
from datetime import timedelta

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402  (load_asos)
from tempest_weather_v2 import obs as O   # noqa: E402

FIT, TEST = range(2015, 2023), range(2023, 2026)
AGES = (0, 1, 2, 3, 6)


def hourly(st, years):
    return gw.load_asos(st, years)


def climatology(series, years):
    acc = {}
    for t, (u, v) in series.items():
        if t.year in years:
            acc.setdefault((t.month, t.hour), []).append((u, v))
    return {k: np.mean(vs, axis=0) for k, vs in acc.items() if len(vs) >= 20}


def anomalies(series, clim):
    return {t: (u - clim[(t.month, t.hour)][0], v - clim[(t.month, t.hour)][1]) for t, (u, v) in series.items() if (t.month, t.hour) in clim}


def pair_arrays(aS, aT, years, age, lon_T, day):
    xs, ys = [], []
    for t, (u, v) in aT.items():
        if t.year not in years:
            continue
        sh = (t.hour + lon_T / 15.0) % 24.0
        if day and not (8.0 <= sh < 17.0):
            continue
        if (not day) and not (sh >= 20.0 or sh < 5.0):
            continue
        s = aS.get(t - timedelta(hours=age))
        if s is not None:
            xs.append(s)
            ys.append((u, v))
    return np.array(xs), np.array(ys)


def main():
    ids = [s for s in O.STATIONS if os.path.isdir(os.path.join(REPO, "data", "raw", "asos", s)) and len(os.listdir(os.path.join(REPO, "data", "raw", "asos", s))) >= 5]
    print("stations with data:", ids, flush=True)
    ser = {s: hourly(s, range(2015, 2026)) for s in ids}
    clim = {s: climatology(ser[s], set(FIT)) for s in ids}
    anom = {s: anomalies(ser[s], clim[s]) for s in ids}
    rows = []
    for S in ids:
        for T in ids:
            if S == T:
                continue
            d = O.haversine_km(O.STATIONS[S][0], O.STATIONS[S][1], O.STATIONS[T][0], O.STATIONS[T][1])
            dz = abs(O.STATIONS[S][2] - O.STATIONS[T][2])
            for day in (True, False):
                for age in AGES:
                    xf, yf = pair_arrays(anom[S], anom[T], set(FIT), age, O.STATIONS[T][1], day)
                    xt, yt = pair_arrays(anom[S], anom[T], set(TEST), age, O.STATIONS[T][1], day)
                    if len(xf) < 300 or len(xt) < 100:
                        continue
                    g = float((xf * yf).sum() / (xf * xf).sum())
                    rows.append(dict(S=S, T=T, d=d, dz=dz, day=day, age=age, g=g, xt=xt, yt=yt, var=float((yt ** 2).mean())))
    print(f"{len(rows)} (pair, regime, age) cells", flush=True)
    out = {}
    for regime in ("day", "night"):
        sel = [r for r in rows if r["day"] == (regime == "day") and r["g"] > 0.02]
        if len(sel) < 20:
            continue
        A = np.array([[1.0, -r["d"], -r["dz"], -r["age"]] for r in sel])
        y = np.log([r["g"] for r in sel])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        c0, kd, kz, ka = coef
        L, H, tau = (1.0 / kd if kd > 1e-6 else 1e4), (1.0 / kz if kz > 1e-6 else 1e5), (1.0 / ka if ka > 1e-6 else 1e3)
        r2 = 1.0 - ((y - A @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        out[regime] = dict(g0=float(np.exp(c0)), L_km=float(L), H_m=float(H), tau_h=float(tau), r2_log_gain=float(r2), cells=len(sel))
        print(f"{regime:5}: g0 {np.exp(c0):.2f}  distance scale {L:7.0f} km  height scale {H:7.0f} m  age scale {tau:5.1f} h   (R2 of ln gain {r2:.2f}, {len(sel)} cells)", flush=True)
    # test-year variance explained
    def explained(pred_fn, regime):
        num = den = 0.0
        for r in rows:
            if r["day"] != (regime == "day"):
                continue
            e = r["yt"] - pred_fn(r) * r["xt"]
            num += float((e ** 2).sum())
            den += float((r["yt"] ** 2).sum())
        return 1.0 - num / den if den else float("nan")
    print("\nTEST 2023-25: share of the target anomaly variance explained by the source anomaly")
    for regime in ("day", "night"):
        if regime not in out:
            continue
        p = out[regime]
        assumed = lambda r: O.persistence_gain(r["age"]) * O.representativeness_gain(r["d"], r["dz"])
        fitted = lambda r: p["g0"] * np.exp(-r["d"] / p["L_km"] - r["dz"] / p["H_m"] - r["age"] / p["tau_h"])
        best = lambda r: r["g"]
        print(f"  {regime:5}: assumed scales {explained(assumed, regime):6.3f} | fitted scales {explained(fitted, regime):6.3f} | best gain per pair {explained(best, regime):6.3f}")
    # the same, only for the near pairs a launch would use (under 150 km)
    print("  near pairs (< 150 km):", end=" ")
    near = [r for r in rows if r["d"] < 150]
    for regime in ("day", "night"):
        if regime not in out:
            continue
        p = out[regime]
        rr = [r for r in near if r["day"] == (regime == "day")]
        if rr:
            num = sum(float(((r["yt"] - p["g0"] * np.exp(-r["d"] / p["L_km"] - r["dz"] / p["H_m"] - r["age"] / p["tau_h"]) * r["xt"]) ** 2).sum()) for r in rr)
            den = sum(float((r["yt"] ** 2).sum()) for r in rr)
            print(f"{regime} fitted {1 - num / den:.3f}", end="  ")
    print()
    print("\nMean gain (fit years) by regime, distance and age:")
    print(f"  {'regime':6} {'distance':>12} " + " ".join(f"age {g} h".rjust(8) for g in AGES))
    for regime in (True, False):
        for lo, hi in ((0, 100), (100, 200), (200, 350), (350, 1000)):
            cells = [r for r in rows if r["day"] == regime and lo <= r["d"] < hi]
            if not cells:
                continue
            vals = [np.mean([r["g"] for r in cells if r["age"] == g]) if any(r["age"] == g for r in cells) else float("nan") for g in AGES]
            print(f"  {'day' if regime else 'night':6} {f'{lo}-{hi} km':>12} " + " ".join(f"{v:8.2f}" for v in vals) + f"   ({len({(r['S'], r['T']) for r in cells})} pairs)")
    with open(os.path.join(REPO, "data", "obs_scales.json"), "w", encoding="utf-8") as f:
        json.dump(dict(fit_years="2015-2022", test_years="2023-2025", stations=ids, scales=out), f, indent=1)


if __name__ == "__main__":
    main()
