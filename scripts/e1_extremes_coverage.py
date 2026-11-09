"""E1 (user 2026-11-08: "winter storms and heat waves exist; the system should account for them and not let outliers break the predictions"): do real extremes fall inside the tool's CLIMATE distribution?

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/e1_extremes_coverage.py

Tool: climate mode, Launch(lat, lon, '2020-MM-15 HH:00', n=600) for local hours 8..20 step 2, month by month, TCS and MAF (2020: inside the training years, no extrapolation).
Truth: every ASOS report 2015-2025 whose local time rounds to that hour (temperature C and wind speed m/s). For each quantile level q the share of reports below the tool's q-quantile of that month and hour is the calibration
curve (should be q). Tail rows: share beyond the tool's 1 % / 99 % (should be 1 % each side) and the most extreme reports with the percentile the tool gives them (zero = outside all 600 samples). Named events listed at the end.
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
QS = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
KT = 0.514444
EVENTS = {"Uri freeze (Texas), Feb 2021": ("MAF", "2021-02-14", "2021-02-18"), "cold January 2025": ("TCS", "2025-01-01", "2025-01-31"), "heat dome June 2023": ("MAF", "2023-06-10", "2023-06-30"),
          "heat wave June 2021": ("MAF", "2021-06-15", "2021-06-20")}


def main():
    warnings.filterwarnings("ignore")
    stats = {}
    events = {k: [] for k in EVENTS}
    for name, (lat, lon, el, tz) in ST.items():
        z = ZoneInfo(tz)
        obs = {}
        for y in range(2015, 2026):
            with open(os.path.join(REPO, "data", "raw", "asos", name, f"{y}.csv"), newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).astimezone(z)
                        spd, tc = float(r["sknt"]) * KT, (float(r["tmpf"]) - 32.0) / 1.8
                    except (ValueError, KeyError):
                        continue
                    h = (t.hour + (1 if t.minute >= 30 else 0)) % 24
                    if h in HOURS:
                        obs.setdefault((t.month, h), []).append((t, tc, spd))
        for m in range(1, 13):
            for h in HOURS:
                a = obs.get((m, h), [])
                if len(a) < 100:
                    continue
                try:
                    s = Launch(lat, lon, f"2020-{m:02d}-15 {h:02d}:00", mode="ai", n=600, units="si", elevation=el, tz=tz, seed=5)._ensure_pool()["samples"]
                except Exception:   # noqa: BLE001
                    continue
                tool = {"T": np.sort(s["t2m"] - 273.15), "V": np.sort(np.hypot(s["u"][:, 0], s["v"][:, 0]))}
                for kind, col in (("T", 1), ("V", 2)):
                    x = np.array([r[col] for r in a])
                    pct = np.searchsorted(tool[kind], x) / len(tool[kind])
                    stats.setdefault((name, kind), []).append(pct)
                    for ev, (st, d0, d1) in EVENTS.items():
                        if st != name:
                            continue
                        for (t, tc, spd), p in zip(a, pct):
                            if d0 <= t.strftime("%Y-%m-%d") <= d1:
                                events[ev].append((kind, p, t, tc if kind == "T" else spd))
    for (name, kind), lst in stats.items():
        p = np.concatenate(lst)
        lab = "2 m temperature" if kind == "T" else "10 m wind speed"
        print(f"\n{name} {lab}: {len(p)} reports 2015-2025. share of reports below the tool's quantile (ideal = the level):")
        print("  " + "  ".join(f"q{int(q * 100):02d}:{(p <= q).mean():.3f}" for q in QS) + f"   beyond the tool's samples: below all {(p <= 0).mean():.4f}, above all {(p >= 1).mean():.4f}")
    for ev, lst in events.items():
        for kind in ("T", "V"):
            e = [x for x in lst if x[0] == kind]
            if not e:
                continue
            ps = np.array([x[1] for x in e])
            vals = np.array([x[3] for x in e])
            lab = "temperature" if kind == "T" else "wind speed"
            i = int(np.argmin(ps) if (kind == "T" and ps.mean() < 0.5) else np.argmax(ps))
            print(f"{ev} ({lab}): {len(e)} reports; median percentile in the tool {np.median(ps):.2f}; most extreme report {vals[i]:.1f} {'C' if kind == 'T' else 'm/s'} at percentile {ps[i]:.3f}; share outside all samples {(ps <= 0).mean() + (ps >= 1).mean():.2f}")


if __name__ == "__main__":
    main()
