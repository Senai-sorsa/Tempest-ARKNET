"""New_Plan 25 GF4: conditional calibration on CPU, fitted on top of the full stack (b) of the paired base.

    PYTHONPATH=. python scripts/s25_gf4_condcal.py FIT.npz SCORE.npz --out models/s25/gf4_result.csv      (FIT/SCORE: s25_shape.py --dump)
    PYTHONPATH=. python scripts/s25_gf4_condcal.py --selfcheck

Per var (u, v, T, RH) x band (0-1, 1-5, 5-12, 12-18 km) one monotone stretch about the ensemble mean, x' = mean + f (x - mean) with
f = exp(a + b1 z_spread + b2 z_stab + b3 z_w500) > 0, so member order never changes and there are 4 parameters per cell. The drivers are all
read off the forecast: z_spread = log ensemble sd (band mean), z_stab = band mean dT/dz of the ensemble mean, z_w500 = ensemble mean wind
speed at the height nearest 500 hPa (standard atmosphere), each standardised on the fit rows. Fitted on 2021-23 by fair CRPS (L-BFGS,
analytic gradient), scored on 2024-25 by PIT total variation (10 bins, mean over var x band) unstretched vs stretched, with a 95 % interval
from a 7-day date-block bootstrap. Sign check: refit on 2021 alone and on 2022 alone; a swap is a b with opposite signs and both |b| > 0.05.
Writes key,value rows (gain, gain_lo, gain_hi, swaps, cells, tv_raw, tv_cal) and OUT stem + _cells.csv (per-cell TV and coefficients).
The PRE-SET pass/kill rule lives in new_plan_kit/s25_judges.py gf4.
Deviation: the plan scores against balloons; this scores against ERA5 2024-25 (recorded in docs/agent/SECTION25_CODE_STATUS.md).
"""
import argparse
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

H = None  # 44 heights, set lazily so --selfcheck needs no repo import
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
VARS = ["u", "v", "T", "RH"]
NH = 44
SWAP_MIN = 0.05


def heights():
    global H
    if H is None:
        from tempest.profiles.to_heights import HEIGHTS
        H = np.asarray(HEIGHTS, float)
    return H


def drivers(x, h, p500_col):
    """x (n, m, 179) physical -> per-row z-able drivers: log sd per column (n, 179), stability per band (n, 4), 500 hPa speed (n,)."""
    mu = x.mean(1)
    lsd = np.log(np.maximum(x.std(1), 1e-6))
    t = mu[:, 2 * NH:3 * NH]
    dtdz = np.gradient(t, h, axis=1)
    stab = np.stack([dtdz[:, (h >= lo) & (h < hi)].mean(1) for _, lo, hi in BANDS], 1)
    w500 = np.hypot(mu[:, p500_col], mu[:, NH + p500_col])
    return mu, lsd, stab, w500


def cell_cols(vi, lo, hi, h):
    return vi * NH + np.flatnonzero((h >= lo) & (h < hi))


def gini(d):
    """E|d - d'| per (row, col) over members, fair (m - 1 in the denominator), from the sorted sample."""
    m = d.shape[1]
    s = np.sort(d, 1)
    w = (2 * np.arange(1, m + 1) - m - 1).astype(float)
    return 2 * np.tensordot(s, w, axes=([1], [0])) / (m * (m - 1))


def fit_cell(d, r, g, Z):
    """d (n, m, k) departures, r (n, k) truth - mean, g (n, k) gini, Z (n, 3) drivers -> theta (4,) minimising mean fair CRPS."""
    X = np.concatenate([np.ones((len(Z), 1)), Z], 1)

    def f_and_grad(th):
        f = np.exp(X @ th)
        e = f[:, None, None] * d - r[:, None, :]
        crps = np.abs(e).mean(1) - 0.5 * f[:, None] * g
        dcf = (d * np.sign(e)).mean(1) - 0.5 * g                     # d crps / d f, per (row, col)
        dl = (dcf.mean(1) * f)[:, None] * X                          # chain rule through f = exp(X th)
        return crps.mean(), dl.mean(0)

    res = minimize(f_and_grad, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B", options=dict(maxiter=200))
    return res.x


def pit_counts(x, y, block, rng, bins=10):
    """Per date block, histogram counts of PIT over every (row, col): returns (blocks, bins) and the block ids."""
    m = x.shape[1]
    below = (x < y[:, None, :]).sum(1)
    ties = (x == y[:, None, :]).sum(1)
    pit = (below + rng.uniform(0, 1, below.shape) * (ties + 1)) / (m + 1)
    b = np.minimum((pit * bins).astype(int), bins - 1)
    ub, inv = np.unique(block, return_inverse=True)
    out = np.zeros((len(ub), bins))
    np.add.at(out, (np.repeat(inv, b.shape[1]), b.ravel()), 1)
    return out, ub


def tv(counts):
    p = counts / counts.sum(-1, keepdims=True)
    return 0.5 * np.abs(p - 1.0 / counts.shape[-1]).sum(-1)


def run(fit, score, rng, n_boot=500):
    h = heights()
    from tempest.generator.sample import standard_pressure
    p500 = int(np.argmin(np.abs(standard_pressure(h) - 50000.0)))
    fx = fit["x"].astype(np.float32)
    sx = score["x"].astype(np.float32)
    fmu, flsd, fstab, fw = drivers(fx, h, p500)
    smu, slsd, sstab, sw = drivers(sx, h, p500)
    rows, coefs = [], {}
    blocks = None
    raw_c, cal_c = [], []
    for vi, var in enumerate(VARS):
        for bi, (band, lo, hi) in enumerate(BANDS):
            cols = cell_cols(vi, lo, hi, h)
            if not len(cols):
                continue

            def z_of(lsd, stab, w, ref):
                z = np.stack([lsd[:, cols].mean(1), stab[:, bi], w], 1)
                return (z - ref[0]) / ref[1]
            zf_raw = np.stack([flsd[:, cols].mean(1), fstab[:, bi], fw], 1)
            ref = (zf_raw.mean(0), np.maximum(zf_raw.std(0), 1e-9))
            zf, zs = (zf_raw - ref[0]) / ref[1], z_of(slsd, sstab, sw, ref)
            d = fx[:, :, cols] - fmu[:, None, cols]
            r = fit["y"][:, cols] - fmu[:, cols]
            g = gini(d)
            th = fit_cell(d, r, g, zf)
            ths = {}
            for yr in (2021, 2022):
                k = fit["year"] == yr
                ths[yr] = fit_cell(d[k], r[k], g[k], zf[k]) if k.sum() > 50 else np.zeros(4)
            swap = int(np.sum((np.sign(ths[2021][1:]) != np.sign(ths[2022][1:])) & (np.abs(ths[2021][1:]) > SWAP_MIN) & (np.abs(ths[2022][1:]) > SWAP_MIN)))
            f = np.exp(np.concatenate([np.ones((len(zs), 1)), zs], 1) @ th)
            xs = sx[:, :, cols]
            xc = smu[:, None, cols] + f[:, None, None] * (xs - smu[:, None, cols])
            cr, blocks = pit_counts(xs, score["y"][:, cols], score["block"], rng)
            cc, _ = pit_counts(xc, score["y"][:, cols], score["block"], rng)
            raw_c.append(cr)
            cal_c.append(cc)
            coefs[(var, band)] = th
            rows.append(dict(var=var, band=band, tv_raw=tv(cr.sum(0)), tv_cal=tv(cc.sum(0)), a=th[0], b_spread=th[1], b_stab=th[2], b_w500=th[3],
                             swaps=swap, f_mean=float(f.mean())))
    raw_c, cal_c = np.stack(raw_c), np.stack(cal_c)                   # (cells, blocks, bins)
    gain = float(np.mean(tv(raw_c.sum(1)) - tv(cal_c.sum(1))))
    nb = raw_c.shape[1]
    boots = []
    for _ in range(n_boot):
        w = np.bincount(rng.integers(0, nb, nb), minlength=nb).astype(float)
        boots.append(np.mean(tv(np.einsum("cbk,b->ck", raw_c, w)) - tv(np.einsum("cbk,b->ck", cal_c, w))))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    cells = pd.DataFrame(rows)
    res = dict(gain=gain, gain_lo=float(lo), gain_hi=float(hi), swaps=int(cells.swaps.sum()), cells=len(cells),
               tv_raw=float(cells.tv_raw.mean()), tv_cal=float(cells.tv_cal.mean()), blocks=nb)
    return res, cells


def load(path, years):
    z = np.load(path)
    out = {k: z[k] for k in ("x", "y", "year", "block")}
    k = (out["year"] >= years[0]) & (out["year"] <= years[1])
    assert k.any(), f"{path}: no rows in {years}"
    assert out["year"].max() <= 2025, "never the 2026 window"
    return {kk: v[k] for kk, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fit", nargs="?")
    ap.add_argument("score", nargs="?")
    ap.add_argument("--out", default="models/s25/gf4_result.csv")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return _selfcheck()
    res, cells = run(load(a.fit, (2021, 2023)), load(a.score, (2024, 2025)), np.random.default_rng(a.seed), a.boot)
    pd.DataFrame(dict(key=list(res), value=list(res.values()))).to_csv(a.out, index=False)
    cells.to_csv(a.out[:-4] + "_cells.csv", index=False)
    print(cells.round(4).to_string(index=False))
    print(res)
    print(f"wrote {a.out}")


def _selfcheck():
    """Synthetic: an ensemble whose spread is too small exactly when a driver is high. The fit must find b_spread or the driver,
    raise TV gain above 0 with an interval above 0, and the fair CRPS gradient must match finite differences."""
    global H
    H = np.linspace(0, 18000, NH)
    rng = np.random.default_rng(0)

    def make(n, years):
        sd_true = rng.uniform(0.5, 2.0, (n, 1, 1))
        x = rng.standard_normal((n, 30, 179)) * 1.0                    # sd 1 everywhere: too narrow when sd_true > 1
        x *= np.exp(0.3 * np.log(sd_true))                              # spread partly tracks the true sd, so log sd is a driver
        y = rng.standard_normal((n, 179)) * sd_true[:, 0]
        yr = rng.choice(years, n)
        return dict(x=x.astype(np.float16), y=y, year=yr, block=yr * 100 + rng.integers(0, 52, n))
    import tempest.generator.sample  # noqa: F401  (standard_pressure import works)
    fit, score = make(1500, [2021, 2022, 2023]), make(1500, [2024, 2025])
    d = rng.standard_normal((40, 9, 3))
    r = rng.standard_normal((40, 3))
    g = gini(d)
    Z = rng.standard_normal((40, 3))
    X = np.concatenate([np.ones((40, 1)), Z], 1)

    def L(th):
        f = np.exp(X @ th)
        return (np.abs(f[:, None, None] * d - r[:, None, :]).mean(1) - 0.5 * f[:, None] * g).mean()
    pair = np.abs(d[:, :, None, :] - d[:, None, :, :]).sum((1, 2)) / (9 * 8)
    assert np.allclose(g, pair), "fair gini"
    th0 = rng.standard_normal(4) * 0.3
    eps = 1e-6
    num = np.array([(L(th0 + eps * e) - L(th0 - eps * e)) / (2 * eps) for e in np.eye(4)])
    f0 = np.exp(X @ th0)
    e0 = f0[:, None, None] * d - r[:, None, :]
    ana = ((((d * np.sign(e0)).mean(1) - 0.5 * g).mean(1) * f0)[:, None] * X).mean(0)
    assert np.allclose(num, ana, atol=1e-4), (num, ana)
    th = fit_cell(d, r, g, Z)
    assert L(th) <= min(L(np.zeros(4)), L(th0)) + 1e-9, "fit did not lower the loss"
    res, cells = run(fit, score, rng, 100)
    print(cells[["var", "band", "tv_raw", "tv_cal", "b_spread", "f_mean"]].round(3).to_string(index=False))
    print(res)
    assert res["gain"] > 0 and res["gain_lo"] > 0 and (cells.f_mean > 1).all(), res
    print("selfcheck ok")


if __name__ == "__main__":
    sys.exit(main())
