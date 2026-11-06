"""IL-86: full PIT recalibration for the climate generator. Fits one probability map per variable x height band (and per surface field) on 2021-23 rows, with the calibrated samples of the
OPERATIONAL kind (unknown drivers: ONI/WWV/QBO copied from earlier years' rows of the same group), writes <model>.pitrecal2021.npz for `score --pit-recal` / `diagnose --pit-recal`.
    PYTHONPATH=. python scripts/il86_fit.py MODEL.pt CALIB.npz DATA.npz [--rows 4000]"""
import argparse

import numpy as np
import torch

from tempest.calibrate import pit_recal, spread
from tempest.generator.features import FEATURES, drivers
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.scoring.score import band_masks, group_keys

ap = argparse.ArgumentParser()
ap.add_argument("model")
ap.add_argument("calib")
ap.add_argument("data")
ap.add_argument("--rows", type=int, default=4000)
ap.add_argument("--m", type=int, default=199)
a = ap.parse_args()
rng = np.random.default_rng(0)
torch.manual_seed(0)
s = Sampler(torch.load(a.model, map_location="cpu", weights_only=True))
cal = spread.load(a.calib, a.model)
d = load_npz(a.data)
year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
keys = group_keys(cond)
idx = np.sort(rng.choice(np.flatnonzero((year >= 2021) & (year <= 2023)), a.rows, replace=False))
truth = to_physical(np.asarray(d["target"][idx]))
tr = np.flatnonzero(year < 2021)
tr = tr[np.argsort(keys[tr], kind="stable")]
lo, hi = np.searchsorted(keys[tr], keys[idx], "left"), np.searchsorted(keys[tr], keys[idx], "right")
draws = tr[np.minimum(lo[:, None] + (rng.random((len(idx), a.m)) * np.maximum(hi - lo, 1)[:, None]).astype(np.int64), len(tr) - 1)]
dc = [FEATURES.index(k) for k in drivers()]
x = np.empty((len(idx), a.m, truth.shape[1]), np.float32)
for i in range(0, len(idx), 400):
    sl = slice(i, i + 400)
    rep = np.repeat(cond[idx[sl]], a.m, 0)
    rep[:, dc] = cond[draws[sl].ravel()][:, dc]
    x[sl] = spread.apply(cal, s.profiles(rep).reshape(len(idx[sl]), a.m, -1))
groups = np.zeros(truth.shape[1], int)
for g, (_, _, sel) in enumerate(band_masks()):
    groups[sel] = g
t = pit_recal.fit(x, truth, groups, rng)
out = a.model.rsplit(".", 1)[0] + ".pitrecal2021.npz"
np.savez(out, **t, fit_from=2021, fit_to=2023)
print("wrote", out)
