"""A3 physics check for E12 on 2024-25: wind shear and lapse rate between neighbouring heights, samples vs truth
(station-corrected targets). Raw samples (no range calibration) and calibrated ones."""
import numpy as np, torch
from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS

torch.manual_seed(0); rng = np.random.default_rng(0)
M = "models/generator_80_b0smix.pt"
s = Sampler(torch.load(M, map_location="cpu", weights_only=True), device="cuda")
cal = spread.load("models/generator_80_b0smix.calib2021.npz", M)
d = load_npz("data/train/pilot80_smix.npz")
idx = rng.choice(np.flatnonzero(d["year"] >= 2024), 4000, replace=False)
m, n = 199, len(HEIGHTS)
truth = to_physical(d["target"][idx])
raw = s.profiles(np.repeat(d["cond"][idx], m, axis=0)).reshape(len(idx), m, -1)
sets = {"truth": truth[:, None], "raw": raw, "calibrated": spread.apply(cal, raw)}
dz = np.diff(HEIGHTS) / 1000.0  # km
bands = [("0-1 km", HEIGHTS[1:] <= 1000), ("1-5 km", (HEIGHTS[1:] > 1000) & (HEIGHTS[1:] <= 5000)),
         ("5-12 km", (HEIGHTS[1:] > 5000) & (HEIGHTS[1:] <= 12000)), (">12 km", HEIGHTS[1:] > 12000)]
for b, sel in bands:
    print(f"--- {b}")
    for k, x in sets.items():
        u, v, T = x[..., :n], x[..., n:2 * n], x[..., 2 * n:3 * n]
        shear = (np.hypot(np.diff(u), np.diff(v)) / dz)[..., sel].ravel()  # m/s per km
        lapse = (-np.diff(T) / dz)[..., sel].ravel()  # K per km, positive = cooling with height
        q = np.percentile(shear, [50, 99, 99.9])
        print(f"{k:>10}: shear p50/p99/p99.9 {q[0]:6.2f} {q[1]:6.2f} {q[2]:6.2f} m/s/km | "
              f"superadiabatic (>9.8 K/km) {100 * (lapse > 9.8).mean():5.2f} % | inversion (<0) {100 * (lapse < 0).mean():5.2f} %")
