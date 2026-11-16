"""New_Plan WD6 (step 0): (a) sodar time zone (audit A8), (b) ERA5-vs-sodar speed ratio by height at the five WFIP1 sodars. Measurement only, CPU, no training.
Data: data/raw/a2e/wfip1_sodar_<site>/*.clean.csv (10-min speeds 30-200 m, timestamps of unknown zone), ERA5 hourly u10 v10 u100 v100 at the nearest point
(scripts/wd6_era5_points.py -> data/kit/wd6_era5_points.nc, 2011-06 to 2012-10). ERA5 speed at height z: linear in ln z between 10 m and 100 m, extended above 100 m with the same line.
(a) Hourly sodar mean (hours with >= 4 of 6 valid 10-min values) of the 60-100 m speeds against ERA5 100 m speed: for each shift of -12..+12 h applied to the sodar clock, the correlation of
    the deviations from the mean (the diurnal cycle is kept: it is what fixes the zone); the best shift = the zone offset. Reported per site; a site is "clear" if the best shift beats the second best by 0.02.
(b) After the shift: heights with under 70 % valid hours dropped; mean sodar / mean ERA5 speed by height 30 / 60 / 100 / 150 / 200 m.
Rule (set 2026-11-16 before running, New_Plan WD6 step 0): STOP (WD6 closed) if the ratio at the highest kept height is not above the ratio at the lowest kept height (30 m) by at least 0.03 at 4 of 5 sodars.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b59_wd6_step0.py
Result: docs/results/logs/kit_b59_wd6_step0.log
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

NAME = "b59_wd6_step0"
SITES = ("brady", "cleburne", "colorado_city", "jayton", "ozona")
HEIGHTS = (30, 60, 100, 150, 200)   # 50 m is blank at Ozona, so 60 m replaces it


def era_speed(u10, v10, u100, v100, z):
    s10, s100 = np.hypot(u10, v10), np.hypot(u100, v100)
    return s10 + (s100 - s10) * np.log(z / 10.0) / np.log(10.0)


def best_shift(a, b):
    """a, b hourly pd.Series; -> {shift h: corr of anomalies after shifting a's index by shift}."""
    out = {}
    for sh in range(-12, 13):
        x = a.copy()
        x.index = x.index + pd.Timedelta(hours=sh)
        j = pd.concat([x, b], axis=1, join="inner").dropna()
        if len(j) < 500:
            continue
        an = j - j.mean()
        out[sh] = float(np.corrcoef(an.iloc[:, 0], an.iloc[:, 1])[0, 1])
    return out


def judge(rises):
    return "STOP, WD6 closed" if sum(rises) < 4 else f"continue ({sum(rises)} of {len(rises)} sodars rise)"


def load_sodar(site):
    fs = sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "a2e", f"wfip1_sodar_{site}", "*.clean.csv")))
    d = pd.concat([pd.read_csv(f, usecols=["Start Time"] + [f"Spd {z}m" for z in range(30, 210, 10)], na_values=["", "M"]) for f in fs])
    d.index = pd.to_datetime(d.pop("Start Time"))
    d = d[~d.index.duplicated()].sort_index()
    d.columns = [int(c.split()[1][:-1]) for c in d.columns]
    d = d.where((d >= 0) & (d < 60))
    return d


def main():
    K.ram_gate(3.0)
    e = xr.open_dataset(os.path.join(K.REPO, "data", "kit", "wd6_era5_points.nc"))
    lines = ["WD6 step 0: sodar time zone (best clock shift in h, corr; second best) and ERA5-vs-sodar speed ratio by height"]
    rises = []
    for s in SITES:
        d = load_sodar(s)
        h = d.resample("1h").mean().where(d.resample("1h").count() >= 4)
        ev = e.sel(site=s).to_dataframe().drop(columns="site", errors="ignore")
        ev.index = pd.DatetimeIndex(ev.index)
        e100 = pd.Series(np.hypot(ev["u100"], ev["v100"]), index=ev.index)
        sc = h[[z for z in range(60, 110, 10)]].mean(axis=1, skipna=False).dropna()
        c = best_shift(sc, e100)
        srt = sorted(c.items(), key=lambda kv: -kv[1])
        if len(srt) < 2:
            lines.append(f"  {s}: only {len(sc)} usable sodar hours at 60-100 m, skipped")
            rises.append(False)
            continue
        sh = srt[0][0]
        lines.append(f"  {s}: best shift {sh:+d} h (corr {srt[0][1]:.2f}), next {srt[1][0]:+d} h ({srt[1][1]:.2f}); {'clear' if srt[0][1] - srt[1][1] >= 0.02 else 'NOT clear'}")
        h.index = h.index + pd.Timedelta(hours=sh)
        r = {}
        for z in HEIGHTS:
            if h[z].notna().mean() < 0.7:
                continue
            es = pd.Series(era_speed(ev["u10"], ev["v10"], ev["u100"], ev["v100"], z), index=ev.index)
            j = pd.concat([h[z], es], axis=1, join="inner").dropna()
            if len(j) > 300:
                r[z] = j.iloc[:, 0].mean() / j.iloc[:, 1].mean()
        lines.append("      ratio sodar / ERA5: " + ", ".join(f"{z} m {v:.2f}" for z, v in r.items()) + f"  (valid hours at 200 m: {h[200].notna().mean():.2f})")
        ks = sorted(r)
        rises.append(len(ks) >= 2 and r[ks[-1]] - r[ks[0]] >= 0.03)
    lines.append("Rule (set 2026-11-16): stop if the highest-kept-height ratio is not above the lowest-kept-height (30 m) ratio by >= 0.03 at 4 of 5 sodars.")
    lines.append("Result: " + judge(rises))
    K.report(NAME, lines)


def _selfcheck():
    assert abs(era_speed(3, 4, 6, 8, 100) - 10) < 1e-9 and abs(era_speed(3, 4, 6, 8, 10) - 5) < 1e-9
    i = pd.date_range("2011-08-01", periods=24 * 60, freq="h")
    b = pd.Series(np.sin(2 * np.pi * i.hour / 24.0), index=i)
    a = b.copy()
    a.index = a.index - pd.Timedelta(hours=6)           # sodar clock 6 h behind -> shift +6 recovers
    c = best_shift(a, b)
    assert max(c, key=c.get) == 6
    assert judge([True] * 4 + [False]).startswith("continue") and judge([True] * 3 + [False] * 2).startswith("STOP")


_selfcheck()
if __name__ == "__main__":
    main()
