"""New_Plan 10.2 O4: analog referee and tail fix. The analog ensemble of scripts/gw_analog.py (K = 40 most similar ERA5 hours of the library
2015-23, each giving the ASOS speed that followed; test 2024-25) under-predicts strong wind (TCS: median 7.71 vs 10.16 observed at >= 8 m/s).
Fix tested (one, pre-set): add the gap between the test hour's predictor and the analogs' mean predictor to every analog speed,
    s_k' = max(0, s_k + (x_t - mean_k x_k)),   x = ERA5 10 m speed (the analogs' own raw predictor).
Deterministic (no seed: the analog search has no random draw).
PASS (pre-set, New_Plan 10.2): at TCS AND MAF the strong-wind under-prediction (mean obs minus analog median over hours with obs >= 8 m/s)
      is at most half of the plain analog's (TCS 2.45 -> <= 1.2 m/s), AND overall CRPS (fixed minus plain) <= +0.0009 m/s.
Either way the plain analog stays the referee bar in every 10 m table (it is not a pad tool: it needs a station record).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b4_analog_tail.py      # a few minutes
Result: docs/results/logs/kit_b4_analog_tail.log
"""
import argparse
import os

import numpy as np
import xarray as xr

import kit_common as K
import ground_wind_bench as gw
from gw_analog import feats, hours_of
from gw_extrapolate_down import load
from tempest.scoring.score import crps_ensemble

W = np.array([1.0, 1.0, 1.0, 1.0, 0.6, 1.2, 1.2, 0.8, 0.8])     # the gw_analog weights, unchanged
NK = 40


def gap_fix(a_sp, x_t, x_k, up_only=False):
    """a_sp (N, K) analog speeds; x_t (N,) predictor now; x_k (N, K) analogs' predictor -> shifted analog speeds, floored at 0.
    up_only (AV9, opt-in): shift only when the gap is > 0, so no ensemble is pushed down onto the 0 floor (no narrowing)."""
    g = x_t - x_k.mean(1)
    return np.maximum(a_sp + (np.maximum(g, 0.0) if up_only else g)[:, None], 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--up-only", action="store_true", help="AV9: shift only upward; adds odd / even test-day halves as two replicates")
    ap.add_argument("--report", default="b4_analog_tail")
    a = ap.parse_args()
    z = xr.open_zarr(os.path.join(K.REPO, "data", "pilot", "profiles.zarr"))
    lines = [f"O4 analog tail fix: library 2015-23, test 2024-25, K = {NK}, fix = analog speed + (ERA5 10 m speed now - analogs' mean ERA5 10 m speed)"]
    ok_all = True
    for st in ("TCS", "MAF"):
        Al, ul, vl, Tl = load(z, st, list(range(2015, 2024)))
        At, ut, vt, Tt = load(z, st, [2024, 2025])
        tl, tt_ = hours_of(z, st, list(range(2015, 2024))), hours_of(z, st, [2024, 2025])
        assert not np.any(tt_.astype("datetime64[Y]").astype(int) + 1970 >= 2026)
        Xl, Xt = feats(ul, vl, Tl, tl), feats(ut, vt, Tt, tt_)
        mu, sd = Xl.mean(0), Xl.std(0) + 1e-9
        Zl, Zt = (Xl - mu) / sd * W, (Xt - mu) / sd * W
        d2 = (Zt ** 2).sum(1)[:, None] + (Zl ** 2).sum(1)[None, :] - 2 * Zt @ Zl.T
        nn = np.argpartition(d2, NK, axis=1)[:, :NK]
        y = np.hypot(At[:, 0], At[:, 1])
        plain = np.hypot(Al[nn][..., 0], Al[nn][..., 1])
        xl, xt = np.hypot(ul[:, 0], vl[:, 0]), np.hypot(ut[:, 0], vt[:, 0])
        fixed = gap_fix(plain, xt, xl[nn], up_only=a.up_only)
        days = [str(t)[:10] for t in tt_]
        cr = lambda e: crps_ensemble(e[:, :, None], y[:, None])[:, 0]
        cov = lambda e: float(np.mean((y >= np.quantile(e, 0.05, axis=1)) & (y <= np.quantile(e, 0.95, axis=1))))
        cp, cf = cr(plain), cr(fixed)
        dm, dlo, dhi = K.block_boot(cf - cp, days, draws=1000)
        hi = y >= 8.0
        up = float((y[hi] - np.median(plain, 1)[hi]).mean())
        uf = float((y[hi] - np.median(fixed, 1)[hi]).mean())
        ok = uf <= 0.5 * up and dm <= 0.0009
        ok_all &= bool(ok)
        lines += [f"{st}: {len(y)} test hours, {int(hi.sum())} with obs >= 8 m/s",
                  f"  plain analog  CRPS {cp.mean():.3f}  coverage {cov(plain):.2f}  strong-wind under-prediction {up:.2f} m/s",
                  f"  gap fix       CRPS {cf.mean():.3f}  coverage {cov(fixed):.2f}  strong-wind under-prediction {uf:.2f} m/s",
                  f"  fix minus plain CRPS {dm:+.4f} [{dlo:+.4f}, {dhi:+.4f}]; under-prediction ratio {uf / up if up else float('nan'):.2f}  {'ok' if ok else 'fail'}"]
        if a.up_only:
            odd = np.array([int(d[8:10]) % 2 == 1 for d in days])
            for nm, m in (("odd days", odd), ("even days", ~odd)):
                hm, hlo, hhi = K.block_boot(cf[m] - cp[m], [d for d, k in zip(days, m) if k], draws=1000)
                c0 = float(np.mean((y[m] >= np.quantile(plain[m], 0.05, axis=1)) & (y[m] <= np.quantile(plain[m], 0.95, axis=1))))
                c1 = float(np.mean((y[m] >= np.quantile(fixed[m], 0.05, axis=1)) & (y[m] <= np.quantile(fixed[m], 0.95, axis=1))))
                lines.append(f"  half {nm:<9} fix minus plain CRPS {hm:+.4f} [{hlo:+.4f}, {hhi:+.4f}]  coverage {c0:.2f} -> {c1:.2f}")
    lines.append("Rule (pre-set): under-prediction at >= 8 m/s at most half of plain AND CRPS fix minus plain <= +0.0009, at TCS and MAF.")
    lines.append("VERDICT: " + ("PASS -> the referee uses the gap-fixed analog; score S1 against it" if ok_all else "FAIL -> the plain analog stays the referee; tail bias recorded as a known limit of the referee"))
    K.report(a.report, lines)


def _selfcheck():
    out = gap_fix(np.array([[1.0, 3.0]]), np.array([5.0]), np.array([[2.0, 4.0]]))
    assert np.allclose(gap_fix(np.array([[1.0, 3.0]]), np.array([0.0]), np.array([[2.0, 4.0]]), up_only=True), [[1.0, 3.0]])
    assert np.allclose(out, [[3.0, 5.0]]) and gap_fix(np.array([[1.0]]), np.array([0.0]), np.array([[5.0]]))[0, 0] == 0.0


_selfcheck()
if __name__ == "__main__":
    main()
