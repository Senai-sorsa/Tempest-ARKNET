"""F-26: does stability information (wind at 500 m, lapse t2m - T(500 m)) improve the gust distribution? Fit 2000-2020, score 2024-25 like gust_check.py.
    PYTHONPATH=. python scripts/gust_stab_check.py
Writes models/gust_stab_check.csv; the model file models/gust_model.npz is NOT touched."""
import numpy as np
import pandas as pd
import xarray as xr

from scripts.gust_check import load, SITES
from tempest import region
from tempest.gust import model as gm
from tempest.scoring.score import crps_ensemble, coverage90

surf = xr.open_zarr("data/pilot/surface_hourly.zarr")[["u10", "v10", "fg10"]].load()
d = load("data/raw/asos", surf)
prof = xr.open_zarr("data/pilot/profiles80.zarr")
H = 6                                                       # 500 m
stab = np.full((len(d), 2), np.nan)
tt = pd.DatetimeIndex(d.time)
for st, (lat, lon) in SITES.items():
    pt = int(region.load().point_index(lat, lon))
    sel = (d.station == int(st == "TCS")).values
    sub = prof.isel(point=pt, height=H)
    tix = pd.DatetimeIndex(sub.time.values).get_indexer(tt[sel])
    u, v, T, t2 = (sub[k].values for k in ("u", "v", "T", "t2m"))
    ok = tix >= 0
    r = np.full((sel.sum(), 2), np.nan)
    r[ok, 0] = np.hypot(u[tix[ok]], v[tix[ok]])
    r[ok, 1] = t2[tix[ok]] - T[tix[ok]]
    stab[sel] = r
good = np.isfinite(stab).all(1)
d, stab = d[good].reset_index(drop=True), stab[good]
fit_m, test_m = (d.year <= 2020).values, ((d.year >= 2024) & (d.year <= 2025)).values
X = {"wind": gm.design(d.ws, d.doy, d.hour, station=d.station), "wind+stab": gm.design(d.ws, d.doy, d.hour, station=d.station, stab=stab)}
rng = np.random.default_rng(0)
rows = []
y = d.G.values[test_m]
for k, x in X.items():
    mod = gm.fit(x[fit_m], d.G.values[fit_m])
    s = gm.sample(mod, x[test_m], 199, rng)
    cr = crps_ensemble(s[..., None], y[:, None])[:, 0]
    rows.append(dict(method=k, n=len(y), crps=cr.mean(), mae_median=np.abs(np.median(s, 1) - y).mean(),
                     cov90=coverage90(s[..., None], y[:, None], 0.9).mean(), cov99=coverage90(s[..., None], y[:, None], 0.99).mean()))
t = pd.DataFrame(rows)
print(t.to_string(index=False))
t.to_csv("models/gust_stab_check.csv", index=False)
