"""Build / refresh the EWMA bias state of the live forecast feed for every registered site (IL-98 item B).

    PYTHONPATH=. python scripts/update_bias.py [--out data/ops/bias] [--model ecmwf_ifs025] [--refresh]

Reads the Previous Runs history (data/raw/om_previous_runs) and the ASOS reports (data/raw/asos, data/raw/asos_2026), replays the same tracker as scripts/bias_backtest.py (alpha = 1/30 per day,
one EWMA per UTC hour and lead 1..7 d) and writes <out>/<site>_<model>.json for tempest_weather.bias. With --refresh the current and the previous month are requested again first (network).
Run it daily after the logger; the tool uses the files only when you pass bias_dir to the forecast query (default off)."""
import argparse
import json
import os
from datetime import date

import numpy as np
import pandas as pd

from scripts import bias_backtest as bb
from tempest.ingest import openmeteo as om
from tempest.ops import logger as lg


def refresh(site, model, today):
    """Re-request this month and last month into the Previous Runs folder (overwrites those two files)."""
    hourly = [f"{v}_previous_day{d}" for v in ("temperature_2m", "wind_speed_10m") for d in range(1, 8)]
    for k in (1, 0):
        y, m = (today.year, today.month - k) if today.month - k >= 1 else (today.year - 1, 12)
        s, e = f"{y}-{m:02d}-01", (today if k == 0 else date(y, m, 28)).isoformat()
        e = min(e, (today - pd.Timedelta(days=1)).isoformat())
        doc = om.previous_runs(site["lat"], site["lon"], model, hourly, s, e, cache_dir="data/raw/om_previous_runs/_cache")
        d = os.path.join(bb.PR, site["name"], model)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{y}{m:02d}.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/ops/bias")
    ap.add_argument("--model", default="ecmwf_ifs025")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for site in lg.sites():
        if site["name"] not in bb.SITE_STATION:
            continue
        if a.refresh:
            refresh(site, a.model, date.today())
        obs = bb.obs_series(bb.SITE_STATION[site["name"]])
        state = dict(site=site["name"], model=a.model, lat=site["lat"], lon=site["lon"], alpha=bb.ALPHA)
        for var, col in (("temperature_2m", "t"), ("wind_speed_10m", "ws")):
            state[var] = {}
            for D in range(1, 8):
                f = bb.forecasts(site["name"], a.model, var, D)
                df = pd.DataFrame(dict(f=f, o=obs[col])).dropna()
                df = df[df.index >= "2024-01-01"]
                df["err"] = df.f - df.o
                df["day"], df["hour"] = df.index.normalize(), df.index.hour
                E = df.pivot_table(index="day", columns="hour", values="err").reindex(columns=range(24))
                E = E.reindex(pd.date_range(E.index.min(), E.index.max()))
                B, V, N = bb.track(E)
                state[var][str(D)] = dict(b=[float(x) for x in B.iloc[-1]], n=[int(x) for x in N.iloc[-1]], se=[float(np.sqrt(v / (2 / bb.ALPHA - 1))) for v in V.iloc[-1]], sd=[float(np.sqrt(v)) for v in V.iloc[-1]])
        state["updated"] = str(E.index.max().date())
        with open(os.path.join(a.out, f"{site['name']}_{a.model}.json"), "w", encoding="utf-8") as f:
            json.dump(state, f)
        print(f"{site['name']}: state through {state['updated']}", flush=True)


if __name__ == "__main__":
    main()
