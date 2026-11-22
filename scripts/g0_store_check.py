"""G0 int16 tail and below-ground check of the global store (data/raw/era5_global, tempest.ingest.fetch_global).

    python scripts/g0_store_check.py [--store data/raw/era5_global] [--out docs/results/g0_store_check.txt]

Per variable: values at the int16 limits (|q| >= 32760 = saturated or about to be), decoded min / max, and the share of
rows below ground per pressure level (p > sp). Also: every month 1991-01..2025-12 present, no valid time in 2026 or later,
no point inside the locked holdouts. Exit 1 on any saturated value, missing month, 2026 time or holdout point.
"""
import argparse
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tempest.geo import holdout  # noqa: E402
from tempest.geo.masks import below_ground  # noqa: E402

CODE = {"u": (0.01, 0), "v": (0.01, 0), "t": (0.01, 200), "r": (0.01, 0), "z": (10.0, 0),  # = fetch_global.CODE (no dask import)
        "u10": (0.01, 0), "v10": (0.01, 0), "u100": (0.01, 0), "v100": (0.01, 0),
        "t2m": (0.01, 200), "d2m": (0.01, 200), "sp": (2.0, 80000)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/raw/era5_global")
    ap.add_argument("--out", default="docs/results/g0_store_check.txt")
    a = ap.parse_args()
    want = [f"{y}-{m:02d}" for y in range(1991, 2026) for m in range(1, 13)]
    have = sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(a.store, "[0-9]*-[0-9]*.npz")))
    missing = sorted(set(want) - set(have))
    sat = {k: 0 for k in CODE}
    lo = {k: np.inf for k in CODE}
    hi = {k: -np.inf for k in CODE}
    bg, nrows, late, levels = 0, 0, 0, None
    for m in have:
        d = np.load(os.path.join(a.store, m + ".npz"))
        late += int((d["valid_time"] >= np.datetime64("2026-01-01")).sum())
        for k, (s, o) in CODE.items():
            q = d[k]
            sat[k] += int((np.abs(q.astype(np.int32)) >= 32760).sum())
            lo[k], hi[k] = min(lo[k], q.min() * s + o), max(hi[k], q.max() * s + o)
        levels = d["pressure_level"]
        sp = d["sp"] * 2.0 + 80000                                        # (time, point)
        bg = bg + below_ground(levels, sp).sum((0, 1))
        nrows += sp.size
    if not have:
        sys.exit(f"G0 store check {a.store}: no month files")
    p = np.load(os.path.join(a.store, "points.npz"))
    nhold = int(holdout.locked_mask(p["lat"], p["lon"]).sum())
    lines = [f"G0 store check {a.store}: {len(have)} months ({have[0]}..{have[-1]}), {len(missing)} missing, "
             f"{late} valid times >= 2026, {len(p['lat'])} points, {nhold} inside the locked holdouts"]
    lines += [f"  {k:5s} saturated {sat[k]:>8d}  min {lo[k]:10.2f}  max {hi[k]:10.2f}" for k in CODE]
    lines += ["  below ground (p > sp) share per level: " + ", ".join(f"{int(l)} {b / nrows:.3f}" for l, b in zip(levels, bg))]
    bad = missing or late or nhold or any(sat.values())
    lines += [("FAIL" if bad else "OK") + (f" missing {missing[:5]}" if missing else "")]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
