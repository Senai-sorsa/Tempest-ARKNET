"""W6 (2026-11-10): is there room for observation conditioning in Weibull (speed) space? The engine already conditions in Gaussian-copula space PER COLUMN (u and v through their own marginals),
so W6 reduces to conditioning on the SPEED instead of the components. Test on the W3 cases (scripts/weibull_persistence.py: TCS and MAF, 2023-25, 08-20 local, the measured speed and
direction an hour earlier, predict the speed at the hour): the tool's 10 m wind (i) without an observation and (ii) after Launch.observe(wind_10m=, wind_from_deg=, age_hours=1, distance_km=0,
elevation_diff_m=0) (soft, the shipped weights), CRPS and 90 % coverage of the speed. W3 on the same station and years gave: cell Weibull 1.450 / 1.506, linear persistence 1.035 / 0.923,
Weibull-copula AR(1) 1.072 / 0.925 (TCS / MAF). If the tool after observe() is already at or below the Weibull-space AR(1), a speed-space variant of observe() cannot add much.
    PYTHONPATH=. python -W ignore scripts/w6_observe_eval.py [--n 300] [--out docs/results/logs/w6_observe_eval.log]"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch   # noqa: E402

KT = 0.514444
ST = {"TCS": ("America/Denver", 33.2369, -107.2672, 1479.0), "MAF": ("America/Chicago", 31.9425, -102.2019, 872.0)}


def crps(ens, y):
    e = np.sort(np.asarray(ens, float))
    m = len(e)
    return float(np.abs(e - y).mean() - ((2 * np.arange(1, m + 1) - m - 1) * e).sum() / (m * m))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="docs/results/logs/w6_observe_eval.log")
    ap.add_argument("--per-hour", default="", help="A1: also write one CSV row per station and hour (CRPS of every variant) to this path; default off")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    per_hour = []
    lines = ["W6: tool 10 m wind speed one hour after a measured wind, CRPS (m/s) / 90 % coverage, 2023-25, 08-20 local (W3 cases)"]
    for st, (tz, lat, lon, elev) in ST.items():
        z_ = ZoneInfo(tz)
        obs = {}
        for y in range(2023, 2026):
            with open(os.path.join(REPO, "data", "raw", "asos", st, f"{y}.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                        s, d = float(r["sknt"]) * KT, float(r["drct"])
                    except (ValueError, KeyError):
                        continue
                    h = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                    if abs((t - h).total_seconds()) <= 20 * 60:
                        obs[h] = (s, d)
        test = [h for h in obs if (h - timedelta(hours=1)) in obs and 8 <= h.astimezone(z_).hour <= 20 and obs[h - timedelta(hours=1)][0] >= 0.5]
        test = [test[i] for i in rng.choice(len(test), min(a.n, len(test)), replace=False)]
        res = {"tool, no observation": ([], []), "tool + observe(previous hour, soft)": ([], []), "tool + observe(..., speed_space=True)": ([], [])}
        for h in test:
            cur = {}
            sp0, d0 = obs[h - timedelta(hours=1)]
            y = obs[h][0]
            when = h.strftime("%Y-%m-%d %H:%M")
            try:
                L = Launch(lat, lon, when, tz="UTC", n=200, seed=int(h.timestamp()) % 100000, units="si", elevation=elev, mode="ai")
                L1 = L.observe(wind_10m=f"{sp0:.2f} m/s", wind_from_deg=float(d0), age_hours=1.0, distance_km=0.0, elevation_diff_m=0.0, source=f"ASOS {st}")
                L2 = L.observe(wind_10m=f"{sp0:.2f} m/s", wind_from_deg=float(d0), age_hours=1.0, distance_km=0.0, elevation_diff_m=0.0, source=f"ASOS {st}", speed_space=True)
                for name, LL in (("tool, no observation", L), ("tool + observe(previous hour, soft)", L1), ("tool + observe(..., speed_space=True)", L2)):
                    s = LL._ensure_pool()["samples"]
                    w = np.hypot(np.asarray(s["u"])[:, 0], np.asarray(s["v"])[:, 0])
                    res[name][0].append(crps(w, y))
                    cur[name] = res[name][0][-1]
                    res[name][1].append(np.percentile(w, 5) <= y <= np.percentile(w, 95))
            except Exception as e:  # noqa: BLE001 - count and continue
                print(st, h, "skipped:", repr(e)[:80], flush=True)
            else:
                per_hour.append((st, when, y, cur))
        for name, (c, cv) in res.items():
            lines.append(f"  {st} n {len(c)}: {name:38s} CRPS {np.mean(c):.3f}  cov90 {np.mean(cv):.2f}")
            print(lines[-1], flush=True)
    lines.append("  W3 reference (same stations / years): cell Weibull 1.450 / 1.506, linear persistence 1.035 / 0.923, Weibull-copula AR(1) 1.072 / 0.925 (TCS / MAF)")
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")
    if a.per_hour:
        names = list(per_hour[0][3]) if per_hour else []
        with open(a.per_hour, "w", encoding="utf-8", newline="") as fh:
            fh.write("station,time,obs_speed," + ",".join(n.replace(",", ";") for n in names) + "\n")
            for st_, when_, y_, cur_ in per_hour:
                fh.write(f"{st_},{when_},{y_:.3f}," + ",".join(f"{cur_[n]:.5f}" for n in names) + "\n")


if __name__ == "__main__":
    main()
