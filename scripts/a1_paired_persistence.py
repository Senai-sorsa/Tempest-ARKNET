"""A1 step 1 (2026-11-10): paired persistence baseline for the W6 observe() evaluation.
The 300 test hours per station are chosen EXACTLY as in scripts/w6_observe_eval.py (same ASOS files 2023-25, same filters, np.random.default_rng(0) drawn TCS then MAF), so the numbers
below are on the same hours as the tool rows of docs/results/logs/w6_observe_eval.log (TCS: tool + observe soft 1.148, speed-space 1.140; MAF: 1.016 / 0.987).
Baselines (fitted on ASOS 2016-2022 only, same station, same local hours 08-20, previous-hour speed >= 0.5 m/s; nothing from 2023-25 is used for fitting):
  (i) linear persistence: y = a + b x, residuals drawn from the empirical residuals of the fit years in the same tercile of x (200 draws, clipped at 0);
  (ii) multiplicative persistence: y = x * exp(e), e from the empirical log-ratio pool of the fit years in the same tercile of x.
Prints CRPS and 90 % coverage per station. CPU only, about 1 minute.
    .venv/Scripts/python -W ignore scripts/a1_paired_persistence.py [--n 300] [--out docs/results/logs/a1_paired_persistence.log]"""
import argparse
import csv
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KT = 0.514444
ST = {"TCS": "America/Denver", "MAF": "America/Chicago"}


def crps(ens, y):
    e = np.sort(np.asarray(ens, float))
    m = len(e)
    return float(np.abs(e - y).mean() - ((2 * np.arange(1, m + 1) - m - 1) * e).sum() / (m * m))


def load(st, years):
    obs = {}
    for y in years:
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
    return obs


def cases(obs, z_):
    return [h for h in obs if (h - timedelta(hours=1)) in obs and 8 <= h.astimezone(z_).hour <= 20 and obs[h - timedelta(hours=1)][0] >= 0.5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="docs/results/logs/a1_paired_persistence.log")
    a = ap.parse_args()
    rng = np.random.default_rng(0)                 # same stream as w6_observe_eval.py (one rng, TCS first, then MAF)
    rng2 = np.random.default_rng(1)
    lines = ["A1 paired persistence on the W6 hours (m/s CRPS / 90 % coverage), baselines fitted on ASOS 2016-22"]
    for st, tz in ST.items():
        z_ = ZoneInfo(tz)
        obs = load(st, range(2023, 2026))
        test = cases(obs, z_)
        test = [test[i] for i in rng.choice(len(test), min(a.n, len(test)), replace=False)]
        fit = load(st, range(2016, 2023))
        fh = cases(fit, z_)
        x = np.array([fit[h - timedelta(hours=1)][0] for h in fh])
        y = np.array([fit[h][0] for h in fh])
        b, a0 = np.polyfit(x, y, 1)
        res = y - (a0 + b * x)
        lr = np.log(np.maximum(y, 0.3) / x)
        edges = np.quantile(x, [1 / 3, 2 / 3])
        terc = np.digitize(x, edges)
        out = {"linear persistence": ([], []), "multiplicative persistence": ([], [])}
        for h in test:
            x0, yv = obs[h - timedelta(hours=1)][0], obs[h][0]
            k = int(np.digitize(x0, edges))
            e1 = np.maximum(a0 + b * x0 + rng2.choice(res[terc == k], 200), 0.0)
            e2 = x0 * np.exp(rng2.choice(lr[terc == k], 200))
            for name, e in (("linear persistence", e1), ("multiplicative persistence", e2)):
                out[name][0].append(crps(e, yv))
                out[name][1].append(np.percentile(e, 5) <= yv <= np.percentile(e, 95))
        for name, (c, cv) in out.items():
            lines.append(f"  {st} n {len(c)} (fit n {len(fh)}, y = {a0:.2f} + {b:.2f} x): {name:28s} CRPS {np.mean(c):.3f}  cov90 {np.mean(cv):.2f}")
            print(lines[-1], flush=True)
    lines.append("  Tool rows on the same hours (w6_observe_eval.log): TCS no obs 1.636 / soft 1.148 / speed-space 1.140; MAF no obs 1.480 / soft 1.016 / speed-space 0.987")
    os.makedirs(os.path.dirname(os.path.join(REPO, a.out)), exist_ok=True)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh_:
        fh_.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
