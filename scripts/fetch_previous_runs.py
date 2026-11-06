"""A1 (Downloads to do.md): lead-time history of the live models at the registered sites, surface variables, from the Open-Meteo Previous Runs API.

    python scripts/fetch_previous_runs.py [--first 2021-01] [--models ecmwf_ifs025 gfs_seamless] [--out data/raw/om_previous_runs] [--sleep 4]

For every site in configs/sites.toml, every model and every month from --first to last month: hourly `<variable>_previous_day1 ... _previous_day7` for 2 m temperature, 2 m
dew point, 10 m wind speed and direction, and surface pressure (surface only: pressure-level variants are refused by the API). One request per site, model and month, saved as
<out>/<site>/<model>/<yyyymm>.json; existing months are skipped; months with only nulls (before the model's archive starts) are recorded in <out>/<site>/<model>/empty.txt so
they are not asked again. A pause between calls keeps far below the free limit. The self-check at the end asserts that previous_day1 and previous_day3 differ (real leads).
"""
import argparse
import json
import os
import time
from datetime import date

import numpy as np

from tempest.ingest import openmeteo as om
from tempest.ops import logger as lg

VARS = ["temperature_2m", "dew_point_2m", "wind_speed_10m", "wind_direction_10m", "surface_pressure"]
DAYS = range(1, 8)


def months(first, today=None):
    today = today or date.today()
    y, m = map(int, first.split("-"))
    while (y, m) < (today.year, today.month):                    # complete months only
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def month_range(y, m):
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return date(y, m, 1).isoformat(), (nxt - date.resolution).isoformat()


def has_data(doc):
    h = doc.get("hourly", {})
    return any(v is not None for k, vals in h.items() if k != "time" for v in vals)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--first", default="2021-01")
    ap.add_argument("--models", nargs="*", default=["ecmwf_ifs025", "gfs_seamless"])
    ap.add_argument("--out", default="data/raw/om_previous_runs")
    ap.add_argument("--sleep", type=float, default=4.0)
    a = ap.parse_args()
    hourly = [f"{v}_previous_day{d}" for v in VARS for d in DAYS]
    got = skipped = 0
    for site in lg.sites():
        for model in a.models:
            d = os.path.join(a.out, site["name"], model)
            os.makedirs(d, exist_ok=True)
            empty_file = os.path.join(d, "empty.txt")
            empty = set(open(empty_file).read().split()) if os.path.exists(empty_file) else set()
            for y, m in months(a.first):
                tag = f"{y}{m:02d}"
                path = os.path.join(d, tag + ".json")
                if os.path.exists(path) or tag in empty:
                    skipped += 1
                    continue
                s, e = month_range(y, m)
                try:
                    doc = om.previous_runs(site["lat"], site["lon"], model, hourly, s, e, cache_dir=os.path.join(a.out, "_cache"))
                except Exception as ex:  # noqa: BLE001 - one bad month must not stop the rest
                    print(f"{site['name']} {model} {tag}: {type(ex).__name__}: {str(ex)[:120]}", flush=True)
                    time.sleep(a.sleep * 4)
                    continue
                if has_data(doc):
                    with open(path + ".part", "w", encoding="utf-8") as f:
                        json.dump(doc, f)
                    os.replace(path + ".part", path)
                    got += 1
                else:
                    with open(empty_file, "a") as f:
                        f.write(tag + "\n")
                print(f"{site['name']} {model} {tag}: {'saved' if has_data(doc) else 'no data (before the archive starts)'}", flush=True)
                time.sleep(a.sleep)
    print(f"done: {got} new months, {skipped} already there", flush=True)
    # self-check: real leads, not a copy of the analysis
    for site in lg.sites():
        for model in a.models:
            files = sorted(f for f in os.listdir(os.path.join(a.out, site["name"], model)) if f.endswith(".json"))
            if not files:
                continue
            h = json.load(open(os.path.join(a.out, site["name"], model, files[-1]), encoding="utf-8"))["hourly"]
            x1 = np.array([v if v is not None else np.nan for v in h["temperature_2m_previous_day1"]], float)
            x3 = np.array([v if v is not None else np.nan for v in h["temperature_2m_previous_day3"]], float)
            ok = np.isfinite(x1) & np.isfinite(x3)
            print(f"self-check {site['name']} {model} {files[-1]}: mean |day1 - day3| = {np.abs(x1[ok] - x3[ok]).mean():.3f} K over {int(ok.sum())} hours", flush=True)
            assert np.abs(x1[ok] - x3[ok]).mean() > 0.05, "previous_day1 equals previous_day3: the API returned the analysis, not lead history"


if __name__ == "__main__":
    main()
