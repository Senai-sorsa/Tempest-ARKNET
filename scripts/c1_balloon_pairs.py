"""C1 check against balloons: the correlation between the 00Z and the 12Z sounding of the same day (12 hours apart, anomalies against the station's month x hour climatology of 2005-2022, 2005-2025
pairs) against the 12-hour ERA5 lag correlation in the table, per variable and height group.
    PYTHONPATH=. python scripts/c1_balloon_pairs.py"""
import numpy as np
import pandas as pd

from tempest.calibrate import station
from tempest.profiles.to_heights import HEIGHTS, PROFILE

rho = np.load("models/coherence_lagcorr.npz")["rho"]            # (4, 13, 176)
nh = len(HEIGHTS)
groups = {"0-1 km": (HEIGHTS <= 1000), "1-5 km": (HEIGHTS > 1000) & (HEIGHTS <= 5000), "5-12 km": (HEIGHTS > 5000) & (HEIGHTS <= 12000), "12-18 km": HEIGHTS > 12000}
rows = []
for sid in station.STATIONS:
    t, prof, _ = station.read_igra(f"data/raw/igra_2026/{sid}-drvd.txt.zip", 2005, 2025)
    ok = np.isfinite(prof).all((1, 2))
    t, prof = t[ok], prof[ok]
    h, month, day = t.hour, t.month, t.normalize()
    train = t.year <= 2022
    z = np.full_like(prof, np.nan)
    for hh in (0, 12):
        for m in range(1, 13):
            sel = (h == hh) & (month == m)
            fit = sel & train
            if fit.sum() > 20:
                z[sel] = (prof[sel] - prof[fit].mean(0)) / (prof[fit].std(0) + 1e-6)
    d0 = pd.Series(np.arange(len(t))[h == 0], index=day[h == 0])
    d12 = pd.Series(np.arange(len(t))[h == 12], index=day[h == 12])
    common = d0.index.intersection(d12.index)
    common = common[~common.duplicated()] if hasattr(common, "duplicated") else common
    i0, i12 = d0.loc[common].to_numpy(), d12.loc[common].to_numpy()
    season = ((month[i0] % 12) // 3)
    for s in range(4):
        m = season == s
        for v, name in enumerate(PROFILE):
            for g, sel in groups.items():
                a, b = z[i0[m]][:, v][:, sel].ravel(), z[i12[m]][:, v][:, sel].ravel()
                ok2 = np.isfinite(a) & np.isfinite(b)
                rows.append(dict(station=sid, season=s, var=name, band=g, balloon=np.corrcoef(a[ok2], b[ok2])[0, 1], era5_table=rho[s, 12, v * nh:(v + 1) * nh][sel].mean(), n=int(m.sum())))
t = pd.DataFrame(rows)
g = t.groupby(["var", "band"])[["balloon", "era5_table"]].mean()
g["diff"] = g.balloon - g.era5_table
with pd.option_context("display.width", 200):
    print(g.round(3).to_string())
print(f"mean |balloon - table| over var x band: {g['diff'].abs().mean():.3f}, worst {g['diff'].abs().max():.3f}")

# the nugget: kappa per variable x height band = balloon 12 h correlation / ERA5 12 h correlation (mean over stations and seasons), stored for every column and applied by tempest_weather.coherence
kappa = np.ones(4 * nh)
for (v, g), r in g.iterrows() if False else []:
    pass
tab = g.reset_index()
for _, r in tab.iterrows():
    v = list(PROFILE).index(r["var"])
    kappa[v * nh:(v + 1) * nh][groups[r["band"]]] = float(np.clip(r["balloon"] / r["era5_table"], 0.5, 1.0))
z0 = dict(np.load("models/coherence_lagcorr.npz"))
z0["kappa"] = kappa.astype(np.float32)
np.savez("models/coherence_lagcorr.npz", **z0)
print("kappa range", kappa.min().round(3), kappa.max().round(3), "mean", kappa.mean().round(3), "written to models/coherence_lagcorr.npz")
