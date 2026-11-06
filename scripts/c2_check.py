"""C2 check: downrange sequences (tempest_weather.api.atmosphere_downrange) reproduce the ERA5 distance correlation x kappa within 0.05, keep each point's marginal, and the points are not
identical copies. 6 dates x 4 bearings, starts inside the box, distances 0..60 km, n = 800.
    PYTHONPATH=. python scripts/c2_check.py ASSETS_DIR"""
import sys

import numpy as np

from tempest_weather import _core, api
from tempest_weather.distributions import norm_ppf

A = sys.argv[1]
mz = np.load(A + "/model.npz")
rho, km, kappa = mz["coherence_dist/rho"], mz["coherence_dist/km"], mz["coherence/kappa"]
nh = _core.NH
D = (0, 30, 60)
dates = ["2027-01-20 12:00", "2027-04-10 13:00", "2027-07-15 12:00", "2027-10-05 14:00", "2028-02-12 12:00", "2028-08-22 13:00"]
z = lambda x: norm_ppf((np.argsort(np.argsort(x, 0), 0) + 0.5) / len(x))
dev, spread = [], []
for d in dates:
    season = (int(d[5:7]) % 12) // 3
    for bearing, start in ((90, (32.5, -105.5)), (0, (31.6, -104.0)), (180, (33.5, -104.0)), (270, (32.5, -102.5))):
        atms, _ = api.atmosphere_downrange(start[0], start[1], d, bearing, D, n=800, seed=4, assets=A)
        solo, _ = api.atmosphere_set(start[0] + 30 * np.cos(np.radians(bearing)) / 111, start[1] + 30 * np.sin(np.radians(bearing)) / (111 * np.cos(np.radians(start[0]))), d, n=800, seed=2030, assets=A)
        for v, name in enumerate(("u", "v", "T", "RH")):
            cols = np.arange(4, nh, 4)
            for i in (1, 2):
                lagkm = D[i]
                row = np.array([np.interp(lagkm, km, rho[season][:, v * nh + h]) for h in cols])
                c = np.array([np.corrcoef(z(atms[0][name][:, h]), z(atms[i][name][:, h]))[0, 1] for h in cols])
                dev.append(np.abs(c - kappa[v * nh + cols] * row).mean())
        spread.append(np.abs(atms[1]["T"].std(0) / np.maximum(solo["T"].std(0), 1e-9) - 1).mean())
print(f"distance correlation vs kappa x ERA5: mean |difference| {np.mean(dev):.3f}, worst {np.max(dev):.3f} (goal 0.05)")
print(f"marginal spread kept at 30 km: mean relative change of the T sd {np.mean(spread) * 100:.1f} %")
