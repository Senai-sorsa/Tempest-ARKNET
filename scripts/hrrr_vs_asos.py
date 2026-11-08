"""L1 / C3 quick test: how good is HRRR's 10 m wind against real station winds, next to the tool's climate and past modes? Same test cases as scripts/ground_wind_bench.py (2024-25).

    PYTHONPATH=. TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore scripts/hrrr_vs_asos.py [--n-test 240]

HRRR comes from Open-Meteo's historical-forecast archive (model ncep_hrrr_conus, keyless, through tempest_weather_v2._net). That archive stitches the first hours of each model run, so it is a near-analysis (short lead)
value, the best HRRR can do; it is not a day-ahead forecast. A deterministic value scores CRPS = MAE; the tool's ensembles use the exact CRPS. Truth: hourly ASOS u, v at TCS and MAF.
"""
import argparse
import os
import sys
from datetime import timedelta

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
from tempest_weather_v2 import _net   # noqa: E402


def hrrr_series(st, year):
    """-> {UTC hour datetime: (u, v)} for one station and year from the archive."""
    lat, lon, _ = gw.STATIONS[st]
    url = (f"https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&start_date={year}-01-01&end_date={year}-12-31"
           f"&hourly=wind_speed_10m,wind_direction_10m&models=ncep_hrrr_conus&wind_speed_unit=ms&timezone=UTC")
    d = _net.fetch_json(url, service="open-meteo", retries=2, timeout=60)
    h = d["hourly"]
    out = {}
    for t, sp, dr in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"]):
        if sp is None or dr is None:
            continue
        from datetime import datetime, timezone
        out[datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)] = (-sp * np.sin(np.radians(dr)), -sp * np.cos(np.radians(dr)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-test", type=int, default=240)
    ap.add_argument("--m", type=int, default=100)
    a = ap.parse_args()
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(REPO, "data", "pilot", "profiles.zarr")
    rng = np.random.default_rng(0)
    asos = {st: gw.load_asos(st, range(2000, 2026)) for st in gw.STATIONS}
    gw.sample_cases(rng, {2021, 2022, 2023}, 240, asos, list(gw.STATIONS))          # same draw order as the benchmark: the fit cases first (not used here)
    fit_cases = gw.sample_cases(rng, {2021, 2022, 2023}, 240, asos, list(gw.STATIONS))   # the benchmark's fit cases (HRRR has been archived since 2018)
    cases = gw.sample_cases(rng, {2024, 2025}, a.n_test, asos, list(gw.STATIONS))
    hr = {(st, y): hrrr_series(st, y) for st in gw.STATIONS for y in (2021, 2022, 2023, 2024, 2025)}
    # --- fit HRRR's weight on the fit years: today's anomaly of the truth against the past-mode median, regressed on HRRR's departure from it
    ft, fh, fp = [], [], []
    for k, (st, h) in enumerate(fit_cases):
        hv = hr[(st, h.year)].get(h)
        if hv is None:
            continue
        ft.append(asos[st][h])
        fh.append(hv)
        fp.append(np.stack(gw.ensemble(st, h, a.m, "past", 1000 + k)))
    FT, FH, FP = np.array(ft), np.array(fh), np.array(fp)
    rr, kk = [], []
    for c in (0, 1):
        med = np.median(FP[:, c], 1)
        x, y = FH[:, c] - med, FT[:, c] - med
        r = float(np.clip((x * y).sum() / max((x * x).sum(), 1e-9), 0.0, 1.0))
        sc = min((np.mean([gw.crps(med[i] + r * x[i] + k * (FP[i, c] - med[i]), FT[i, c]) for i in range(len(FT))]), k) for k in np.arange(0.5, 2.6, 0.1))[1]
        rr.append(r)
        kk.append(float(sc))
    print(f"fitted on {len(FT)} cases (2021-23): HRRR weight r = {rr[0]:.2f} (u), {rr[1]:.2f} (v); remaining past-mode spread scale k = {kk[0]:.1f}, {kk[1]:.1f}")
    rows, ens_ai, ens_past, truth, hrrr = [], [], [], [], []
    for k, (st, h) in enumerate(cases):
        hv = hr[(st, h.year)].get(h)
        if hv is None:
            continue
        truth.append(asos[st][h])
        hrrr.append(hv)
        ens_ai.append(np.stack(gw.ensemble(st, h, a.m, "ai", 5000 + k)))
        ens_past.append(np.stack(gw.ensemble(st, h, a.m, "past", 5000 + k)))
    T, H, A, P = (np.array(x) for x in (truth, hrrr, ens_ai, ens_past))
    n = len(T)
    print(f"{n} test cases (2024-25) with ASOS truth and HRRR values")
    print(f"{'variant':36} {'CRPS u':>8} {'CRPS v':>8} {'mean':>7}   bias u / v")
    def line(name, crps_u, crps_v, bu, bv):
        print(f"{name:36} {crps_u:8.3f} {crps_v:8.3f} {(crps_u + crps_v) / 2:7.3f}   {bu:+.2f} / {bv:+.2f}")
    line("HRRR (near-analysis, deterministic)", *[np.mean(np.abs(H[:, c] - T[:, c])) for c in (0, 1)], *[np.mean(H[:, c] - T[:, c]) for c in (0, 1)])
    line("tool climate mode (ensemble CRPS)", *[np.mean([gw.crps(A[i, c], T[i, c]) for i in range(n)]) for c in (0, 1)], *[np.mean(np.median(A[:, c], 1) - T[:, c]) for c in (0, 1)])
    line("tool past mode (ensemble CRPS)", *[np.mean([gw.crps(P[i, c], T[i, c]) for i in range(n)]) for c in (0, 1)], *[np.mean(np.median(P[:, c], 1) - T[:, c]) for c in (0, 1)])
    line("tool past mode median only (MAE)", *[np.mean(np.abs(np.median(P[:, c], 1) - T[:, c])) for c in (0, 1)], *[0.0, 0.0])
    # HRRR as the centre of the past-mode spread: shift the past ensemble to HRRR's value and keep its (inflated x1.2) spread
    Q = np.array([[H[i, c] + 1.2 * (P[i, c] - np.median(P[i, c])) for c in (0, 1)] for i in range(n)])
    W = np.array([[np.median(P[i, c]) + rr[c] * (H[i, c] - np.median(P[i, c])) + kk[c] * (P[i, c] - np.median(P[i, c])) for c in (0, 1)] for i in range(n)])
    line(f"past + HRRR (fitted r {rr[0]:.2f}/{rr[1]:.2f}, k {kk[0]:.1f}/{kk[1]:.1f})", *[np.mean([gw.crps(W[i, c], T[i, c]) for i in range(n)]) for c in (0, 1)], *[np.mean(np.median(W[:, c], 1) - T[:, c]) for c in (0, 1)])
    line("HRRR centre + past spread x 1.2", *[np.mean([gw.crps(Q[i, c], T[i, c]) for i in range(n)]) for c in (0, 1)], *[np.mean(np.median(Q[:, c], 1) - T[:, c]) for c in (0, 1)])
    R = np.array([[0.5 * (H[i, c] + np.median(P[i, c])) + 1.2 * (P[i, c] - np.median(P[i, c])) for c in (0, 1)] for i in range(n)])
    line("mean of HRRR and past median + spread", *[np.mean([gw.crps(R[i, c], T[i, c]) for i in range(n)]) for c in (0, 1)], *[np.mean(np.median(R[:, c], 1) - T[:, c]) for c in (0, 1)])
    sp = lambda x: np.hypot(x[..., 0], x[..., 1])
    print(f"wind SPEED mean abs error: HRRR {np.mean(np.abs(sp(H) - sp(T))):.2f} m/s, tool past median {np.mean(np.abs(sp(np.median(P, 2)) - sp(T))):.2f}, tool climate median {np.mean(np.abs(sp(np.median(A, 2)) - sp(T))):.2f}")


if __name__ == "__main__":
    main()
