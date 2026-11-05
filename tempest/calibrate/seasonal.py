"""Seasonal width correction (improvement-loop IL-2): a width factor per calendar month and variable x height band on top of the range calibration.

    python -m tempest.calibrate.seasonal --model models/X.pt --data D.npz --calib models/X.calib2021.npz [--year 2023] [--from-year 2021] [--rows 12000]

The stress table of the adopted model shows one systematic weakness: summer temperature at 5-12 km, whose 99 % range holds only ~96 % of outcomes at every
hour. A single global range map cannot be right in every season. For each month and each variable x band, a factor s is fitted on the calibration years so that
the 99 % range (lowest to highest of 199 samples, widened about the row median by s) holds 99 % of the truths of that month; the 12 monthly factors are
smoothed circularly over 3 months. Applying is x' = median + s (x - median) per column: ranks are kept, so joint shape and CRPS barely move. Off by default
(score/sonde --seasonal FILE). Writes <model>.seasonal<from-year>.npz with the model and calibration hashes.
"""
import argparse

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.calibrate.trust import file_sha
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz

S_MIN, S_MAX = 0.85, 1.6


def apply(table, x, month):
    """x (N, m, D), month (N,) 1..12 -> widened copy. table['scale'] is (12, D)."""
    s = table["scale"][np.asarray(month, int) - 1][:, None, :]           # (N, 1, D)
    med = np.median(x, axis=1, keepdims=True)
    from tempest.generator.sample import clip_ranges
    return clip_ranges((med + s * (x - med)).astype(x.dtype))


def fit_scale(lo, med, hi, y, target=0.99):
    """Smallest s in [S_MIN, S_MAX] with coverage >= target for per-row lowest / median / highest and truth (all (n, c)); bisection on the pooled coverage."""
    def cov(s):
        return ((y >= med - s * (med - lo)) & (y <= med + s * (hi - med))).mean()
    if cov(S_MIN) >= target:
        return S_MIN
    a, b = S_MIN, S_MAX
    if cov(b) < target:
        return S_MAX
    for _ in range(30):
        mid = (a + b) / 2
        a, b = (mid, b) if cov(mid) < target else (a, mid)
    return b


def smooth_months(s):
    """s (12, G) -> circular 3-month moving average."""
    return (np.roll(s, 1, 0) + s + np.roll(s, -1, 0)) / 3.0


def restrict(table, variables):
    """Copy of a seasonal table with factor 1 everywhere except the physical columns of the given variables (names as in scoring.score.band_masks, e.g. RH, rh2m)."""
    from tempest.scoring.score import band_masks
    keep = np.zeros(table["scale"].shape[1], bool)
    for v, _, sel in band_masks():
        if v in variables:
            keep |= sel
    out = dict(table)
    out["scale"] = np.where(keep[None, :], table["scale"], 1.0).astype(np.float32)
    return out


def main():
    from tempest.generator.features import FEATURES, drivers
    from tempest.scoring.score import band_masks, group_keys
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
    year, cond, target = d["year"], np.asarray(d["cond"]), d["target"]
    keys = group_keys(cond)
    rows = np.sort(rng.choice(np.flatnonzero((year >= a.from_year) & (year <= a.year)), a.rows, replace=False))
    tr = np.flatnonzero(year < a.from_year)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[rows], "left"), np.searchsorted(keys[tr], keys[rows], "right")
    keep = hi > lo
    rows, lo, hi = rows[keep], lo[keep], hi[keep]
    draws = tr[lo[:, None] + (rng.random((len(rows), a.m)) * (hi - lo)[:, None]).astype(np.int64)]
    dc = [FEATURES.index(k) for k in drivers()]
    truth = to_physical(np.asarray(target[rows]))
    D = truth.shape[1]
    month = (keys[rows] // 12) % 12 + 1
    stats = np.empty((len(rows), 3, D), np.float32)
    for i in range(0, len(rows), 400):
        sl = slice(i, i + 400)
        rep = np.repeat(cond[rows[sl]], a.m, axis=0)
        rep[:, dc] = cond[draws[sl].ravel()][:, dc]
        x = spread.apply(cal, sampler.profiles(rep).reshape(-1, a.m, D))
        stats[sl] = np.stack([x.min(1), np.median(x, 1), x.max(1)], 1)
        print(f"{min(i + 400, len(rows)):,}/{len(rows):,} rows", flush=True)
    groups = band_masks()
    scale = np.ones((12, D))
    for g, (v, b, sel) in enumerate(groups):
        cols = np.flatnonzero(sel)
        s_m = np.ones((12, 1))
        for mo in range(1, 13):
            r = month == mo
            if r.sum() >= 150:
                s_m[mo - 1, 0] = fit_scale(stats[r][:, 0][:, cols], stats[r][:, 1][:, cols], stats[r][:, 2][:, cols], truth[r][:, cols])
        scale[:, cols] = smooth_months(s_m)
        if np.abs(scale[:, cols[0]] - 1).max() > 0.02:
            print(f"{v:<5}{b:<10} monthly factors: " + " ".join(f"{x:.2f}" for x in scale[:, cols[0]]))
    out = a.model.rsplit(".", 1)[0] + f".seasonal{a.from_year}.npz"
    np.savez(out, scale=scale.astype(np.float32), fit_from=a.from_year, fit_to=a.year, m=a.m, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
