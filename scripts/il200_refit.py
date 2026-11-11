"""IL-200 step 4 (CPU): a shear map with FINE low layers fitted on balloons. The shipped map has bands 0-1 / 1-5 / 5-12 / 12-18 km, so it cannot treat 100-300 m on its own, where the tool is 25 % too sharp
against balloons at the median (il200_lowlayer_shear.log). Here: tempest.calibrate.shear_map.fit(edges=[0, 100, 300, 1000, 5000, 12000, 18001]) fitted so the INSTALLED tool's shear matches EPZ + MAF
balloons of 2005-2020 (00Z + 12Z, a random per-group sample), applied on top of the tool's output, judged on balloons 2021-2022: shear p50 / p99 per neighbour layer 10-1000 m (tool, tool + fine map,
balloons) and the CRPS of u and v by height band (a map that fixes the shear but costs CRPS is no win). Nothing is installed or exported; the table goes to models/il200_fine_shearmap.npz.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il200_refit.py [--fit-per-group 300] [--test-per-group 160] [--out docs/results/logs/il200_refit.log]"""
import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import il103_balloon_shearmap as M   # noqa: E402
from tempest.calibrate import shear_map   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402

EDGES_FINE = [0, 100, 300, 1000, 5000, 12000, 18001]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit-per-group", type=int, default=300)
    ap.add_argument("--test-per-group", type=int, default=160)
    ap.add_argument("--out", default="docs/results/logs/il200_refit.log")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    xf, yf = M.collect((2005, 2020), a.fit_per_group, rng)
    table = shear_map.fit(xf, yf, edges=EDGES_FINE)
    np.savez(os.path.join(REPO, "models", "il200_fine_shearmap.npz"), **table)
    xt, yt = M.collect((2021, 2022), a.test_per_group, rng)
    xb = shear_map.apply(table, xt)
    NH, H = M.NH, np.asarray(M._core.HEIGHTS, float)

    def lay(x):
        return shear_map.shears(x.reshape(*x.shape[:-1], 2, NH).astype(np.float64))[1]
    st, sb, so = lay(xt), lay(xb), lay(yt[:, None, :])
    lines = [f"IL-200 step 4: fine-band shear map (edges {EDGES_FINE}) fitted on {len(yf)} balloons 2005-20, tested on {len(yt)} balloons 2021-22 (EPZ + MAF, 00Z + 12Z), shear m/s per km p50 / p99",
             "  layer (m)          tool          tool + fine map    balloons"]
    for k in range(9):
        f = lambda s: f"{np.median(s[..., k]):6.1f} /{np.quantile(s[..., k], .99):6.1f}"  # noqa: E731
        lines.append(f"  {H[k]:5.0f}-{H[k + 1]:5.0f}   {f(st)}   {f(sb)}   {f(so)}")
    c0, c1 = crps_ensemble(xt, yt), crps_ensemble(xb, yt)
    for name, sl in (("u", slice(0, NH)), ("v", slice(NH, 2 * NH))):
        for bn, (lo, hi) in (("0-100 m", (0, 100)), ("100-300 m", (100, 300)), ("300-1000 m", (300, 1000)), ("1-5 km", (1000, 5000)), ("5-12 km", (5000, 12000)), ("12-18 km", (12000, 18001))):
            j = np.flatnonzero((H >= lo) & (H < hi))
            a0, a1 = c0[:, sl][:, j].mean(), c1[:, sl][:, j].mean()
            lines.append(f"  CRPS {name} {bn:10s} tool {a0:.3f} -> + fine map {a1:.3f} ({100 * (a1 / a0 - 1):+.1f} %)")
    print("\n".join(lines), flush=True)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
