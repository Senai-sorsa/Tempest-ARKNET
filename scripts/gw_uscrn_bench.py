"""GW-F: a pad-like (not airport) truth in the ground-wind benchmark. USCRN Las Cruces 20 N (Jornada basin, 39 km from the Spaceport America pad, wind at 1.5 m, hourly means of
5-minute values), scaled to 10 m with the log law (z0 0.03 m, factor 1.48; valid in mixed daytime air only, so the score uses local hours 10-18, UTC-7; other hours are shown separately
and marked). Years 2019-22 (default): the station's wind is flagged bad (QC 3) from mid-2023 (15 % of 2023, all of 2024-25), so the development window cannot be used; 2019-22 are inside the
generator's training span (its ERA5 rows, never this station's wind) and inside the past-mode residual's span only before 2018, so the station is an independent truth but the years are not unseen. Variants on the same hours: raw ERA5 10 m (nearest grid point), tool climate mode ('ai'), tool past
mode, past + ERA5 anchor (past_era5_anchor=True), past + anchor + spread x1.2 (the M5c best at the airports). Speed CRPS, MAE of the median, 90 % coverage, mean speed.
GW-H: --station monahans = USCRN Monahans 6 ENE (TX, 31.62 N 102.81 W, near Midland, not an airport; clean wind 2019-25, so the development window 2024-25 is usable; local time UTC-6).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_uscrn_bench.py [--n 250] [--station lascruces|monahans] [--years 2019 2022]
"""
import argparse
import os
import sys
from datetime import timedelta, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from uscrn_compare import read_uscrn   # noqa: E402
from datetime import datetime   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402

SITES = {"lascruces": (32.61, -106.74, "America/Denver", -7), "monahans": (31.62, -102.81, "America/Chicago", -6)}


def read_station(path):
    """USCRN subhourly file -> {hour (UTC, aware): mean 1.5 m wind} (good-flag values, >= 10 of 12 per hour), as uscrn_compare.read_uscrn."""
    out = {}
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) < 23:
                continue
            try:
                w, flag = float(p[21]), p[22]
            except ValueError:
                continue
            if flag != "0" or w < 0 or w > 60:
                continue
            t = datetime.strptime(p[1] + p[2], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            h = (t - timedelta(minutes=1)).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            out.setdefault(h, []).append(w)
    return {h: float(np.mean(v)) for h, v in out.items() if len(v) >= 10}
F10 = np.log(10 / 0.03) / np.log(1.5 / 0.03)
STORE = os.path.join(REPO, "data", "pilot", "profiles.zarr")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--years", type=int, nargs=2, default=[2019, 2022])
    ap.add_argument("--station", default="lascruces", choices=sorted(SITES))
    a = ap.parse_args()
    jr = {}
    print(f"USCRN station {a.station}: using {a.years[0]}-{a.years[1]}")
    LAT, LON, TZ, OFF = SITES[a.station]
    for y in range(a.years[0], a.years[1] + 1):
        jr.update(read_uscrn(y) if a.station == "lascruces" else read_station(os.path.join(REPO, "data", "raw", "uscrn_monahans", f"CRNS_MONAHANS_{y}.txt")))
    z = xr.open_zarr(STORE)
    i = int(np.argmin((z.lat.values - LAT) ** 2 + (z.lon.values - LON) ** 2))
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(z["time"].values)}
    hs = [h for h in sorted(jr) if np.datetime64(h.replace(tzinfo=None), "h") in tt]
    rng = np.random.default_rng(0)
    pick = sorted(rng.choice(len(hs), min(a.n * 2, len(hs)), replace=False))
    variants = ("raw ERA5 10 m", "tool climate", "tool past", "past + anchor", "past + anchor + x1.2")
    res = {v: {"day": [], "other": []} for v in variants}
    used = 0
    for k in pick:
        h = hs[k]
        lt = h.astimezone(timezone(timedelta(hours=OFF)))
        part = "day" if 10 <= lt.hour <= 18 else "other"
        if len(res["tool climate"]["day"]) >= a.n and part == "day":
            continue
        y = jr[h] * F10
        ix = tt[np.datetime64(h.replace(tzinfo=None), "h")]
        e = float(np.hypot(z["u"].isel(point=i, height=0, time=ix).values, z["v"].isel(point=i, height=0, time=ix).values))
        local = h.astimezone(__import__("zoneinfo").ZoneInfo(TZ)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
        try:
            ens = {}
            L = Launch(LAT, LON, local, tz=TZ, mode="ai", n=200, units="si", seed=int(k))
            s = L._ensure_pool()["samples"]
            ens["tool climate"] = np.hypot(s["u"][:, 0], s["v"][:, 0])
            for name, kw in (("tool past", dict(past_era5_anchor=False)), ("past + anchor", dict(past_era5_anchor=True)), ("past + anchor + x1.2", dict(past_era5_anchor=True, past_wind_spread=1.2))):
                P = Launch(LAT, LON, local, tz=TZ, mode="past", era5_store=STORE, n=200, units="si", seed=int(k), **kw)
                pool = P._ensure_pool()
                assert set(pool["modes"]) == {"past"}, f"past mode fell back: {pool['modes']}"
                ens[name] = np.hypot(pool["samples"]["u"][:, 0], pool["samples"]["v"][:, 0])
        except AssertionError:
            raise
        except Exception:   # noqa: BLE001  (an hour outside the served window)
            continue
        used += 1
        res["raw ERA5 10 m"][part].append((np.array([e]), y))
        for name, x in ens.items():
            res[name][part].append((x, y))
    for part, label in (("day", "local 10-18 h (log-law scaling valid)"), ("other", "other hours (log law NOT valid in stable air: the scaled truth is too high or too low; read with care)")):
        n = len(res["tool climate"][part])
        if n == 0:
            continue
        ys = np.array([v[1] for v in res["tool climate"][part]])
        print(f"\n{label}: {n} hours {a.years[0]}-{a.years[1]}, USCRN scaled to 10 m mean {ys.mean():.2f} m/s")
        print("  variant                  CRPS   MAE(median)  cov90  mean speed")
        for name in variants:
            rows = res[name][part]
            c = np.mean([crps_ensemble(x[None, :, None], np.array([[yy]]))[0, 0] for x, yy in rows])
            mae = np.mean([abs(np.median(x) - yy) for x, yy in rows])
            cov = np.mean([coverage90(x[None, :, None], np.array([[yy]]), 0.9)[0, 0] for x, yy in rows]) if name != "raw ERA5 10 m" else float("nan")
            print(f"  {name:22s} {c:6.3f}  {mae:8.3f}    {cov:5.2f}  {np.mean([np.median(x) for x, _ in rows]):6.2f}")


if __name__ == "__main__":
    main()
