"""IL-67: is the target inhomogeneous? Mean (balloon - raw ERA5) by year, per variable x band, at the two IGRA stations (00Z and 12Z soundings).
    PYTHONPATH=. python scripts/era5_vs_balloon_by_year.py [--first 2005] [--last 2025]
"""
import argparse

import numpy as np
import pandas as pd

from tempest.forecast import modeP
from tempest.profiles.to_heights import HEIGHTS, PROFILE

ap = argparse.ArgumentParser()
ap.add_argument("--first", type=int, default=2005)
ap.add_argument("--last", type=int, default=2025)
a = ap.parse_args()
d = modeP.load_pairs("data/pilot/profiles80.zarr", "data/raw/igra", a.first, a.last)
diff = d["obs"] - d["era"]                                   # (S, 4, 44)
yr = d["time"].year.to_numpy()
bands = [("0-1 km", HEIGHTS <= 1000), ("1-5 km", (HEIGHTS > 1000) & (HEIGHTS <= 5000)), ("5-12 km", (HEIGHTS > 5000) & (HEIGHTS <= 12000)), ("12-18 km", HEIGHTS > 12000)]
rows = []
for y in range(a.first, a.last + 1):
    k = yr == y
    if k.sum() < 50:
        continue
    for v, name in enumerate(PROFILE):
        for b, sel in bands:
            rows.append(dict(year=y, var=name, band=b, bias=float(np.nanmean(diff[k][:, v][:, sel])), n=int(k.sum())))
t = pd.DataFrame(rows)
pv = t.pivot_table(index=["var", "band"], columns="year", values="bias", sort=False)
with pd.option_context("display.width", 300, "display.float_format", "{:+.2f}".format):
    print(pv[[c for c in pv.columns if c >= 2010]].to_string())
