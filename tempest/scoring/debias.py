"""Climatology debias (LOOP3 L3-34): subtract the calibrated model's mean error per grid point x month x 4-hour bin.

    python -m tempest.scoring.debias --model M --calib C --data D [--from-year 2021 --year 2023 --rows 60000 --m <calib m>]
    -> <model stem>.debias<from-year>.npz; then score with --debias <file> (outputs get a _debias suffix)

Why: at Denver most of the p2f loss is mean bias (u 0-1 km +7.8 m/s, 77 % of its MSE), which the NM/TX-trained model cannot
know and climatology inputs barely fix. The table is fitted on calibration years only (default 2021-23), never on test years.
delta = point x month mean error + (n / (n + K)) x the 4-hour-bin residual, so thin bins shrink towards the monthly value.
shortcut: shifts the mean only (spread and shape unchanged); a site needs >= 3 fitted years, and a new region needs its own fit
(G2 should learn this in the SAMOS target space, L3-8, instead).
"""
import argparse

import numpy as np

from tempest.calibrate import spread
from tempest.calibrate.trust import file_sha
from tempest.generator.features import FEATURES
from tempest.generator.sample import clip_ranges

NB = 6  # 4-hour bins per day
K = 10.0


def _groups(keys):
    """score.group_keys -> (point x month x 4-hour bin, point x month)."""
    k = np.asarray(keys)
    pm = (k // 144) * 12 + (k // 12) % 12
    return pm * NB + (k % 12) // 2, pm


def points(cond):
    return np.unique(np.round(np.asarray(cond)[:, [FEATURES.index("lat"), FEATURES.index("lon")]], 3), axis=0)


def fit(err, keys, n_points):
    """err (N, D) = sample mean - truth per row -> delta (n_points * 12 * NB, D)."""
    g, pm = _groups(keys)
    G, PM = n_points * 12 * NB, n_points * 12
    sg, spm = np.zeros((G, err.shape[1])), np.zeros((PM, err.shape[1]))
    np.add.at(sg, g, err)
    np.add.at(spm, pm, err)
    ng, npm = np.bincount(g, minlength=G)[:, None], np.bincount(pm, minlength=PM)[:, None]
    mpm = spm / np.maximum(npm, 1)
    base = np.repeat(mpm, NB, axis=0)
    return (base + ng / (ng + K) * (sg / np.maximum(ng, 1) - base)).astype(np.float32)


def rh_columns(D):
    """Boolean mask (D,) of the relative-humidity columns: the RH profile block and the 2 m humidity (the layout of to_physical: PROFILE blocks, then t2m, sp, rh2m)."""
    from tempest.profiles.to_heights import HEIGHTS, PROFILE
    n = len(HEIGHTS)
    m = np.zeros(D, bool)
    m[PROFILE.index("RH") * n:(PROFILE.index("RH") + 1) * n] = True
    if D >= len(PROFILE) * n + 3:
        m[len(PROFILE) * n + 2] = True
    return m


def to_logit(rh):
    """IL-142: humidity in %RH -> logit of the fraction (clipped to 0.5 .. 99.5 %), the coordinate in which a shift cannot leave 0 .. 100 %."""
    p = np.clip(np.asarray(rh, np.float64), 0.5, 99.5) / 100.0
    return np.log(p / (1.0 - p))


def from_logit(z):
    return 100.0 / (1.0 + np.exp(-np.asarray(z, np.float64)))


def apply(tab, x, keys):
    """x (N, m, D) physical samples, keys (N,) score.group_keys of the rows -> debiased samples. A table fitted with --rh-logit (IL-142) shifts the humidity columns in logit space."""
    d = tab["delta"][_groups(keys)[0]][:, None, :]
    if "rh_logit" in tab and int(tab["rh_logit"]):
        r = rh_columns(x.shape[-1])
        out = x.astype(np.float64, copy=True)
        out[..., ~r] = x[..., ~r] - d[..., ~r]
        out[..., r] = from_logit(to_logit(x[..., r]) - d[..., r])
        return clip_ranges(out.astype(x.dtype))
    return clip_ranges(x - d)


def check_points(tab, cond):
    if not np.array_equal(tab["points"], points(cond)):
        raise SystemExit("--debias table was fitted on a different grid than --data")


def main():
    import torch
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    from tempest.scoring.score import group_keys
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--rows", type=int, default=60000)
    ap.add_argument("--m", type=int, help="default: the m the calibration was fitted with")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--rh-logit", action="store_true", help="IL-142: fit and apply the humidity shift in logit space (the physical-space shift collapses the lower tail at 0 %%RH); off = as L3-34")
    a = ap.parse_args()
    if a.year >= 2024:
        raise SystemExit("debias must be fitted before the test years (2024-25)")
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    a.m = a.m or int(cal.get("m", 8))  # spread.apply refuses any other m
    d = load_npz(a.data)
    cond_all, year = np.asarray(d["cond"]), d["year"]
    keys_all = group_keys(cond_all)
    pool = np.flatnonzero((year >= a.from_year) & (year <= a.year))
    idx = np.sort(rng.choice(pool, min(a.rows, len(pool)), replace=False))
    truth = to_physical(np.asarray(d["target"][idx]))
    err = np.empty(truth.shape, np.float64)
    for i in range(0, len(idx), 2000):
        sl = slice(i, i + 2000)
        x = spread.apply(cal, sampler.profiles(np.repeat(cond_all[idx[sl]], a.m, axis=0)).reshape(len(idx[sl]), a.m, -1))
        err[sl] = x.mean(1) - truth[sl]
        if a.rh_logit:
            r = rh_columns(x.shape[-1])
            err[sl][:, r] = to_logit(x[..., r]).mean(1) - to_logit(truth[sl][:, r])
    pts = points(cond_all)
    delta = fit(err, keys_all[idx], len(pts))
    out = a.out or a.model.rsplit(".", 1)[0] + f".debias{a.from_year}.npz"
    extra = dict(rh_logit=1) if a.rh_logit else {}
    np.savez(out, **extra, delta=delta, points=pts, fit_from=a.from_year, fit_to=a.year, rows=len(idx), m=a.m, k=K,
             model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    print(f"{len(idx):,} rows {a.from_year}-{a.year}, mean |error| before {np.abs(err).mean():.3f}, "
          f"after (in-sample) {np.abs(err - delta[_groups(keys_all[idx])[0]]).mean():.3f} -> {out}")


if __name__ == "__main__":
    if __import__("sys").argv[1:]:
        main()
    else:  # self-check: a constant per-group bias is recovered and removed; groups with no rows fall back to the monthly mean
        r = np.random.default_rng(0)
        keys = r.integers(0, 2 * 144, 20000)
        bias = (keys // 144) * 3.0 + ((keys // 12) % 12) * 0.5
        err = bias[:, None] + 0.01 * r.standard_normal((20000, 2))
        tab = fit(err, keys, 2)
        g = _groups(keys)[0]
        assert np.abs(tab[g] - bias[:, None]).max() < 0.05
        assert tab.shape == (2 * 12 * NB, 2) and np.isfinite(tab).all()
        print("debias self-check ok")
