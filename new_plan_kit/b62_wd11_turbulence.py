"""New_Plan WD11 (measurement): turbulence-intensity ratios by height, stability and campaign, SWiFT tower 10-min file. CPU, no training, nothing in the tool changes.
Data: data/raw/a2e/ttu_swift_200m/processed/swift_10min.csv. Heights 33 / 155 / 382 / 656 ft (10 / 47 / 116 / 200 m). Ratios: TI_u = sd_stream / speed, TI_w = sd_w / speed (speed >= 3 m/s at that height).
Stability class from the 656 ft - 33 ft temperature difference dT (K, t_C): stable dT > -0.5, neutral -1.5 .. -0.5, unstable < -1.5 (adiabatic lapse over 190 m is -1.9 K). Campaigns by month: 2013-11, 2014-05, 2014-09.
Rule (set 2026-11-16 before running): measurement. The flight engine's assumed constants live in the external simulator, not in this repo, so no replacement is proposed; the plan's test
(two stability classes differ from one constant by > 20 % in all three campaigns) is run against the pooled median of all classes as the stand-in constant: reported as "stability matters" at a height
if the median TI_u of two classes each differs from the all-class median by > 20 % in all three campaigns that have >= 20 hours in those classes.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b62_wd11_turbulence.py
Result: docs/results/logs/kit_b62_wd11_turbulence.log
"""
import os

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b62_wd11_turbulence"
FT = {10: "33ft", 47: "155ft", 116: "382ft", 200: "656ft"}
CLASSES = ("stable", "neutral", "unstable")


def cls(dt):
    return np.where(dt > -0.5, "stable", np.where(dt >= -1.5, "neutral", "unstable"))


def matters(med):
    """med = {campaign: {class: median, 'all': median}} -> True if >= 2 classes are > 20 % off the all-class median in every campaign (classes with a median present)."""
    ok = []
    for c, m in med.items():
        ok.append({k for k in CLASSES if k in m and abs(m[k] / m["all"] - 1) > 0.2})
    return len(ok) == len(med) and len(set.intersection(*ok)) >= 2 if ok else False


def main():
    d = pd.read_csv(os.path.join(K.REPO, "data", "raw", "a2e", "ttu_swift_200m", "processed", "swift_10min.csv"), parse_dates=["time_utc"])
    d["camp"] = d.time_utc.dt.strftime("%Y-%m")
    d["cls"] = cls((d["t_C_656ft"] - d["t_C_33ft"]).values)
    d.loc[(d["t_C_656ft"] - d["t_C_33ft"]).isna(), "cls"] = None
    lines = ["WD11 turbulence ratios (medians; 10-min rows, speed >= 3 m/s) by height, stability class and campaign: TI_u = sd_stream / speed | TI_w = sd_w / speed (n)"]
    for z, f in FT.items():
        x = d[d[f"speed_{f}"] >= 3].copy()
        x["tiu"], x["tiw"] = x[f"sd_stream_{f}"] / x[f"speed_{f}"], x[f"sd_w_{f}"] / x[f"speed_{f}"]
        x = x.dropna(subset=["tiu", "tiw", "cls"])
        med = {}
        lines.append(f"  {z} m:")
        for c, g in x.groupby("camp"):
            if len(g) < 100:
                continue
            m = {"all": g.tiu.median()}
            parts = []
            for k in CLASSES:
                gk = g[g.cls == k]
                if len(gk) >= 20:
                    m[k] = gk.tiu.median()
                    parts.append(f"{k} {gk.tiu.median():.3f} | {gk.tiw.median():.3f} ({len(gk)})")
            med[c] = m
            lines.append(f"    {c}: all {g.tiu.median():.3f} | {g.tiw.median():.3f} ({len(g)}); " + "; ".join(parts))
        lines.append(f"    stability matters (> 20 % off the all-class median in >= 2 classes, every campaign): {matters(med)}")
    lines.append("Rule (set 2026-11-16): measurement; no replacement of the engine constants proposed (not in this repo).")
    K.report(NAME, lines)


def _selfcheck():
    assert matters({"a": {"all": 1, "stable": 1.5, "unstable": 0.6, "neutral": 1.0}, "b": {"all": 1, "stable": 1.3, "unstable": 0.7}})
    assert not matters({"a": {"all": 1, "stable": 1.5, "unstable": 1.0}})


_selfcheck()
if __name__ == "__main__":
    main()
