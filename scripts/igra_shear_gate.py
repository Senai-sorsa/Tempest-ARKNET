"""L3 / IL-112: how tight can a '99th-percentile shear within X % of IGRA' gate honestly be?

For each IGRA station in data/igra_heights (scale 0.1 m/s, missing -32768) compute the p99 of layer shear (|dV|/dz, m/s per km) in two bands (0-1 km, 1-5 km), for the odd years and the even years of 2000-2025
separately. Even/odd ratio of the SAME atmosphere = pure sampling scatter of the p99 statistic (what a model could not be expected to beat). The gate must be wider than the spread of that ratio.
Also: a year-block bootstrap of the p99 per station. Output: percentiles of |ratio - 1| across stations that have enough data, and the share of stations that would pass at 10 / 12 / 15 / 20 %.

    .venv/Scripts/python scripts/igra_shear_gate.py [--min-n 3000]
"""
import argparse
import glob
import os

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANDS = {"0-1 km": (0.0, 1000.0), "1-5 km": (1000.0, 5000.0)}


def station_shear(path):
    d = np.load(path)
    t = d["time"].astype("datetime64[Y]").astype(int) + 1970
    ok = (t >= 2000) & (t <= 2025)
    h = d["heights"].astype(float)
    u, v = d["u"][ok].astype(float), d["v"][ok].astype(float)
    bad = (d["u"][ok] == -32768) | (d["v"][ok] == -32768)
    u[bad] = np.nan
    v[bad] = np.nan
    u *= 0.1
    v *= 0.1
    dz = np.diff(h) / 1000.0
    sh = np.hypot(np.diff(u, axis=1), np.diff(v, axis=1)) / dz                 # m/s per km, (time, layer)
    mid = 0.5 * (h[1:] + h[:-1])
    return t[ok], mid, sh


def p99(x):
    x = x[np.isfinite(x)]
    return (np.percentile(x, 99), x.size) if x.size else (np.nan, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=3000, help="minimum shear values per half and band")
    a = ap.parse_args()
    rows = {b: [] for b in BANDS}
    for f in sorted(glob.glob(os.path.join(REPO, "data", "igra_heights", "*.npz"))):
        try:
            yr, mid, sh = station_shear(f)
        except Exception as e:        # noqa: BLE001
            print("skip", os.path.basename(f), e)
            continue
        for b, (lo, hi) in BANDS.items():
            sel = (mid > lo) & (mid <= hi)
            odd, even = sh[(yr % 2 == 1)][:, sel], sh[(yr % 2 == 0)][:, sel]
            (po, no), (pe, ne) = p99(odd), p99(even)
            if min(no, ne) >= a.min_n:
                rows[b].append((os.path.basename(f)[:11], po / pe, min(no, ne)))
    for b, r in rows.items():
        x = np.array([q[1] for q in r])
        dev = np.abs(np.log(x))                                                   # log ratio is symmetric
        print(f"\n{b}: {len(x)} stations with >= {a.min_n} values per half")
        print("  odd/even p99 ratio percentiles 2.5 / 16 / 50 / 84 / 97.5:", np.round(np.percentile(x, [2.5, 16, 50, 84, 97.5]), 3))
        print("  |ratio - 1| percentiles 50 / 68 / 90 / 95:", np.round(np.expm1(np.percentile(dev, [50, 68, 90, 95])), 3))
        for g in (0.10, 0.12, 0.15, 0.20):
            print(f"  share of stations whose own two halves agree within {int(g * 100)} %: {np.mean(np.abs(x - 1) <= g):.2f}")
        big = np.array([q[2] for q in r]) >= 20000
        if big.sum() > 10:
            print(f"  stations with >= 20000 values per half ({big.sum()}): 95th percentile |ratio - 1| = {np.expm1(np.percentile(dev[big], 95)):.3f}")


if __name__ == "__main__":
    main()
