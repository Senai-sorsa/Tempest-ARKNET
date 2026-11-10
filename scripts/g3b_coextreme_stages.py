"""IL-169 (2026-11-10): where are the wind / shear co-extremes lost? G3b showed the shipped stack at 0.053 (ERA5 truth rows 0.088) with templates per point or per 2-degree block,
and 0.022 without the shuffle. This follows the score pipeline of tempest.scoring.score for the shipped stack (unknown drivers, range calibration, Schaake shuffle with 2-degree block
templates, shear map, lapse map) on the same kind of held-out rows and prints the co-extreme ratio (tempest.scoring.mc.coextreme) after EACH step, next to
  - the truth rows (ERA5, one per row),
  - the climatology ensemble (real ERA5 profiles of the same group, what the shuffle templates are drawn from),
  - the templates themselves,
  - the model with its marginals and the template ranks swapped in from the climatology (shuffle of clim by the template: should match clim),
  - IL-169 (3): the shuffle done in (10 m wind, 0-1 km shear) coordinates: the 1 km wind is rebuilt as the 10 m wind plus a shuffled shear vector.
Diagnostic only (no model or asset change). One GPU job (sampling), about 10 GB RAM.
Usage: PYTHONPATH=. python -W ignore scripts/g3b_coextreme_stages.py [--rows 2000] [--seed 0]"""
import argparse

import numpy as np
import torch

from tempest.calibrate import lapse_map, shear_map, spread
from tempest.calibrate import shuffle as shuf_mod
from tempest.generator.features import FEATURES, drivers
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS
from tempest.scoring.mc import IU, IV, N, coextreme
from tempest.scoring.score import group_keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/generator_80_c4w.pt")
    ap.add_argument("--data", default="data/train/pilot80_dpd.npz")
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--first-test-year", type=int, default=2024)
    ap.add_argument("--last-test-year", type=int, default=2025)
    a = ap.parse_args()
    stem = a.model.rsplit(".", 1)[0]
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    ckpt = torch.load(a.model, map_location="cpu", weights_only=True)
    sampler = Sampler(ckpt, device="cuda" if torch.cuda.is_available() else "cpu")
    d = load_npz(a.data)
    cond, year, target = d["cond"], d["year"], d["target"]
    held = (year >= a.first_test_year) & (year <= a.last_test_year)
    keys = group_keys(cond)
    tr = np.flatnonzero(~held & (year <= a.last_test_year))
    tr = tr[np.argsort(keys[tr], kind="stable")]
    va = rng.choice(np.flatnonzero(held), min(a.rows, int(held.sum())), replace=False)
    lo, hi = np.searchsorted(keys[tr], keys[va], "left"), np.searchsorted(keys[tr], keys[va], "right")
    ok = hi > lo
    va, lo, hi = va[ok], lo[ok], hi[ok]
    draws = tr[lo[:, None] + (rng.random((len(va), a.m)) * (hi - lo)[:, None]).astype(np.int64)]
    truth = to_physical(target[va])
    clim = to_physical(target[draws.ravel()].reshape(*draws.shape, -1))
    rep = np.repeat(cond[va], a.m, axis=0)
    dc = [FEATURES.index(k) for k in drivers()]
    rep[:, dc] = cond[draws.ravel()][:, dc]
    raw = sampler.profiles(rep).reshape(len(va), a.m, -1)
    cal = spread.load(stem + ".calib2021.npz", a.model)
    x_cal = spread.apply(cal, raw)
    tpl = shuf_mod.group_template(target, keys, year, va, a.m, np.random.default_rng(a.seed + 5), a.first_test_year, cell=8, n_lon=shuf_mod.grid_n_lon(cond))
    x_shuf = shuf_mod.apply(x_cal, tpl)
    smt, lmt = dict(np.load(stem + ".shearmap2021_cell8.npz")), dict(np.load(stem + ".lapsemap2021.npz"))
    x_smap = shear_map.apply(smt, x_shuf)
    x_lmap = lapse_map.apply(lmt, x_smap)
    # IL-169 (3): shuffle in (10 m wind, 0-1 km shear) coordinates for the 1 km level only (a probe, not a full method)
    j1 = int(np.argmin(np.abs(np.asarray(HEIGHTS) - 1000.0)))
    def to_shear(p):
        q = p.copy()
        q[..., IU + j1] -= p[..., IU]
        q[..., IV + j1] -= p[..., IV]
        return q
    def from_shear(q):
        p = q.copy()
        p[..., IU + j1] += q[..., IU]
        p[..., IV + j1] += q[..., IV]
        return p
    x_sspace = from_shear(shuf_mod.apply(to_shear(x_cal), to_shear(tpl)))
    rows = [("truth rows (ERA5)", truth), ("climatology ensemble (ERA5, same groups)", clim), ("templates (2-degree blocks)", tpl),
            ("model raw", raw), ("+ range calibration", x_cal), ("+ shuffle", x_shuf), ("+ shear map", x_smap), ("+ lapse map (shipped stack)", x_lmap),
            ("climatology shuffled by the templates", shuf_mod.apply(clim, tpl)), ("IL-169(3): calibrated, shuffled in shear space (1 km)", x_sspace)]
    print(f"{len(va):,} rows {a.first_test_year}-{a.last_test_year}, m = {a.m}, seed {a.seed}; co-extreme ratio P(10 m wind > q95 and 0-1 km shear > q95) / 0.05 (1 = always together, 0.05 = independent)", flush=True)
    for name, x in rows:
        print(f"  {name:<58s} {coextreme(x):.4f}", flush=True)
    # marginal check: how heavy are the 10 m wind and 0-1 km shear tails in the model vs climatology
    for name, x in (("clim", clim), ("model shipped", x_lmap)):
        f = x.reshape(-1, x.shape[-1])
        w = np.hypot(f[:, IU], f[:, IV])
        sh = np.hypot(f[:, IU + j1] - f[:, IU], f[:, IV + j1] - f[:, IV])
        print(f"  {name:<14s} wind10 q50 / q95 {np.quantile(w, 0.5):.2f} / {np.quantile(w, 0.95):.2f} m/s   shear0-1km q50 / q95 {np.quantile(sh, 0.5):.2f} / {np.quantile(sh, 0.95):.2f} m/s   rank corr {np.corrcoef(np.argsort(np.argsort(w)), np.argsort(np.argsort(sh)))[0, 1]:+.3f}", flush=True)


if __name__ == "__main__":
    main()
