"""Index-forecast bake-off (PHASED_PLAN 3.7): how well can ENSO (ONI), warm water volume (WWV) and the QBO be forecast 1-12
months ahead, and is the analog draw (indices.analog, K = 8) that the tool uses the best way to describe that?

    PYTHONPATH=. python scripts/index_bakeoff.py [--first-origin 2012] [--last-origin 2025]

Hindcast: for every origin month t from first to last origin, using only data up to t, forecast the index at t + h for
h = 1..12 months with
  persistence      the latest value, no spread (CRPS = absolute error),
  climatology      mean and sd of that calendar month in earlier years (Gaussian),
  regression       ridge regression of the target on the latest 6 months of ONI, WWV and QBO30/50 and the calendar month,
                   fitted on origins before t - h, Gaussian with the regression's residual sd for that horizon,
  analog (K = 8)   the tool's current draw: past years' months whose recent values resemble the present ones.
Scores: CRPS per horizon (lower is better) with 95 % intervals from a bootstrap over origin years, for each index.
Chronos-2 and CPC/IRI/NMME forecasts from the written plan need an external model download / archive and are not part of
this run (docs/agent/ASK_LATER.md).
"""
import argparse

import numpy as np
import pandas as pd
from scipy.stats import norm

from tempest.ingest import indices

COLS = ["oni", "wwv", "qbo30", "qbo50"]


def crps_gauss(mu, sd, y):
    z = (y - mu) / np.maximum(sd, 1e-6)
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def crps_ens(x, y):
    x = np.sort(x, axis=-1)
    m = x.shape[-1]
    i = np.arange(1, m + 1)
    return 2 / m ** 2 * ((x - y[..., None]) * (m * (y[..., None] < x) - i + 0.5)).sum(-1)


def features(tab, t_idx, lags=6):
    """Regression inputs at origin months t_idx (positions): latest `lags` values of every index and the month harmonics."""
    cols = []
    for c in COLS:
        v = tab[c].to_numpy()
        for L in range(lags):
            cols.append(v[t_idx - L])
    month = tab.index[t_idx].month.to_numpy()
    cols += [np.sin(2 * np.pi * month / 12), np.cos(2 * np.pi * month / 12)]
    return np.stack(cols, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--first-origin", type=int, default=2012)
    ap.add_argument("--last-origin", type=int, default=2025)
    ap.add_argument("--ridge", type=float, default=3.0)
    ap.add_argument("--m", type=int, default=200)
    ap.add_argument("--out", default="models/index_bakeoff.csv")
    a = ap.parse_args()
    tab = indices.load().dropna(subset=COLS).loc["1980-01-01":]
    pos = {t: i for i, t in enumerate(tab.index)}
    rng = np.random.default_rng(0)
    origins = [t for t in tab.index if a.first_origin <= t.year <= a.last_origin]
    rows = []
    for h in range(1, 13):
        xs_all = features(tab, np.arange(6, len(tab) - h))                      # candidate training origins
        for c in COLS:
            org_idx = np.arange(6, len(tab) - h)
            per = {k: [] for k in ("persistence", "climatology", "regression", "analog")}
            keep = []
            for t in origins:
                i = pos[t]
                if i + h >= len(tab):
                    continue
                keep.append(t.year)
                target_t = tab.index[i + h]
                y = tab[c].to_numpy()[i + h]
                # persistence
                per["persistence"].append(abs(tab[c].to_numpy()[i] - y))
                # climatology: same calendar month of the target, earlier years only, years before the origin
                past = tab[(tab.index.month == target_t.month) & (tab.index < t)][c]
                per["climatology"].append(float(crps_gauss(past.mean(), past.std(), y)))
                # regression fitted on origins whose target is already known at t
                train = org_idx + h <= i
                X, y_all_c = xs_all[train], tab[c].to_numpy()[org_idx[train] + h]
                mu_x, sd_x = X.mean(0), X.std(0) + 1e-9
                Z = (X - mu_x) / sd_x
                beta = np.linalg.solve(Z.T @ Z + a.ridge * len(Z) / 100 * np.eye(Z.shape[1]), Z.T @ (y_all_c - y_all_c.mean()))
                resid = (y_all_c - y_all_c.mean()) - Z @ beta
                xt = (features(tab, np.array([i])) - mu_x) / sd_x
                per["regression"].append(float(crps_gauss(y_all_c.mean() + (xt @ beta)[0], resid.std(), y)))
                # analog: the tool's draw, using only history before the origin month's year
                lag = h * 30.4375
                ens = indices.analog(tab, pd.DatetimeIndex([target_t]), lag, a.m, rng, before=t.year)[0, :, indices.COLS.index(c)]
                per["analog"].append(float(crps_ens(ens, np.array(y))))
            yrs = np.array(keep)
            for k, v in per.items():
                v = np.array(v, float)
                if np.isnan(v).all():
                    continue
                boots = [np.nanmean(v[np.isin(yrs, rng.choice(np.unique(yrs), len(np.unique(yrs))))]) for _ in range(300)]
                rows.append(dict(index=c, horizon=h, method=k, crps=np.nanmean(v), lo=np.percentile(boots, 2.5), hi=np.percentile(boots, 97.5)))
    t = pd.DataFrame(rows)
    t.to_csv(a.out, index=False)
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        for c in COLS:
            pv = t[t["index"] == c].pivot(index="horizon", columns="method", values="crps")
            print(f"\n{c}: CRPS by horizon (months)")
            print(pv.loc[[1, 2, 3, 6, 9, 12]].to_string())
        best = t.groupby(["index", "method"]).crps.mean().unstack()
        print("\nmean CRPS over horizons 1-12:")
        print(best.to_string())


if __name__ == "__main__":
    main()
