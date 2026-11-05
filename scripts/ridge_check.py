"""Offline choice of the ridge strength for the balloon correction (PHASED_PLAN 2.7). No model involved.

    PYTHONPATH=. python scripts/ridge_check.py [--profiles data/pilot/profiles80.zarr] [--lams 0 1 10 100 1000]

Fit the station map on 1991-2020 for each lambda; score the corrected ERA5 against the balloons of 2021-22 (selection)
and 2023-25 (confirmation), with station.check: distance of the corrected values and height steps to the balloons'
distribution (lower is better) and the 99th-percentile shear ratio (1 = balloon-like). Lambda is chosen on 2021-22 only.
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--lams", type=float, nargs="+", default=[0, 1, 10, 100, 1000])
    ap.add_argument("--out", default="data/ridge_check.csv")
    a = ap.parse_args()
    ds = xr.open_zarr(a.profiles)
    pairs = station.station_pairs(ds, a.igra, 1991, 2025)
    groups = [station.group_id(s, t.month, (t.hour == 12).astype(int)) for s, (t, *_) in enumerate(pairs)]
    cat = lambda j, sel: np.concatenate([p[j][m] for p, m in zip(pairs, sel)])
    gcat = lambda sel: np.concatenate([g[m] for g, m in zip(groups, sel)])
    fit_rows = [t.year <= 2020 for t, *_ in pairs]
    periods = {"2021-22": [(t.year >= 2021) & (t.year <= 2022) for t, *_ in pairs],
               "2023-25": [t.year >= 2023 for t, *_ in pairs]}
    rows = []
    for lam in a.lams:
        tab = station.fit(cat(1, fit_rows), cat(2, fit_rows), gcat(fit_rows), len(station.STATIONS) * 8, ridge=lam)
        for name, sel in periods.items():
            era, obs = cat(1, sel), cat(2, sel)
            rep = station.check(era, obs, station.apply(tab, era, gcat(sel), np.random.default_rng(1)))
            for _, r in rep.iterrows():
                rows.append(dict(lam=lam, period=name, var=r["var"], level_gap=r.level_gap_corrected,
                                 step_gap=r.step_gap_corrected, shear99=r.shear99_corrected, spread=r.spread_corrected))
    t = pd.DataFrame(rows)
    t.to_csv(a.out, index=False)
    s = t.groupby(["period", "lam"])[["level_gap", "step_gap"]].mean()
    s["shear99_dev"] = t.assign(d=(t.shear99 - 1).abs()).groupby(["period", "lam"]).d.mean()
    with pd.option_context("display.width", 160, "display.float_format", "{:.4f}".format):
        print(s.to_string())
        print("\nper variable, 2021-22:")
        print(t[t.period == "2021-22"].pivot(index="lam", columns="var", values="step_gap").to_string())
    sel = s.loc["2021-22"]
    best = (sel.level_gap / sel.level_gap.iloc[0] + sel.step_gap / sel.step_gap.iloc[0]).idxmin()
    print(f"\nchosen on 2021-22: lambda = {best}")


if __name__ == "__main__":
    main()
