"""Stress test: where does the model fail? Cells of season x ENSO phase x time of day x (variable, height band).

For each cell: n (rows), cov99 (share of truths inside the 99 % range; target 0.99), skill15 (CRPS skill vs the
15-year climatology). Prints the 10 worst cells by coverage distance and the 10 worst by skill (cells with fewer than
`min_n` rows are skipped: a 99 % range needs hundreds of rows to be judged). Read-only diagnostic: writes
<stem>_stress.csv and changes nothing else. Used by score.py --stress.
"""
import numpy as np
import pandas as pd


def labels(cond, names):
    """Feature rows -> season, ENSO phase and time-of-day labels (strings)."""
    c = {k: cond[:, names.index(k)] for k in ("doy_sin", "doy_cos", "hour_sin", "hour_cos", "oni")}
    month = (np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12 + 1
    season = np.select([np.isin(month, (12, 1, 2)), np.isin(month, (3, 4, 5)), np.isin(month, (6, 7, 8))],
                       ["DJF", "MAM", "JJA"], "SON")
    enso = np.select([c["oni"] > 0.5, c["oni"] < -0.5], ["El Nino", "La Nina"], "neutral")
    hour = np.arctan2(c["hour_sin"], c["hour_cos"]) % (2 * np.pi) / (2 * np.pi) * 24
    tod = np.select([hour < 10, hour < 15], ["morning", "midday"], "evening")
    return season, enso, tod


def table(unknown, clim15, truth, cond, names, groups, min_n=200):
    from tempest.scoring.score import coverage90, crps_ensemble
    season, enso, tod = labels(cond, names)
    cov = coverage90(unknown, truth, 0.99)       # (N, D)
    cu, cc = crps_ensemble(unknown, truth), crps_ensemble(clim15, truth)
    rows = []
    for s in np.unique(season):
        for e in np.unique(enso):
            for t in np.unique(tod):
                r = (season == s) & (enso == e) & (tod == t)
                if r.sum() < min_n:
                    continue
                for v, b, sel in groups:
                    rows.append(dict(season=s, enso=e, time=t, var=v, band=b, n=int(r.sum()),
                                     cov99=cov[r][:, sel].mean(),
                                     skill15=1 - cu[r][:, sel].mean() / cc[r][:, sel].mean()))
    return pd.DataFrame(rows)


def write(stem, unknown, clim15, truth, cond, names, groups, min_n=200):
    t = table(unknown, clim15, truth, cond, names, groups, min_n)
    t.to_csv(stem + "_stress.csv", index=False)
    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        print(f"\nSTRESS ({len(t)} cells with >= {min_n} rows): worst 10 by |cov99 - 0.99|")
        print(t.assign(dev=(t.cov99 - 0.99).abs()).nlargest(10, "dev").drop(columns="dev").to_string(index=False))
        print("\nSTRESS worst 10 by skill15 (negative = worse than the 15-year climatology)")
        print(t.nsmallest(10, "skill15").to_string(index=False))
    return t
