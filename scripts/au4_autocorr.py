"""AU-4 step 0 (New_Plan 15.1): lag 1-10 day autocorrelation of the daily mean CRPS difference (model minus clim15) per headline band,
from a score --daily csv. Day ids (year * 1000 + doy) become true day numbers, so lags run across the year end; a lag uses only the
pairs of days both present. Prints the table and the first lag where every band is below 0.1.
usage: python scripts/au4_autocorr.py STEM_daily.csv [--model unknown]"""
import argparse

import numpy as np
import pandas as pd


def day_number(d):
    d = np.asarray(d, np.int64)
    start = np.array([f"{y}-01-01" for y in d // 1000], "datetime64[D]")
    return (start + (d % 1000).astype("timedelta64[D]")).astype(np.int64)


def lag_corr(t, x, lags):
    s = pd.Series(np.asarray(x, float) - np.mean(x), index=t)
    v = (s ** 2).mean()
    return [float(np.nanmean(s.values * s.reindex(s.index + k).values) / v) for k in lags]  # pairs (t, t + k) both present


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("daily")
    ap.add_argument("--model", default="unknown")
    a = ap.parse_args()
    t = pd.read_csv(a.daily)
    t["t"] = day_number(t.day)
    lags = range(1, 11)
    rows = []
    for (v, b), g in t.groupby(["var", "band"], sort=False):
        g = g[g.rows > 0].sort_values("t")
        diff = (g[f"crps_{a.model}"] - g["crps_clim15"]) / g.rows
        rows.append(dict(var=v, band=b, days=len(g), **{f"lag{k}": r for k, r in zip(lags, lag_corr(g.t.values, diff.values, lags))}))
    r = pd.DataFrame(rows)
    with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
        print(r.to_string(index=False))
    below = [k for k in lags if (r[f"lag{k}"] < 0.1).all()]
    print(f"first lag with every band below 0.1: {below[0] if below else 'none up to 10'}")


if __name__ == "__main__":
    main()
