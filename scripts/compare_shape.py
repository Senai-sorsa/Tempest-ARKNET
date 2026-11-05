"""Shape verdict: compare the shape diagnostics (scripts/diagnose.py output: metric, var, band, value, goal) of a candidate with the baseline's.

    python scripts/compare_shape.py BASE_diag.csv NEW_diag.csv [--noise SEED1_diag.csv SEED2_diag.csv ...] [--rel 0.10]

Per metric (PIT distance, mean coverage error, skew / kurtosis difference, tail-rate error, event-coverage gap (absolute), vertical-correlation error, shear
KS) the table gives the mean over cells of the baseline and the candidate, and the worst single cell. A metric is WORSE when the candidate's mean exceeds the
baseline's by more than the tolerance: `--rel` (default 10 %), or, when other seeds of the BASELINE are given with --noise, the largest spread between the
baseline and those seeds on that metric (a change smaller than seed-to-seed variation is not a change). Exit code 1 if any metric is WORSE.
This is the shape half of the verdict rule (AUTOPILOT.md rule 4): a candidate that wins on skill but makes the shape worse does not pass."""
import argparse
import sys

import numpy as np
import pandas as pd

METRICS = ["preclip_rate", "pit_tv", "cov_err_mean", "skew_diff", "kurt_diff", "tail_rate_err", "event_cov_gap", "vcorr_err", "shear_ks"]


def means(path):
    d = pd.read_csv(path)
    d = d[d.metric.isin(METRICS)].copy()
    d["value"] = d.value.abs()
    return d.groupby("metric").value.mean(), d.set_index(["metric", "var", "band"]).value


def compare(base, new, noise=(), rel=0.10):
    bm, bc = means(base)
    nm, nc = means(new)
    tol = {m: rel * bm[m] for m in bm.index}
    if noise:                                                                   # seed spread replaces the relative tolerance, floored at 2 % of the baseline so a lucky tie is not zero
        spread = {m: 0.0 for m in bm.index}
        for f in noise:
            sm, _ = means(f)
            for m in bm.index:
                if m in sm.index:
                    spread[m] = max(spread[m], abs(sm[m] - bm[m]))
        tol = {m: max(spread[m], 0.02 * bm[m]) for m in bm.index}
    rows = []
    for m in bm.index:
        if m not in nm.index:
            continue
        both = bc[m].index.intersection(nc[m].index)
        diff = (nc[m][both] - bc[m][both])
        worst = diff.idxmax() if len(diff) else None
        rows.append(dict(metric=m, base=bm[m], new=nm[m], delta=nm[m] - bm[m], tolerance=tol[m], flag="WORSE" if nm[m] - bm[m] > tol[m] else ("better" if bm[m] - nm[m] > tol[m] else ""),
                         worst_cell="/".join(worst) + f" (+{diff.max():.4f})" if worst is not None else ""))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--noise", nargs="*", default=[], help="diag CSVs of other seeds of the baseline")
    ap.add_argument("--rel", type=float, default=0.10)
    a = ap.parse_args()
    t = compare(a.base, a.new, a.noise, a.rel)
    with pd.option_context("display.width", 200, "display.max_colwidth", 50):
        print(t.round(4).to_string(index=False))
    bad = (t.flag == "WORSE").any()
    print("SHAPE RESULT:", "FAIL (a shape metric got worse: " + ", ".join(t.metric[t.flag == "WORSE"]) + ")" if bad else "PASS (no shape metric worse" + (", " + str((t.flag == "better").sum()) + " better)" if (t.flag == "better").any() else ")"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
