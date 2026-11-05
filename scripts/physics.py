"""Physics check (PLAN "A3"): wind shear and lapse rate between neighbouring heights, samples vs truth
(station-corrected targets), for the development years. Raw samples (no range calibration) and calibrated ones.

    PYTHONPATH=. python scripts/physics.py MODEL.pt CALIB.npz DATA.npz [--rows 4000] [--seed 0] [--first-year 2024]
                                           [--out table.csv]

Reproduces the A3 table in docs/PLAN.md for E12 (m = 199, 4000 rows, seed 0). Shear is in m/s per km, lapse in K/km.
Needs the GPU only for speed; pass --device cpu to run without it.
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS

BANDS = [("0-1 km", lambda h: h <= 1000), ("1-5 km", lambda h: (h > 1000) & (h <= 5000)),
         ("5-12 km", lambda h: (h > 5000) & (h <= 12000)), (">12 km", lambda h: h > 12000)]


def table(model, calib, data, rows=4000, seed=0, first_year=2024, m=199, device=None, apply_extra=None):
    """-> DataFrame with one row per band x set (truth/raw/calibrated): shear p50/p99/p99.9, superadiabatic and
    inversion shares. apply_extra(x) is an optional further post-processing step (for example the trust layer)."""
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    s = Sampler(torch.load(model, map_location="cpu", weights_only=True), device=device)
    cal = spread.load(calib, model)
    d = load_npz(data)
    idx = np.sort(rng.choice(np.flatnonzero(d["year"] >= first_year), rows, replace=False))
    n = len(HEIGHTS)
    truth = to_physical(d["target"][idx])
    raw = s.profiles(np.repeat(d["cond"][idx], m, axis=0)).reshape(len(idx), m, -1)
    sets = {"truth": truth[:, None], "raw": raw, "calibrated": spread.apply(cal, raw)}
    if apply_extra is not None:
        sets["calibrated+extra"] = apply_extra(sets["calibrated"])
    dz = np.diff(HEIGHTS) / 1000.0
    out = []
    for b, f in BANDS:
        sel = f(HEIGHTS[1:])
        for k, x in sets.items():
            u, v, T = x[..., :n], x[..., n:2 * n], x[..., 2 * n:3 * n]
            shear = (np.hypot(np.diff(u), np.diff(v)) / dz)[..., sel].ravel()
            lapse = (-np.diff(T) / dz)[..., sel].ravel()
            q = np.percentile(shear, [50, 99, 99.9])
            out.append(dict(band=b, set=k, shear_p50=q[0], shear_p99=q[1], shear_p999=q[2],
                            superadiabatic_pct=100 * (lapse > 9.8).mean(), inversion_pct=100 * (lapse < 0).mean()))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--rows", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--device")
    ap.add_argument("--out", help="also write the table as CSV")
    a = ap.parse_args()
    t = table(a.model, a.calib, a.data, a.rows, a.seed, a.first_year, device=a.device)
    for b, g in t.groupby("band", sort=False):
        print(f"--- {b}")
        for _, r in g.iterrows():
            print(f"{r['set']:>10}: shear p50/p99/p99.9 {r.shear_p50:6.2f} {r.shear_p99:6.2f} {r.shear_p999:6.2f} m/s/km | "
                  f"superadiabatic (>9.8 K/km) {r.superadiabatic_pct:5.2f} % | inversion (<0) {r.inversion_pct:5.2f} %")
    if a.out:
        t.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
