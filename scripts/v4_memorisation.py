"""V4: does the generator memorise training days? For 2024-25 DAY rows of the 21-level data: distance (standardised physical profile, all 179 columns, per-column scale = the group's training spread) of
 (a) each generated sample, (b) the truth of the row, (c) each training day (leave-one-out) to the nearest training day of the SAME group (grid point x month x 2-hour bin, years <= 2023, up to 800 days).
Memorisation would show as generated samples much closer to training days than real days are (a << b, c). Reports the median distances, the share of samples closer than the 5th percentile of the training-to-training distance, and the same for the range-calibrated samples.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/v4_memorisation.py
"""
import numpy as np
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.scoring.score import group_keys


def nn_dist(x, pool, sd):
    """x (A, D), pool (P, D) -> distance to the nearest pool row, each column divided by sd."""
    a, b = x / sd, pool / sd
    d2 = (a ** 2).sum(1)[:, None] + (b ** 2).sum(1)[None] - 2.0 * a @ b.T
    return np.sqrt(np.maximum(d2.min(1), 0.0))


def main():
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    d = load_npz("data/train/pilot80_l21_day_dpd.npz")
    model, calib = "models/l3_h_l21.pt", "models/l3_h_l21.calib2021.npz"
    s = Sampler(torch.load(model, map_location="cpu", weights_only=True))
    cal = spread.load(calib, model)
    year, keys = np.asarray(d["year"]), group_keys(np.asarray(d["cond"]))
    va = np.sort(rng.choice(np.flatnonzero(year >= 2024), 200, replace=False))
    cond = np.asarray(d["cond"])[va]
    m = 199
    samp = np.empty((len(va), m, d["target"].shape[1]), np.float32)
    for i in range(0, len(va), 50):
        sl = slice(i, i + 50)
        samp[sl] = s.profiles(np.repeat(cond[sl], m, axis=0)).reshape(len(cond[sl]), m, -1)
    calx = spread.apply(cal, samp)
    res = {"raw": [], "cal": [], "truth": [], "train_loo": []}
    for r, k in enumerate(keys[va]):
        pool_idx = np.flatnonzero((keys == k) & (year <= 2023))
        if len(pool_idx) < 60:
            continue
        pool_idx = rng.choice(pool_idx, min(len(pool_idx), 800), replace=False)
        pool = to_physical(np.asarray(d["target"][pool_idx])).astype(np.float64)
        sd = pool.std(0) + 1e-6
        res["truth"].append(nn_dist(to_physical(np.asarray(d["target"][va[r]]))[None].astype(np.float64), pool, sd)[0])
        res["raw"].append(nn_dist(samp[r, :60].astype(np.float64), pool, sd))
        res["cal"].append(nn_dist(calx[r, :60].astype(np.float64), pool, sd))
        sub = pool[:200]
        dd = ((sub / sd)[:, None, :] - (pool / sd)[None]) ** 2
        dd = dd.sum(-1)
        dd[np.arange(len(sub)), np.arange(len(sub))] = np.inf
        res["train_loo"].append(np.sqrt(dd.min(1)))
    tr = np.array(res["truth"])
    loo = np.concatenate(res["train_loo"])
    p5 = np.percentile(loo, 5)
    print(f"{len(tr)} rows with a group of >= 60 training days")
    print(f"nearest-training-day distance (standardised, {len(loo)} leave-one-out training days): median {np.median(loo):.2f}, 5th percentile {p5:.2f}")
    print(f"real held-out days (2024-25 truth):  median {np.median(tr):.2f}, 5th percentile {np.percentile(tr, 5):.2f}")
    for k, nm in (("raw", "generated, raw network"), ("cal", "generated, range-calibrated")):
        x = np.concatenate(res[k])
        print(f"{nm:30} median {np.median(x):.2f}, 5th percentile {np.percentile(x, 5):.2f}, share closer than the training 5th percentile {np.mean(x < p5):.3f}, share closer than 0.5 x that {np.mean(x < 0.5 * p5):.4f}")


if __name__ == "__main__":
    main()
