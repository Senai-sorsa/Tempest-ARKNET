"""A1 step 2: is the observe()-vs-persistence CRPS gap real? Joins data/a1_perhour.csv (per-hour CRPS of the tool + observe variants, from scripts/w6_observe_eval.py --per-hour)
with data/a1_persist_perhour.csv (linear persistence, scripts/a1_paired_persistence.py --per-hour) on station and hour, then a DATE-BLOCK bootstrap (whole calendar days resampled, 5,000 draws)
of the mean difference (tool - persistence, m/s CRPS; positive = tool worse) per station, for the soft and the speed-space variant. Prints the mean and the 95 % interval.
    .venv/Scripts/python -W ignore scripts/a1_bootstrap.py [--out docs/results/logs/a1_bootstrap.log]"""
import argparse
import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/logs/a1_bootstrap.log")
    ap.add_argument("--draws", type=int, default=5000)
    a = ap.parse_args()
    t = pd.read_csv(os.path.join(REPO, "data", "a1_perhour.csv"))
    p = pd.read_csv(os.path.join(REPO, "data", "a1_persist_perhour.csv"))
    d = t.merge(p, on=["station", "time"], how="inner")
    soft = [c for c in d.columns if c.startswith("tool + observe(previous")][0]
    fast = [c for c in d.columns if "speed_space" in c][0]
    d["day"] = d.time.str[:10]
    rng = np.random.default_rng(0)
    lines = ["A1 step 2: tool + observe minus linear persistence, CRPS m/s on the same hours (positive = tool worse), date-block bootstrap (days), 95 % interval"]
    for st, g in d.groupby("station"):
        days = g.day.unique()
        by = {k: v for k, v in g.groupby("day")}
        for name, col in (("soft", soft), ("speed-space", fast)):
            diff = {k: (v[col] - v.linear_persistence).to_numpy() for k, v in by.items()}
            obs = np.concatenate(list(diff.values())).mean()
            boots = np.empty(a.draws)
            for i in range(a.draws):
                pick = rng.choice(len(days), len(days))
                boots[i] = np.concatenate([diff[days[j]] for j in pick]).mean()
            lo, hi = np.percentile(boots, [2.5, 97.5])
            lines.append(f"  {st} n {len(g)} hours, {len(days)} days: {name:11s} mean diff {obs:+.3f}  95 % [{lo:+.3f}, {hi:+.3f}]  ({'gap is real' if lo > 0 else 'tool better' if hi < 0 else 'not distinguishable from zero'})")
    for l in lines:
        print(l)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
