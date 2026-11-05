"""Gust check (PHASED_PLAN 3.1): fit the gust model on 2000-2020 airport reports, choose settings on 2021-23, score on the
development years 2024-25 against two baselines.

    PYTHONPATH=. python scripts/gust_check.py [--asos data/raw/asos] [--surface data/pilot/surface_hourly.zarr]

Truth: the larger of the reported gust and the sustained wind at Midland (MAF) and Truth or Consequences (TCS, ~30 km
from Spaceport America), hourly routine reports. Inputs come from ERA5 at the nearest grid point (10 m wind, and its
own gust field fg10 for the "wind+fg" variant). Baselines: (1) a constant gust factor c * wind (c fitted on 2000-2020),
(2) bias-corrected ERA5 gust a + b * fg10. Both are single values, so their CRPS equals their MAE. Reports CRPS, MAE of the
median and 90/99 % coverage with day-block 95 % intervals.
"""
import argparse
import os

import numpy as np
import pandas as pd
import xarray as xr

from tempest.gust import model as gm
from tempest.scoring.score import coverage90, crps_ensemble

SITES = {"MAF": (31.9425, -102.2019), "TCS": (33.2369, -107.2672)}


def load(asos, surf):
    rows = []
    for st, (lat, lon) in SITES.items():
        d = pd.concat([pd.read_csv(os.path.join(asos, st, f), na_values=["", "M"]) for f in sorted(os.listdir(os.path.join(asos, st))) if f.endswith(".csv")])
        d["valid"] = pd.to_datetime(d["valid"], utc=True).dt.tz_localize(None)
        d = d[(d.valid.dt.minute >= 40) & d.sknt.notna()].copy()  # hourly routine reports (about :53)
        d["time"] = d.valid.dt.round("h")
        d = d.drop_duplicates("time")
        point = int(np.round((34 - lat) / 0.25)) * 29 + int(np.round((lon + 108) / 0.25))
        t = pd.DatetimeIndex(surf.time.values)
        ix = t.get_indexer(d["time"])
        ok = ix >= 0
        d, ix = d[ok], ix[ok]
        u, v, fg = (surf[k].isel(point=point).values[ix] for k in ("u10", "v10", "fg10"))
        out = pd.DataFrame(dict(time=d["time"].values, station=int(st == "TCS"), ws_obs=d.sknt.values * gm.KT,
                                gust_obs=d.gust.values * gm.KT, ws=np.hypot(u, v), fg=fg))
        rows.append(out)
    t = pd.concat(rows, ignore_index=True)
    tt = pd.DatetimeIndex(t.time)
    t["doy"], t["hour"], t["year"] = tt.dayofyear, tt.hour + tt.minute / 60, tt.year
    t["reported"] = t.gust_obs.notna()
    t["G"] = np.fmax(t.gust_obs.fillna(0), t.ws_obs)
    return t[np.isfinite(t.ws) & np.isfinite(t.fg)].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--asos", default="data/raw/asos")
    ap.add_argument("--surface", default="data/pilot/surface_hourly.zarr")
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="models/gust_check.csv")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    surf = xr.open_zarr(a.surface)[["u10", "v10", "fg10"]].load()
    d = load(a.asos, surf)
    fit_m, val_m, test_m = d.year <= 2020, (d.year >= 2021) & (d.year <= 2023), (d.year >= 2024) & (d.year <= 2025)
    print({k: int(v.sum()) for k, v in (("fit", fit_m), ("validation", val_m), ("test", test_m))}, "reports; share with a reported gust:",
          f"{d.reported[fit_m].mean():.2f}")
    # the wind input is the ERA5 10 m wind here (in the tool: the generator's 10 m wind sample)
    X = {"wind": gm.design(d.ws, d.doy, d.hour, station=d.station), "wind+fg": gm.design(d.ws, d.doy, d.hour, fg=d.fg, station=d.station)}
    models = {k: gm.fit(x[fit_m], d.G[fit_m].values) for k, x in X.items()}
    np.savez("models/gust_model.npz", **{f"{k}_{p_}": v_ for k, m_ in models.items() for p_, v_ in m_.items()}, fit_years="2000-2020")
    c = float(np.mean((d.G / np.maximum(d.ws, 0.5))[fit_m]))
    b1, b0 = np.polyfit(d.fg[fit_m], d.G[fit_m], 1)
    print(f"baselines: constant factor c = {c:.2f}; bias-corrected fg10: G = {b0:.2f} + {b1:.2f} fg10")
    day = d.year.astype(np.int64) * 1000 + pd.DatetimeIndex(d.time).dayofyear
    results = []
    for split, mask in (("validation 2021-23", val_m), ("test 2024-25", test_m)):
        dd = d[mask].reset_index(drop=True)
        _, inv = np.unique(day[mask], return_inverse=True)
        nd = inv.max() + 1
        boot = np.vstack([np.ones(nd), np.random.default_rng(0).multinomial(nd, np.full(nd, 1 / nd), 500)])
        cnt = np.bincount(inv, minlength=nd)

        def stat(v):
            m = (boot @ np.bincount(inv, np.asarray(v, float), nd)) / (boot @ cnt)
            return f"{m[0]:.3f} [{np.percentile(m[1:], 2.5):.3f}, {np.percentile(m[1:], 97.5):.3f}]"
        y = dd.G.values
        cands = {}
        for k, mod in models.items():
            cands[k] = gm.sample(mod, X[k][mask], a.m, rng)
        cands["constant factor"] = np.repeat((c * dd.ws.values)[:, None], 2, 1)
        cands["bias-corrected fg10"] = np.repeat((b0 + b1 * dd.fg.values)[:, None], 2, 1)
        for name, x in cands.items():
            ens = x[..., None]
            cr = crps_ensemble(ens, y[:, None])[:, 0]
            row = dict(split=split, method=name, crps=stat(cr), mae_median=stat(np.abs(np.median(x, 1) - y)))
            if x.shape[1] > 2:
                row["cov90"], row["cov99"] = stat(coverage90(ens, y[:, None], 0.9)[:, 0]), stat(coverage90(ens, y[:, None], 0.99)[:, 0])
            results.append(row)
    t = pd.DataFrame(results)
    with pd.option_context("display.width", 220, "display.max_colwidth", 40):
        print(t.fillna("").to_string(index=False))
    t.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
