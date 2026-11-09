"""M5b: the tool's past-mode ensemble (Launch / api.atmosphere_set, mode "past") against the analog ensemble of gw_analog.py on the SAME hours: speed CRPS, speed MAE of the median, 90 % coverage.
N random 2024-25 daytime hours per station (default 250), tool ensemble m = 100. The analog library is 2015-23 (never contains the test hours).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_tool_vs_analog.py [--n 250]"""
import argparse
import os
import sys
from datetime import datetime, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
from gw_analog import feats, hours_of   # noqa: E402
from gw_extrapolate_down import load   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=250)
a = ap.parse_args()
z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
K = 40
W = np.array([1.0, 1.0, 1.0, 1.0, 0.6, 1.2, 1.2, 0.8, 0.8])
sp = lambda x: np.hypot(x[..., 0], x[..., 1])
for st in gw.STATIONS:
    Al, ul, vl, Tl = load(z, st, list(range(2015, 2024)))
    At, ut, vt, Tt = load(z, st, [2024, 2025])
    tl, tt_ = hours_of(z, st, list(range(2015, 2024))), hours_of(z, st, [2024, 2025])
    Xl, Xt = feats(ul, vl, Tl, tl), feats(ut, vt, Tt, tt_)
    mu, sd = Xl.mean(0), Xl.std(0) + 1e-9
    Zl, Zt = (Xl - mu) / sd * W, (Xt - mu) / sd * W
    pick = np.sort(np.random.default_rng(3).choice(len(Zt), min(a.n, len(Zt)), replace=False))
    d2 = (Zt[pick] ** 2).sum(1)[:, None] + (Zl ** 2).sum(1)[None, :] - 2 * Zt[pick] @ Zl.T
    nn = np.argpartition(d2, K, axis=1)[:, :K]
    an = sp(Al[nn])
    obs = sp(At[pick])
    tool = []
    for j, i in enumerate(pick):
        t = tt_[i].astype("datetime64[s]").astype(datetime).replace(tzinfo=timezone.utc)
        u, v = gw.ensemble(st, t, 100, "past", 11 + j)
        tool.append(np.hypot(u, v))
    tool = np.array(tool)
    cr = lambda e: float(crps_ensemble(e[:, :, None], obs[:, None])[:, 0].mean())
    cov = lambda e: float(np.mean((obs >= np.quantile(e, 0.05, axis=1)) & (obs <= np.quantile(e, 0.95, axis=1))))
    raw = np.hypot(ut[pick, 0], vt[pick, 0])
    print(f"\n{st}: {len(pick)} test hours (2024-25), ASOS mean speed {obs.mean():.2f} m/s")
    print(f"  raw ERA5 10 m:        MAE {np.abs(raw - obs).mean():.3f}")
    print(f"  tool past ensemble:   MAE of median {np.abs(np.median(tool, 1) - obs).mean():.3f}   CRPS {cr(tool):.3f}   90 % coverage {cov(tool):.2f}   mean {tool.mean():.2f}")
    print(f"  analog ensemble:      MAE of median {np.abs(np.median(an, 1) - obs).mean():.3f}   CRPS {cr(an):.3f}   90 % coverage {cov(an):.2f}   mean {an.mean():.2f}")
