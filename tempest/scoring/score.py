"""Scorecard: generator vs climatology on the held-out years, in physical units.

    python -m tempest.scoring.score --model models/generator_pilot.pt --data data/train/pilot.npz
                                    [--rows 5000] [--m 50] [--device cpu]

For each held-out row (the last `val_years` years, as in training) it draws m samples four ways:
- climatology: real training-year rows from the same grid point, calendar month and 2-hour solar-time bin
- gauss: monthly mean + correlated bell-curve spread per grid point, the way NASA Earth-GRAM / Range Reference
  Atmospheres build dispersions (the tool aerospace uses today; the bar to clear)
- generator, drivers known: ONI, WWV, QBO as observed (upper bound, like a perfect seasonal forecast)
- generator, drivers unknown: drivers copied from random training rows of the same group (what a query
  years ahead gets: the model's spread then also covers ENSO/QBO uncertainty)
Per column: CRPS (lower is better), 90 % interval coverage (should be ~0.90) and skill = 1 - CRPS / CRPS_clim
(> 0 beats climatology). Variogram score (p = 0.5, Scheuerer & Hamill 2015) per variable checks profile shape:
shear and differences between heights, which CRPS per value cannot see. Truth is ERA5, not radiosondes: coverage against real soundings will be lower until the
phase 6 correction. Writes <model>.score.csv (every column), prints a summary by variable and height band, and saves
charts + tables in <model>_report/ (see scoring.report).
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.features import FEATURES
from tempest.generator.sample import SURFACE, Sampler, clip_ranges, to_physical
from tempest.generator.train import load_npz
from tempest.scoring.report import report
from tempest.profiles.to_heights import HEIGHTS, PROFILE

DRIVERS = ["oni", "wwv", "qbo30", "qbo50"]
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def crps_ensemble(x, y):
    """x (N, m, D) samples, y (N, D) truth -> (N, D) CRPS, exact for the m-member ensemble (sorted formula)."""
    x = np.sort(x, axis=1)
    m = x.shape[1]
    i = np.arange(1, m + 1)[None, :, None]
    return 2 / m ** 2 * ((x - y[:, None]) * (m * (y[:, None] < x) - i + 0.5)).sum(1)


def coverage90(x, y, p=0.9):
    """Truth inside the ensemble's central p range: the k-th lowest to k-th highest of m samples, k = (1-p)/2 (m+1).
    A perfect ensemble then holds the truth (m+1-2k)/(m+1) of the time (= p when (1-p)/2 (m+1) is whole, e.g.
    m = 199 for 90 % and 99 %); interpolated quantiles undercount (a perfect m = 100 ensemble scores 0.97 at 99 %)."""
    m = x.shape[1]
    k = max(1, int(round((1 - p) / 2 * (m + 1))))
    s = np.partition(x, [k - 1, m - k], axis=1)
    return (y >= s[:, k - 1]) & (y <= s[:, m - k])


def variogram_score(x, y, p=0.5, chunk=200):
    """x (N, m, H) samples, y (N, H) truth -> (N,) variogram score over all height pairs. Lower is better."""
    out = np.empty(len(y))
    for i in range(0, len(y), chunk):
        xs, ys = x[i:i + chunk], y[i:i + chunk]
        vy = np.abs(ys[:, :, None] - ys[:, None, :]) ** p
        vx = (np.abs(xs[:, :, :, None] - xs[:, :, None, :]) ** p).mean(1)
        out[i:i + chunk] = ((vy - vx) ** 2).sum((1, 2)) / 2
    return out


def gaussian_samples(x, n, m, rng):
    """x (R, D) physical training rows of one group -> (n, m, D) draws from their mean + full covariance."""
    mu, sd = x.mean(0), x.std(0) + 1e-9
    L = np.linalg.cholesky(np.corrcoef((x - mu) / sd, rowvar=False) + 1e-6 * np.eye(x.shape[1]))
    return clip_ranges(mu + (rng.standard_normal((n, m, x.shape[1])) @ L.T) * sd)


def group_keys(cond):
    """Grid point x calendar month x 2-hour solar-time bin, from the feature columns."""
    c = {k: cond[:, FEATURES.index(k)] for k in FEATURES}
    _, point = np.unique(np.round(np.stack([c["lat"], c["lon"]], 1), 3), axis=0, return_inverse=True)
    month = (np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    hbin = (np.arctan2(c["hour_sin"], c["hour_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    return point.ravel().astype(np.int64) * 144 + month * 12 + hbin


def physical_names():
    return [f"{v}_{int(h)}" for v in PROFILE for h in HEIGHTS] + SURFACE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--m", type=int, default=50)
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--calib", help="range calibration from tempest.calibrate.spread (outputs get a _cal suffix)")
    ap.add_argument("--first-test-year", type=int, help="score only from this year (keep the calibration year out)")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    ckpt = torch.load(a.model, map_location="cpu", weights_only=True)
    sampler = Sampler(ckpt, device=a.device)
    histories = [c.get("history") for c in ckpt.get("members", [ckpt])]
    ckpt = ckpt.get("members", [ckpt])[0]
    d = load_npz(a.data)
    cond, year = d["cond"], d["year"]
    held = (year > year.max() - ckpt["cfg"]["val_years"]) & (year >= (a.first_test_year or 0))
    cal = spread.load(a.calib)
    keys = group_keys(cond)

    tr = np.flatnonzero(~held)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    trk = keys[tr]
    va = rng.choice(np.flatnonzero(held), min(a.rows, int(held.sum())), replace=False)
    lo, hi = np.searchsorted(trk, keys[va], "left"), np.searchsorted(trk, keys[va], "right")
    ok = hi > lo
    va, lo, hi = va[ok], lo[ok], hi[ok]
    print(f"{len(va):,} held-out rows ({int((~ok).sum())} without a climatology group dropped), m = {a.m}", flush=True)

    draws = tr[lo[:, None] + (rng.random((len(va), a.m)) * (hi - lo)[:, None]).astype(np.int64)]  # (N, m)
    target = d["target"]
    truth = to_physical(target[va])
    clim = to_physical(target[draws.ravel()].reshape(*draws.shape, -1))

    gk = keys // 12  # grid point x month, no hour: monthly statistics like a reference atmosphere
    trg = tr[np.argsort(gk[tr], kind="stable")]
    gauss = np.empty_like(clim)
    for g in np.unique(gk[va]):
        rows = trg[np.searchsorted(gk[trg], g, "left"):np.searchsorted(gk[trg], g, "right")]
        rows = np.sort(rng.choice(rows, min(len(rows), 3000), replace=False))
        sel = np.flatnonzero(gk[va] == g)
        gauss[sel] = gaussian_samples(to_physical(target[rows]).astype(np.float64), len(sel), a.m, rng)

    rep = np.repeat(cond[va], a.m, axis=0)
    known = sampler.profiles(rep).reshape(len(va), a.m, -1)
    if cal:
        known = spread.apply(cal, known)
    dc = [FEATURES.index(k) for k in DRIVERS]
    rep[:, dc] = cond[draws.ravel()][:, dc]
    unknown = sampler.profiles(rep).reshape(len(va), a.m, -1)
    if cal:
        unknown = spread.apply(cal, unknown)

    res = pd.DataFrame({"column": physical_names()})
    sets = [("clim", clim), ("gauss", gauss), ("known", known), ("unknown", unknown)]
    n = len(HEIGHTS)
    vs = pd.DataFrame([{"var": v, **{f"vs_{name}": variogram_score(x[..., i * n:(i + 1) * n], truth[:, i * n:(i + 1) * n]).mean()
                                     for name, x in sets}} for i, v in enumerate(PROFILE)])
    for name in ("gauss", "known", "unknown"):
        vs[f"vs_skill_{name}"] = 1 - vs[f"vs_{name}"] / vs["vs_clim"]
    for name, x in sets:
        res[f"crps_{name}"] = crps_ensemble(x, truth).mean(0)
        res[f"cov90_{name}"] = coverage90(x, truth).mean(0)
        res[f"cov99_{name}"] = coverage90(x, truth, 0.99).mean(0)
    for name in ("gauss", "known", "unknown"):
        res[f"skill_{name}"] = 1 - res[f"crps_{name}"] / res["crps_clim"]
    stem = a.model.rsplit(".", 1)[0] + ("_cal" if cal else "")
    out = stem + ".score.csv"
    res.to_csv(out, index=False)

    rows = []
    for i, v in enumerate(PROFILE):
        for b0, b1 in BANDS:
            sel = np.zeros(len(res), bool)
            sel[i * len(HEIGHTS):(i + 1) * len(HEIGHTS)] = (HEIGHTS >= b0) & (HEIGHTS < b1)
            rows.append((v, f"{b0 / 1000:g}-{min(b1, 18000) / 1000:g} km", res[sel]))
    rows += [(s, "surface", res[res.column == s]) for s in SURFACE]
    summary = pd.DataFrame([dict(var=v, band=b, crps_clim=r.crps_clim.mean(), crps_known=r.crps_known.mean(),
                                 skill_gauss=1 - r.crps_gauss.mean() / r.crps_clim.mean(),
                                 skill_known=1 - r.crps_known.mean() / r.crps_clim.mean(),
                                 skill_unknown=1 - r.crps_unknown.mean() / r.crps_clim.mean(),
                                 cov90_known=r.cov90_known.mean(), cov90_unknown=r.cov90_unknown.mean(),
                                 cov90_clim=r.cov90_clim.mean(), cov90_gauss=r.cov90_gauss.mean(),
                                 cov99_known=r.cov99_known.mean(), cov99_unknown=r.cov99_unknown.mean(),
                                 cov99_clim=r.cov99_clim.mean(), cov99_gauss=r.cov99_gauss.mean()) for v, b, r in rows])
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(summary.to_string(index=False))
        print("\nprofile shape (variogram score, skill vs climatology):")
        print(vs.to_string(index=False))
    print(f"wrote {out}")
    rdir = stem + "_report"
    report(rdir, res, vs, (known < truth[:, None]).sum(1), (truth[:3], known[:3]), histories, PROFILE, HEIGHTS, SURFACE)
    summary.to_csv(f"{rdir}/summary.csv", index=False)
    print(f"wrote charts to {rdir}/")


if __name__ == "__main__":
    main()
