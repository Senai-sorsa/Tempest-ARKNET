"""F-27: calibrate the vertical-wind head. The head is trained on TRUE profiles but used on generated, range-calibrated ones, and its spread is never mapped.
Fit a range-calibration table for w (same method as the generator's: spread.parts / table) on 2021-23 rows whose head inputs are generated profiles,
then score raw vs calibrated on 2024-25 (CRPS, 99 % coverage, spread/skill).

    PYTHONPATH=. python scripts/whead_calib.py --model MODEL.pt --calib CALIB.npz --data D.npz --w W.npz --head models/whead.pt [--fit-rows 2500] [--rows 1500]
Writes <head>.wcalib2021.npz (only a new file; the head and the tool are untouched until the export flag is used)."""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.sample import Sampler
from tempest.generator.train import load_npz
from tempest.scoring.score import coverage90, crps_ensemble

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
for k in ("model", "calib", "data", "w", "head"):
    ap.add_argument("--" + k, required=True)
ap.add_argument("--fit-rows", type=int, default=2500)
ap.add_argument("--rows", type=int, default=1500)
ap.add_argument("--m", type=int, default=199)
a = ap.parse_args()
torch.manual_seed(0)
rng = np.random.default_rng(0)
gen = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device="cpu")
head = Sampler(torch.load(a.head, map_location="cpu", weights_only=True), device="cpu")
cal = spread.load(a.calib, a.model)
d = load_npz(a.data)
w = np.load(a.w)["w"]
year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
ok = np.isfinite(w).all(1)


def draw(rows):
    n = len(rows)
    rep = np.repeat(cond[rows], a.m, 0)
    phys = spread.apply(cal, gen.profiles(rep).reshape(n, a.m, -1)).reshape(n * a.m, -1)
    return head(np.concatenate([rep, phys], 1)).reshape(n, a.m, -1)


fit_rows = np.sort(rng.choice(np.flatnonzero(ok & (year >= 2021) & (year <= 2023)), a.fit_rows, replace=False))
zs, us = zip(*[spread.parts(draw(fit_rows[i:i + 250]), w[fit_rows[i:i + 250]], rng=rng) for i in range(0, len(fit_rows), 250)])
tab = spread.table(np.concatenate(zs), np.concatenate(us))
tab["m"] = np.array(a.m)
out = a.head.rsplit(".", 1)[0] + ".wcalib2021.npz"
np.savez(out, **tab)
print("wrote", out)
test = np.sort(rng.choice(np.flatnonzero(ok & (year >= 2024) & (year <= 2025)), a.rows, replace=False))
raw = np.concatenate([draw(test[i:i + 250]) for i in range(0, len(test), 250)])
cald = spread.apply(tab, raw, clip=False)
truth = w[test]
rec = np.flatnonzero(ok & (year >= 2009) & (year < 2024))
clim = w[rec[rng.integers(0, len(rec), (len(test), a.m))]]               # coarse climatology (all months), the same for every row: only used as the skill reference
cc = crps_ensemble(clim, truth)
bands = {"0-1 km": slice(0, 9), "1-5 km": slice(9, 22), "5-12 km": slice(22, 36), "12-18 km": slice(36, 44)}
rows_out = []
for name, x in (("raw", raw), ("calibrated", cald)):
    cr, cov = crps_ensemble(x, truth), coverage90(x, truth, 0.99).astype(float)
    sd, rmse = np.sqrt(x.var(1, ddof=1).mean(0)), np.sqrt(((x.mean(1) - truth) ** 2).mean(0))
    for b, s in bands.items():
        rows_out.append(dict(version=name, band=b, crps_cm_s=100 * cr[:, s].mean(), cov99=cov[:, s].mean(), spread_over_skill=sd[s].mean() / rmse[s].mean()))
t = pd.DataFrame(rows_out)
print(t.round(4).to_string(index=False))
t.to_csv(a.head.rsplit(".", 1)[0] + "_wcalib_eval.csv", index=False)
