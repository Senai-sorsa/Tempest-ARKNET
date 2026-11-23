"""G6 analysis: per flight, median apogee and sd for each turbulence variant, and the paired difference of each variant against the shipped Dryden (same atmosphere index k)."""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE, "flights5.csv"))
col = "apogee_ft" if "apogee_ft" in df else [c for c in df.columns if "apogee" in c][0]
base = "H1 + Dryden (shipped)"
out = []
for fl, g in df.groupby("flight"):
    truth = g.truth_ft.iloc[0]
    b = g[g.scenario == base].set_index("k")[col]
    for sc, h in g.groupby("scenario", sort=False):
        x = h.set_index("k")[col]
        d = (x - b).dropna()
        out.append(f"| {fl} | {sc} | {np.median(x):.0f} ({100 * (np.median(x) / truth - 1):+.1f} %) | {x.std():.0f} | {d.mean():+.1f} +- {d.std() / np.sqrt(max(len(d), 1)):.1f} |")
txt = "| flight | scenario | median apogee ft (error) | sd ft | paired vs shipped Dryden, ft |\n|---|---|---|---|---|\n" + "\n".join(out)
print(txt)
open(os.path.join(HERE, "summary5.md"), "w", encoding="utf-8").write(txt + "\n")
