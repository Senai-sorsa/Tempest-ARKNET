"""Median error (truth - median of calibrated samples) per year and variable x band, 2015-2025: shows whether the cold bias is stable or grows with the year (IL-19).
Diagnostic only (the years before 2021 are training years, so their bias is optimistic); nothing here is fitted.

    PYTHONPATH=. python scripts/bias_by_year.py MODEL.pt CALIB.npz DATA.npz [--rows-per-year 1500] [--first 2015] [--last 2025] [--out csv]
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.scoring.score import band_masks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--rows-per-year", type=int, default=1500)
    ap.add_argument("--first", type=int, default=2015)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--out")
    ap.add_argument("--device")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    year, cond = d["year"], np.asarray(d["cond"])
    rows = []
    for y in range(a.first, a.last + 1):
        idx = np.sort(rng.choice(np.flatnonzero(year == y), a.rows_per_year, replace=False))
        truth = to_physical(np.asarray(d["target"][idx]))
        med = np.empty_like(truth)
        for i in range(0, len(idx), 300):
            sl = slice(i, i + 300)
            x = spread.apply(cal, sampler.profiles(np.repeat(cond[idx[sl]], a.m, axis=0)).reshape(len(cond[idx[sl]]), a.m, -1))
            med[sl] = np.median(x, 1)
        err = np.median(truth - med, 0)
        for v, b, sel in band_masks():
            rows.append(dict(year=y, var=v, band=b, median_error=float(err[sel].mean())))
        print(y, flush=True)
    t = pd.DataFrame(rows)
    out = a.out or a.model.rsplit(".", 1)[0] + "_bias_by_year.csv"
    t.to_csv(out, index=False)
    pv = t.pivot_table(index=["var", "band"], columns="year", values="median_error", sort=False)
    slope = pv.apply(lambda r: np.polyfit(r.index.values.astype(float), r.values, 1)[0], axis=1)
    pv["slope_per_year"] = slope
    with pd.option_context("display.width", 250, "display.float_format", "{:+.3f}".format):
        print(pv.to_string())
    print("wrote", out)


if __name__ == "__main__":
    main()
