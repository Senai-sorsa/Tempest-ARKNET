"""Rare shear patches (improvement-loop IL-5, idea from the Earth-GRAM 2026 guide, section 2.12.2 "patchy severe turbulence").

    python -m tempest.calibrate.shear_tail --model models/X.pt --data D.npz --calib models/X.calib2021.npz [--p 0.05] [--year 2023] [--from-year 2021]

Earth-GRAM keeps its wind-shear tail heavy by letting a small share of the atmosphere be "severe": variance several times larger, on a shorter
vertical scale. Here the generator already matches the 99th-percentile neighbour shear but is 6-20 % low at the 99.9th. A fraction p of the samples
gets a patch: a vertically correlated random wind perturbation (AR(1) along the 44 heights, correlation rho) whose size sigma_b (m/s) per height band
is fitted on the calibration years so the 99.9th-percentile neighbour shear of the samples equals the truth's. The other 1 - p of the samples are
untouched, so medians and most CRPS barely move. Off by default (score --shear-tail FILE); writes <model>.sheartail<from-year>.npz.
"""
import argparse

import numpy as np
import torch

from tempest.calibrate import spread
from tempest.calibrate.trust import file_sha
from tempest.profiles.to_heights import HEIGHTS

N = len(HEIGHTS)
EDGES = [0, 1000, 5000, 12000, 18001]
RHO = 0.6
DZ = np.diff(HEIGHTS) / 1000.0


def sigma_profile(sig):
    """sig (4,) per band -> (N,) amplitude per height (linear between band centres, held at the ends)."""
    centres = np.array([(EDGES[i] + EDGES[i + 1]) / 2 for i in range(4)])
    return np.interp(HEIGHTS, centres, sig)


def patch(sig, shape, rng):
    """(shape..., 2, N) AR(1)-in-height perturbation scaled by the per-height amplitude."""
    z = rng.standard_normal(shape + (2, N)).astype(np.float32)
    for j in range(1, N):
        z[..., j] = RHO * z[..., j - 1] + np.sqrt(1 - RHO ** 2) * z[..., j]
    return z * sigma_profile(sig).astype(np.float32)


def apply(table, x, rng):
    """x (S, m, D) physical samples -> copy with a share p of the samples carrying a wind patch."""
    p, sig = float(table["p"]), np.asarray(table["sigma"], float)
    hit = rng.random(x.shape[:2]) < p
    if not hit.any():
        return x
    out = x.copy()
    d = patch(sig, (int(hit.sum()),), rng)
    out[hit, :N] += d[:, 0]
    out[hit, N:2 * N] += d[:, 1]
    return out


def band_shear_q(x, q):
    """x (..., D) -> {band: q-th percentile of neighbour vector shear (m/s per km)}."""
    u, v = x[..., :N], x[..., N:2 * N]
    sh = np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / DZ
    mid = HEIGHTS[1:]
    return np.array([np.percentile(sh[..., (mid >= EDGES[i]) & (mid < EDGES[i + 1])], q) for i in range(4)])


def fit_sigma(samples, truth, p, rng, q=99.9, iters=14, free=(True, True, True, True)):
    """Bisection per band on sigma so that the q-th shear percentile of (patched) samples equals the truth's."""
    target = band_shear_q(truth, q)
    lo, hi = np.zeros(4), np.full(4, 8.0)
    free = np.asarray(free, bool)
    for _ in range(iters):
        mid = np.where(free, (lo + hi) / 2, 0.0)          # bands that are not free stay at zero (IL-12: only the band where the patches helped)
        cur = band_shear_q(apply(dict(p=p, sigma=mid), samples, np.random.default_rng(int(rng.integers(1 << 30)))), q)
        lo, hi = np.where(cur < target, mid, lo), np.where(cur < target, hi, mid)
    return np.where(free, (lo + hi) / 2, 0.0), target


def main():
    from tempest.generator.features import FEATURES
    from tempest.generator.sample import Sampler, to_physical
    from tempest.generator.train import load_npz
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--calib", required=True)
    ap.add_argument("--p", type=float, default=0.05)
    ap.add_argument("--only-bands", type=int, nargs="+", help="band numbers 0-3 (0-1, 1-5, 5-12, 12-18 km) that get patches; default all")
    ap.add_argument("--out")
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--from-year", type=int, default=2021)
    ap.add_argument("--rows", type=int, default=3000)
    ap.add_argument("--m", type=int, default=199)  # the range map was fitted at m = 199
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    idx = np.sort(rng.choice(np.flatnonzero((d["year"] >= a.from_year) & (d["year"] <= a.year)), a.rows, replace=False))
    truth = to_physical(np.asarray(d["target"][idx]))
    x = spread.apply(cal, sampler.profiles(np.repeat(np.asarray(d["cond"])[idx], a.m, axis=0)).reshape(len(idx), a.m, -1))
    free = [b in (a.only_bands or range(4)) for b in range(4)]
    sig, target = fit_sigma(x, truth, a.p, rng, free=free)
    out = a.out or a.model.rsplit(".", 1)[0] + f".sheartail{a.from_year}.npz"
    before = band_shear_q(x, 99.9)
    after = band_shear_q(apply(dict(p=a.p, sigma=sig), x, rng), 99.9)
    print("99.9th shear (m/s/km) by band 0-1, 1-5, 5-12, 12-18 km")
    print("truth ", np.round(target, 1), "\nbefore", np.round(before, 1), "\nafter ", np.round(after, 1), "\nsigma ", np.round(sig, 2))
    np.savez(out, p=a.p, sigma=sig.astype(np.float32), rho=RHO, fit_from=a.from_year, fit_to=a.year, model_sha=spread.model_hash(a.model), calib_sha=file_sha(a.calib))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
