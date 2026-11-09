"""Lapse-rate quantile map (IL-162): make the upper tail of the layer-by-layer lapse rate of the samples equal the truth's, rank-preserving, temperature twin of the shear map.

    python -m tempest.calibrate.lapse_map --model models/X.pt --data D.npz --calib models/X.calib2021.npz [--shear-map FILE] [--shuffle --template-cell 8]

For every layer between neighbouring heights the lapse rate L = -dT/dz (K per km) is replaced by f_b(L), a monotone map per height band b that is the identity up to the band's median and, above it, takes the
quantiles of the samples' L to the quantiles of the truth's L (fitted on the calibration years). Below the median nothing changes, so ordinary and stable layers are untouched, and the order of the layers
within a sample is kept. The temperature change of each layer is replaced, then the change accumulated up the column is high-pass filtered (its smooth part removed) so the large-scale temperature profile,
and with it the medians, stay as they were: only the rough part of the profile changes. It is a MATCH OF THE DISTRIBUTION, not a cap: the training data themselves are superadiabatic in the lowest km on hot
afternoons (see sample.py), so real superadiabatic layers stay and only the excess goes. Fit AFTER the shuffle and the shear map (the order score.py applies them in). Off by default (score --lapse-map FILE).
"""
import argparse

import numpy as np
from scipy.ndimage import uniform_filter1d

from tempest.generator.sample import PROFILE
from tempest.profiles.to_heights import HEIGHTS

NH = len(HEIGHTS)
EDGES = [0, 1000, 5000, 12000, 18001]
DZ = np.diff(HEIGHTS) / 1000.0
MID = HEIGHTS[1:]
BAND_OF_LAYER = np.digitize(MID, EDGES[1:-1])
LEVELS = np.concatenate([np.linspace(0.5, 0.99, 50), [0.995, 0.997, 0.998, 0.999, 0.9995]])
SMOOTH = 9
T0 = PROFILE.index("T") * NH


def lapse(x):
    """x (..., D) physical -> lapse rate (..., 43) in K per km."""
    t = x[..., T0:T0 + NH].astype(np.float64)
    return -np.diff(t, axis=-1) / DZ


def apply(table, x, chunk=512):
    """x (S, m, D) physical samples -> copy with the lapse map applied to the temperature columns."""
    if x.ndim == 3 and len(x) > chunk:
        return np.concatenate([apply(table, x[i:i + chunk], chunk) for i in range(0, len(x), chunk)])
    out = x.copy()
    t = x[..., T0:T0 + NH].astype(np.float64)
    dT = np.diff(t, axis=-1)
    L = -dT / DZ
    L2 = L.copy()
    for b in range(len(table["xk"])):
        sel = BAND_OF_LAYER == b
        xk, yk = table["xk"][b], table["yk"][b]
        v = L[..., sel]
        mapped = np.interp(v, xk, yk) + np.where(v > xk[-1], v - xk[-1], 0.0)          # beyond the last knot: slope 1 (np.interp would hold the value)
        L2[..., sel] = np.where(v <= xk[0], v, mapped)
    delta = np.cumsum(-L2 * DZ - dT, axis=-1)
    delta = np.concatenate([np.zeros_like(delta[..., :1]), delta], axis=-1)
    rough = delta - uniform_filter1d(delta, SMOOTH, axis=-1, mode="nearest")
    out[..., T0:T0 + NH] = (t + rough).astype(x.dtype)
    return out


def _band_values(L):
    flat = L.reshape(-1, L.shape[-1])
    return [flat[:, BAND_OF_LAYER == b].ravel() for b in range(4)]


def fit(samples, truth, passes=3, damp=0.8):
    """samples (S, m, D), truth (S, D) physical -> table dict(xk (4, K), yk (4, K)): knots of the map from the samples' lapse quantiles (xk) to the values that make the result match the truth's (yk)."""
    q_t = [np.quantile(v, LEVELS) for v in _band_values(lapse(truth))]
    s0 = _band_values(lapse(samples))
    xk = np.stack([np.quantile(v, LEVELS) for v in s0])
    yk = xk.copy()
    table = dict(xk=xk, yk=yk)
    for _ in range(passes):
        cur = [np.quantile(v, LEVELS) for v in _band_values(lapse(apply(table, samples)))]
        for b in range(4):
            yk[b] = np.maximum.accumulate(yk[b] + damp * (q_t[b] - cur[b]))
            yk[b] = np.maximum(yk[b], xk[b][0])
        table = dict(xk=xk, yk=yk)
    return table


def main():
    import torch

    from tempest.calibrate import spread
    from tempest.calibrate.trust import file_sha
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--shear-map", help="apply this shear map before fitting (the map is fitted on what score.py will hand it)")
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--rows", type=int, default=4000)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--template-cell", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    idx = np.sort(rng.choice(np.flatnonzero((d["year"] >= a.from_year) & (d["year"] <= a.year)), a.rows, replace=False))
    truth = to_physical(np.asarray(d["target"][idx]))
    cond = np.asarray(d["cond"])[idx]
    x = np.empty((len(idx), a.m, truth.shape[1]), np.float32)
    for i in range(0, len(idx), 400):
        sl = slice(i, i + 400)
        x[sl] = spread.apply(cal, sampler.profiles(np.repeat(cond[sl], a.m, axis=0)).reshape(len(cond[sl]), a.m, -1))
    if a.shuffle:
        from tempest.calibrate import shuffle as shuf_mod
        from tempest.scoring.score import group_keys
        keys = group_keys(np.asarray(d["cond"]))
        x = shuf_mod.apply(x, shuf_mod.group_template(d["target"], keys, d["year"], idx, a.m, rng, a.from_year, cell=a.template_cell, n_lon=shuf_mod.grid_n_lon(d["cond"])))
    if a.shear_map:
        from tempest.calibrate import shear_map
        x = shear_map.apply(dict(np.load(a.shear_map)), x)
    table = fit(x, truth)
    out = a.out or a.model.rsplit(".", 1)[0] + f".lapsemap{a.from_year}.npz"
    np.savez(out, xk=table["xk"], yk=table["yk"], fit_from=a.from_year, fit_to=a.year, m=a.m, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    qt = [np.quantile(v, [0.9, 0.99, 0.999]) for v in _band_values(lapse(truth))]
    q0 = [np.quantile(v, [0.9, 0.99, 0.999]) for v in _band_values(lapse(x))]
    q1 = [np.quantile(v, [0.9, 0.99, 0.999]) for v in _band_values(lapse(apply(table, x)))]
    for b, name in enumerate(("0-1", "1-5", "5-12", "12-18")):
        print(f"{name:>6} km lapse K/km 90th/99th/99.9th  truth {qt[b][0]:6.1f} {qt[b][1]:6.1f} {qt[b][2]:6.1f}   before {q0[b][0]:6.1f} {q0[b][1]:6.1f} {q0[b][2]:6.1f}   after {q1[b][0]:6.1f} {q1[b][1]:6.1f} {q1[b][2]:6.1f}")
    print(f"superadiabatic share (> 9.8 K/km, all bands): truth {np.mean(lapse(truth) > 9.8):.3f}  before {np.mean(lapse(x) > 9.8):.3f}  after {np.mean(lapse(apply(table, x)) > 9.8):.3f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
