"""C6 run-to-run disagreement ('Innovative idea review.md' lines 198-202 and 627-635), step 2 = PREMISE CHECK only (steps 3-4 are built only if it passes).
Pairs: the F-V2 refetch (data/raw/wb2_hres_v2) has 00Z and 12Z HRES starts every 4 days, offset by 1.5 days, so the closest lagged pair is 36 h apart (the recipe's 12 h pair is
not on disk): newer = 00Z run at lead L, older = 12Z run started 36 h earlier at lead L + 36 h, both valid at the same hour; the same random store points for both (mode F profile
converter forecast_profiles with the shipped boundary-layer tables models/modeF_bl.npz). Truth = the ERA5 height-profile store (data/pilot/profiles80.zarr). Years 2016-2020 only.
Per height band (K.BANDS) and variable (vector wind: u, v together; T): d = RMS over the band of (newer - older), e = RMS over the band of (newer - ERA5).
Premise (recipe step 2): Spearman rank correlation of d with e. Kill rule: a cell passes when the MEAN of its four within-lead-bin rho values is >= 0.3; C6 continues only if at least
4 of the 8 cells pass. (Amended 2026-11-12 09:40 after a 2016-only smoke run, before the 2016-2020 run: the first rule used rho pooled over leads, which is inflated because d and e
both grow with lead and mode F already knows the lead; the amendment is stricter.)

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/c6_lagged_spread.py [--points 16]        # CPU, about 10-30 min, < 4 GB
Result: docs/results/logs/c6_lagged_premise.log

Steps 3-4 (`--step34`, built after the premise passed 2026-11-12): rows = 00Z-start rows of data/modeF_v2 (il6_build_v2) that have the 12Z run 36 h earlier; the SHIPPED mode F
samples (scripts/fv2_eval.tool_samples, 199 members); d per row and band as above (wind d scales u and v, T d scales T; RH untouched). Fit on 2016-2020 rows (recipe years):
x = d / median(d); per cell (wind / T x band) f_q^2 = mean((obs - member mean)^2) / mean(member variance) in deciles of x, then f = a + b x by least squares over the deciles,
clipped 0.5-2; members -> mean + f (member - mean). Test on 2022.
PASS (set 2026-11-12 09:50, before any step-3/4 result): mean PIT distance (tempest.scoring.metrics_ext.pit_tv over u, v, T at 44 heights) falls with its init-date-block 95 %
interval entirely below 0, AND the relative change in mean CRPS (u, v, T) is <= +0.2 %. Otherwise C6 is dropped.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/c6_lagged_spread.py --step34 [--rows 2500]
Result: docs/results/logs/c6_lagged_step34.log

AV4 (New_Plan 13.1, `--cells 0 1 2 6`, rule set 2026-11-13 before the run, from the AV4 row): the factor only in the four cells where the premise held
(wind 0-1, 1-5, 5-12 km; T 5-12 km); the other cells keep f = 1. Same fit years, rows and seeds. PASS = C6's rule unchanged (PIT distance change with the
whole interval below 0, CRPS change <= +0.2 %). KILL: the CRPS interval includes 0. Otherwise MISS. Result: docs/results/logs/c6_av4_cells.log
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/c6_lagged_spread.py --step34 --cells 0 1 2 6
AV25 (New_Plan 13.1, rule set 2026-11-13 before the run = AV4's rule unchanged): same as AV4 but test rows from 2021 + 2022 (more init dates):
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/c6_lagged_spread.py --step34 --cells 0 1 2 6 --test-years 2021 2022
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import spearmanr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from tempest.forecast import modeF as F   # noqa: E402

H = np.asarray(F.HEIGHTS, float)
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
LAG = np.timedelta64(36, "h")


def band_rms(x, lo, hi):
    """x (n, 44) or (n, 2, 44) differences -> (n,) RMS over the band (vector: summed over the first axis)."""
    j = (H >= lo) & (H < hi)
    s = x[..., j] ** 2
    return np.sqrt((s.sum(1) if s.ndim == 3 else s).mean(-1))


def grid_index(h, ds):
    la = np.round(h.latitude.values[None, :] - ds.lat.values[:, None], 3) == 0
    lo = np.round(h.longitude.values[None, :] - 360.0 - ds.lon.values[:, None], 3) == 0
    assert (la.sum(1) == 1).all() and (lo.sum(1) == 1).all(), "store point without a unique HRES grid match"
    return la.argmax(1), lo.argmax(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=int, default=16)
    ap.add_argument("--years", type=int, nargs=2, default=[2016, 2020])
    ap.add_argument("--out", default=os.path.join(REPO, "docs/results/logs/c6_lagged_premise.log"))
    ap.add_argument("--step34", action="store_true")
    ap.add_argument("--rows", type=int, default=2500)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--test-years", type=int, nargs="+", default=[2022], help="AV25: test rows from these years (default 2022 = C6 / AV4)")
    ap.add_argument("--cells", type=int, nargs="+", default=None, help="AV4: apply the factor only in these cells (0-3 wind bands, 4-7 T bands); others f = 1")
    a = ap.parse_args()
    if a.step34:
        return step34(a)
    assert a.years[1] <= 2020, "premise years only (2016-2020)"
    ds = xr.open_zarr(os.path.join(REPO, "data/pilot/profiles80.zarr"))
    bl = dict(np.load(os.path.join(REPO, "models/modeF_bl.npz")))
    zs = ds.z_sfc.values.astype(float)
    tindex = ds.get_index("time")
    hd = os.path.join(REPO, "data/raw/wb2_hres_v2")
    old = {}   # 12Z init time -> (dataset, case index)
    for y in range(a.years[0] - 1, a.years[1] + 1):
        for mo in range(1, 13):
            f = f"{hd}/{y}{mo:02d}_12z.nc"
            if os.path.exists(f):
                h = xr.open_dataset(f)
                for c, t in enumerate(h.time.values):
                    old[t] = (h, c)
    rng = np.random.default_rng(6)
    D, E, LEAD = [], [], []
    for y in range(a.years[0], a.years[1] + 1):
        for mo in range(1, 13):
            f = f"{hd}/{y}{mo:02d}_00z.nc"
            if not os.path.exists(f):
                continue
            hn = xr.open_dataset(f)
            pla, plo = grid_index(hn, ds)
            tdn = hn.prediction_timedelta.values.astype("timedelta64[h]")
            vts = np.unique((hn.time.values[:, None] + tdn[None, :]).ravel())
            vts = vts[tindex.get_indexer(vts) >= 0]
            truth = {v: ds[v].isel(time=tindex.get_indexer(vts)).values for v in ("u", "v", "T")}     # one store read per file: (377, nT, 44)
            for c, t0 in enumerate(hn.time.values):
                if (t0 - LAG) not in old:
                    continue
                ho, co = old[t0 - LAG]
                pla_o, plo_o = grid_index(ho, ds)
                tdo = list(ho.prediction_timedelta.values.astype("timedelta64[h]"))
                for j, L in enumerate(tdn):
                    if (L + LAG) not in tdo:
                        continue
                    k = np.searchsorted(vts, t0 + L)
                    if k >= len(vts) or vts[k] != t0 + L:
                        continue
                    pt = rng.choice(len(zs), a.points, replace=False)
                    n = len(pt)
                    pn = F.forecast_profiles(hn, np.full(n, c), np.full(n, j), pla[pt], plo[pt], zs[pt] * 9.80665, bl)
                    po = F.forecast_profiles(ho, np.full(n, co), np.full(n, tdo.index(L + LAG)), pla_o[pt], plo_o[pt], zs[pt] * 9.80665, bl)
                    tr = {v: truth[v][pt, k] for v in ("u", "v", "T")}
                    dw = np.stack([pn["u"] - po["u"], pn["v"] - po["v"]], 1)
                    ew = np.stack([pn["u"] - tr["u"], pn["v"] - tr["v"]], 1)
                    D.append([band_rms(dw, lo, hi) for _, lo, hi in BANDS] + [band_rms(pn["T"] - po["T"], lo, hi) for _, lo, hi in BANDS])
                    E.append([band_rms(ew, lo, hi) for _, lo, hi in BANDS] + [band_rms(pn["T"] - tr["T"], lo, hi) for _, lo, hi in BANDS])
                    LEAD.append(np.full(n, L.astype(int) / 24.0))
        print(y, "done", len(LEAD), flush=True)
    D, E = (np.concatenate([np.stack(x, 1) for x in z]) for z in (D, E))
    lead = np.concatenate(LEAD)
    ok = np.isfinite(D).all(1) & np.isfinite(E).all(1)
    D, E, lead = D[ok], E[ok], lead[ok]
    names = [f"wind {b[0]}" for b in BANDS] + [f"T {b[0]}" for b in BANDS]
    lines = [f"C6 premise: lagged HRES pairs 36 h apart (00Z newer vs 12Z older), {a.years[0]}-{a.years[1]}, {len(D)} rows ({a.points} store points per valid time); Spearman rho(d = |newer - older|, e = |newer - ERA5|)"]
    lines.append("%-16s %7s %7s %7s %7s %7s %8s %9s %9s" % ("cell", "all", "<=1.5d", "1.5-3.5", "3.5-5.5", ">5.5d", "bin mean", "median d", "median e"))
    passed = 0
    for k, nm in enumerate(names):
        r = [spearmanr(D[s, k], E[s, k])[0] for s in (np.ones(len(lead), bool), lead <= 1.5, (lead > 1.5) & (lead <= 3.5), (lead > 3.5) & (lead <= 5.5), lead > 5.5)]
        passed += np.mean(r[1:]) >= 0.3
        lines.append("%-16s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %9.2f %9.2f" % (nm, *r, np.mean(r[1:]), np.median(D[:, k]), np.median(E[:, k])))
    lines.append("VERDICT: %s (mean within-lead-bin rho >= 0.3 in %d of 8 cells; rule: at least 4)" % ("PREMISE PASSES, go to step 3" if passed >= 4 else "KILL C6 (premise fails)", passed))
    print("\n".join(lines))
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")


def row_d(rows, bl, hd):
    """d (n, 8) for rows (dict of arrays from data/modeF_v2): 4 wind bands then 4 T bands; NaN where the 36 h older run is missing."""
    n = len(rows["valid"])
    out = np.full((n, 8), np.nan)
    init = rows["valid"] - rows["lead_hours"].astype("timedelta64[h]")
    files = {}

    def open_(t, start):
        key = (str(t)[:7].replace("-", ""), start)
        if key not in files:
            f = f"{hd}/{key[0]}_{start}.nc"
            files[key] = xr.open_dataset(f) if os.path.exists(f) else None
        return files[key]
    for t0 in np.unique(init):
        hn, ho = open_(t0, "00z"), open_(t0 - LAG, "12z")
        if hn is None or ho is None:
            continue
        cn, co = np.flatnonzero(hn.time.values == t0), np.flatnonzero(ho.time.values == t0 - LAG)
        if not (len(cn) and len(co)):
            continue
        tdn, tdo = list(hn.prediction_timedelta.values.astype("timedelta64[h]")), list(ho.prediction_timedelta.values.astype("timedelta64[h]"))
        for i in np.flatnonzero(init == t0):
            L = np.timedelta64(int(rows["lead_hours"][i]), "h")
            if L not in tdn or (L + LAG) not in tdo:
                continue
            la = [int(np.argmin(np.abs(h.latitude.values - rows["lat"][i]))) for h in (hn, ho)]
            lo = [int(np.argmin(np.abs(h.longitude.values - 360.0 - rows["lon"][i]))) for h in (hn, ho)]
            zg = np.array([rows["z_sfc"][i] * 9.80665])
            pn = F.forecast_profiles(hn, cn[:1], np.array([tdn.index(L)]), np.array([la[0]]), np.array([lo[0]]), zg, bl)
            po = F.forecast_profiles(ho, co[:1], np.array([tdo.index(L + LAG)]), np.array([la[1]]), np.array([lo[1]]), zg, bl)
            dw = np.stack([pn["u"] - po["u"], pn["v"] - po["v"]], 1)
            out[i] = [band_rms(dw, lo_, hi_)[0] for _, lo_, hi_ in BANDS] + [band_rms(pn["T"] - po["T"], lo_, hi_)[0] for _, lo_, hi_ in BANDS]
    return out


def cell_cols(c):
    """cell c (0-3 wind bands, 4-7 T bands) -> column indices in the (u, v, T, RH) x 44 layout."""
    nh = len(H)
    _, lo, hi = BANDS[c % 4]
    j = np.flatnonzero((H >= lo) & (H < hi))
    return np.concatenate([j, nh + j]) if c < 4 else 2 * nh + j


def fit_cell(x, sq, var):
    """x (n,) scaled disagreement, sq (n,) squared error of the member mean, var (n,) member variance -> (a, b) of f = a + b x."""
    q = np.quantile(x, np.linspace(0, 1, 11))
    k = np.clip(np.searchsorted(q, x, side="right") - 1, 0, 9)
    xq = np.array([x[k == i].mean() for i in range(10)])
    fq = np.sqrt(np.array([sq[k == i].mean() / var[k == i].mean() for i in range(10)]))
    b, a = np.polyfit(xq, fq, 1)
    return a, b


def apply_f(ens, f, cols):
    m = ens[:, :, cols].mean(1, keepdims=True)
    ens[:, :, cols] = m + f[:, None, None] * (ens[:, :, cols] - m)


def step34(a_):
    from fv2_eval import tool_samples
    from tempest_weather import api
    from tempest.scoring.score import crps_ensemble
    from tempest.scoring.metrics_ext import pit_values, pit_tv
    bl = dict(np.load(os.path.join(REPO, "models/modeF_bl.npz")))
    hd = os.path.join(REPO, "data/raw/wb2_hres_v2")
    A = api._assets(None)
    rng = np.random.default_rng(34)

    def rows_for(years, n):
        R = [dict(np.load(os.path.join(REPO, f"data/modeF_v2/{y}.npz"))) for y in years]
        R = {k: np.concatenate([r[k] for r in R]) for k in R[0]}
        keep = (R["start_hour"] == 0) & np.isfinite(R["obs"][:, :3]).all((1, 2))
        R = {k: v[keep] for k, v in R.items()}
        i = np.sort(rng.choice(len(R["valid"]), min(3 * n, len(R["valid"])), replace=False))
        R = {k: v[i] for k, v in R.items()}
        d = row_d(R, bl, hd)
        ok = np.flatnonzero(np.isfinite(d).all(1))[:n]
        return {k: v[ok] for k, v in R.items()}, d[ok]
    assert max(range(2016, 2021)) <= 2020
    tr, dtr = rows_for(range(2016, 2021), a_.rows)
    assert min(a_.test_years) > 2020 and max(a_.test_years) <= 2022, "test years must be outside the fit years and before 2023"
    te, dte = rows_for(a_.test_years, a_.rows * len(a_.test_years))   # fit rows unchanged; same test rows per year
    print("rows", len(dtr), len(dte), flush=True)
    xtr, xte = tool_samples(A, tr, rng).astype(np.float64), tool_samples(A, te, rng).astype(np.float64)
    ytr, yte = tr["obs"].reshape(len(dtr), -1).astype(np.float64), te["obs"].reshape(len(dte), -1).astype(np.float64)
    med = np.median(dtr, 0)
    lines = [f"C6 steps 3-4: shipped mode F (199 members) on 00Z-start rows with the 36 h older 12Z run; fit 2016-2020 ({len(dtr)} rows), test {'+'.join(map(str, a_.test_years))} ({len(dte)} rows); f = a + b d / median(d), clipped 0.5-2"]
    xnew = xte.copy()
    for c in range(8):
        if a_.cells is not None and c not in a_.cells:
            continue
        cols = cell_cols(c)
        sq = ((xtr[:, :, cols].mean(1) - ytr[:, cols]) ** 2).mean(1)
        var = xtr[:, :, cols].var(1, ddof=1).mean(1)
        a, b = fit_cell(dtr[:, c] / med[c], sq, var)
        f = np.clip(a + b * dte[:, c] / med[c], 0.5, 2.0)
        apply_f(xnew, f, cols)
        lines.append("%-16s a %+.3f b %+.3f  median d %.2f  test f 5/50/95 %%: %.2f %.2f %.2f" % ((("wind " if c < 4 else "T ") + BANDS[c % 4][0]), a, b, med[c], *np.percentile(f, [5, 50, 95])))
    nc = 3 * len(H)
    c0, c1 = crps_ensemble(xte, yte)[:, :nc], crps_ensemble(xnew, yte)[:, :nc]
    p0, p1 = pit_values(xte, yte, np.random.default_rng(1))[:, :nc], pit_values(xnew, yte, np.random.default_rng(1))[:, :nc]
    init = (te["valid"] - te["lead_hours"].astype("timedelta64[h]")).astype("datetime64[D]")
    u, inv = np.unique(init, return_inverse=True)
    groups = [np.flatnonzero(inv == k) for k in range(len(u))]
    br = np.random.default_rng(7)
    dp, dc = [], []
    for _ in range(500):
        idx = np.concatenate([groups[k] for k in br.integers(0, len(u), len(u))])
        dp.append(pit_tv(p1[idx]).mean() - pit_tv(p0[idx]).mean())
        dc.append(c1[idx].mean() / c0[idx].mean() - 1)
    tv0, tv1 = pit_tv(p0).mean(), pit_tv(p1).mean()
    rc = c1.mean() / c0.mean() - 1
    for v, nm in enumerate(("u", "v", "T")):
        sl = slice(v * len(H), (v + 1) * len(H))
        lines.append("  %s: PIT distance %.3f -> %.3f, CRPS %.3f -> %.3f" % (nm, pit_tv(p0[:, sl]).mean(), pit_tv(p1[:, sl]).mean(), c0[:, sl].mean(), c1[:, sl].mean()))
    lo_, hi_ = np.percentile(dp, [2.5, 97.5])
    lines.append("all u, v, T: PIT distance %.4f -> %.4f, change %+.4f [%+.4f, %+.4f] (init-date blocks, %d dates); CRPS relative change %+.2f %% [%+.2f, %+.2f]" % (
        tv0, tv1, tv1 - tv0, lo_, hi_, len(u), 100 * rc, *np.percentile(100 * np.array(dc), [2.5, 97.5])))
    ok = hi_ < 0 and rc <= 0.002
    clo, chi = np.percentile(100 * np.array(dc), [2.5, 97.5])
    if a_.cells is not None:
        lines.append(f"AV4 cells {a_.cells}: VERDICT {av4_verdict(hi_, rc, clo, chi)}")
    lines.append("VERDICT: %s (PIT interval below 0: %s; CRPS change <= +0.2 %%: %s)" % ("PASS" if ok else "FAIL, C6 dropped", "yes" if hi_ < 0 else "no", "yes" if rc <= 0.002 else "no"))
    print("\n".join(lines))
    if not a_.smoke:
        with open(os.path.join(REPO, "docs/results/logs/c6_av4_cells.log" if a_.cells is not None else "docs/results/logs/c6_lagged_step34.log"), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n\n")


def av4_verdict(pit_hi, rc, crps_lo, crps_hi):
    """AV4 rule: PASS = C6's rule; KILL = CRPS interval (in %) includes 0; else MISS."""
    if pit_hi < 0 and rc <= 0.002:
        return "PASS"
    return "KILL (CRPS interval includes 0)" if crps_lo <= 0 <= crps_hi else "MISS (record)"


def _selfcheck():
    assert av4_verdict(-0.001, 0.0, -0.5, -0.1) == "PASS" and av4_verdict(0.001, -0.005, -0.9, -0.1).startswith("MISS") and av4_verdict(0.001, -0.001, -0.5, 0.2).startswith("KILL")
    xx = np.repeat(np.linspace(0.5, 2, 10), 50)
    a, b = fit_cell(xx, (0.8 + 0.4 * xx) ** 2, np.ones_like(xx))
    assert abs(a - 0.8) < 0.05 and abs(b - 0.4) < 0.05
    x = np.zeros((3, 2, 44))
    x[0, 0] = 3.0
    x[0, 1] = 4.0
    assert np.allclose(band_rms(x, 0, 18001), [5.0, 0.0, 0.0])
    assert np.allclose(band_rms(np.ones((2, 44)) * 2, 0, 1000), 2.0)


_selfcheck()
if __name__ == "__main__":
    main()
