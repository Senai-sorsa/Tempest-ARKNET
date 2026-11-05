"""IL-60: where does the shear tail gap sit? 99th and 99.9th percentile of neighbour shear per layer group and per season, truth vs samples (optionally with the shear map).
    PYTHONPATH=. python scripts/shear_by_layer.py MODEL CALIB DATA [--shear-map F] [--rows 5000]
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS
from tempest.scoring.score import group_keys

NH = len(HEIGHTS)
ap = argparse.ArgumentParser()
ap.add_argument("model")
ap.add_argument("calib")
ap.add_argument("data")
ap.add_argument("--shear-map")
ap.add_argument("--rows", type=int, default=5000)
ap.add_argument("--m", type=int, default=199)
a = ap.parse_args()
rng = np.random.default_rng(0)
torch.manual_seed(0)
sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True))
cal = spread.load(a.calib, a.model)
d = load_npz(a.data)
idx = np.sort(rng.choice(np.flatnonzero((d["year"] >= 2024) & (d["year"] <= 2025)), a.rows, replace=False))
y = to_physical(np.asarray(d["target"][idx]))
cond = np.asarray(d["cond"])[idx]
month = (group_keys(np.asarray(d["cond"]))[idx] // 12) % 12 + 1
x = np.empty((len(idx), a.m, y.shape[1]), np.float32)
for i in range(0, len(idx), 400):
    x[i:i + 400] = spread.apply(cal, sampler.profiles(np.repeat(cond[i:i + 400], a.m, axis=0)).reshape(len(cond[i:i + 400]), a.m, -1))
if a.shear_map:
    from tempest.calibrate import shear_map
    x = shear_map.apply(dict(np.load(a.shear_map)), x)
dz = np.diff(HEIGHTS) / 1000.0
sh = lambda v: np.hypot(np.diff(v[..., :NH], axis=-1), np.diff(v[..., NH:2 * NH], axis=-1)) / dz
st, ss = sh(y), sh(x)                                            # (N, 43), (N, m, 43)
mid = HEIGHTS[1:]
season = np.select([np.isin(month, [12, 1, 2]), np.isin(month, [3, 4, 5]), np.isin(month, [6, 7, 8])], ["DJF", "MAM", "JJA"], "SON")
rows = []
groups = [("0-1 km", mid <= 1000), ("1-3 km", (mid > 1000) & (mid <= 3000)), ("3-6 km", (mid > 3000) & (mid <= 6000)), ("6-9 km", (mid > 6000) & (mid <= 9000)),
          ("9-12 km", (mid > 9000) & (mid <= 12000)), ("12-15 km", (mid > 12000) & (mid <= 15000)), ("15-18 km", mid > 15000)]
for sname in ["all", "DJF", "MAM", "JJA", "SON"]:
    k = np.ones(len(idx), bool) if sname == "all" else season == sname
    for g, sel in groups:
        t, s = st[k][:, sel].ravel(), ss[k][:, :, sel].ravel()
        rows.append(dict(season=sname, layers=g, p99_truth=np.percentile(t, 99), p99_sample=np.percentile(s, 99), p999_truth=np.percentile(t, 99.9), p999_sample=np.percentile(s, 99.9), n=int(k.sum())))
t = pd.DataFrame(rows)
t["ratio99"] = t.p99_sample / t.p99_truth
t["ratio999"] = t.p999_sample / t.p999_truth
with pd.option_context("display.width", 200, "display.float_format", "{:.2f}".format):
    print(t.pivot_table(index="layers", columns="season", values="ratio999", sort=False).to_string())
    print(t.pivot_table(index="layers", columns="season", values="ratio99", sort=False).to_string())
t.to_csv(a.model.rsplit(".", 1)[0] + ("_smap" if a.shear_map else "") + "_shear_by_layer.csv", index=False)
