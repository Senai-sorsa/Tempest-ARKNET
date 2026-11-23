"""Hybrid rerun (step C, project venv): summarise flights3.csv.   cd <repo> ; .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/analyze3.py"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE, "flights3.csv"))
df["err"] = 100.0 * (df.apogee_ft / df.truth_ft - 1.0)
scen = list(df.scenario.unique())
out = []
P = lambda s="": (print(s), out.append(s))
P("| flight | truth ft | " + " | ".join(s.split(" ")[0] for s in scen) + " |")
P("|---|---|" + "---|" * len(scen))
summ = {s: [] for s in scen}
for fl in df.flight.unique():
    g = df[df.flight == fl]
    truth = g.truth_ft.iloc[0]
    cells = []
    for s in scen:
        x = g[g.scenario == s]
        med = float(np.median(x.apogee_ft))
        e = 100.0 * (med / truth - 1.0)
        summ[s].append(e)
        cells.append(f"{med:.0f} ({e:+.1f} %)" + (f" ±{x.apogee_ft.std():.0f}" if len(x) > 1 else ""))
    P(f"| {fl} | {truth:.0f} | " + " | ".join(cells) + " |")
P()
P("| scenario | what it is | mean abs error (3 flights) | mean signed error | closer than S0 | closer than S1 |")
P("|---|---|---|---|---|---|")
b0, b1 = np.abs(summ[scen[0]]), np.abs(summ[scen[1]])
what = {scen[0]: "the branch's own air and wind", scen[1]: "standard air at the true pad, no wind", scen[2]: "all Tempest (past mode)", scen[3]: "standard air + Tempest wind", scen[4]: "+ Dryden turbulence", scen[5]: "+ discrete gust"}
for s in scen:
    e = np.array(summ[s])
    P(f"| {s} | {what[s]} | {np.abs(e).mean():.2f} % | {e.mean():+.2f} % | {int((np.abs(e) < b0).sum())} of 3 | {int((np.abs(e) < b1).sum())} of 3 |")
P()
P("Paired differences of the median apogee (ft) between scenarios, per flight (same atmosphere index k): wind effect = H0 - S1, air effect = B - H0, turbulence = H1 - H0, gust = H2 - H1")
P("| flight | wind (H0 - S1) | Tempest air instead of standard (B - H0) | turbulence (H1 - H0) | gust (H2 - H1) | sd of H0 | sd of H1 | sd of H2 |")
P("|---|---|---|---|---|---|---|---|")
for fl in df.flight.unique():
    g = df[df.flight == fl]
    m = lambda key: g[g.scenario.str.startswith(key)].sort_values("k").apogee_ft.to_numpy()
    s1 = g[g.scenario.str.startswith("S1")].apogee_ft.iloc[0]
    B, H0, H1, H2 = m("B"), m("H0"), m("H1"), m("H2")
    P(f"| {fl} | {np.median(H0) - s1:+.0f} | {np.median(B - H0):+.0f} | {np.median(H1 - H0):+.0f} | {np.median(H2 - H1):+.0f} | {H0.std():.0f} | {H1.std():.0f} | {H2.std():.0f} |")
P()
P("Truth rank inside the sampled apogees (share of the 100 below the truth; 0 or 1 = outside the whole sample):")
for fl in df.flight.unique():
    g = df[df.flight == fl]
    t = g.truth_ft.iloc[0]
    P(f"- {fl}: " + ", ".join(f"{s.split(' ')[0]} {(g[g.scenario == s].apogee_ft < t).mean():.2f}" for s in scen[2:]))
open(os.path.join(HERE, "summary3.md"), "w", encoding="utf-8").write("\n".join(out))
