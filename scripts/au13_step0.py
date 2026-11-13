"""AU-13 step 0 (New_Plan 15.3): station map A (1991-2020, the shipped recipe) refitted with and without the launch-height filter
(read_igra launch_height, tol 30 m: drops the Santa Teresa soundings launched at the old El Paso site). Compares a, b and the pool sizes;
a table entry 'moves' when |change| exceeds 2 bootstrap sd (40 resamples of the filtered station's soundings). Rule: adopt the filter for
new fits; retrain nothing unless an entry moves. Writes models/au13_step0.csv.
Usage: PYTHONPATH=. python scripts/au13_step0.py [--profiles data/pilot/profiles.zarr] [--igra data/raw/igra]"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station as S

ap = argparse.ArgumentParser()
ap.add_argument("--profiles", default="data/pilot/profiles.zarr")
ap.add_argument("--igra", default="data/raw/igra")
ap.add_argument("--tol", type=float, default=30.0)
ap.add_argument("--boot", type=int, default=40)
a = ap.parse_args()
ds = xr.open_zarr(a.profiles)
G = len(S.STATIONS) * 8


def stack(pairs, sel=None):
    groups = [S.group_id(s, t.month, (t.hour == 12).astype(int)) for s, (t, *_) in enumerate(pairs)]
    keep = [t.year <= 2020 for t, *_ in pairs]
    cat = lambda j: np.concatenate([p[j][m] for p, m in zip(pairs, keep)])
    return cat(1), cat(2), np.concatenate([g[m] for g, m in zip(groups, keep)])


E0, O0, g0 = stack(S.station_pairs(ds, a.igra, 1991, 2020))
E1, O1, g1 = stack(S.station_pairs(ds, a.igra, 1991, 2020, launch_tol=a.tol))
print(f"pairs 1991-2020: plain {len(g0):,}, filtered {len(g1):,} ({len(g0) - len(g1):,} dropped)", flush=True)
t0, t1 = S.fit(E0, O0, g0, G), S.fit(E1, O1, g1, G)
changed = sorted(set(np.flatnonzero([(g0 == g).sum() != (g1 == g).sum() for g in range(G)])))
rng = np.random.default_rng(0)
rows = []
for g in changed:
    m = g1 == g
    Eg, Og = E1[m], O1[m]
    boots = [S.fit(Eg[i], Og[i], np.full(len(i), g), G, pool_max=1) for i in (rng.integers(0, len(Eg), len(Eg)) for _ in range(a.boot))]
    for k in ("a", "b"):
        sd = np.std([bt[k][g] for bt in boots], 0)
        d = np.abs(t1[k][g] - t0[k][g])
        for i, v in enumerate(S.PROFILE):
            r = d[i] / np.maximum(sd[i], 1e-9)
            rows.append(dict(group=g, var=v, coef=k, n_plain=int((g0 == g).sum()), n_filt=int(m.sum()), max_change=float(d[i].max()),
                             max_ratio=float(r.max()), n_over_2sd=int((r > 2).sum()), pool_plain=t0["n"][g].tolist(), pool_filt=t1["n"][g].tolist()))
df = pd.DataFrame(rows)
df.to_csv("models/au13_step0.csv", index=False)
with pd.option_context("display.width", 220, "display.max_rows", 200, "display.float_format", "{:.3f}".format):
    print(df.to_string(index=False))
moved = int(df.n_over_2sd.sum())
print(f"groups touched {changed}; entries over 2 bootstrap sd: {moved} of {len(df) * len(S.HEIGHTS)} -> {'RETRAIN CANDIDATE' if moved else 'no retrain'}")
