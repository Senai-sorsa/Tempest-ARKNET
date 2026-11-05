"""Chronos-2 in the index-forecast bake-off (PHASED_PLAN 3.7, improvement loop): same hindcast, scores and bootstrap as scripts/index_bakeoff.py,
with two extra methods: chronos (the index alone) and chronos_cov (the other three indices as past covariates).

    CHRONOS_LIB=<dir with chronos-forecasting and its dependencies> PYTHONPATH=. python scripts/chronos_bakeoff.py [--first-origin 2012] [--last-origin 2025]

Weights: data/chronos2/{config.json,model.safetensors} (amazon/chronos-2). Runs on the CPU by default (small series). The 21 predicted quantiles are turned into a
200-member sample through the inverse CDF so the CRPS is computed exactly as for the other methods. Reads the existing bake-off table models/index_bakeoff.csv
for the other methods and writes models/index_bakeoff_chronos.csv.
"""
import argparse
import os
import sys

if os.environ.get("CHRONOS_LIB"):
    sys.path.append(os.environ["CHRONOS_LIB"])

import numpy as np
import pandas as pd

from tempest.ingest import indices

COLS = ["oni", "wwv", "qbo30", "qbo50"]
Q = [0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99]


def crps_ens(x, y):
    x = np.sort(x, axis=-1)
    m = x.shape[-1]
    i = np.arange(1, m + 1)
    return 2 / m ** 2 * ((x - y[..., None]) * (m * (y[..., None] < x) - i + 0.5)).sum(-1)


def sample_from_quantiles(qv, m=200):
    """qv (21,) sorted -> m-member sample by inverse-CDF interpolation (tails held at the 1 % / 99 % values)."""
    qv = np.maximum.accumulate(qv)
    return np.interp((np.arange(m) + 0.5) / m, Q, qv)


def main():
    from chronos import Chronos2Pipeline
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--first-origin", type=int, default=2012)
    ap.add_argument("--last-origin", type=int, default=2025)
    ap.add_argument("--weights", default="data/chronos2")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="models/index_bakeoff_chronos.csv")
    a = ap.parse_args()
    pipe = Chronos2Pipeline.from_pretrained(a.weights, device_map=a.device)
    tab = indices.load().dropna(subset=COLS).loc["1980-01-01":]
    origins = [t for t in tab.index if a.first_origin <= t.year <= a.last_origin and t + pd.DateOffset(months=1) <= tab.index[-1]]
    rng = np.random.default_rng(0)
    res = {}
    for variant, cov in (("chronos", False), ("chronos_cov", True)):
        preds = {}
        for t in origins:
            ctx = tab.loc[:t, COLS].reset_index()
            ctx.columns = ["timestamp"] + COLS
            ctx["id"] = "x"
            for c in COLS:
                tgt = [c]
                cols = ["id", "timestamp"] + (COLS if cov else tgt)
                p = pipe.predict_df(ctx[cols], prediction_length=12, quantile_levels=Q, id_column="id", timestamp_column="timestamp", target=tgt)
                preds[(t, c)] = p
            print(variant, t.strftime("%Y-%m"), flush=True)
        res[variant] = preds
    rows = []
    for variant, preds in res.items():
        for c in COLS:
            for h in range(1, 13):
                v, yrs = [], []
                for t in origins:
                    i = tab.index.get_loc(t)
                    if i + h >= len(tab):
                        continue
                    p = preds[(t, c)].sort_values("timestamp").iloc[h - 1]
                    qv = np.array([p[str(q)] if str(q) in p else p[q] for q in Q], float)
                    v.append(float(crps_ens(sample_from_quantiles(qv), np.array(tab[c].to_numpy()[i + h]))))
                    yrs.append(t.year)
                v, yrs = np.array(v), np.array(yrs)
                u = np.unique(yrs)
                boots = [v[np.isin(yrs, rng.choice(u, len(u)))].mean() for _ in range(300)]
                rows.append(dict(index=c, horizon=h, method=variant, crps=v.mean(), lo=np.percentile(boots, 2.5), hi=np.percentile(boots, 97.5)))
    t = pd.DataFrame(rows)
    t.to_csv(a.out, index=False)
    base = pd.read_csv("models/index_bakeoff.csv")
    allt = pd.concat([base, t])
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        for c in COLS:
            pv = allt[allt["index"] == c].pivot(index="horizon", columns="method", values="crps")
            print(f"\n{c}: CRPS by horizon (months)\n" + pv.loc[[1, 2, 3, 6, 9, 12]].to_string())
        print("\nmean CRPS over horizons 1-12:\n" + allt.groupby(["index", "method"]).crps.mean().unstack().to_string())


if __name__ == "__main__":
    main()
