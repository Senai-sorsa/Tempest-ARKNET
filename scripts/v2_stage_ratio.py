"""V2 follow-up: where does the flat 10 -> 200 m wind profile come from? Median ratio of speed at 50 / 100 / 200 m to the 10 m speed, by 10 m speed class, on 2024-25 DAY rows of the 21-level data, for
 truth (the training target of those rows), the RAW network samples, the range-CALIBRATED samples, and calibrated + SHUFFLE (template cell 8) + shear map (the shipped stack, without the lapse map).

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/v2_stage_ratio.py
"""
import numpy as np
import torch

from tempest.calibrate import shear_map, shuffle as shuf, spread
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.score import group_keys

CLASSES = [(0, 3), (3, 6), (6, 10), (10, 40)]
IZ = {50: 1, 100: 2, 200: 4}          # indices into HEIGHTS 10, 50, 100, 150, 200


def ratios(x, name):
    n = len(HEIGHTS)
    iu, iv = PROFILE.index("u") * n, PROFILE.index("v") * n
    sp = np.hypot(x[..., iu:iu + n], x[..., iv:iv + n]).reshape(-1, n)
    s10 = sp[:, 0]
    cells = []
    for lo, hi in CLASSES:
        sel = (s10 >= lo) & (s10 < hi) & (s10 > 0.3)
        cells.append(" ".join(f"{np.median(sp[sel, i] / s10[sel]):5.2f}" for i in IZ.values()) + f" (n{sel.sum()})" if sel.sum() > 30 else "-")
    print(f"  {name:36} " + " | ".join(cells))


def main():
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    d = load_npz("data/train/pilot80_l21_day_dpd.npz")
    model, calib, smap = "models/l3_h_l21.pt", "models/l3_h_l21.calib2021.npz", "models/l3_h_l21.shearmap2021_cell8.npz"
    s = Sampler(torch.load(model, map_location="cpu", weights_only=True))
    cal = spread.load(calib, model)
    idx = np.sort(rng.choice(np.flatnonzero(d["year"] >= 2024), 1200, replace=False))
    truth = to_physical(np.asarray(d["target"][idx]))
    cond = np.asarray(d["cond"])[idx]
    m = 50
    raw = np.empty((len(idx), m, truth.shape[1]), np.float32)
    for i in range(0, len(idx), 300):
        sl = slice(i, i + 300)
        raw[sl] = s.profiles(np.repeat(cond[sl], m, axis=0)).reshape(len(cond[sl]), m, -1)
    cal_x = spread.apply(cal, raw) if cal["m"] == m else None
    print("columns per 10 m speed class: " + " | ".join(f"{lo}-{hi} m/s" for lo, hi in CLASSES) + "; ratios of speed at 50 / 100 / 200 m to the 10 m speed (median)")
    ratios(truth[:, None, :], "truth (training target)")
    ratios(raw, "raw network")
    if cal_x is None:                                       # the calibration table was fitted with m = 199: draw 199
        raw199 = np.empty((len(idx), 199, truth.shape[1]), np.float32)
        for i in range(0, len(idx), 100):
            sl = slice(i, i + 100)
            raw199[sl] = s.profiles(np.repeat(cond[sl], 199, axis=0)).reshape(len(cond[sl]), 199, -1)
        cal_x = spread.apply(cal, raw199)
    ratios(cal_x, "range calibration")
    keys = group_keys(np.asarray(d["cond"]))
    tpl = shuf.group_template(d["target"], keys, d["year"], idx, cal_x.shape[1], rng, 2024, cell=8, n_lon=shuf.grid_n_lon(d["cond"]))
    sh = shuf.apply(cal_x, tpl)
    ratios(sh, "calibration + shuffle")
    ratios(shear_map.apply(dict(np.load(smap)), sh), "calibration + shuffle + shear map")


if __name__ == "__main__":
    main()
