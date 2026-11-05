"""Shear-space quantile map (improvement-loop IL-58, shear track): make the distribution of neighbour-height wind shear of the samples equal the truth's, rank-preserving.

    python -m tempest.calibrate.shear_map --model models/X.pt --data D.npz --calib models/X.calib2021.npz [--year 2023] [--from-year 2021] [--rows 4000]

For every layer between neighbouring heights the samples' vector shear s is multiplied by a gain g_b(s) that depends on the shear itself and the height band b,
fitted so the quantiles of s (50 ... 99.95 %) of the pooled samples equal those of the truth. The gain is 1 up to the median, so ordinary layers are untouched,
and g(s) * s increases with s, so the order of the layers within a sample is kept. The wind difference of each layer is scaled, then the change accumulated up the column is
high-pass filtered (its smooth part removed) so the large-scale winds, and with them the medians and the 10 m to 18 km wind change, stay as they were: only the rough
part of the profile gets sharper or smoother. Two or three fitting passes make the result match the target quantiles. Off by default (score --shear-map FILE).
Fits on the calibration years; the 2021-23 tail differs from 2024-25 (1-5 km 99.9th: 29.2 vs 25.7 m/s per km), so judge on the shear table and the scorer.
"""
import argparse

import numpy as np
from scipy.ndimage import uniform_filter1d

from tempest.profiles.to_heights import HEIGHTS

NH = len(HEIGHTS)
EDGES = [0, 1000, 5000, 12000, 18001]
DZ = np.diff(HEIGHTS) / 1000.0
MID = HEIGHTS[1:]
LEVELS = np.concatenate([np.linspace(0.5, 0.99, 50), [0.995, 0.997, 0.998, 0.999, 0.9995]])
GRID = 400                       # points of the shear-value grid per band
SMOOTH = 9                       # heights; the accumulated change keeps no variation on larger scales than this
BAND_OF_LAYER = np.digitize(MID, EDGES[1:-1])      # (43,) 0..3


def shears(uv):
    """uv (..., 2, NH) -> du, dv differences (..., 2, 43) and shear magnitude (..., 43) in m/s per km."""
    d = np.diff(uv, axis=-1)
    return d, np.hypot(d[..., 0, :], d[..., 1, :]) / DZ


def apply(table, x, chunk=256):
    """x (S, m, D) physical samples (u, v first) -> copy with the shear gain applied to the wind columns (rows in chunks to bound memory)."""
    if x.ndim == 3 and len(x) > chunk:
        return np.concatenate([apply(table, x[i:i + chunk], chunk) for i in range(0, len(x), chunk)])
    out = x.copy()
    uv = x[..., :2 * NH].reshape(*x.shape[:-1], 2, NH).astype(np.float64)
    d, s = shears(uv)
    g = np.ones_like(s)
    for b in range(4):
        sel = BAND_OF_LAYER == b
        g[..., sel] = np.interp(s[..., sel], table["grid"][b], table["gain"][b])
    delta = np.cumsum(d * (g[..., None, :] - 1.0), axis=-1)                   # change of the wind at heights 1..NH-1 (height 0 fixed)
    delta = np.concatenate([np.zeros_like(delta[..., :1]), delta], axis=-1)    # (..., 2, NH)
    rough = delta - uniform_filter1d(delta, SMOOTH, axis=-1, mode="nearest")
    new = uv + rough
    out[..., :2 * NH] = new.reshape(*x.shape[:-1], 2 * NH).astype(x.dtype)
    return out


def _quantiles(s_by_band, levels=LEVELS):
    return [np.quantile(s, levels) for s in s_by_band]


def _band_values(s):
    flat = s.reshape(-1, s.shape[-1])
    return [flat[:, BAND_OF_LAYER == b].ravel() for b in range(4)]


def fit(samples, truth, passes=3, damp=0.8):
    """samples (S, m, D), truth (S, D) -> table dict(grid (4, GRID), gain (4, GRID))."""
    uv_t = truth[:, :2 * NH].reshape(len(truth), 2, NH).astype(np.float64)
    q_t = _quantiles(_band_values(shears(uv_t)[1]))
    uv_s = samples[..., :2 * NH].reshape(*samples.shape[:-1], 2, NH).astype(np.float64)
    s0 = _band_values(shears(uv_s)[1])
    grid = np.stack([np.quantile(v, np.linspace(0.0, 0.9999, GRID)) for v in s0])
    gain = np.ones((4, GRID))
    table = dict(grid=grid, gain=gain)
    q_ref = _quantiles(s0)
    for _ in range(passes):
        cur = _quantiles(_band_values(shears(apply(table, samples)[..., :2 * NH].reshape(*samples.shape[:-1], 2, NH).astype(np.float64))[1]))
        for b in range(4):
            ratio = np.where(q_ref[b] > 0, q_t[b] / np.maximum(cur[b], 1e-9), 1.0)         # at the original sample quantile values
            # gain as a function of the ORIGINAL shear value: multiply the current gain at those values
            g_at = np.interp(q_ref[b], grid[b], gain[b])
            target = g_at * ratio ** damp
            new = np.interp(grid[b], q_ref[b], target, left=1.0, right=target[-1])
            new = np.where(grid[b] <= q_ref[b][0], 1.0, new)                              # nothing below the median
            gain[b] = np.maximum.accumulate(np.clip(new, 0.5, 3.0) * grid[b]) / np.maximum(grid[b], 1e-9)   # keep g(s) * s increasing
        table = dict(grid=grid, gain=gain)
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
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--rows", type=int, default=4000)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
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
    table = fit(x, truth)
    out = a.out or a.model.rsplit(".", 1)[0] + f".shearmap{a.from_year}.npz"
    np.savez(out, grid=table["grid"], gain=table["gain"], fit_from=a.from_year, fit_to=a.year, m=a.m, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    qt = _quantiles(_band_values(shears(truth[:, :2 * NH].reshape(len(truth), 2, NH).astype(np.float64))[1]), [0.99, 0.999])
    q0 = _quantiles(_band_values(shears(x[..., :2 * NH].reshape(*x.shape[:-1], 2, NH).astype(np.float64))[1]), [0.99, 0.999])
    q1 = _quantiles(_band_values(shears(apply(table, x)[..., :2 * NH].reshape(*x.shape[:-1], 2, NH).astype(np.float64))[1]), [0.99, 0.999])
    for b, name in enumerate(("0-1", "1-5", "5-12", "12-18")):
        print(f"{name:>6} km  99th / 99.9th  truth {qt[b][0]:6.1f} {qt[b][1]:6.1f}   before {q0[b][0]:6.1f} {q0[b][1]:6.1f}   after {q1[b][0]:6.1f} {q1[b][1]:6.1f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
