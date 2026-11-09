"""W5: rank-preserving speed map per cell (month x local hour) from the tool's 10 m speed distribution onto the ASOS one, fitted on odd years 2015-25 and scored on even years.
Compared by KS distance to the held-out ASOS speeds, calm share (< 0.5 m/s), Weibull shape and p99. Tool in climate mode (n = 600 per cell, as in weibull_check.py).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/weibull_map_test.py"""
import csv
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from weibull_check import HOURS, KT, ST, ks, weibull_mle   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402
from tempest.scoring.score import crps_ensemble, twcrps_ensemble   # noqa: E402


def qmap(tool, train):
    q = np.linspace(0.005, 0.995, 199)
    src, dst = np.quantile(tool, q), np.quantile(train, q)
    out = np.interp(tool, src, dst)
    hi = tool > src[-1]
    return np.where(hi, dst[-1] + (tool - src[-1]) * (dst[-1] - dst[-2]) / max(src[-1] - src[-2], 1e-9), out)


rows = []
for name, (lat, lon, el, tz) in ST.items():
    zi = ZoneInfo(tz)
    tr, te = {}, {}
    for y in range(2015, 2026):
        with open(os.path.join(REPO, "data", "raw", "asos", name, f"{y}.csv"), newline="") as f:
            for r in csv.DictReader(f):
                try:
                    t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).astimezone(zi)
                    s = float(r["sknt"]) * KT
                except (ValueError, KeyError):
                    continue
                h = (t.hour + (1 if t.minute >= 30 else 0)) % 24
                if h in HOURS:
                    (tr if y % 2 else te).setdefault((t.month, h), []).append(s)
    for m in range(1, 13):
        for h in HOURS:
            a, b = np.array(tr.get((m, h), [])), np.array(te.get((m, h), []))
            if len(a) < 100 or len(b) < 100:
                continue
            try:
                sm = Launch(lat, lon, f"2020-{m:02d}-15 {h:02d}:00", mode="ai", n=600, units="si", elevation=el, tz=tz, seed=5)._ensure_pool()["samples"]
            except Exception:   # noqa: BLE001
                continue
            tool = np.hypot(sm["u"][:, 0], sm["v"][:, 0])
            mp = qmap(tool, a)
            rows.append([ks(b, tool), ks(b, mp), (b < 0.5).mean(), (tool < 0.5).mean(), (mp < 0.5).mean(), weibull_mle(b)[0], weibull_mle(tool)[0], weibull_mle(mp)[0],
                         np.percentile(b, 99), np.percentile(tool, 99), np.percentile(mp, 99), np.abs(np.sort(tool) - np.quantile(b, (np.arange(len(tool)) + .5) / len(tool))).mean(),
                         np.abs(np.sort(mp) - np.quantile(b, (np.arange(len(mp)) + .5) / len(mp))).mean()]
                        + [v[0, 0] for v in (crps_ensemble(tool[None, :, None].repeat(len(b), 0)[:200], b[:200, None]).mean(0, keepdims=True), crps_ensemble(mp[None, :, None].repeat(len(b), 0)[:200], b[:200, None]).mean(0, keepdims=True),
                                             twcrps_ensemble(tool[None, :, None].repeat(len(b), 0)[:200], b[:200, None], 8.0).mean(0, keepdims=True), twcrps_ensemble(mp[None, :, None].repeat(len(b), 0)[:200], b[:200, None], 8.0).mean(0, keepdims=True))])
r = np.array(rows)
print(f"{len(r)} cells (fit odd years, test even years)")
print(f"KS to held-out ASOS speeds: tool median {np.median(r[:, 0]):.3f} (p90 {np.percentile(r[:, 0], 90):.3f}) -> mapped {np.median(r[:, 1]):.3f} (p90 {np.percentile(r[:, 1], 90):.3f}); mapped better in {100 * (r[:, 1] < r[:, 0]).mean():.0f} % of cells")
print(f"calm share: ASOS {r[:, 2].mean():.3f}, tool {r[:, 3].mean():.3f}, mapped {r[:, 4].mean():.3f}")
print(f"Weibull k median: ASOS {np.median(r[:, 5]):.2f}, tool {np.median(r[:, 6]):.2f}, mapped {np.median(r[:, 7]):.2f}")
print(f"p99 median: ASOS {np.median(r[:, 8]):.1f}, tool {np.median(r[:, 9]):.1f}, mapped {np.median(r[:, 10]):.1f}")
print(f"mean quantile-quantile distance to the held-out ASOS (m/s): tool {r[:, 11].mean():.2f}, mapped {r[:, 12].mean():.2f}")
print(f"climate-distribution CRPS of the speed against held-out ASOS (200 reports per cell): tool {r[:, 13].mean():.3f} -> mapped {r[:, 14].mean():.3f}; twCRPS above 8 m/s: tool {r[:, 15].mean():.4f} -> mapped {r[:, 16].mean():.4f}")
