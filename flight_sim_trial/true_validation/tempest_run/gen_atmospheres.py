"""Step A (project venv): Tempest-ARKNET atmospheres for the Spaceport America flights of the JARVIS-TRUE-VALIDATION set.

    cd <repo> ; TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/gen_atmospheres.py [--n 200]

Writes tempest_run/inputs/<flight>__<scenario>.npz (the sample set, canonical schema) and <flight>__<scenario>.json (what was asked and what came back).
Scenarios: ai = climate distribution for that date and hour; past = ERA5 corrected to balloons for that date and hour;
past_obs = past, then conditioned on the surface values really measured that hour at the nearest ASOS station (Truth or Consequences, a proxy: 78 m higher than the pad, tens of km away).
"""
import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch, Window   # noqa: E402

FT = 0.3048
# lat, lon: the RocketPy notebooks' Spaceport America launch site; pad elevation 1401 m (4595 ft is the site figure the flight_sim example uses)
SITE = dict(lat=32.939377, lon=-106.911986, elev_m=1401.0, tz="America/Denver")
FLIGHTS = {
    "Prometheus": dict(when="2022-06-24 09:17", truth_ft=12788.714, note="Spaceport America Cup 2022, 09:17 local (flight card)"),
    "Juno3": dict(when="2023-06-23 17:00", truth_ft=10541.339, note="Spaceport America Cup 2023, about 17:00 local (flight card)"),
    "HeartOfSteel": dict(when=("2017-06-22 09:00", "2017-06-22 14:00"), truth_ft=30411.0, note="IREC 2017-06-22; launch hour NOT known: uniform 09:00-14:00 local"),
}


def asos(station, utc_dt):
    """Linear interpolation between the two hourly ASOS reports around utc_dt -> dict(speed_ms, from_deg, temp_c, hours_apart). Wind by components."""
    path = os.path.join(REPO, "data", "raw", "asos", station, f"{utc_dt.year}.csv")
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            try:
                t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if abs((t - utc_dt).total_seconds()) <= 3 * 3600:
                try:
                    kt, d, tf = float(r["sknt"]), float(r["drct"] or 0.0), float(r["tmpf"])
                except ValueError:
                    continue
                rows.append((t, kt, d, tf))
    rows.sort()
    before = [r for r in rows if r[0] <= utc_dt]
    after = [r for r in rows if r[0] >= utc_dt]
    if not before or not after:
        raise LookupError(f"no ASOS {station} reports around {utc_dt}")
    a, b = before[-1], after[0]
    w = 0.0 if a[0] == b[0] else (utc_dt - a[0]).total_seconds() / (b[0] - a[0]).total_seconds()
    comp = lambda kt, d: (-kt * 0.514444 * math.sin(math.radians(d)), -kt * 0.514444 * math.cos(math.radians(d)))   # u, v of the air
    ua, va, ub, vb = *comp(a[1], a[2]), *comp(b[1], b[2])
    u, v = ua + w * (ub - ua), va + w * (vb - va)
    return dict(speed_ms=float(math.hypot(u, v)), from_deg=float((math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0), temp_c=((a[3] + w * (b[3] - a[3])) - 32.0) / 1.8,
                hours_apart=float((b[0] - a[0]).total_seconds() / 3600.0), reports=[str(a[0]), str(b[0])])


def save_pool(L, name, extra):
    pool = L._ensure_pool()
    s = pool["samples"]
    arrays = {k: np.asarray(v) for k, v in s.items()}
    np.savez(os.path.join(HERE, "inputs", name + ".npz"), **arrays)
    meta = dict(trust=L.trust, flags=pool["flags"], modes=pool["modes"], window=pool["window"], elevation_source=pool["elevation_source"], n=int(len(s["u"])), **extra)
    json.dump(meta, open(os.path.join(HERE, "inputs", name + ".json"), "w"), indent=1, default=str)
    print(f"  {name}: {meta['n']} atmospheres, {pool['window'][:70]}; flags {pool['flags']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "inputs"), exist_ok=True)
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(REPO, "data", "pilot", "profiles.zarr")
    for fl, spec in FLIGHTS.items():
        when = spec["when"] if isinstance(spec["when"], str) else Window(earliest=spec["when"][0], latest=spec["when"][1])
        kw = dict(units="si", elevation=SITE["elev_m"], tz=SITE["tz"], n=a.n, seed=1)
        print(fl, spec["note"], flush=True)
        for mode in ("ai", "past"):
            L = Launch(SITE["lat"], SITE["lon"], when, mode=mode, **kw)
            save_pool(L, f"{fl}__{mode}", dict(flight=fl, scenario=mode, truth_ft=spec["truth_ft"]))
            if mode == "past":
                r = L.resolved_window()
                mid = r.cells_utc[len(r.cells_utc) // 2].astype(datetime).replace(tzinfo=timezone.utc)
                if isinstance(spec["when"], str):
                    mid = r.cells_utc[0].astype(datetime).replace(tzinfo=timezone.utc)
                ob = asos("TCS", mid)
                temp_pad = ob["temp_c"] + 0.0065 * (1479.0 - SITE["elev_m"])        # TCS airport is 1479 m: move the temperature down to the pad with the standard lapse rate
                Lo = L.observe(wind_10m=f"{max(ob['speed_ms'], 0.1):.2f} m/s", wind_from_deg=ob["from_deg"], temperature=f"{temp_pad:.2f} C")
                save_pool(Lo, f"{fl}__past_obs", dict(flight=fl, scenario="past_obs", truth_ft=spec["truth_ft"], asos=ob, observed_temp_pad_c=temp_pad))


if __name__ == "__main__":
    main()
