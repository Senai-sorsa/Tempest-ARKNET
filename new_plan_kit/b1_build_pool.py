"""Block 1, GPU job 1: the shared sample pool. One draw of the shipped network on dev-test rows (2024-25), kept after every stage of the
fixed stack: range calibration -> shuffle -> shear map -> lapse map (the same calls, in the same order, as tempest/scoring/score.py).
Later CPU scripts read the file instead of sampling again (c2 premise, IL-128, G1-4, G1-2, gauss blend check).

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_build_pool.py                 # 1500 rows, about 1 GB on disk
    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_build_pool.py --rows 20 --out data/kit/pool_smoke.npz   # smoke test

Output data/kit/pool.npz: idx (rows of the dataset), truth (N, 179), cond (N, F), tpl_seed, and x_cal / x_shuf / x_smap / x_lmap, each (N, 199, 179) float32.
Columns: u 0-43, v 44-87, T 88-131, RH 132-175, then t2m, sp, rh2m (tempest.generator.sample.to_physical).
"""
import argparse
import os

import numpy as np

import kit_common as K

MODEL = "models/l3_c4w"
DATA = "data/train/pilot80_l21_day_dpd.npz"


def stages(model=MODEL + ".pt", data=DATA, rows=1500, years=(2024, 2025), m=199, seed=0, device=None, calib=None, smap=None, lmap=None, before_year=None, idx=None):
    """-> dict(idx, truth, cond, x_cal, x_shuf, x_smap, x_lmap, d). d is the open dataset (memory-mapped). Maps default to the shipped ones next to the model."""
    import torch
    from tempest.calibrate import lapse_map, shear_map, shuffle, spread
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    from tempest.scoring.score import group_keys
    stem = MODEL
    calib = calib or stem + ".calib2021.npz"
    smap = smap or stem + ".shearmap2021_cell8.npz"
    lmap = lmap or stem + ".lapsemap2021.npz"
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    d = load_npz(os.path.join(K.REPO, data))
    year = np.asarray(d["year"])
    assert years[1] <= 2025, "never 2026 data"
    if idx is None:
        pool = np.flatnonzero((year >= years[0]) & (year <= years[1]))
        idx = np.sort(rng.choice(pool, min(rows, len(pool)), replace=False))
    sampler = Sampler(torch.load(os.path.join(K.REPO, model), map_location="cpu", weights_only=True), device=device)
    cal = spread.load(os.path.join(K.REPO, calib), os.path.join(K.REPO, model))
    cond = np.asarray(d["cond"][idx])
    truth = to_physical(np.asarray(d["target"][idx]))
    x = np.empty((len(idx), m, truth.shape[1]), np.float32)
    for i in range(0, len(idx), 400):
        sl = slice(i, i + 400)
        x[sl] = spread.apply(cal, sampler.profiles(np.repeat(cond[sl], m, axis=0)).reshape(len(cond[sl]), m, -1))
    keys = group_keys(np.asarray(d["cond"]))
    tpl = shuffle.group_template(d["target"], keys, year, idx, m, np.random.default_rng(seed + 5), before_year or years[0], cell=8, n_lon=shuffle.grid_n_lon(d["cond"]))
    out = dict(idx=idx, truth=truth, cond=cond, x_cal=x, d=d, keys=keys)
    out["x_shuf"] = shuffle.apply(x, tpl)
    out["x_smap"] = shear_map.apply(dict(np.load(os.path.join(K.REPO, smap))), out["x_shuf"])
    out["x_lmap"] = lapse_map.apply(dict(np.load(os.path.join(K.REPO, lmap))), out["x_smap"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device")
    ap.add_argument("--out", default="data/kit/pool.npz")
    a = ap.parse_args()
    K.ram_gate(8.0)
    s = stages(rows=a.rows, seed=a.seed, device=a.device)
    for k in ("x_cal", "x_shuf", "x_smap", "x_lmap"):       # every stage keeps each column's value set up to the maps: the shuffle only re-orders
        assert s[k].shape == s["x_cal"].shape and np.isfinite(s[k]).all(), k
    assert np.allclose(np.sort(s["x_cal"], 1), np.sort(s["x_shuf"], 1)), "shuffle changed the marginals"
    os.makedirs(os.path.dirname(os.path.join(K.REPO, a.out)), exist_ok=True)
    np.savez(os.path.join(K.REPO, a.out), **{k: v for k, v in s.items() if k not in ("d", "keys")}, seed=a.seed)
    from tempest.scoring.score import crps_ensemble
    K.report("b1_build_pool", [f"pool {a.out}: {len(s['idx'])} rows 2024-25, m 199, seed {a.seed}",
                               "  mean CRPS over all columns by stage: " + ", ".join(f"{k[2:]} {crps_ensemble(s[k], s['truth']).mean():.4f}" for k in ("x_cal", "x_shuf", "x_smap", "x_lmap"))])


if __name__ == "__main__":
    main()
