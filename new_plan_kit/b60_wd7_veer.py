"""New_Plan WD7 (measurement): wind veer (direction change with height) of the sodars against ERA5. CPU, no training, nothing in the tool changes.
Data: the five WFIP1 sodars (data/raw/a2e, clock = UTC after b59), 30 m and 100 m direction, hourly vector-mean (>= 4 of 6 valid 10-min values), speed >= 3 m/s at both heights;
ERA5 hourly u10 v10 u100 v100 ssrd (data/kit/wd6_era5_points.nc). Real veer = dir(100 m) - dir(30 m), wrapped to +-180. ERA5 has only 10 and 100 m, so its 10 -> 100 m veer is scaled by
ln(100/30) / ln(100/10) = 0.523 to the sodar layer (veer taken to grow with ln z; stated limit). Classes: night (ERA5 ssrd = 0) and day (ssrd > 0), the stability proxy available at all sites.
Rule (set 2026-11-16 before running; New_Plan WD7 says 4 of 6 sites in 2 stability classes, the tower is not usable here so the base is the 5 sodars -> 4 of 5):
  a fix is PROPOSED only if the median real veer differs from the scaled ERA5 veer by more than 10 degrees in BOTH classes at 4 of 5 sodars. Otherwise measurement only, no fix.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b60_wd7_veer.py
Result: docs/results/logs/kit_b60_wd7_veer.log
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

NAME = "b60_wd7_veer"
SITES = ("brady", "cleburne", "colorado_city", "jayton", "ozona")
SCALE = np.log(100 / 30) / np.log(100 / 10)


def wrap(d):
    return (np.asarray(d) + 180) % 360 - 180


def deg(u, v):
    return (np.rad2deg(np.arctan2(-np.asarray(u), -np.asarray(v))) + 360) % 360


def load(site):
    """hourly vector-mean u / v at 30 and 100 m (UTC clock), hours with >= 4 valid 10-min values."""
    fs = sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "a2e", f"wfip1_sodar_{site}", "*.clean.csv")))
    cols = ["Start Time", "Spd 30m", "Spd 100m", "Dir 30m", "Dir 100m"]
    d = pd.concat([pd.read_csv(f, usecols=cols, na_values=["", "M"]) for f in fs])
    d.index = pd.to_datetime(d.pop("Start Time"))
    d = d[~d.index.duplicated()].sort_index()
    ok = (d["Spd 30m"] >= 0) & (d["Spd 30m"] < 60) & (d["Spd 100m"] >= 0) & (d["Spd 100m"] < 60) & (d["Dir 30m"] <= 360) & (d["Dir 100m"] <= 360)
    d = d.where(ok)
    out = {}
    for z in (30, 100):
        r = np.deg2rad(d[f"Dir {z}m"])
        s = d[f"Spd {z}m"]
        out[f"u{z}"], out[f"v{z}"] = (-s * np.sin(r)).resample("1h").mean(), (-s * np.cos(r)).resample("1h").mean()
    n = d["Spd 30m"].resample("1h").count()
    return pd.DataFrame(out).where(n >= 4).dropna()


def judge(diffs):
    """diffs = {site: (night diff, day diff)} -> verdict."""
    n = sum(abs(a) > 10 and abs(b) > 10 for a, b in diffs.values() if np.isfinite(a) and np.isfinite(b))
    return f"fix proposed ({n} of {len(diffs)} sodars above 10 deg in both classes)" if n >= 4 else f"measurement only, no fix ({n} of {len(diffs)} sodars above 10 deg in both classes)"


def main():
    K.ram_gate(3.0)
    e = xr.open_dataset(os.path.join(K.REPO, "data", "kit", "wd6_era5_points.nc"))
    lines = ["WD7 veer: median dir(100 m) - dir(30 m), sodar vs ERA5 10->100 m veer x 0.523, by class, speeds >= 3 m/s at 10 / 30 / 100 m; difference = sodar - ERA5 (deg)"]
    diffs = {}
    for s in SITES:
        h = load(s)
        h.index = h.index + pd.Timedelta(hours=1)           # b59: sodar clock + 1 h matches ERA5 (UTC)
        ev = e.sel(site=s).to_dataframe()
        ev.index = pd.DatetimeIndex(ev.index)
        j = h.join(ev[["u10", "v10", "u100", "v100", "ssrd"]].add_prefix("e_"), how="inner").dropna()
        j = j[(np.hypot(j.u30, j.v30) >= 3) & (np.hypot(j.u100, j.v100) >= 3) & (np.hypot(j.e_u10, j.e_v10) >= 3)]
        real = wrap(deg(j["u100"], j["v100"]) - deg(j["u30"], j["v30"]))
        era = wrap(deg(j["e_u100"], j["e_v100"]) - deg(j["e_u10"], j["e_v10"])) * SCALE
        night = j["e_ssrd"].values <= 0
        res = []
        for name, m in (("night", night), ("day", ~night)):
            if m.sum() < 100:
                res.append(np.nan)
                continue
            rm, em = np.median(real[m]), np.median(era[m])
            res.append(rm - em)
            lines.append(f"  {s} {name}: n {int(m.sum())}; median veer sodar {rm:+.1f}, ERA5 scaled {em:+.1f}; diff {rm - em:+.1f}")
        diffs[s] = tuple(res)
    lines.append("Rule (set 2026-11-16): fix proposed only if |median sodar - ERA5 veer| > 10 deg in both classes at 4 of 5 sodars.")
    lines.append("Result: " + judge(diffs))
    K.report(NAME, lines)


def _selfcheck():
    assert abs(wrap(350 - 10) + 20) < 1e-9 and abs(deg(-1.0, 0.0) - 90) < 1e-9
    assert judge({str(i): (12, -15) for i in range(4)} | {"x": (1, 1)}).startswith("fix") and judge({str(i): (12, 3) for i in range(5)}).startswith("measurement")


_selfcheck()
if __name__ == "__main__":
    main()
