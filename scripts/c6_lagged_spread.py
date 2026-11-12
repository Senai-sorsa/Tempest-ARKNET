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
    a = ap.parse_args()
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


def _selfcheck():
    x = np.zeros((3, 2, 44))
    x[0, 0] = 3.0
    x[0, 1] = 4.0
    assert np.allclose(band_rms(x, 0, 18001), [5.0, 0.0, 0.0])
    assert np.allclose(band_rms(np.ones((2, 44)) * 2, 0, 1000), 2.0)


_selfcheck()
if __name__ == "__main__":
    main()
