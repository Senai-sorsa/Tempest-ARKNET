"""IL-200 (2026-11-10): the 0-1 km MEDIAN shear of the tool is about 20 % above pre-change balloons (14.0 vs 11.7 m/s per km, il194_shear_2021_22.log). Which layers carry it, and is the balloon
side smoothed by the sounding interpolation near the ground? Per neighbour-height layer between 10 m and 1500 m: median shear (m/s per km) of the tool's samples and of the balloons of 2021-2022
(EPZ + MAF, 00Z + 12Z), and the share of balloon layers with exactly zero shear (a sounding value copied across two grid heights). Climate mode, installed tool, CPU only.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/il200_lowlayer_shear.py [--per-group 80] [--out docs/results/logs/il200_lowlayer_shear.log]"""
import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import il103_balloon_shearmap as M   # noqa: E402
from tempest.calibrate import shear_map   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=80)
    ap.add_argument("--out", default="docs/results/logs/il200_lowlayer_shear.log")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    xt, yt = M.collect((2021, 2022), a.per_group, rng)
    NH = M.NH
    st = shear_map.shears(xt.reshape(*xt.shape[:-1], 2, NH).astype(np.float64))[1]      # (rows, samples, layers)
    sb = shear_map.shears(yt.reshape(yt.shape[0], 2, NH).astype(np.float64))[1]         # (rows, layers)
    H = np.asarray(M._core.HEIGHTS, float)
    lines = [f"IL-200 low-layer shear, balloons 2021-22 vs the tool, {yt.shape[0]} balloons (per layer between neighbour heights; m/s per km)",
             "  layer (m)        tool p50   balloon p50   tool p99   balloon p99   balloon zero-shear share"]
    for k in range(min(12, sb.shape[-1])):
        t_ = st[..., k].ravel()
        b_ = sb[..., k].ravel()
        lines.append(f"  {H[k]:6.0f}-{H[k + 1]:5.0f}    {np.median(t_):8.1f}   {np.median(b_):11.1f}   {np.quantile(t_, .99):8.1f}   {np.quantile(b_, .99):11.1f}   {np.mean(b_ == 0):.3f}")
    for l in lines:
        print(l)
    with open(os.path.join(REPO, a.out), "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
