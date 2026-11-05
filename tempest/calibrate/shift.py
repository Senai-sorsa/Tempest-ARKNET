"""Median bias shift (improvement-loop IL-13): move every sample so the median of the samples agrees with the truth on average in the calibration years.

    python -m tempest.calibrate.shift --model models/X.pt --data D.npz --calib models/X.calib2021.npz [--year 2023] [--from-year 2021] [--rows 12000]

After all work the generator is still cold by 0.36-0.46 K at 0-12 km (PLAN P3-5). The range calibration only changes the width, so a plain shift is the most direct
fix: per column, shift = median over the calibration rows of (truth - median of the calibrated samples). Applying it adds the shift to all samples of that column
(RH and the other bounded fields are clipped afterwards), so spread and ranks stay. Off by default (score --shift FILE); writes <model>.shift<from-year>.npz.
The shift is a 2021-23 average: it removes a stable bias, not a trend; `--halflife-years` is not used on purpose (test years must not leak into the fit).
"""
import argparse

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.calibrate.trust import file_sha


def apply(table, x):
    """x (N, m, D) -> x + shift per column, kept inside the physical ranges."""
    from tempest.generator.sample import clip_ranges
    return clip_ranges((x + table["shift"][None, None, :]).astype(x.dtype))


def fit(med, truth, shrink=0.0):
    """med, truth (N, D) -> (D,) median of the residual (truth - median of samples), optionally shrunk toward 0 by `shrink`."""
    return (1.0 - shrink) * np.median(truth - med, axis=0)


def main():
    from tempest.generator.features import FEATURES  # noqa: F401  (activates the feature list after load_npz)
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--rows", type=int, default=12000)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    idx = np.sort(rng.choice(np.flatnonzero((d["year"] >= a.from_year) & (d["year"] <= a.year)), a.rows, replace=False))
    truth = to_physical(np.asarray(d["target"][idx]))
    cond = np.asarray(d["cond"])[idx]
    med = np.empty_like(truth)
    for i in range(0, len(idx), 400):
        sl = slice(i, i + 400)
        x = spread.apply(cal, sampler.profiles(np.repeat(cond[sl], a.m, axis=0)).reshape(len(cond[sl]), a.m, -1))
        med[sl] = np.median(x, 1)
        print(f"{min(i + 400, len(idx)):,}/{len(idx):,} rows", flush=True)
    shift = fit(med, truth)
    out = a.model.rsplit(".", 1)[0] + f".shift{a.from_year}.npz"
    np.savez(out, shift=shift.astype(np.float32), fit_from=a.from_year, fit_to=a.year, m=a.m, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    from tempest.scoring.score import band_masks
    for v, b, sel in band_masks():
        print(f"{v:<5}{b:<10} median shift {shift[sel].mean():+.3f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
