"""Raw (uncalibrated) per-year mean bias (model mean - truth) of E12 for T/RH bands, years 2011-2025."""
import numpy as np, torch, pandas as pd
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.scoring.score import physical_names

torch.manual_seed(0); rng = np.random.default_rng(0)
ck = torch.load("models/generator_80_b0smix.pt", map_location="cpu", weights_only=True)
s = Sampler(ck, device="cuda")
d = load_npz("data/train/pilot80_smix.npz")
names = np.array(physical_names())
h = np.array([int(n.split("_")[1]) if n.count("_") and n.split("_")[1].isdigit() else -1 for n in names])
var = np.array([n.split("_")[0] for n in names])
groups = {"T 0-1k": (var == "T") & (h >= 0) & (h < 1000), "T 1-5k": (var == "T") & (h >= 1000) & (h < 5000),
          "T 5-12k": (var == "T") & (h >= 5000) & (h <= 12000), "t2m": names == "t2m",
          "RH 1-5k": (var == "RH") & (h >= 1000) & (h < 5000)}
m, out = 16, []
for y in range(2011, 2026):
    idx = np.flatnonzero(d["year"] == y)
    if not len(idx):
        continue
    idx = rng.choice(idx, min(20000, len(idx)), replace=False)
    x = s.profiles(np.repeat(d["cond"][idx], m, axis=0)).reshape(len(idx), m, -1).mean(1)
    e = x - to_physical(d["target"][idx])
    out.append({"year": y, **{k: float(e[:, g].mean()) for k, g in groups.items()}})
    print(out[-1], flush=True)
print(pd.DataFrame(out).round(3).to_string(index=False))
