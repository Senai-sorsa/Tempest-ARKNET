"""New_Plan WD8 (census): low-level jet nights in the five WFIP1 sodars. CPU, no training, nothing in the tool changes.
Hourly mean speed profiles (30-200 m, hours with >= 4 of 6 valid 10-min values), UTC clock (b59). Night hours = 06-11 UTC (00-06 local Central). Profile usable if the lowest valid level is
30 m, valid levels reach >= 150 m and no more than 3 interior levels are missing (linear fill). Jet nose = speed maximum at an interior level with speed at least 2 m/s above the speed
at the highest valid level. A night is a jet night if any usable night hour has a nose. The sodar top is 200 m, so only noses BELOW 200 m are seen (the plan's 300 m is out of reach: stated limit).
Rule (set 2026-11-16 before running): the plan's fix proposal needs jets below 300 m in >= 15 % of sodar nights AND the ERA5 profile showing one in fewer than half of them.
The ERA5 half cannot be run here: the sodars (lat 30.7-33.3, lon -101.2 to -97.4 except none) lie outside the era5_em / era5_cds box (lon -108 to -101), so no ERA5 profile exists at them.
So this is the census only: report the share of jet nights per site; no fix is proposed from it (the ERA5 comparison is blocked on a pressure-level point pull, not requested).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b61_wd8_jet_census.py
Result: docs/results/logs/kit_b61_wd8_jet_census.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b61_wd8_jet_census"
SITES = ("brady", "cleburne", "colorado_city", "jayton", "ozona")
Z = list(range(30, 210, 10))


def has_nose(p, margin=2.0):
    """p: speeds at Z (nan = missing) -> True / False for a usable profile with a nose, None if unusable."""
    ok = ~np.isnan(p)
    if not ok[0] or p.size != len(Z):
        return None
    top = np.max(np.nonzero(ok)[0])
    if Z[top] < 150 or (~ok[:top + 1]).sum() > 3:
        return None
    q = np.interp(np.arange(top + 1), np.nonzero(ok)[0], p[ok])
    k = int(np.argmax(q))
    return bool(0 < k < top and q[k] - q[top] >= margin)


def load(site):
    fs = sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "a2e", f"wfip1_sodar_{site}", "*.clean.csv")))
    d = pd.concat([pd.read_csv(f, usecols=["Start Time"] + [f"Spd {z}m" for z in Z], na_values=["", "M"]) for f in fs])
    d.index = pd.to_datetime(d.pop("Start Time"))
    d = d[~d.index.duplicated()].sort_index()
    d.columns = Z
    d = d.where((d >= 0) & (d < 60))
    return d.resample("1h").mean().where(d.resample("1h").count() >= 4)


def main():
    lines = ["WD8 jet census: nights with a speed maximum below 200 m (>= 2 m/s above the top level), night = 06-11 UTC hours"]
    for s in SITES:
        h = load(s)
        h = h[(h.index.hour >= 6) & (h.index.hour <= 11)]
        nights = {}
        for t, row in h.iterrows():
            r = has_nose(row.values.astype(float))
            if r is None:
                continue
            day = (t - pd.Timedelta(hours=6)).date()
            nights[day] = nights.get(day, False) or r
        n = len(nights)
        j = sum(nights.values())
        lines.append(f"  {s}: {n} usable nights, {j} with a nose below 200 m ({100 * j / max(n, 1):.0f} %)")
    lines.append("Rule (set 2026-11-16): census only; ERA5 comparison blocked (sodars outside the ERA5 box); no fix proposed.")
    K.report(NAME, lines)


def _selfcheck():
    p = np.array([6, 8, 10, 9, 8, 7, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6], float)
    assert has_nose(p) is True
    assert has_nose(np.linspace(4, 9, 18)) is False
    q = p.copy()
    q[8:] = np.nan
    assert has_nose(q) is None


_selfcheck()
if __name__ == "__main__":
    main()
