"""IL-198: intervals for the P3 radar claim (CRPS gain of conditioning on the El Paso radar winds at 0.5-2 km, scored against the 00Z balloon above 2.5 km, FINAL_REPORT / LOOP3 '+32 / +16 / +7 %').
Input: data/il198_p3_perday.csv from `scripts/p3_vad_condition.py --per-day` (one row per day x method x variable x band; the days are balloon launches, so the resampling unit is the day).
Gain = 1 - mean CRPS(method) / mean CRPS(free) over days (u and v averaged), 5,000 bootstrap draws over days, 95 % interval; also the share of draws in which the gain is above zero.
    .venv/Scripts/python -W ignore scripts/il198_bootstrap.py [--in data/il198_p3_perday.csv] [--out docs/results/logs/il198_bootstrap.log]"""
import argparse
import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/il198_p3_perday.csv")
    ap.add_argument("--out", default="docs/results/logs/il198_bootstrap.log")
    ap.add_argument("--draws", type=int, default=5000)
    a = ap.parse_args()
    d = pd.read_csv(os.path.join(REPO, a.inp))
    day = d.groupby(["band", "method", "day"]).crps.mean().unstack("day")          # (band, method) x day, u and v averaged
    rng = np.random.default_rng(0)
    lines = [f"IL-198 P3 radar gain with a date-block bootstrap ({day.shape[1]} balloon days, {a.draws} draws): CRPS gain vs the free pool, 95 % interval"]
    for band in ("2.5-5 km", "5-12 km", "12-18 km"):
        free = day.loc[(band, "free")].to_numpy()
        for meth in ("radar 0.5-2 km", "radar+all to 5 km"):
            x = day.loc[(band, meth)].to_numpy()
            ok = np.isfinite(free) & np.isfinite(x)
            f, m = free[ok], x[ok]
            g0 = 1 - m.mean() / f.mean()
            idx = rng.integers(0, len(f), (a.draws, len(f)))
            gb = 1 - m[idx].mean(1) / f[idx].mean(1)
            lo, hi = np.percentile(gb, [2.5, 97.5])
            note = "  (overlaps the observed levels)" if meth.startswith("radar+all") and band == "2.5-5 km" else ""
            lines.append(f"  {band:8s} {meth:18s} gain {100 * g0:+5.1f} %  95 % [{100 * lo:+5.1f}, {100 * hi:+5.1f}]  share of draws > 0: {np.mean(gb > 0):.3f}  (n {len(f)} days){note}")
    for l in lines:
        print(l)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
