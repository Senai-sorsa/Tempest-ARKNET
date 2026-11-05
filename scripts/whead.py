"""Train and evaluate the vertical-wind head (PHASED_PLAN 3.2).

    PYTHONPATH=. python scripts/whead.py train --data data/train/pilot80_dpd.npz --w data/train/pilot80_w.npz --out models/whead.pt
    PYTHONPATH=. python scripts/whead.py eval  --model models/generator_80_p2c.pt --calib models/generator_80_p2c.calib2021.npz \\
                                               --data data/train/pilot80_dpd.npz --w data/train/pilot80_w.npz --head models/whead.pt

train: rows 1991-2023 with w (validation = 2021-23, so the head sees nothing from 2024-25), inputs = generator features +
the TRUE (station-corrected) physical profile of the row. eval: on 2024-25, the realistic path: m = 199 profiles from the
generator, one w per profile from the head, against ERA5's w. Reports, per height band, CRPS skill vs the recent
15-year climatology of w (same grid point, month and hour bin), MAE of the median, 99 % coverage and spread/skill,
with day-block 95 % intervals. Expect skill near zero (vertical wind a month ahead is not predictable); the value is a
correct, coherent spread.
"""
import argparse
import tomllib

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.features import FEATURES
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz, train
from tempest.output.whead import head_inputs
from tempest.profiles.to_heights import HEIGHTS
from tempest.scoring.score import coverage90, crps_ensemble, group_keys

BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def physical_rows(target, idx, chunk=200_000):
    return np.concatenate([to_physical(np.asarray(target[idx[i:i + chunk]])) for i in range(0, len(idx), chunk)]).astype(np.float32)


def cmd_train(a):
    d = load_npz(a.data)
    w = np.load(a.w)["w"]
    year = np.asarray(d["year"])
    ok = np.isfinite(w).all(1) & (year >= 1991) & (year <= a.max_year)
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(np.flatnonzero(ok), min(a.rows, int(ok.sum())), replace=False))
    cond = np.asarray(d["cond"][idx], np.float32)
    x = np.concatenate([cond, physical_rows(d["target"], idx)], 1)
    names = list(FEATURES) + [f"x{i}" for i in range(179)]
    cfg = dict(tomllib.load(open(a.config, "rb")), steps=a.steps, noise_dim=16, val_years=a.val_years, step_weight=0.0, es_weight=0.1, eval_every=500)
    cfg.pop("members", None)
    train(x, w[idx].astype(np.float32), year[idx], cfg, out=a.out, meta=dict(cond_names=names), members=2)
    print("wrote", a.out)


def cmd_eval(a):
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    gen = Sampler(torch.load(a.model, map_location="cpu", weights_only=True))
    head = Sampler(torch.load(a.head, map_location="cpu", weights_only=True))
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    w = np.load(a.w)["w"]
    year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
    keys = group_keys(cond)
    first = 2024
    test = np.flatnonzero((year >= first) & (year <= 2025) & np.isfinite(w).all(1))
    rows = np.sort(rng.choice(test, a.rows, replace=False))
    rec = np.flatnonzero((year >= first - 15) & (year < first) & np.isfinite(w).all(1))
    rec = rec[np.argsort(keys[rec], kind="stable")]
    lo, hi = np.searchsorted(keys[rec], keys[rows], "left"), np.searchsorted(keys[rec], keys[rows], "right")
    ok = hi > lo
    rows, lo, hi = rows[ok], lo[ok], hi[ok]
    m = a.m
    clim = w[rec[lo[:, None] + (rng.random((len(rows), m)) * (hi - lo)[:, None]).astype(np.int64)]]
    n = len(rows)
    rep = np.repeat(cond[rows], m, 0)
    phys = spread.apply(cal, gen.profiles(rep).reshape(n, m, -1)).reshape(n * m, -1)
    ws = head(np.concatenate([rep, phys], 1)).reshape(n, m, -1)
    truth = w[rows]
    day = year[rows].astype(np.int64) * 1000 + np.round(np.arctan2(cond[rows, FEATURES.index("doy_sin")], cond[rows, FEATURES.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25).astype(np.int64)
    _, inv = np.unique(day, return_inverse=True)
    nd = inv.max() + 1
    boot = np.vstack([np.ones(nd), np.random.default_rng(0).multinomial(nd, np.full(nd, 1 / nd), 500)])
    cnt = np.bincount(inv, minlength=nd)
    daymean = lambda v: (boot @ np.stack([np.bincount(inv, v[:, g], nd) for g in range(v.shape[1])], 1)) / (boot @ cnt)[:, None]
    rows_out = []
    cr_m, cr_c = crps_ensemble(ws, truth), crps_ensemble(clim, truth)
    cov = coverage90(ws, truth, 0.99).astype(float)
    mae_m, mae_c = np.abs(np.median(ws, 1) - truth), np.abs(np.median(clim, 1) - truth)
    sd = np.sqrt(ws.var(1, ddof=1).mean(0) * (m + 1) / m)
    rmse = np.sqrt(((ws.mean(1) - truth) ** 2).mean(0))
    for b0, b1 in BANDS:
        s = (HEIGHTS >= b0) & (HEIGHTS < b1)
        mat = np.stack([cr_m[:, s].mean(1), cr_c[:, s].mean(1), cov[:, s].mean(1), mae_m[:, s].mean(1), mae_c[:, s].mean(1)], 1)
        bm = daymean(mat)
        skill = 1 - bm[:, 0] / bm[:, 1]
        f = lambda v: f"{v[0]:.4f} [{np.percentile(v[1:], 2.5):.4f}, {np.percentile(v[1:], 97.5):.4f}]"
        rows_out.append(dict(band=f"{b0 / 1000:g}-{min(b1, 18000) / 1000:g} km", skill_vs_clim15=f(skill), cov99=f(bm[:, 2]), mae_model_cm_s=f"{100 * bm[0, 3]:.2f}",
                             mae_clim15_cm_s=f"{100 * bm[0, 4]:.2f}", spread_over_skill=f"{sd[s].mean() / rmse[s].mean():.2f}"))
    t = pd.DataFrame(rows_out)
    with pd.option_context("display.width", 200):
        print(t.to_string(index=False))
    t.to_csv(a.head.rsplit(".", 1)[0] + "_eval.csv", index=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", required=True)
    t.add_argument("--w", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--config", default="configs/generator.toml")
    t.add_argument("--rows", type=int, default=2_000_000)
    t.add_argument("--steps", type=int, default=4000)
    t.add_argument("--max-year", type=int, default=2023, help="last year used (training + early stopping); 2020 with --val-years 2 keeps 2021-23 free for the w range map (F-27 clean version)")
    t.add_argument("--val-years", type=int, default=3)
    e = sub.add_parser("eval")
    e.add_argument("--model", required=True)
    e.add_argument("--calib", required=True)
    e.add_argument("--data", required=True)
    e.add_argument("--w", required=True)
    e.add_argument("--head", required=True)
    e.add_argument("--rows", type=int, default=2000)
    e.add_argument("--m", type=int, default=199)
    a = ap.parse_args()
    (cmd_train if a.cmd == "train" else cmd_eval)(a)


if __name__ == "__main__":
    main()
