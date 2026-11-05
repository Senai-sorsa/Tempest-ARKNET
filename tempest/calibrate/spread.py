"""Range calibration: stretch each output's samples so that p % ranges hold p % of real values, at every p.

    python -m tempest.calibrate.spread --model models/generator_pilot_st2.pt --data data/train/pilot_st.npz
                                       [--year 2023] [--rows 20000] [--m 100]

Per output column, each sample is written as a distance from its row's median, in units of that row's 5-95 %
half-width: z = (x - median) / halfwidth. On a held-out year (default: the first validation year, never trained
on) the same is done for the truth: u = (y - median) / halfwidth. If the model is well calibrated, z and u have
the same distribution; the fix maps z's quantiles onto u's (separately for the low and high side, so skew is
learned too). The map is monotone per column, so each row's samples keep their rank order and therefore their
joint shape across heights (ensemble copula coupling). Writes <model>.calib.npz, used by score/sonde --calib.
Test on other years than the fit year (score/sonde --first-test-year), or coverage is flattered.
"""
import argparse

import numpy as np
import torch

from tempest.generator.sample import Sampler, clip_ranges, to_physical
from tempest.generator.train import load_npz

# dense in the tails, where 99 % ranges live
LEVELS = np.r_[0.0005, 0.001, 0.0025, 0.005, 0.0075, np.linspace(0.01, 0.99, 99), 0.9925, 0.995, 0.9975, 0.999, 0.9995]


def _standardise(x):
    """x (N, m, D) -> z (N, m, D), median (N, 1, D), halfwidth (N, 1, D)."""
    lo, med, hi = np.quantile(x, [0.05, 0.5, 0.95], axis=1, keepdims=True)
    hw = (hi - lo) / 2
    hw = np.maximum(hw, 0.1 * np.median(hw, axis=0, keepdims=True) + 1e-6)  # RH clipped at 0/100 can have ~zero width
    return (x - med) / hw, med, hw


def parts(samples, truth, keep=20, rng=None):
    """One batch -> (z of `keep` random members per row, (keep*N, D)), (u of the truth, (N, D)). Fitting from parts
    keeps memory small: the truth's tails need many rows, the samples' tails are well filled by a few per row."""
    z, med, hw = _standardise(samples.astype(np.float64))
    u = (truth.astype(np.float64) - med[:, 0]) / hw[:, 0]
    pick = (rng or np.random.default_rng(0)).choice(z.shape[1], min(keep, z.shape[1]), replace=False)
    return z[:, pick].reshape(-1, z.shape[-1]).astype(np.float32), u.astype(np.float32)


def fit(samples, truth, keep=20):
    """samples (N, m, D), truth (N, D) physical -> table {qz, qu} (len(LEVELS), D). Use the same m as when applying."""
    z, u = parts(samples, truth, keep)
    return dict(qz=np.quantile(z, LEVELS, axis=0), qu=np.quantile(u, LEVELS, axis=0))


def table(z, u, groups=None):
    """Quantile table from parts(). groups (D,): columns with the same id share one map, pooled, for small
    fit sets (e.g. one year of balloons) where a single column's 99 % tail is too thin to estimate."""
    if groups is None:
        return dict(qz=np.quantile(z, LEVELS, axis=0), qu=np.quantile(u, LEVELS, axis=0))
    qz, qu = np.empty((len(LEVELS), z.shape[1])), np.empty((len(LEVELS), z.shape[1]))
    for g in np.unique(groups):
        c = groups == g
        qz[:, c], qu[:, c] = np.quantile(z[:, c], LEVELS)[:, None], np.quantile(u[:, c], LEVELS)[:, None]
    return dict(qz=qz, qu=qu)


def apply(table, samples, clip=True):
    """samples (N, m, D) physical -> calibrated copy. Beyond the outer knots the end slope is extended. clip=False skips the
    179-column RH range rule (for other column layouts, e.g. the profile-only residual model)."""
    if "m" in table and int(table["m"]) != samples.shape[1]:  # the 5-95 % width a map is fitted on depends on m
        raise ValueError(f"calibration fitted with m = {int(table['m'])}, applied to m = {samples.shape[1]}")
    z, med, hw = _standardise(samples.astype(np.float64))
    qz, qu = table["qz"], table["qu"]
    out = np.empty_like(z)
    for j in range(z.shape[-1]):
        a, b, zj = qz[:, j], qu[:, j], z[..., j]
        a = np.maximum.accumulate(a + np.arange(len(a)) * 1e-9)  # strictly increasing knots for interp
        y = np.interp(zj, a, b)
        lo_s = (b[4] - b[0]) / max(a[4] - a[0], 1e-9)
        hi_s = (b[-1] - b[-5]) / max(a[-1] - a[-5], 1e-9)
        y = np.where(zj < a[0], b[0] + (zj - a[0]) * lo_s, y)
        out[..., j] = np.where(zj > a[-1], b[-1] + (zj - a[-1]) * hi_s, y)
    res = (med + out * hw).astype(samples.dtype)
    return clip_ranges(res) if clip else res


def model_hash(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()[:16]


def load(path, model=None):
    """Load a calibration file; refuse it if it records a different model than `model` (files without a hash load as before)."""
    if not path:
        return None
    cal = dict(np.load(path))
    if model and "model_sha" in cal and str(cal["model_sha"]) != model_hash(model):
        raise SystemExit(f"{path} was fitted for a different model than {model}; refit it with tempest.calibrate.spread")
    return cal


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--year", type=int, help="last fit year (default: first validation year)")
    ap.add_argument("--from-year", type=int, help="fit on from-year..year (default: just year); several years teach "
                    "the map year-to-year swings that one year cannot show (earlier years are training years)")
    ap.add_argument("--rows", type=int, default=30000)
    ap.add_argument("--m", type=int, default=199, help="samples per row; use the same m when scoring/applying")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--drawn-drivers", action="store_true", help="fit on samples whose ENSO/QBO/solar inputs are copied "
                    "from earlier years' rows of the same place/month/hour group, as score's 'unknown' set and the tool use")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)  # the generator draws its noise with torch; unseeded, reruns differ by ~0.001 skill
    ckpt = torch.load(a.model, map_location="cpu", weights_only=True)
    sampler = Sampler(ckpt, device=a.device)
    d = load_npz(a.data)
    year = d["year"]
    fy = a.year or int(year.max()) - ckpt.get("members", [ckpt])[0]["cfg"]["val_years"] + 1
    rows = np.sort(rng.choice(np.flatnonzero((year >= (a.from_year or fy)) & (year <= fy)), a.rows, replace=False))
    truth = to_physical(np.asarray(d["target"][rows]))
    cond = d["cond"]
    if a.drawn_drivers:
        from tempest.generator.features import FEATURES, drivers
        from tempest.scoring.score import group_keys  # late import: score imports this module
        keys = group_keys(np.asarray(cond))
        tr = np.flatnonzero(year < (a.from_year or fy))
        tr = tr[np.argsort(keys[tr], kind="stable")]
        lo, hi = np.searchsorted(keys[tr], keys[rows], "left"), np.searchsorted(keys[tr], keys[rows], "right")
        assert (hi > lo).all(), "a fit row has no earlier-year group to draw drivers from"
        draws = tr[lo[:, None] + (rng.random((len(rows), a.m)) * (hi - lo)[:, None]).astype(np.int64)]
        dc = [FEATURES.index(k) for k in drivers()]

    def inputs(i):
        rep = np.repeat(cond[rows[i:i + 1000]], a.m, 0)
        if a.drawn_drivers:
            rep[:, dc] = cond[draws[i:i + 1000].ravel()][:, dc]
        return rep
    zs, us = zip(*[parts(sampler.profiles(inputs(i)).reshape(-1, a.m, truth.shape[1]), truth[i:i + 1000], rng=rng)
                   for i in range(0, len(rows), 1000)])
    t = table(np.concatenate(zs), np.concatenate(us))
    out = a.model.rsplit(".", 1)[0] + (f".calib{a.from_year}" if a.from_year else ".calib") + ("drawn" if a.drawn_drivers else "") + ".npz"
    np.savez(out, **t, levels=LEVELS, fit_year=fy, m=a.m, model_sha=model_hash(a.model))
    print(f"fit on {len(rows):,} rows of {a.from_year or fy}-{fy}, m = {a.m}; 99 % range ends scale by median "
          f"{np.median(t['qu'][0] / t['qz'][0]):.2f} (low) / {np.median(t['qu'][-1] / t['qz'][-1]):.2f} (high); wrote {out}")


if __name__ == "__main__":
    main()
