"""Robustness of the tool-vs-Earth-GRAM significance to the bootstrap block length. REPORT ONLY.
Reads data/kit/breakdown_scores.npz (per-case CRPS from b9_earthgram_breakdown.py). Per variable and band, the paired CRPS difference
(source - tool, % of the tool's CRPS) with 95 % intervals from resampling whole days, ISO weeks and calendar months (both stations
share a block, so same-day weather at EPZ and MAF is never split). 2024-25 balloons: development set, reused.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore paper/gram_block_robust.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "new_plan_kit"))
import kit_common as K

QS = ("u", "v", "T", "spd")


def main():
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv"))
    d = np.load(os.path.join(K.OUT, "breakdown_scores.npz"))
    assert list(d["case"]) == list(cases.case), "breakdown_scores.npz is not in gram_cases.csv order"
    t = pd.to_datetime(cases.time_utc)
    iso = t.dt.isocalendar()
    blocks = {"day": t.dt.strftime("%Y-%m-%d").values, "week": (iso.year.astype(str) + "-W" + iso.week.astype(str)).values,
              "month": t.dt.strftime("%Y-%m").values}
    bands = [("all 0-18 km", 0, 18000)] + list(K.BANDS)
    L = [f"Block-length robustness of the paired CRPS test: {len(cases)} cases; blocks: "
         + ", ".join(f"{k} ({len(np.unique(v))} blocks)" for k, v in blocks.items())
         + ". Entry: mean source-minus-tool CRPS in % of the tool's, then the 95 % interval per block length (below 0 = source better; "
           "* = interval excludes 0 for every block length).", ""]
    for src in ("gram_ncep", "gram_rra"):
        L.append(src)
        for q in QS:
            tool, s = d[f"tool__{q}__crps"].astype(float), d[f"{src}__{q}__crps"].astype(float)
            for name, lo, hi in bands:
                ix = K.band_idx(lo, hi)
                bt, bs = np.nanmean(tool[:, ix], 1), np.nanmean(s[:, ix], 1)
                ok = np.isfinite(bt) & np.isfinite(bs)
                diff, base = bs[ok] - bt[ok], bt[ok].mean()
                cis = {k: K.block_boot(diff, v[ok], draws=4000)[1:] for k, v in blocks.items()}
                sig = all(l > 0 for l, _ in cis.values()) or all(h < 0 for _, h in cis.values())
                L.append(f"  {q:4s} {name:12s} {100 * diff.mean() / base:+6.1f} %  " + "  ".join(
                    f"{k} [{100 * l / base:+5.1f},{100 * h / base:+5.1f}]" for k, (l, h) in cis.items()) + ("  *" if sig else ""))
        L.append("")
    L.append("Notes: the tool is balloon-corrected at these stations (not a blind test). Month blocks leave 24 blocks, so their intervals are "
             "themselves rough; a result that holds for day, week and month blocks is not an artefact of day-to-day weather persistence.")
    K.report("b9_gram_block_robust", L)


if __name__ == "__main__":
    # self-check: identical values in a block -> block length does not move the mean
    m, lo, hi = K.block_boot(np.r_[np.ones(10), -np.ones(10)], np.repeat([0, 1], 10), draws=500)
    assert m == 0 and lo <= 0 <= hi
    main()
