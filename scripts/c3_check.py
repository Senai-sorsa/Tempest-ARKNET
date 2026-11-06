"""C3 check: with per-regime lag tables, the generated trajectories reproduce the regime-specific time correlation (kappa x regime table) within 0.05 at lags up to 12 h. Offsets -6 and 6 h
(12 h apart) and a middle hour; regime of a trajectory = tercile of the 0-3 km shear of its first hour.
    PYTHONPATH=. python scripts/c3_check.py ASSETS_DIR"""
import sys

import numpy as np

from tempest_weather import _core, api
from tempest_weather.distributions import norm_ppf

A = sys.argv[1]
mz = np.load(A + "/model.npz")
rr, edges, kappa = mz["coherence/rho_regime"], mz["coherence/shear_edges"], mz["coherence/kappa"]
nh = _core.NH
I3 = int(np.argmin(np.abs(_core.HEIGHTS - 3000)))
z = lambda x: norm_ppf((np.argsort(np.argsort(x, 0), 0) + 0.5) / len(x))
dates = ["2027-01-20 13:00", "2027-04-10 13:00", "2027-07-15 13:00", "2027-10-05 13:00"]
dev = []
for d in dates:
    season = (int(d[5:7]) % 12) // 3
    atms, _ = api.atmosphere_sequence(32.0, -102.3, d, offsets=(-6, 0, 6), n=3000, seed=5, assets=A)
    sh = np.hypot(atms[0]["u"][:, I3] - atms[0]["u"][:, 0], atms[0]["v"][:, I3] - atms[0]["v"][:, 0])
    reg = np.digitize(sh, edges)
    for r in range(3):
        m = reg == r
        for v, name in enumerate(("u", "v", "T", "RH")):
            cols = np.arange(4, nh, 4)
            c = np.array([np.corrcoef(z(atms[0][name][m][:, h]), z(atms[2][name][m][:, h]))[0, 1] for h in cols])
            want = kappa[v * nh + cols] * rr[r, season, 12, v * nh + cols]
            dev.append(np.abs(c - want).mean())
print(f"12 h correlation inside each regime vs kappa x regime table: mean |difference| {np.mean(dev):.3f}, worst {np.max(dev):.3f} (goal 0.05; n per regime about 1000, sampling noise about 0.02)")
