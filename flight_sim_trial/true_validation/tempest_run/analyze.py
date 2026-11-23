"""Summarise tempest_run/flights.csv: apogee error vs the measured apogee for each scenario and flight, plus context from the branch (RASAero, RocketPy).
    .venv/Scripts/python -W ignore tempest_run/analyze.py        (project venv has pandas)
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
df = pd.read_csv(os.path.join(HERE, "flights.csv"))
ctx = pd.read_csv(os.path.join(ROOT, "validation", "results", "final_flights.csv")).set_index("flight")
df["err_pct"] = 100.0 * (df.apogee_ft / df.truth_ft - 1.0)
out = []
P = lambda s="": (print(s), out.append(s))

order = ["S0 branch as filed", "S1 plain standard atmosphere at the true pad, no wind", "S2 Tempest climate (date + hour)", "S3 Tempest past (ERA5 + balloon correction)", "S4 Tempest past + measured surface values"]
P("| flight | truth (ft) | " + " | ".join(o.split(" ")[0] for o in order) + " | RASAero | RocketPy (plain) |")
P("|---|---|" + "---|" * (len(order) + 2))
summary = {o: [] for o in order}
for fl in df.flight.unique():
    g = df[df.flight == fl]
    truth = g.truth_ft.iloc[0]
    cells = []
    for o in order:
        x = g[g.scenario == o]
        if x.empty:
            cells.append("-")
            continue
        med = float(np.median(x.apogee_ft))
        e = 100.0 * (med / truth - 1.0)
        summary[o].append(e)
        sd = x.apogee_ft.std() if len(x) > 1 else 0.0
        cells.append(f"{med:.0f} ({e:+.1f} %)" + (f" ±{sd:.0f}" if len(x) > 1 else ""))
    c = ctx.loc[fl]
    P(f"| {fl} | {truth:.0f} | " + " | ".join(cells) + f" | {c.ras_ft:.0f} ({100 * (c.ras_ft / truth - 1):+.1f} %) | {c.rocketpy_plain_ft:.0f} ({100 * (c.rocketpy_plain_ft / truth - 1):+.1f} %) |")
P()
P("| scenario | mean abs error (3 flights) | mean signed error | flights closer than S0 |")
P("|---|---|---|---|")
base = np.abs(summary[order[0]])
for o in order:
    e = np.array(summary[o])
    if len(e) == 0:
        continue
    P(f"| {o} | {np.abs(e).mean():.2f} % | {e.mean():+.2f} % | {int((np.abs(e) < base).sum())} of {len(e)} |")
P()
P("Pad air (mean over the sampled atmospheres) and wind met along the climb:")
P("| flight | scenario | pad T (C) | pad density (kg/m3) | max wind on the way up (m/s) |")
P("|---|---|---|---|---|")
for fl in df.flight.unique():
    for o in order:
        x = df[(df.flight == fl) & (df.scenario == o)]
        if not x.empty:
            P(f"| {fl} | {o.split(' ')[0]} | {x.T_pad.mean() - 273.15:.1f} | {x.rho_pad.mean():.3f} | {x.max_wind.mean():.1f} |")
open(os.path.join(HERE, "summary.md"), "w", encoding="utf-8").write("\n".join(out))
