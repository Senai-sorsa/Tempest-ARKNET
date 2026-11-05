"""F-23: does the quantile-level range map leave the min-max coverage of 199 draws at 0.99 on the rows it was fitted on? (the map equates pooled quantile levels; coverage uses the extreme draws)
In-sample (fit years 2021-23, rows drawn afresh) and out-of-sample (2024-25), per column, then the mean |cov99 - 0.99|."""
import numpy as np
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz

M, C, D = "models/generator_80_p2f.pt", "models/generator_80_p2f.calib2021.npz", "data/train/pilot80_dpd.npz"
torch.manual_seed(1)
rng = np.random.default_rng(1)
s = Sampler(torch.load(M, map_location="cpu", weights_only=True), device="cpu")
cal = spread.load(C, M)
d = load_npz(D)
year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
for label, lo, hi in (("fit years 2021-23", 2021, 2023), ("test years 2024-25", 2024, 2025)):
    rows = np.sort(rng.choice(np.flatnonzero((year >= lo) & (year <= hi)), 2500, replace=False))
    truth = to_physical(np.asarray(d["target"][rows]))
    x = np.concatenate([spread.apply(cal, s.profiles(np.repeat(cond[rows[i:i + 250]], 199, 0)).reshape(-1, 199, truth.shape[1])) for i in range(0, len(rows), 250)])
    inside = ((truth >= x.min(1)) & (truth <= x.max(1))).mean(0)
    print(f"{label}: mean cov99 {inside.mean():.4f}, mean |cov99-0.99| per column {np.abs(inside - 0.99).mean():.4f}, worst column {inside.min():.4f}/{inside.max():.4f}", flush=True)
