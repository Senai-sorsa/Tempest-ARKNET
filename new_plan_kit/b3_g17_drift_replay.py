"""G1-7 drift replay (README Part 5, recipe 'Innovative idea review.md' G1-7 step 4): does the climate mode drift from ERA5 month by month, and would a tracker fix it? PASS RULE BELOW.
For each month 2015-2025 (never 2026) and each of two pilot grid points (the ERA5 store points nearest TCS and MAF), draw 20 random store hours, ask the installed tool
(climate mode, K.tool) for n atmospheres, and take bias = ERA5 - pool mean, averaged over the heights of a band (K.BANDS) for u, v, T. Monthly bias = mean of the 20 hours.
Tracker = EWMA over 12 months (alpha 1/12, start 0), updated after each month and used only for the NEXT month (no look-ahead). Scored on 2016-2025 (2015 = warm-up).
The network has a 'year' input (b1_quick_checks trend), so the drift may already be small: first gate below.
Gate (README Part 5): if the mean absolute monthly bias is under the typical day-block 95 % half-width of one month's bias (K.block_boot over its hours), "no tracker needed", stop.
PASS: mean |bias - tracker| of the following month is smaller than mean |bias| in most cells (more than half of the 12 variable x band cells, both points pooled).
FAIL: otherwise -> no tracker. Measurement only; nothing in the tool changes.

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b3_g17_drift_replay.py            # about 20-40 min, 1-2 GB RAM, 12 threads max
    KIT_SMOKE=1 PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b3_g17_drift_replay.py --hours 2 --years 2015 2015   # smoke test
Result: docs/results/logs/kit_b3_g17_drift_replay.log
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

import kit_common as K

SITES = {"TCS": (33.2369, -107.2672), "MAF": (31.9425, -102.2019)}
VARS = ("u", "v", "T")


def ewma_errors(b, alpha=1 / 12):
    """b (months,) monthly biases -> (|b| of months 1.., |b - tracker before that month|)."""
    tr, raw, cor = 0.0, [], []
    for k, x in enumerate(b):
        if k >= 12 and np.isfinite(x):  # first 12 months only warm the tracker up
            raw.append(abs(x)), cor.append(abs(x - tr))
        if np.isfinite(x):
            tr += alpha * (x - tr)
    return np.array(raw), np.array(cor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=20)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--years", type=int, nargs=2, default=[2015, 2025])
    a = ap.parse_args()
    assert a.years[1] <= 2025
    K.ram_gate(4.0)
    z = xr.open_zarr(K.REPO + "/data/pilot/profiles.zarr")
    zt = pd.DatetimeIndex(z["time"].values)
    rng = np.random.default_rng(17)
    months = pd.period_range("%d-01" % a.years[0], "%d-12" % a.years[1], freq="M")
    B = np.full((len(SITES), len(months), len(VARS), len(K.BANDS)), np.nan)  # monthly bias
    HW = []  # day-block 95 % half-widths of single months
    for si, (st, (lat, lon)) in enumerate(SITES.items()):
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        plat, plon = float(z.lat.values[i]), float(z.lon.values[i])
        for mi, mo in enumerate(months):
            cand = zt[(zt.year == mo.year) & (zt.month == mo.month)]
            days = pd.DatetimeIndex(sorted(set(cand.normalize())))
            pick_days = rng.choice(len(days), size=min(a.hours, len(days)), replace=False)
            times = [cand[cand.normalize() == days[d]][rng.integers((cand.normalize() == days[d]).sum())] for d in pick_days]
            assert all(K.day_ok(t) for t in times)
            tf, E = K.era5_at(plat, plon, times)
            hb = np.full((len(tf), len(VARS), len(K.BANDS)), np.nan)
            for h, t in enumerate(tf):
                atm = K.tool(plat, plon, t, seed=int(t.value // 3600e9) % 100000, n=a.n)
                for vi, v in enumerate(VARS):
                    d = E[v][h] - np.asarray(atm[v], float).mean(0)
                    for bi, (_, lo, hi) in enumerate(K.BANDS):
                        hb[h, vi, bi] = np.nanmean(d[K.band_idx(lo, hi)])
            B[si, mi] = np.nanmean(hb, 0)
            for vi in range(len(VARS)):
                for bi in range(len(K.BANDS)):
                    m_, lo_, hi_ = K.block_boot(hb[:, vi, bi], np.arange(len(tf)), draws=500)
                    HW.append((vi, bi, (hi_ - lo_) / 2))
        print("%s done (point %.2f %.2f)" % (st, plat, plon), flush=True)

    hw = np.array(HW)
    lines = ["G1-7 drift replay: points nearest %s, months %s..%s, %d hours per month (one per day), n %d, climate mode; bias = ERA5 - pool mean (m/s, K)" % (
        "/".join(SITES), months[0], months[-1], a.hours, a.n)]
    lines.append("%-4s %-9s %10s %10s %10s %12s %12s %8s" % ("var", "band", "mean bias", "mean|bias|", "half-width", "|b| next mo", "|b-tracker|", "better"))
    better, gate_small = 0, 0
    for vi, v in enumerate(VARS):
        for bi, (bn, _, _) in enumerate(K.BANDS):
            b_all = B[:, :, vi, bi]
            h_ = float(np.median(hw[(hw[:, 0] == vi) & (hw[:, 1] == bi), 2]))
            raw, cor = zip(*(ewma_errors(b_all[s]) for s in range(len(SITES))))
            raw, cor = np.concatenate(raw), np.concatenate(cor)
            mb = float(np.nanmean(np.abs(b_all)))
            ok = cor.size and cor.mean() < raw.mean()
            better += bool(ok)
            gate_small += mb < h_
            lines.append("%-4s %-9s %+10.3f %10.3f %10.3f %12.3f %12.3f %8s" % (v, bn, np.nanmean(b_all), mb, h_,
                         raw.mean() if raw.size else np.nan, cor.mean() if cor.size else np.nan, "yes" if ok else "no"))
    yr = np.array([m.year for m in months])
    for lab, sel in (("<= 2020 (generator training years)", yr <= 2020), ("2021-25 (unseen)", yr >= 2021)):
        if sel.any():
            lines.append("mean bias %s: " % lab + "  ".join("%s %s %+.3f" % (v, bn, np.nanmean(B[:, sel, vi, bi])) for vi, v in enumerate(VARS) for bi, (bn, _, _) in enumerate(K.BANDS)))
    ncell = len(VARS) * len(K.BANDS)
    if gate_small > ncell / 2:
        verdict = "VERDICT: NO TRACKER NEEDED (mean |monthly bias| under one month's day-block half-width in %d of %d cells)" % (gate_small, ncell)
    else:
        verdict = "VERDICT: %s (tracker better in %d of %d cells; gate: bias under the half-width in %d of %d)" % (
            "PASS" if better > ncell / 2 else "FAIL, no tracker", better, ncell, gate_small, ncell)
    lines.append(verdict)
    K.report("b3_g17_drift_replay", lines)


def _selfcheck():
    # a constant bias of 1 is learned by the tracker: after warm-up, |b - tracker| < |b|
    raw, cor = ewma_errors(np.ones(36))
    assert raw.size == 24 and cor.mean() < raw.mean()
    # pure noise around 0: the tracker cannot help much
    raw, cor = ewma_errors(np.random.default_rng(0).normal(size=400))
    assert cor.mean() > 0.9 * raw.mean()


_selfcheck()
if __name__ == "__main__":
    main()
