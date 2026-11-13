"""AU-5 step 0: replace the test years of a training file with freshly built rows.

    python scripts/au5_splice.py OUT BASE.npz NEW.npz [--from-year 2024]

OUT = rows of BASE before --from-year (the training years the scorer's baselines draw on) + every row of NEW (all from
--from-year on). Columns and humidity target must match. Peak RAM about twice BASE's target array.
"""
import argparse

import numpy as np

META = ("cond_names", "target_names", "rh_target")


def splice(base, new, from_year):
    """Dicts with cond, target, year (+ META) -> the joined dict, sorted by year as BASE was."""
    assert all(np.array_equal(base[k], new[k]) for k in META), "columns differ"
    assert (new["year"] >= from_year).all(), "NEW holds rows before --from-year"
    nk = int((base["year"] < from_year).sum())
    assert (base["year"][:nk] < from_year).all(), "BASE is not sorted by year"
    out = {k: np.concatenate([base[k][:nk], new[k]]) for k in ("cond", "target", "year")}   # a prefix view: no extra copy of BASE
    assert np.all(np.diff(out["year"]) >= 0)
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
