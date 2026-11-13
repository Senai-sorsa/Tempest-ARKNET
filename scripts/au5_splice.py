"""AU-5 step 0: replace the test years of a training file with freshly built rows.

    python scripts/au5_splice.py OUT BASE.npz NEW.npz [--from-year 2024]

OUT = rows of BASE before --from-year (the training years the scorer's baselines draw on) + every row of NEW (all from
--from-year on). Columns and humidity target must match. Peak RAM about twice BASE's target array.
"""
import argparse

import numpy as np

META = ("cond_names", "target_names", "rh_target")


def splice(base, new, from_year):
    """Dicts with cond, target, year (+ META) -> BASE's rows before from_year in their own order, then NEW's rows.

    BASE is laid out in date blocks that start on 30 Dec, so it is not sorted by year; the scorer picks years by mask."""
    assert all(np.array_equal(base[k], new[k]) for k in META), "columns differ"
    assert (new["year"] >= from_year).all(), "NEW holds rows before --from-year"
    keep = np.flatnonzero(base["year"] < from_year)
    out = {}
    for k in ("cond", "target", "year"):   # one preallocated array per column: peak RAM is BASE + OUT, no temporary copy
        out[k] = np.empty((len(keep) + len(new[k]),) + base[k].shape[1:], base[k].dtype)
        np.take(base[k], keep, axis=0, out=out[k][:len(keep)])
        out[k][len(keep):] = new[k]
    return out | {k: base[k] for k in META}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--from-year", type=int, default=2024)
    a = ap.parse_args()
    with np.load(a.base) as b, np.load(a.new) as n:
        new = {k: n[k] for k in ("cond", "target", "year") + META}
        base = {k: b[k] for k in ("cond", "target", "year") + META}
    out = splice(base, new, a.from_year)
    del base
    with open(a.out, "wb") as fh:
        np.savez(fh, **out)
    print(f"wrote {a.out}: {len(out['year']):,} rows ({len(new['year']):,} from {a.new})", flush=True)


if __name__ == "__main__":
    main()
