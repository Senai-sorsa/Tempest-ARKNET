"""AU-11 step 0 (New_Plan 15.3): how often does the batch width floor of the range map bind in the scorer?
spread._standardise floors each row's 5-95 % half-width at 0.1 x the median half-width over the rows of the batch. The scorer
applies the map to all test rows at once, the tool to one block (N = 1, where the floor is 0.1 x its own width and never binds).
This wraps spread._standardise to count, per output column, the cells (row x column) where the floor binds, then runs the
scorer unchanged (sys.argv after '--' go to tempest.scoring.score). Rule: share below 0.1 % in every column outside RH -> close.
Usage: PYTHONPATH=. python scripts/au11_step0.py --out models/au11_step0.csv -- --model ... (score.py flags)"""
import runpy
import sys

import numpy as np
import pandas as pd

from tempest.calibrate import spread

i = sys.argv.index("--")
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv[:i] else "models/au11_step0.csv"
sys.argv = ["tempest.scoring.score"] + sys.argv[i + 1:]
counts = {"calls": 0, "rows": 0, "bind": None}
_orig = spread._standardise


def counted(x):
    lo, hi = np.quantile(x, [0.05, 0.95], axis=1)
    hw = (hi - lo) / 2                                                    # (N, D), as in _standardise
    b = (hw < 0.1 * np.median(hw, axis=0, keepdims=True) + 1e-6).sum(0)   # the floor replaces the row's own width
    counts["bind"] = b if counts["bind"] is None else counts["bind"] + b
    counts["calls"] += 1
    counts["rows"] += x.shape[0]
    return _orig(x)


spread._standardise = counted


def report():
    from tempest.generator.build_dataset import target_names
    b, n = counts["bind"], counts["rows"]
    names = target_names()
    names = names if len(names) == len(b) else [f"c{j}" for j in range(len(b))]
    df = pd.DataFrame(dict(column=names, bind=b, cells=n, share=b / max(n, 1)))
    df.to_csv(out, index=False)
    rh = df.column.str.lower().str.startswith(("rh", "dpd"))
    print(f"[AU11] {counts['calls']} apply calls, {n:,} rows; worst share outside RH {df.share[~rh].max():.5f} "
          f"({df.column[~rh][df.share[~rh].idxmax()]}), RH {df.share[rh].max() if rh.any() else float('nan'):.5f}; "
          f"columns over 0.1 %: {int((df.share > 0.001).sum())} ({int((df.share[~rh] > 0.001).sum())} outside RH) -> "
          f"{'close' if (df.share[~rh] <= 0.001).all() else 'store hw_floor'}", flush=True)


assert spread.apply.__globals__["_standardise"] is counted  # apply looks the floor function up in the module, so the wrap is seen
try:
    runpy.run_module("tempest.scoring.score", run_name="__main__")
finally:
    if counts["bind"] is not None:
        report()
