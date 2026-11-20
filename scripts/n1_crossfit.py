"""N1 (New_Plan 10.4): cross-fitted generator members. The p2f recipe (configs/generator_p2f.toml), data 1991-2023, but each of the 4
members leaves out its own 4 years (train.holdout_years: 2-year blocks of 2008-2023) and trains a fixed 6000 steps (cfg holdout_fold).
Range map: tempest.calibrate.spread parts / table, each member sampled alone on rows of its own held-out years, pooled into one table
(<out stem>.calibcf.npz), so every fit row is unseen by the member that draws it.
shortcut: one pooled map fitted on single members, applied to the 4-member pool (score / sonde take one map); a map per member needs
per-member apply in score.py and sonde.py, worth it only if the coverage rule is what fails.
Step 1 of the plan needs no run: in data/phase2_train_p2f.log every p2f member's best validation step is the last one (6000), so p2f
already is "data <= 2020, fixed steps" (difference 0).
    PYTHONPATH=. .venv/Scripts/python -W ignore -u scripts/n1_crossfit.py --seed 0 --out models/generator_80_n1cf.pt
Runner: scripts/gpu_n1_crossfit.sh. Verdict: new_plan_kit/b5_crossfit.py.
"""
import argparse
import os
import subprocess
import time
import tomllib

import numpy as np
import torch

from tempest.calibrate.spread import LEVELS, model_hash, parts, table
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import holdout_years, load_npz, train

DATA, K, LAST = "data/train/pilot80_dpd.npz", 4, 2023
assert sorted(y for k in range(K) for y in holdout_years(LAST, k)) == list(range(LAST - 15, LAST + 1)), "folds must split the last 16 years"


def free_gb():
    return int(subprocess.check_output(["powershell", "-NoProfile", "-c", "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB)"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0, help="member k trains with seed + k (p2f: 0, p2f_s1: 100)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", type=int, default=60000)
    ap.add_argument("--config", default="configs/generator_p2f.toml", help="generator recipe (28.8: configs/s25/gen/base_s0.toml = the c4w paired base)")
    ap.add_argument("--data", default=DATA, help="training rows (28.8: data/train/pilot80_l21_all24_dpd.npz, as scripts/s25_arm.sh)")
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--same-fold", type=int, default=-1, choices=(-1, 0, 1, 2, 3), help="UR8 control (New_Plan 17.2): every member holds out the SAME fold's 4 years "
                    "(no cross-fitting, same amount of data; fold 0 = 2008-09 + 2016-17 keeps 2021-23 in training), range map from that fold's rows; -1 = cross-fit as before")
    a = ap.parse_args()
    fold_of = (lambda k: k) if a.same_fold < 0 else (lambda k: a.same_fold)
    d = load_npz(a.data)
    if not os.path.exists(a.out):
        with open(a.config, "rb") as f:
            cfg = tomllib.load(f)
        cfg.pop("members", None)
        year = np.asarray(d["year"])
        ok = (year >= 1991) & (year <= LAST)
        keep = slice(np.flatnonzero(ok)[0], np.flatnonzero(ok)[-1] + 1)   # a memory-mapped slice (the kept years are not contiguous: a row copy would hold 4.4 GB RAM)
        year = np.where(ok, year, 0)[keep]                               # year 0 = not a training row (train.split, holdout_fold branch)
        meta = {k: [str(x) for x in d[k]] for k in ("cond_names", "target_names")}
        meta["rh_target"] = str(d["rh_target"])
        mem = []
        for k in range(K):
            part = f"{a.out}.fold{k}"                           # one file per finished fold: a GPU fault (CUBLAS error at step 5800, 2026-11-11) costs one fold, not all
            if os.path.exists(part):
                mem.append(torch.load(part, map_location="cpu", weights_only=True))
                continue
            while free_gb() < 6:                                # 2 GB floor + ~4 GB fold peak (rows already loaded); was 10, stalled s100 at 6.7 GB free 2026-11-19
                time.sleep(30)
            print(f"fold {k}: held-out years {holdout_years(LAST, fold_of(k))}", flush=True)
            mem.append(train(d["cond"][keep], d["target"][keep], year, {**cfg, "seed": a.seed + k, "holdout_fold": fold_of(k)}, meta=meta, out=part))
        torch.save(dict(members=mem), a.out + ".part")
        os.replace(a.out + ".part", a.out)
    sampler = Sampler(torch.load(a.out, map_location="cpu", weights_only=True))
    allm, rng, zs, us = sampler.members, np.random.default_rng(0), [], []
    torch.manual_seed(0)
    for k in range(K):
        sampler.members = [allm[k]]
        rows = np.sort(rng.choice(np.flatnonzero(np.isin(d["year"], holdout_years(LAST, fold_of(k)))), a.rows // K, replace=False))
        truth = to_physical(np.asarray(d["target"][rows]))
        for i in range(0, len(rows), 1000):
            z, u = parts(sampler.profiles(np.repeat(d["cond"][rows[i:i + 1000]], a.m, 0)).reshape(-1, a.m, truth.shape[1]), truth[i:i + 1000], rng=rng)
            zs.append(z), us.append(u)
    t = table(np.concatenate(zs), np.concatenate(us))
    out = a.out.rsplit(".", 1)[0] + ".calibcf.npz"
    np.savez(out, **t, levels=LEVELS, fit_year=LAST, m=a.m, model_sha=model_hash(a.out))
    print(f"range map from {a.rows // K * K:,} held-out rows; 99 % range ends scale by median {np.median(t['qu'][0] / t['qz'][0]):.2f} (low) / "
          f"{np.median(t['qu'][-1] / t['qz'][-1]):.2f} (high); wrote {out}", flush=True)


if __name__ == "__main__":
    main()
