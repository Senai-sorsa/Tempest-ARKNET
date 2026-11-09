"""Simultaneous 99 % band for whole profiles.

    python -m tempest.calibrate.joint --model models/X.pt --data D.npz --calib models/X.calib2021.npz
                                      [--year 2023] [--from-year 2021] [--rows 12000] [--m 199]

The ordinary 99 % range holds each height's real value 99 % of the time, but all 44 heights at once only about
85-93 % of the time (the misses are at different heights on different days). This fits, per variable, one width
multiplier s so that 99 % of whole profiles lie inside the band at every height together:
    lo = median - s * (median - lowest sample),  hi = median + s * (highest sample - median)
(lowest/highest of m = 199 samples is the ordinary 99 % range, s = 1). It is an OUTPUT only (band99_joint_lo/hi);
it never stretches the samples, so skill and joint shape are untouched. Fitted per driver mode (known/unknown),
on the calibration years; score.py reports the whole-profile coverage of the band on the test years.
Writes <model>.joint<from-year>.npz (stores the model and calibration hashes).
"""
import argparse

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.calibrate.trust import file_sha
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE


def band(x, s):
    """x (N, m, n) samples of one variable, s scalar -> (lo, hi) each (N, n)."""
    lo, med, hi = x.min(1), np.median(x, 1), x.max(1)
    return med - s * (med - lo), med + s * (hi - med)


def inside(x, y, s):
    """Share of rows whose whole profile y (N, n) lies inside the s-scaled band of samples x."""
    lo, hi = band(x, s)
    return ((y >= lo) & (y <= hi)).all(1)


def fit_scale(x, y, target=0.99):
    """Smallest s on a fine grid (found by bisection) with whole-profile coverage >= target."""
    lo, hi = 1.0, 8.0
    if inside(x, y, lo).mean() >= target:
        return lo
    for _ in range(25):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if inside(x, y, mid).mean() < target else (lo, mid)
    return hi


def apply(scale, x):
    """scale (len(PROFILE),) per profile variable, x (N, m, D) physical samples -> (lo, hi) each (N, D_profile)."""
    n = len(HEIGHTS)
    los, his = [], []
    for i in range(len(PROFILE)):
        lo, hi = band(x[..., i * n:(i + 1) * n], scale[i])
        los.append(lo), his.append(hi)
    return np.concatenate(los, 1), np.concatenate(his, 1)


def load(path, model=None, calib=None):
    t = dict(np.load(path))
    if model and str(t["model_sha"]) != spread.model_hash(model):
        raise SystemExit(f"{path} was fitted for a different model than {model}; refit with tempest.calibrate.joint")
    if calib and str(t["calib_sha"]) != file_sha(calib):
        raise SystemExit(f"{path} was fitted on a different calibration than {calib}; refit with tempest.calibrate.joint")
    return t


def main():
    from tempest.generator.features import FEATURES, drivers
    from tempest.scoring.score import group_keys  # late import: score imports this module
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
    if int(cal["m"]) != a.m:
        raise SystemExit(f"calibration was fitted with m = {int(cal['m'])}, not {a.m}")
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
    D, n = truth.shape[1], len(HEIGHTS)
    # whole-profile coverage needs all rows at once per variable; keep only the three statistics the band needs
    stats = {k: [] for k in ("known", "unknown")}
    for i in range(0, len(rows), 400):
        sl = slice(i, i + 400)
        rep = np.repeat(cond[rows[sl]], a.m, axis=0)
        for mode in ("known", "unknown"):
            if mode == "unknown":
                rep[:, dc] = cond[draws[sl].ravel()][:, dc]
            x = spread.apply(cal, sampler.profiles(rep).reshape(-1, a.m, D))[..., :n * len(PROFILE)]
            stats[mode].append(np.stack([x.min(1), np.median(x, 1), x.max(1)], 1).astype(np.float32))  # (n_rows, 3, 176)
        print(f"{min(i + 400, len(rows)):,}/{len(rows):,} rows", flush=True)
    out = {}
    for mode in ("known", "unknown"):
        st = np.concatenate(stats[mode])  # (N, 3, 176)
        s = np.empty(len(PROFILE))
        before = []
        for v in range(len(PROFILE)):
            sl = slice(v * n, (v + 1) * n)
            mn, md, mx = st[:, 0, sl], st[:, 1, sl], st[:, 2, sl]
            y = truth[:, sl]

            def cov(sc):
                return ((y >= md - sc * (md - mn)) & (y <= md + sc * (mx - md))).all(1).mean()
            before.append(cov(1.0))
            lo_, hi_ = 1.0, 8.0
            if before[-1] >= 0.99:
                s[v] = 1.0
                continue
            for _ in range(25):
                mid = (lo_ + hi_) / 2
                lo_, hi_ = (mid, hi_) if cov(mid) < 0.99 else (lo_, mid)
            s[v] = hi_
        out[mode] = s
        print(f"{mode}: whole-profile coverage of the plain 99 % range " +
              "  ".join(f"{v} {b:.3f}" for v, b in zip(PROFILE, before)) + "  ->  width multiplier " +
              "  ".join(f"{v} {x:.2f}" for v, x in zip(PROFILE, s)))
    path = a.model.rsplit(".", 1)[0] + f".joint{a.from_year}.npz"
    np.savez(path, scale_known=out["known"], scale_unknown=out["unknown"], fit_from=a.from_year, fit_to=a.year, m=a.m,
             model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
