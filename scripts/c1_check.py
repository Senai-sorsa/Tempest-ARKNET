"""C1 check: the sequences made by tempest_weather.api.atmosphere_sequence (a) reproduce the ERA5 lag correlations of the table within 0.05, (b) keep each hour's marginal spread, (c) keep the vertical
correlation of the single-hour ensemble. 6 dates x 2 sites, offsets -3..6 h, n = 800.
    PYTHONPATH=. python scripts/c1_check.py ASSETS_DIR"""
import sys

import numpy as np

from tempest_weather import _core, api
from tempest_weather.distributions import norm_ppf

A = sys.argv[1]
mz = np.load(A + "/model.npz")
table, kappa = mz["coherence/rho"], (mz["coherence/kappa"] if "coherence/kappa" in mz.files else np.ones(176))
nh = _core.NH
OFF = (-3, -1, 0, 2, 4, 6)
dates = ["2027-01-20 12:00", "2027-04-10 13:00", "2027-07-15 12:00", "2027-10-05 14:00", "2028-02-12 12:00", "2028-08-22 13:00"]
sites = [(31.94, -102.19), (32.99, -106.97)]
z = lambda x: norm_ppf((np.argsort(np.argsort(x, 0), 0) + 0.5) / len(x))
dev, keep, vert = [], [], []
for lat, lon in sites:
    for d in dates:
        season = (int(d[5:7]) % 12) // 3
        atms, _ = api.atmosphere_sequence(lat, lon, d, offsets=OFF, n=800, seed=3, assets=A)
        solo = [api.atmosphere_set(lat, lon, d, n=800, seed=1000 + o, assets=A) for o in OFF]
        for v, name in enumerate(("u", "v", "T", "RH")):
            cols = np.arange(4, nh, 4)
            for i in range(1, len(OFF)):
                lag = OFF[i] - OFF[0]
                c = np.array([np.corrcoef(z(atms[0][name][:, h]), z(atms[i][name][:, h]))[0, 1] for h in cols])
                dev.append(np.abs(c - kappa[v * nh + cols] * table[season, lag, v * nh + cols]).mean())     # expected: nugget model, kappa x ERA5 lag correlation
            keep.append(np.abs(atms[2][name].std(0) / np.maximum(solo[2][0][name].std(0), 1e-9) - 1).mean())
            cs = np.corrcoef(solo[2][0][name][:, ::4].T)
            cq = np.corrcoef(atms[2][name][:, ::4].T)
            vert.append(np.abs(cs - cq)[np.triu_indices_from(cs, 1)].mean())
print(f"lag correlation vs table: mean |difference| {np.mean(dev):.3f}, worst case {np.max(dev):.3f} (goal 0.05)")
print(f"hour spread kept: mean relative change of the sample sd {np.mean(keep) * 100:.1f} %")
print(f"vertical correlation kept: mean |change| of the correlation between heights {np.mean(vert):.3f}")
