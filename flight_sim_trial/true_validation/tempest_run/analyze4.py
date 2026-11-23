"""Rerun 2026-11-10 (copy of the 2026-11-08 script, all-hours tool; writes inputs4 / flights4 / summary4, the 2026-11-08 outputs untouched); was: Rerun 2026-11-08 (step C, project venv): summarise flights4.csv and diagnose.

    cd <repo> ; .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/analyze4.py
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
df = pd.read_csv(os.path.join(HERE, "flights4.csv"))
ctx = pd.read_csv(os.path.join(ROOT, "validation", "results", "final_flights.csv")).set_index("flight")
df["err"] = 100.0 * (df.apogee_ft / df.truth_ft - 1.0)
out = []
P = lambda s="": (print(s), out.append(s))
scen = [s for s in df.scenario.unique()]
P("## Apogee error vs the measured apogee: median of the sampled atmospheres (sd in ft; truth rank = share of the sampled apogees below the truth)\n")
P("| flight | truth ft | " + " | ".join(s.split(" ")[0] + " " + " ".join(s.split(" ")[1:3]) for s in scen) + " |")
P("|---|---|" + "---|" * len(scen))
summ = {s: [] for s in scen}
for fl in df.flight.unique():
    g = df[df.flight == fl]
    truth = g.truth_ft.iloc[0]
    cells = []
    for s in scen:
        x = g[g.scenario == s]
        if x.empty:
            cells.append("-")
            continue
        med = float(np.median(x.apogee_ft))
        e = 100.0 * (med / truth - 1.0)
        summ[s].append(e)
        cells.append(f"{med:.0f} ({e:+.1f} %)" + (f" ±{x.apogee_ft.std():.0f} r{(x.apogee_ft < truth).mean():.2f}" if len(x) > 1 else ""))
    P(f"| {fl} | {truth:.0f} | " + " | ".join(cells) + " |")
P()
P("| scenario | mean abs error (3 flights) | mean signed error | closer than S0 | closer than S1 |")
P("|---|---|---|---|---|")
b0, b1 = np.abs(summ[scen[0]]), np.abs(summ[scen[1]])
for s in scen:
    e = np.array(summ[s])
    if len(e) < 3:
        P(f"| {s} | only {len(e)} flights (no HRRR value for the Heart of Steel window) | | | |")
        continue
    P(f"| {s} | {np.abs(e).mean():.2f} % | {e.mean():+.2f} % | {int((np.abs(e) < b0).sum())} of 3 | {int((np.abs(e) < b1).sum())} of 3 |")
P()
P("## What each scenario put on the pad and aloft (mean over sampled atmospheres)\n")
P("| flight | scenario | pad T (C) | pad density | 10 m wind median (m/s) | wind 10-200 m mean (m/s) | max wind on the way up (m/s) | corr(apogee, pad density) | corr(apogee, mean wind <= 200 m) |")
P("|---|---|---|---|---|---|---|---|---|")
key = {"A": "ai", "B": "past", "C": "past_pin", "D": "past_w", "E": "ai_w", "F": "past_hrrr", "G": "past_s12"}
for fl in df.flight.unique():
    for s in scen[2:]:
        g = df[(df.flight == fl) & (df.scenario == s)].sort_values("k")
        if g.empty:
            continue
        z = np.load(os.path.join(HERE, "inputs4", f"{fl}__{key[s.split(' ')[0]]}.npz"))
        n = len(g)
        u, v = z["u"][:n], z["v"][:n]
        h = z["height_agl"]
        low = h <= 200
        sp = np.hypot(u, v)
        w10 = np.median(sp[:, 0])
        wl = sp[:, low].mean(1)
        c_rho = np.corrcoef(g.apogee_ft, g.rho_pad)[0, 1]
        c_w = np.corrcoef(g.apogee_ft, wl)[0, 1]
        P(f"| {fl} | {s.split(' ')[0]} | {g.T_pad.mean() - 273.15:.1f} | {g.rho_pad.mean():.3f} | {w10:.1f} | {wl.mean():.1f} | {g.max_wind.mean():.1f} | {c_rho:+.2f} | {c_w:+.2f} |")
P()
P("## Ground wind at the launch hour vs what the stations / reanalysis saw\n")
for fl in df.flight.unique():
    j = json.load(open(os.path.join(HERE, "inputs4", f"{fl}__past_pin.json")))
    ob = j["asos"]
    P(f"- {fl}: ASOS TCS at the hour: {ob['speed_ms']:.1f} m/s from {ob['from_deg']:.0f} deg, {ob['temp_c']:.1f} C (stations {ob['reports']}).")
ref = {"Prometheus": "RocketPy ERA5 notebook print: 26.8 C, 0.2 m/s", "Juno3": "RocketPy ERA5 notebook print: 33.8 C, 10.8 m/s from 244 deg"}
for k_, v_ in ref.items():
    P(f"- {k_} reference: {v_}")
P()
P("## Context from the branch (same flights)\n")
for fl in df.flight.unique():
    c = ctx.loc[fl]
    t = df[df.flight == fl].truth_ft.iloc[0]
    P(f"- {fl}: RASAero {c.ras_ft:.0f} ft ({100 * (c.ras_ft / t - 1):+.1f} %), RocketPy plain {c.rocketpy_plain_ft:.0f} ft ({100 * (c.rocketpy_plain_ft / t - 1):+.1f} %)")
open(os.path.join(HERE, "summary4.md"), "w", encoding="utf-8").write("\n".join(out))
