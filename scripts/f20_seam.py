"""F-20 seam check: median of the generator across neighbouring grid longitudes (0.25 degree apart), at 33 N, for several months and hours. The old station choice switches at the midpoint
of the two stations (about 104.4 W); a seam shows as a bigger median step there than at control pairs elsewhere. Reports mean |step| in standardised units (step / spread of the samples) for
T, RH, u, v at 1-5 km and 5-12 km, seam pair vs the average of the other pairs.
    PYTHONPATH=. python scripts/f20_seam.py MODEL.pt CALIB.npz DATA.npz"""
import sys

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.generator import features as feat
from tempest.generator.sample import Sampler
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE

M, C, D = sys.argv[1:4]
d = load_npz(D)
s = Sampler(torch.load(M, map_location="cpu", weights_only=True), device="cpu")
cal = spread.load(C, M)
torch.manual_seed(0)
lons = np.arange(-107.0, -101.0 + 1e-9, 0.25)
names = list(feat.FEATURES)
tbl = dict(oni=0.0, wwv=0.0, qbo30=0.0, qbo50=0.0)
bands = {"1-5 km": (1000, 5000), "5-12 km": (5000, 12000)}
steps = {(v, b): [] for v in PROFILE for b in bands}
for month in (1, 4, 7, 10):
    for hour in (7.0, 12.0, 15.0, 18.0):
        doy = int((month - 0.5) * 30.4)
        rows = []
        for lon in lons:
            rows.append(feat.features(33.0, lon, 1300.0, 1300.0, doy, hour, 2024, 0.0, 0.0, 0.0, 0.0,
                                      **({"gmst": 1.2, "oni_lag3": 0.0} if "gmst" in names else {})) if False else None)
        # build with the dataset's own conventions: take a template row and set lat/lon/hour/doy
        base = np.asarray(d["cond"][:1]).copy()
        c = np.repeat(base, len(lons), 0)
        c[:, names.index("lat")], c[:, names.index("lon")] = 33.0, lons
        a = 2 * np.pi * doy / 365.25
        c[:, names.index("doy_sin")], c[:, names.index("doy_cos")] = np.sin(a), np.cos(a)
        h = 2 * np.pi * hour / 24
        c[:, names.index("hour_sin")], c[:, names.index("hour_cos")] = np.sin(h), np.cos(h)
        x = np.stack([spread.apply(cal, s.profiles(np.repeat(c[i:i + 1], 199, 0)).reshape(1, 199, -1))[0] for i in range(len(lons))])    # (L, 199, 179)
        med, sd = np.median(x, 1), x.std(1)
        nh = len(HEIGHTS)
        for vi, v in enumerate(PROFILE):
            for b, (lo, hi) in bands.items():
                sel = (HEIGHTS >= lo) & (HEIGHTS < hi)
                col = slice(vi * nh, (vi + 1) * nh)
                st = np.abs(np.diff(med[:, col][:, sel], axis=0)) / np.maximum(sd[:, col][:, sel][:-1], 1e-6)
                steps[(v, b)].append(st.mean(1))                                  # (L-1,)
seam = int(np.argmin(np.abs(lons[:-1] + 0.125 + 104.4)))
print(f"seam pair: {lons[seam]:.2f} -> {lons[seam + 1]:.2f}")
for k, v in steps.items():
    arr = np.mean(v, 0)
    print(f"{k[0]:>3} {k[1]:>8}  seam step {arr[seam]:.3f}  other pairs {np.delete(arr, seam).mean():.3f}  ratio {arr[seam] / np.delete(arr, seam).mean():.2f}")
