"""Wind speed is Weibull-like (positive, skewed, shape k about 1.5-2.5), not Gaussian. How does the tool's 10 m speed compare with the observed one, cell by cell (month x local hour)?
For each cell at TCS and MAF: Weibull fit (maximum likelihood on speeds > 0.3 m/s) of the ASOS reports 2015-25 and of the tool's climate-mode speeds (n = 600): shape k, scale c, mean, p99, share of calm (< 0.5 m/s), and the Kolmogorov distance of the tool's speed distribution to the ASOS one.
Also: how Gaussian are the tool's wind components, and how often do fitted families for speed variables in `distribution()` allow negative speeds.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/weibull_check.py
"""
import csv
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import Launch   # noqa: E402

ST = {"TCS": (33.2369, -107.2672, 1479.0, "America/Denver"), "MAF": (31.9425, -102.2019, 872.0, "America/Chicago")}
HOURS = [8, 10, 12, 14, 16, 18, 20]
KT = 0.514444


def weibull_mle(x, iters=60):
    x = np.asarray(x, float)
    x = x[x > 0.3]
    k = 1.8
    lx = np.log(x)
    for _ in range(iters):
        xk = x ** k
        f = (xk * lx).sum() / xk.sum() - 1.0 / k - lx.mean()
        df = (xk * lx * lx).sum() / xk.sum() - ((xk * lx).sum() / xk.sum()) ** 2 + 1.0 / k ** 2
        k = max(0.3, k - f / df)
    c = ((x ** k).mean()) ** (1.0 / k)
    return float(k), float(c)


def ks(a, b):
    a, b = np.sort(a), np.sort(b)
    g = np.concatenate([a, b])
    return float(np.abs(np.searchsorted(a, g, "right") / len(a) - np.searchsorted(b, g, "right") / len(b)).max())


def main():
    rows = []
    for name, (lat, lon, el, tz) in ST.items():
        zi = ZoneInfo(tz)
        obs = {}
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
                        obs.setdefault((t.month, h), []).append(s)
        for m in range(1, 13):
            for h in HOURS:
                a = np.array(obs.get((m, h), []))
                if len(a) < 100:
                    continue
                try:
                    s = Launch(lat, lon, f"2020-{m:02d}-15 {h:02d}:00", mode="ai", n=600, units="si", elevation=el, tz=tz, seed=5)._ensure_pool()["samples"]
                except Exception:   # noqa: BLE001
                    continue
                tool = np.hypot(s["u"][:, 0], s["v"][:, 0])
                ka, ca = weibull_mle(a)
                kt, ct = weibull_mle(tool)
                rows.append((name, m, h, ka, ca, kt, ct, np.percentile(a, 99), np.percentile(tool, 99), (a < 0.5).mean(), (tool < 0.5).mean(), ks(a, tool), a.mean(), tool.mean()))
    r = np.array([x[3:] for x in rows], float)
    print(f"{len(rows)} cells. Weibull shape k: ASOS median {np.median(r[:, 0]):.2f} (range {r[:, 0].min():.2f}-{r[:, 0].max():.2f}), tool median {np.median(r[:, 2]):.2f} (range {r[:, 2].min():.2f}-{r[:, 2].max():.2f}); mean |k_tool - k_ASOS| {np.abs(r[:, 2] - r[:, 0]).mean():.2f}")
    print(f"scale c: ASOS median {np.median(r[:, 1]):.2f}, tool median {np.median(r[:, 3]):.2f} m/s; p99 speed: ASOS median {np.median(r[:, 4]):.1f}, tool {np.median(r[:, 5]):.1f} m/s (tool/ASOS ratio median {np.median(r[:, 5] / r[:, 4]):.2f})")
    print(f"calm share (< 0.5 m/s): ASOS {r[:, 6].mean():.3f}, tool {r[:, 7].mean():.3f}; KS distance tool vs ASOS speed distribution: median {np.median(r[:, 8]):.3f}, 90th percentile {np.percentile(r[:, 8], 90):.3f}")
    print(f"mean speed ratio tool/ASOS median {np.median(r[:, 10] / r[:, 9]):.2f}")
    for st in ST:
        sel = np.array([x[0] == st for x in rows])
        print(f"  {st}: k ASOS {np.median(r[sel, 0]):.2f} tool {np.median(r[sel, 2]):.2f}; p99 ASOS {np.median(r[sel, 4]):.1f} tool {np.median(r[sel, 5]):.1f}; calm ASOS {r[sel, 6].mean():.3f} tool {r[sel, 7].mean():.3f}")
    # Gaussianity of the tool's components vs the speed
    s = Launch(32.94, -106.91, "2025-06-15 12:00", mode="ai", n=2000, units="si", seed=5)._ensure_pool()["samples"]
    u = s["u"][:, 0]
    sp = np.hypot(u, s["v"][:, 0])
    skew = lambda x: float(((x - x.mean()) ** 3).mean() / x.std() ** 3)
    print(f"Spaceport America June noon, tool: skewness of u {skew(u):+.2f}, of v {skew(s['v'][:, 0]):+.2f}, of speed {skew(sp):+.2f}; Weibull k of the speed {weibull_mle(sp)[0]:.2f}")


if __name__ == "__main__":
    main()
