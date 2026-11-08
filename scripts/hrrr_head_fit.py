"""L12a / IL-158: fit how much to trust HRRR's 10 m wind, by regime, and score it against the fixed anchor of `Launch.observe_hrrr` (weight 1.0, spread x0.8).

    PYTHONPATH=. TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore -u scripts/hrrr_head_fit.py [--n-fit 900] [--n-test 240]

Per case: the tool's past-mode ensemble (median m, members x) and HRRR's value h for the same hour. Anchored ensemble = m + r (h - m) + k (x - m). r and k are fitted separately per regime (HRRR speed class x day / night)
on 2021-23 cases (r by least squares on the anomaly, k by a CRPS grid), then scored on the same 2024-25 test cases as scripts/hrrr_vs_asos.py. Regimes with fewer than 40 fit cases fall back to the pooled value.
Writes data/hrrr_head_weights.json. Truth: hourly ASOS u, v at TCS and MAF.
"""
import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
import hrrr_vs_asos as hv   # noqa: E402
from tempest_weather_v2 import timeutil   # noqa: E402

SPEED_EDGES = (3.0, 6.0)          # m/s: calm / moderate / strong HRRR 10 m wind


def regime(h_uv, hour, lon):
    spd = float(np.hypot(*h_uv))
    sc = int(np.searchsorted(SPEED_EDGES, spd))
    sol = timeutil.solar_hour(hour.replace(tzinfo=None), lon)
    night = int(not (8.0 <= sol < 17.0))
    return f"s{sc}n{night}"


def collect(cases, hr, asos, m, seed0):
    rows = []
    for k, (st, h) in enumerate(cases):
        hvv = hr[(st, h.year)].get(h)
        if hvv is None:
            continue
        P = np.stack(gw.ensemble(st, h, m, "past", seed0 + k))
        rows.append(dict(reg=regime(hvv, h, gw.STATIONS[st][1]), t=np.array(asos[st][h]), h=np.array(hvv), p=P))
    return rows


def fit_regime(rows):
    r, k = [], []
    for c in (0, 1):
        med = np.array([np.median(x["p"][c]) for x in rows])
        hh = np.array([x["h"][c] for x in rows])
        tt = np.array([x["t"][c] for x in rows])
        xx, yy = hh - med, tt - med
        rr = float(np.clip((xx * yy).sum() / max((xx * xx).sum(), 1e-9), 0.0, 1.0))
        best = min((np.mean([gw.crps(med[i] + rr * xx[i] + kk * (rows[i]["p"][c] - med[i]), tt[i]) for i in range(len(rows))]), kk) for kk in np.arange(0.4, 2.01, 0.1))
        r.append(rr)
        k.append(float(best[1]))
    return r, k


def anchored(x, r, k):
    out = []
    for c in (0, 1):
        med = np.median(x["p"][c])
        out.append(med + r[c] * (x["h"][c] - med) + k[c] * (x["p"][c] - med))
    return out


def mean_crps(rows, params):
    v = []
    for x in rows:
        r, k = params(x["reg"])
        a = anchored(x, r, k)
        v.append([gw.crps(a[c], x["t"][c]) for c in (0, 1)])
    return np.mean(v, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-fit", type=int, default=900)
    ap.add_argument("--n-test", type=int, default=240)
    ap.add_argument("--m", type=int, default=100)
    a = ap.parse_args()
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(REPO, "data", "pilot", "profiles.zarr")
    rng = np.random.default_rng(7)
    asos = {st: gw.load_asos(st, range(2000, 2026)) for st in gw.STATIONS}
    fit_cases = gw.sample_cases(rng, {2021, 2022, 2023}, a.n_fit, asos, list(gw.STATIONS))
    rng0 = np.random.default_rng(0)
    gw.sample_cases(rng0, {2021, 2022, 2023}, 240, asos, list(gw.STATIONS))
    gw.sample_cases(rng0, {2021, 2022, 2023}, 240, asos, list(gw.STATIONS))
    test_cases = gw.sample_cases(rng0, {2024, 2025}, a.n_test, asos, list(gw.STATIONS))               # the same 2024-25 cases as hrrr_vs_asos.py
    hr = {(st, y): hv.hrrr_series(st, y) for st in gw.STATIONS for y in (2021, 2022, 2023, 2024, 2025)}
    fit = collect(fit_cases, hr, asos, a.m, 20000)
    test = collect(test_cases, hr, asos, a.m, 5000)
    print(f"{len(fit)} fit cases, {len(test)} test cases")
    pooled = fit_regime(fit)
    table = {}
    for reg in sorted({x["reg"] for x in fit}):
        sub = [x for x in fit if x["reg"] == reg]
        table[reg] = fit_regime(sub) if len(sub) >= 40 else pooled
        print(f"  {reg}: {len(sub):4d} fit cases  r = {table[reg][0][0]:.2f}/{table[reg][0][1]:.2f}  k = {table[reg][1][0]:.1f}/{table[reg][1][1]:.1f}" + ("" if len(sub) >= 40 else "  (pooled fallback)"))
    print(f"  pooled: r = {pooled[0][0]:.2f}/{pooled[0][1]:.2f}  k = {pooled[1][0]:.1f}/{pooled[1][1]:.1f}")
    variants = {"fixed observe_hrrr (r 1.0, k 0.8)": lambda g: ([1.0, 1.0], [0.8, 0.8]),
                "pooled fit": lambda g: pooled,
                "regime fit": lambda g: table.get(g, pooled)}
    print(f"{'variant':36} {'CRPS u':>8} {'CRPS v':>8} {'mean':>7}")
    res = {}
    for name, f in variants.items():
        c = mean_crps(test, f)
        res[name] = float(c.mean())
        print(f"{name:36} {c[0]:8.3f} {c[1]:8.3f} {c.mean():7.3f}")
    # day-block-free quick uncertainty: bootstrap the paired difference regime fit - fixed over test cases
    d = np.array([np.mean([gw.crps(anchored(x, *table.get(x["reg"], pooled))[c], x["t"][c]) - gw.crps(anchored(x, [1.0, 1.0], [0.8, 0.8])[c], x["t"][c]) for c in (0, 1)]) for x in test])
    bs = [np.random.default_rng(i).choice(d, len(d)).mean() for i in range(500)]
    print(f"paired change regime fit - fixed: {d.mean():+.4f} (bootstrap 95 % interval {np.percentile(bs, 2.5):+.4f} .. {np.percentile(bs, 97.5):+.4f}, n = {len(d)})")
    with open(os.path.join(REPO, "data", "hrrr_head_weights.json"), "w", encoding="utf-8") as f:
        json.dump(dict(speed_edges=SPEED_EDGES, regimes={k: dict(r=v[0], k=v[1]) for k, v in table.items()}, pooled=dict(r=pooled[0], k=pooled[1]), test_crps=res), f, indent=1)


if __name__ == "__main__":
    main()
