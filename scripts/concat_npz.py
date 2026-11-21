"""Join training files (e.g. the day and night builds of the all-hours test) into one, sorted by year.

    python scripts/concat_npz.py OUT A.npz B.npz [--frac 0.667] [--seed 0] [--group]

--group (G2) writes row_group = the input's position (0, 1, ...) per row, for train.py balance_groups / --exclude-group.

--frac keeps a random share of every input's rows (the same density for each). Rows are sorted by year (stable), so
train.py's --min-year/--max-year stay a contiguous slice. Columns and humidity target must match exactly.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tempest.generator.train import _load  # memory maps; also reads overlay files (base_npz + wider cond)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--frac", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--group", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    meta, picks, years = None, [], []
    for p in a.inputs:  # pass 1: headers, years and the row choice only (small)
        d = _load(p)
        m = {k: np.asarray(d[k]) for k in ("cond_names", "target_names", "rh_target")}
        assert meta is None or all(np.array_equal(meta[k], m[k]) for k in m), f"{p}: columns differ"
        meta = m
        y = np.asarray(d["year"])
        keep = np.flatnonzero(rng.random(len(y)) < a.frac)
        picks.append(keep)
        years.append(y[keep])
    year = np.concatenate(years)
    order = np.argsort(year, kind="stable")
    pos = np.empty_like(order)
    pos[order] = np.arange(len(order))
    out = {}
    s = 0
    for p, keep in zip(a.inputs, picks):  # pass 2: one input in RAM at a time, written straight to its sorted rows
        d = _load(p)
        for k in ("cond", "target"):
            x = d[k]
            if k not in out:
                out[k] = np.empty((len(order), x.shape[1]), x.dtype)
            out[k][pos[s:s + len(keep)]] = x[keep]
            del x
        s += len(keep)
    out["year"] = year[order]
    if a.group:
        out["row_group"] = np.repeat(np.arange(len(picks), dtype=np.int16), [len(k) for k in picks])[order]
    assert np.all(np.diff(out["year"]) >= 0)
    with open(a.out, "wb") as fh:
        np.savez(fh, **out, **meta)
    print(f"wrote {a.out}: {len(order):,} rows from {len(a.inputs)} files (frac {a.frac})", flush=True)


if __name__ == "__main__":
    main()
