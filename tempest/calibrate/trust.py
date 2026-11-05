"""Trust layer: where the model has no skill over "what is normal for this date", lean on the 15-year climatology.

    python -m tempest.calibrate.trust --model models/X.pt --data D.npz --calib models/X.calib2021.npz
                                      [--year 2023] [--from-year 2021] [--rows 12000] [--m 199]

After range calibration, each sample keeps its rank among the m samples of its row, but its value becomes
    x' = w * x_model + (1 - w) * Q_clim15(rank)
where Q_clim15 is the quantile of the recent-15-year climatology of the same group (grid point x calendar month x
2-hour solar bin, the group score.py uses) at that rank. w is one number per variable x height band (and per
surface field), fitted on the calibration years by CRPS of the "unknown drivers" samples (what a query years ahead
gets). w = 1 changes nothing; w = 0 gives the climatology's quantiles in the model's rank order, so each profile
keeps its joint shape. Used by score/sonde with --trust FILE (off by default).
Honest limit: the weights are fitted on the calibration years, so "never worse" holds there only; the test years
decide whether the layer is kept. Writes <model>.trust<from-year>.npz (stores the model and calibration hashes).
"""
import argparse
import hashlib

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, clip_ranges, to_physical
from tempest.generator.train import load_npz

W_GRID = np.linspace(0, 1, 21)


def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()[:16]


class ClimPool:
    """Quantiles of past rows by group key. `years` = (first, last) of the window; a group with no row in the window
    falls back to the same group in all years before `last + 1` (as score.py's clim15 does)."""

    def __init__(self, keys, year, target, years, m):
        self.target, self.m, self.cache = target, m, {}
        self.levels = (np.arange(m) + 0.5) / m
        win = np.flatnonzero((year >= years[0]) & (year <= years[1]))
        allp = np.flatnonzero(year <= years[1])
        self.win, self.allp = win[np.argsort(keys[win], kind="stable")], allp[np.argsort(keys[allp], kind="stable")]
        self.kw, self.ka = keys[self.win], keys[self.allp]

    def _rows(self, k):
        for pool, kk in ((self.win, self.kw), (self.allp, self.ka)):
            lo, hi = np.searchsorted(kk, k, "left"), np.searchsorted(kk, k, "right")
            if hi > lo:
                return pool[lo:hi]
        raise KeyError(f"no climatology rows for group {k}")

    def quantiles(self, keys):
        """keys (N,) -> (N, m, D) float32 sorted quantiles (physical units) at the m rank positions."""
        out = None
        for k in np.unique(keys):
            if k not in self.cache:
                rows = np.sort(self._rows(k))
                phys = to_physical(np.asarray(self.target[rows])).astype(np.float64)
                self.cache[k] = np.quantile(phys, self.levels, axis=0).astype(np.float32)
            q = self.cache[k]
            if out is None:
                out = np.empty((len(keys),) + q.shape, np.float32)
            out[keys == k] = q
        return out


def keys_like(ref_cond, cond):
    """Group keys (as score.group_keys) for new feature rows, with point ids taken from the reference rows' grid points,
    so they match the dataset's keys. A point not on the reference grid raises KeyError."""
    from tempest.generator.features import FEATURES
    col = lambda c, k: c[:, FEATURES.index(k)]
    pts, _ = np.unique(np.round(np.stack([col(ref_cond, "lat"), col(ref_cond, "lon")], 1), 3), axis=0, return_inverse=True)
    new = np.round(np.stack([col(cond, "lat"), col(cond, "lon")], 1), 3)
    point = np.array([np.flatnonzero((pts == p).all(1))[0] for p in new])
    month = (np.arctan2(col(cond, "doy_sin"), col(cond, "doy_cos")) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    hbin = (np.arctan2(col(cond, "hour_sin"), col(cond, "hour_cos")) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    return point.astype(np.int64) * 144 + month * 12 + hbin


def apply(w, x, q):
    """w (D,) in [0, 1], x (N, m, D) calibrated samples, q (N, m, D) sorted climatology quantiles -> blended copy.
    Rank-preserving: the sample of rank r gets w * x + (1 - w) * q[r]. Columns with w = 1 are untouched."""
    cols = np.flatnonzero(np.asarray(w) < 1)
    if len(cols) == 0:
        return x
    out = x.copy()
    xs = x[..., cols]
    rank = np.argsort(np.argsort(xs, axis=1), axis=1)
    qc = np.take_along_axis(q[..., cols], rank, axis=1)
    wc = np.asarray(w, np.float32)[cols]
    out[..., cols] = wc * xs + (1 - wc) * qc
    return clip_ranges(out)


def apply_full(t, x, q):
    """Trust file dict, calibrated samples, climatology quantiles -> blended samples. If the file holds a second range
    map (qz, qu fitted on blended samples), it is applied after the blend: blending narrows the tails, and this restores
    the 99 % coverage. Files without the map (older fits) only blend."""
    out = apply(t["w"], x, q)
    if "qz" in t:
        out = spread.apply(dict(qz=t["qz"], qu=t["qu"], m=t["m"]), out)
    return out


def crps_sorted(xs, y):
    """Like score.crps_ensemble for samples already sorted along axis 1 (skips the sort)."""
    m = xs.shape[1]
    i = np.arange(1, m + 1, dtype=np.float32)[None, :, None]
    return 2 / m ** 2 * ((xs - y[:, None]) * (m * (y[:, None] < xs) - i + 0.5)).sum(1)


def load(path, model=None, calib=None):
    """Trust file -> dict. Refuses a file fitted for another model or another calibration."""
    t = dict(np.load(path))
    if model and str(t["model_sha"]) != spread.model_hash(model):
        raise SystemExit(f"{path} was fitted for a different model than {model}; refit with tempest.calibrate.trust")
    if calib and str(t["calib_sha"]) != file_sha(calib):
        raise SystemExit(f"{path} was fitted on a different calibration than {calib}; refit with tempest.calibrate.trust")
    return t


def main():
    from tempest.generator.features import FEATURES, drivers
    from tempest.scoring.score import band_masks, group_keys  # late import: score imports this module
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--rows", type=int, default=12000)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--clim-years", type=int, default=15)
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
    pool = ClimPool(keys, year, target, (a.from_year - a.clim_years, a.from_year - 1), a.m)
    tr = np.flatnonzero(year < a.from_year)  # drivers are drawn from earlier years of the same group, as in score
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[rows], "left"), np.searchsorted(keys[tr], keys[rows], "right")
    keep = hi > lo
    rows, lo, hi = rows[keep], lo[keep], hi[keep]
    draws = tr[lo[:, None] + (rng.random((len(rows), a.m)) * (hi - lo)[:, None]).astype(np.int64)]
    dc = [FEATURES.index(k) for k in drivers()]
    truth_all = to_physical(np.asarray(target[rows]))
    D = truth_all.shape[1]
    crps = np.zeros((len(W_GRID), D))
    step = 400
    for i in range(0, len(rows), step):
        sl = slice(i, i + step)
        rep = np.repeat(cond[rows[sl]], a.m, axis=0)
        rep[:, dc] = cond[draws[sl].ravel()][:, dc]
        x = spread.apply(cal, sampler.profiles(rep).reshape(-1, a.m, D))
        xs = np.sort(x, axis=1)
        q = pool.quantiles(keys[rows[sl]])
        y = truth_all[sl]
        for j, w in enumerate(W_GRID):
            crps[j] += crps_sorted(w * xs + (1 - w) * q, y).sum(0)
        print(f"{min(i + step, len(rows)):,}/{len(rows):,} rows", flush=True)
    w_col = np.ones(D, np.float32)
    print(f"\n{'variable':<8}{'band':<12}{'w':>6}  CRPS vs model alone (w = 1)   CRPS vs climatology (w = 0)")
    for v, b, sel in band_masks():
        tot = crps[:, sel].sum(1)
        w_col[sel] = W_GRID[int(np.argmin(tot))]
        print(f"{v:<8}{b:<12}{w_col[sel][0]:6.2f}  {tot.min() / tot[-1]:>12.4f}{tot.min() / tot[0]:>30.4f}")
    # second pass: range map on the blended samples (restores 99 % coverage that blending narrows)
    zs, us = [], []
    for i in range(0, len(rows), step):
        sl = slice(i, i + step)
        rep = np.repeat(cond[rows[sl]], a.m, axis=0)
        rep[:, dc] = cond[draws[sl].ravel()][:, dc]
        x = spread.apply(cal, sampler.profiles(rep).reshape(-1, a.m, D))
        z, u = spread.parts(apply(w_col, x, pool.quantiles(keys[rows[sl]])), truth_all[sl], rng=rng)
        zs.append(z), us.append(u)
        print(f"pass 2: {min(i + step, len(rows)):,}/{len(rows):,} rows", flush=True)
    tab = spread.table(np.concatenate(zs), np.concatenate(us))
    out = a.model.rsplit(".", 1)[0] + f".trust{a.from_year}.npz"
    np.savez(out, qz=tab["qz"], qu=tab["qu"], w=w_col, w_grid=W_GRID, crps=crps / len(rows), fit_from=a.from_year, fit_to=a.year, m=a.m,
             clim_years=a.clim_years, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    print(f"fit on {len(rows):,} rows of {a.from_year}-{a.year}; {int((w_col < 1).sum())} of {D} columns lean on climatology; wrote {out}")


if __name__ == "__main__":
    main()
