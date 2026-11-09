"""V1: surface climate of the tool (climate mode) against ASOS at TCS and MAF, by month x local hour, 2021-2025 stations. Looks for time-zone, hour, direction and unit errors.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/v1_surface_check.py

Tool: Launch(lat, lon, '2025-MM-15 HH:00', mode='ai', n=100, units='si', elevation=station elevation, tz=station zone); statistics of the 100 atmospheres: median 10 m speed, vector-mean wind direction (from), median 2 m temperature.
ASOS: all reports of 2021-2025 in that month whose local time rounds to HH:00 (reports are at :53): median speed, vector-mean direction, median temperature (F -> C). Writes data/v1_surface_check.csv.
"""
import csv
import os
import sys
import warnings
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch   # noqa: E402

ST = {"TCS": (33.2369, -107.2672, 1479.0, "America/Denver"), "MAF": (31.9425, -102.2019, 872.0, "America/Chicago")}
HOURS = [8, 10, 12, 14, 16, 18, 20]
KT = 0.514444


def asos(station, tz):
    z = ZoneInfo(tz)
    rows = {}
    for y in range(2021, 2026):
        with open(os.path.join(REPO, "data", "raw", "asos", station, f"{y}.csv"), newline="") as f:
            for r in csv.DictReader(f):
                try:
                    t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).astimezone(z)
                    kt, tf = float(r["sknt"]), float(r["tmpf"])
                    d = float(r["drct"]) if (r["drct"] or "").strip() else None
                except (ValueError, KeyError):
                    continue
                h = (t.hour + (1 if t.minute >= 30 else 0)) % 24
                if kt > 0 and d is None:        # variable direction (3 % of reports): keep the speed, leave the direction out (it used to be read as north)
                    uv = (np.nan, np.nan)
                else:
                    d = d or 0.0
                    uv = (-kt * KT * np.sin(np.radians(d)), -kt * KT * np.cos(np.radians(d)))
                rows.setdefault((t.month, h), []).append((uv[0], uv[1], (tf - 32.0) / 1.8, kt * KT))
    return rows


def direction(u, v):
    return float((np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0)


def main():
    out = []
    for name, (lat, lon, el, tz) in ST.items():
        obs = asos(name, tz)
        for m in range(1, 13):
            for h in HOURS:
                a = np.array(obs.get((m, h), []))
                if len(a) < 30:
                    continue
                try:
                    L = Launch(lat, lon, f"2025-{m:02d}-15 {h:02d}:00", mode="ai", n=100, units="si", elevation=el, tz=tz, seed=1)
                    s = L._ensure_pool()["samples"]
                except Exception as e:   # noqa: BLE001
                    print("skip", name, m, h, str(e)[:80])
                    continue
                u, v = s["u"][:, 0], s["v"][:, 0]
                tool = dict(spd=float(np.median(np.hypot(u, v))), dir=direction(u.mean(), v.mean()), t=float(np.median(s["t2m"]) - 273.15))
                ob = dict(spd=float(np.median(a[:, 3])), dir=direction(np.nanmean(a[:, 0]), np.nanmean(a[:, 1])), t=float(np.median(a[:, 2])))
                dd = (tool["dir"] - ob["dir"] + 180.0) % 360.0 - 180.0
                out.append(dict(station=name, month=m, hour=h, n_obs=len(a), spd_tool=tool["spd"], spd_obs=ob["spd"], dir_tool=tool["dir"], dir_obs=ob["dir"], dir_diff=dd, t_tool=tool["t"], t_obs=ob["t"]))
        print(name, "done", flush=True)
    with open(os.path.join(REPO, "data", "v1_surface_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(out[0]))
        w.writeheader()
        w.writerows(out)
    import pandas as pd
    d = pd.DataFrame(out)
    d["spd_bias"], d["t_bias"] = d.spd_tool - d.spd_obs, d.t_tool - d.t_obs
    print(f"\n{len(d)} cells. Overall bias tool - ASOS: speed {d.spd_bias.mean():+.2f} m/s (obs mean {d.spd_obs.mean():.2f}), temperature {d.t_bias.mean():+.2f} C, direction mean abs diff {d.dir_diff.abs().mean():.0f} deg (median {d.dir_diff.abs().median():.0f})")
    for st, g in d.groupby("station"):
        print(f"\n{st}: by local hour")
        print(g.groupby("hour")[["spd_bias", "t_bias"]].mean().round(2).T.to_string())
        print(f"{st}: by month")
        print(g.groupby("month")[["spd_bias", "t_bias"]].mean().round(2).T.to_string())
        print(f"{st}: direction abs diff by month (deg): " + " ".join(f"{k}:{v:.0f}" for k, v in g.assign(a=g.dir_diff.abs()).groupby("month").a.mean().items()))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
