"""F3: atmosphere-direct check. For a list of launches with observed pad weather (CSV in the format of docs/templates/pad_observations.csv), compare the tool's sampled
atmospheres with the observations: per row and variable the observed value, the pool median, the bias, where the observation falls inside the sampled distribution (percentile,
0-100) and whether it is inside the 90 % interval. This judges the AIR directly, without the rocket model's error (2-4 times larger than the atmosphere effect on apogee).
Modes: climate ('ai') always; 'past' too when an ERA5 profile store is given (--era5-store or TEMPEST_ERA5_STORE) and the date is inside it; a pool that fell back to the climate
generator is reported as such, never scored as past.
Wind above 10 m is read from the model heights (linear in height); a wind measured below 10 m is compared with the 10 m wind and flagged (a log-law transfer is not safe in stable air).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/atmosphere_check.py FILE.csv [--n 400] [--era5-store data/pilot/profiles.zarr] [--modes ai past]
"""
import argparse
import csv
import io
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch   # noqa: E402

VARS = (("wind_speed_ms", "wind (m/s)"), ("temperature_c", "temperature (C)"), ("station_pressure_hpa", "station pressure (hPa)"), ("altimeter_hpa", "altimeter (hPa)"))


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = "".join(line for line in f if not line.lstrip().startswith("#"))
    return [r for r in csv.DictReader(io.StringIO(text)) if (r.get("flight") or "").strip()]


def num(r, k):
    v = (r.get(k) or "").strip()
    return float(v) if v else None


def pool_values(L, height_m):
    s = L._ensure_pool()["samples"]
    d = L._derive(s)
    z = np.asarray(s["height_agl"], float)
    sp = np.hypot(np.asarray(s["u"], float), np.asarray(s["v"], float))
    h = max(float(height_m or 10.0), float(z[0]))
    wind = np.array([np.interp(h, z, row) for row in sp])
    return {"wind_speed_ms": wind, "temperature_c": np.asarray(d["temperature"], float), "station_pressure_hpa": np.asarray(d["station_pressure"], float),
            "altimeter_hpa": np.asarray(d["pressure"], float)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--era5-store", default=os.environ.get("TEMPEST_ERA5_STORE"))
    ap.add_argument("--modes", nargs="*", default=["ai", "past"])
    a = ap.parse_args()
    rows = read_rows(a.csv)
    if not rows:
        raise SystemExit("no rows in " + a.csv)
    summary = {}
    for r in rows:
        print(f"\n{r['flight']}  {r['local_time']} {r['tz']}  ({r.get('source', '')})")
        hgt = num(r, "height_m") or 10.0
        if hgt < 10.0:
            print(f"  note: wind measured at {hgt:g} m is compared with the 10 m model wind (expect the observation to read low)")
        for mode in a.modes:
            if mode == "past" and not a.era5_store:
                print("  past: skipped (no ERA5 store given)")
                continue
            kw = dict(era5_store=a.era5_store) if mode == "past" else {}
            try:
                L = Launch(float(r["lat"]), float(r["lon"]), r["local_time"], tz=r["tz"], elevation=num(r, "elevation_m"), mode=mode, n=a.n, units="si", seed=a.seed, **kw)
                modes = set(L._ensure_pool()["modes"])
            except Exception as e:   # noqa: BLE001  (outside the served area or window: say so and go on)
                print(f"  {mode}: not served ({e})")
                continue
            if mode == "past" and modes != {"past"}:
                print(f"  past: the tool fell back to {sorted(modes)} for this date (outside the ERA5 store?): not scored as past")
                continue
            vals = pool_values(L, hgt)
            for key, label in VARS:
                y = num(r, key)
                if y is None:
                    continue
                x = vals[key]
                pct = 100.0 * (np.mean(x < y) + 0.5 * np.mean(x == y))
                lo, hi = np.percentile(x, [5, 95])
                inside = lo <= y <= hi
                print(f"  {mode:4s} {label:24s} observed {y:8.2f}  pool median {np.median(x):8.2f}  bias {np.median(x) - y:+7.2f}  observation at percentile {pct:5.1f}  {'inside' if inside else 'OUTSIDE'} the 90 % interval [{lo:.2f}, {hi:.2f}]")
                summary.setdefault((mode, label), []).append((np.median(x) - y, pct, inside))
    print("\nsummary (mode, variable: rows, mean bias, mean |bias|, share inside the 90 % interval; percentiles near 50 and a share near 0.9 mean a calibrated pool)")
    for (mode, label), v in summary.items():
        b = np.array([x[0] for x in v])
        print(f"  {mode:4s} {label:24s} {len(v):3d} rows  bias {b.mean():+7.2f}  |bias| {np.abs(b).mean():6.2f}  inside {np.mean([x[2] for x in v]):.2f}  percentiles {', '.join(f'{x[1]:.0f}' for x in v)}")


if __name__ == "__main__":
    main()
