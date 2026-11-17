"""E3 step 0 (New_Plan 16.4 E3): how many usable radar wind pairs do we have? REPORT with the plan's pre-set rule.
Radar files on disk: data/raw/nexrad_nvw_t3 (KNVW VAD winds, first volume of each hour, radars MAF / HDX / ABX; the pulls of 23.T3: June 2024 all three, Jan / Apr / Sep 2024 MAF, hours as pulled).
A volume is usable if u and v are finite at >= 4 of the 44 model heights between 0.5 and 5 km above the radar. A pair = two usable volumes 1, 2, 3 or 6 h apart at the same radar.
RULE (New_Plan E3): KILL if under 500 usable pairs per lag (pooled over radars); otherwise GO to step 1 (the CRPS test, plan's pass: -10 % CRPS at 1-3 h vs tool + observe_radar).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b75_e3_pairs_step0.py
Result: docs/results/logs/kit_b75_e3_pairs_step0.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K
from p3_vad_vs_balloon import parse

ELEV = {"MAF": 872.0, "HDX": 1287.0, "ABX": 1789.0}
LAGS = (1, 2, 3, 6)


def main():
    band = (K.H >= 500) & (K.H <= 5000)
    tot = {k: 0 for k in LAGS}
    L = ["E3 step 0: usable radar wind pairs (u and v finite at >= 4 of the 44 heights, 0.5-5 km), first volume of each UTC hour, KNVW VAD files on disk",
         "radar  volumes  usable   " + "   ".join(f"lag {k} h" for k in LAGS)]
    for rad, elev in ELEV.items():
        first = {}
        for f in sorted(glob.glob(f"data/raw/nexrad_nvw_t3/{rad}_NVW_*")):
            t = pd.to_datetime(os.path.basename(f)[8:], format="%Y_%m_%d_%H_%M_%S").floor("h")
            first.setdefault(t, f)
        ok = set()
        for t, f in first.items():
            try:
                w = np.stack(parse(f, elev))[:, band]
            except Exception:
                continue
            if (np.isfinite(w[0]) & np.isfinite(w[1])).sum() >= 4:
                ok.add(t)
        n = {k: sum((t + pd.Timedelta(hours=k)) in ok for t in ok) for k in LAGS}
        for k in LAGS:
            tot[k] += n[k]
        L.append(f"{rad:<6} {len(first):>7} {len(ok):>7}   " + "   ".join(f"{n[k]:>7}" for k in LAGS))
    L.append("total                     " + "   ".join(f"{tot[k]:>7}" for k in LAGS))
    L.append("VERDICT (pre-set rule, under 500 pairs per lag = KILL): " + ("KILL (too few pairs)" if min(tot.values()) < 500 else "GO to step 1"))
    L.append("Notes: pairs share days, so independent pairs are fewer than counted. Step 0 only counts; a bigger pull (all hours, a year, the 4 radars of the plan) could lift the count past 500, this is what is on disk now.")
    K.report("b75_e3_pairs_step0", L)


if __name__ == "__main__":
    main()
