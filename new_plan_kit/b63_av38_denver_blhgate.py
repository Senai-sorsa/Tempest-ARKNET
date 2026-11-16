"""New_Plan 13 AV38: third-site confirmation of AV36 (blh gate >= 1000 m on the AV12 gust predictor) at Denver: balloons USM00072469 with DEN one-minute ASOS (main), APA (check).
Everything as AV36 / AV12 (b53, b51): truth = balloon mean speed at 300 / 500 / 750 m; predictors ws10 and physical gust excess; least squares fitted on 2016-2020 gated cases, tested on
2021-2023 gated cases; outside the gate the plain 10 m model; paired bootstrap 2000 draws. blh = ERA5 hourly at the Denver cell (data/kit/av38_blh_denver.nc, scripts/av38_blh_denver.py).
Rule (New_Plan AV38 row, set 2026-11-14, copied before the run): PASS = DEN gated MAE gain >= 2 % with the 95 % interval excluding 0 AND the APA gated gain > 0. KILL = DEN gated gain < 1 %. Otherwise MISS.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b63_av38_denver_blhgate.py
Result: docs/results/logs/kit_b63_av38_denver_blhgate.log
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K
from b51_av12_gust_daygate import AL, errors, gain_ci
from gust_1min import physical_hourly

NAME = "b63_av38_denver_blhgate"
SID = "USM00072469"
MIN_BLH = 1000.0


def judge(g, lo, hi, g2):
    if g < 1.0:
        return f"KILL (DEN gated gain {g:+.2f} % < 1 %)"
    if g >= 2.0 and lo > 0 and g2 > 0:
        return f"PASS (DEN gated gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}], APA {g2:+.2f} %)"
    return f"MISS (DEN gated gain {g:+.2f} % [{lo:+.2f}, {hi:+.2f}] (needs >= 2 % and interval > 0), APA {g2:+.2f} % (needs > 0))"


def cases(asos, blh):
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", SID + ".npz"))
    sel = [int(np.argmin(np.abs(d["heights"] - h))) for h in AL]
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    u, v = d["u"][:, sel].astype(float), d["v"][:, sel].astype(float)
    sp = np.where((u == -32768) | (v == -32768), np.nan, np.hypot(u * 0.1, v * 0.1)).mean(1)
    bal = pd.Series(sp, index=t).dropna()
    bal = bal[(bal.index.year >= 2016) & (bal.index.year <= 2023)]
    ph = pd.concat([physical_hourly(f) for f in sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "asos1min_denver", f"{asos}_20[12]*.csv")))])
    ph = ph[~ph.index.duplicated()]
    j = pd.DataFrame({"aloft": bal}).join(ph, how="inner").dropna()
    j = j[(j.ws1 >= 1.0) & (j.gphys >= j.ws1)].copy()
    j["ex"] = j.gphys - j.ws1
    j["blh"] = blh.reindex(j.index.floor("h")).values
    j = j[np.isfinite(j.blh)].copy()
    j["gate"] = j.blh >= MIN_BLH
    return j


def main():
    e = xr.open_dataset(os.path.join(K.REPO, "data", "kit", "av38_blh_denver.nc"))
    blh = pd.Series(e["blh"].values, index=pd.DatetimeIndex(e["valid_time"].values))
    rng = np.random.default_rng(0)
    lines, res = [], {}
    for asos in ("DEN", "APA"):
        j = cases(asos, blh)
        test, out = errors(j)
        g = test.gate.values
        if g.sum() < 30 or j.gate[j.index.year <= 2020].sum() < 30:
            lines.append(f"{asos}: too few gated cases (fit {int(j.gate[j.index.year <= 2020].sum())}, test {int(g.sum())})")
            res[asos] = (np.nan, np.nan, np.nan)
            continue
        ae_a, ae_b = out["a"][1][g], out["b"][1][g]
        res[asos] = gain_ci(ae_a, ae_b, rng)
        lines.append(f"{asos} ASOS + {SID} balloons: {len(j)} matched launches 2016-23 with blh, gated {int(j.gate.sum())}; test 2021-23 gated {int(g.sum())}, outside {int((~g).sum())}; "
                     f"median blh gated {j.blh[j.gate].median():.0f} m")
        lines.append(f"  MAE ws10 {ae_a.mean():.3f} -> ws10 + gust excess {ae_b.mean():.3f} m/s; gain {res[asos][0]:+.2f} % (95 % interval {res[asos][1]:+.2f} to {res[asos][2]:+.2f}); coefficients b {np.round(out['b'][0], 3)}")
    lines.append("AV38 rule (pre-set): PASS = DEN gated gain >= 2 % with interval > 0 AND APA gated gain > 0; KILL = DEN gated gain < 1 %; else MISS.")
    lines.append("AV38 verdict: " + ("NOT RUN (too few gated cases)" if np.isnan(res["DEN"][0]) else judge(*res["DEN"], res["APA"][0])))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(2.5, 0.5, 4.0, 0.3).startswith("PASS") and judge(0.5, 0.1, 1.0, 0.3).startswith("KILL") and judge(2.5, -0.1, 4.0, 0.3).startswith("MISS")


_selfcheck()
if __name__ == "__main__":
    main()
