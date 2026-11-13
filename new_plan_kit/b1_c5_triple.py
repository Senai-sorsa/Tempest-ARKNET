"""C5: three-way referee for "how much real shear is there?" at El Paso, 0.5-5 km. KILL RULE BELOW.
Three systems with independent errors: balloon (EPZ), radar (cached EPZ wind profiles, newest cached volume before the hour, 51-60 min old),
24-hour HRES forecast (data/raw/wb2_hres_v2/<yyyymm>_00z.nc and _12z.nc, valid 00Z and 12Z). Quantity: wind difference between model
heights 500 m apart (u and v). From the covariances over days:
    error variance of the balloon = Var(b) - Cov(b,r) Cov(b,f) / Cov(r,f)   (same pattern for radar and forecast)
    real-shear ratio, lower bound = sqrt(Cov(b,r) / Var(f))                 (what balloon and radar share, over the forecast)
    real-shear ratio, upper bound = sd(b) / sd(ERA5)                        (today's number, about 1.7)

KNOWN WEAKNESS (checked 2026-11-10): the forecast files have 13 pressure levels (about 4 inside 0.5-5 km here) and one start every 4 days,
radar files are 2021-23, forecasts end 2022. So there are only about 50-100 common days and the forecast shear is a straight line between
levels 1.5 km apart: Var(f) is too small and the lower bound comes out too HIGH. Expect the kill rule to fire.
KILL: fewer than 30 common days, or a negative error variance, or the 95 % interval of the lower bound spans both 1.4 and 1.7.
      Then log "C5 killed, use ratio 1.7" and go on: b2_shear_target_fit.py takes --ratio 1.7 by default.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/b1_c5_triple.py        # 5-10 min, 3 threads, no download
Result: docs/results/logs/kit_b1_c5_triple.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

LV = [int(np.flatnonzero(K.H == h)[0]) for h in range(500, 5001, 500)]         # model heights 500 ... 5000 m
TOP = K.H[LV][1:]
PBANDS = [("0.5-2 km", TOP <= 2000), ("2-5 km", TOP > 2000), ("0.5-5 km", TOP > 0)]


def diffs(u, v):
    """(44,) u, v -> (2, 9) differences between heights 500 m apart."""
    return np.stack([np.diff(u[LV]), np.diff(v[LV])])


def triple(b, r, f, e, days, draws=1000, seed=0):
    """b, r, f, e: (n,) values (already minus their column mean), days (n,) labels. -> dict name -> (value, lo, hi)."""
    P = np.stack([b * b, r * r, f * f, e * e, b * r, b * f, r * f], 1)
    _, inv = np.unique(days, return_inverse=True)
    S = np.stack([np.bincount(inv, P[:, j]) for j in range(7)], 1)
    C = np.bincount(inv).astype(float)

    def stats(s, c):
        vb, vr, vf, ve, cbr, cbf, crf = s / c
        with np.errstate(all="ignore"):
            return [vb - cbr * cbf / crf, vr - cbr * crf / cbf, vf - cbf * crf / cbr, np.sqrt(cbr / vf), np.sqrt(vb / ve)]
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(C), (draws, len(C)))
    boot = np.array([stats(S[p].sum(0), C[p].sum()) for p in pick])
    full = stats(S.sum(0), C.sum())
    names = ("err var balloon", "err var radar", "err var forecast", "ratio lower bound", "ratio upper bound")
    return {n: (full[i], np.nanpercentile(boot[:, i], 2.5), np.nanpercentile(boot[:, i], 97.5)) for i, n in enumerate(names)}


def hres_profiles(lat, lon, elev):
    """{valid time: (u, v) on the 44 heights, NaN outside the forecast levels} for every 24-hour forecast on disk."""
    import xarray as xr
    out = {}
    for f in sorted(glob.glob(os.path.join(K.REPO, "data", "raw", "wb2_hres_v2", "20*_*z.nc"))):
        if int(os.path.basename(f)[:4]) < 2021:        # radar files start in 2021
            continue
        h = xr.open_dataset(f)
        td = h.prediction_timedelta.values.astype("timedelta64[h]").astype(int)
        if 24 not in td:
            continue
        p = h.isel(prediction_timedelta=int(np.flatnonzero(td == 24)[0])).sel(latitude=lat, longitude=lon % 360, method="nearest")
        z = p["z"].values / 9.80665 - elev              # (time, level) m above the station
        for i, t0 in enumerate(h.time.values):
            o = np.argsort(z[i])
            zz = z[i][o]
            ok = (K.H >= zz[0]) & (K.H <= zz[-1])
            out[pd.Timestamp(t0) + pd.Timedelta(hours=24)] = tuple(np.where(ok, np.interp(K.H, zz, p[k].values[i][o]), np.nan) for k in ("u", "v"))
        h.close()
    return out


def main():
    lat, lon, elev = K.station_pos(K.EPZ)
    bt, b = K.balloon(K.EPZ)
    fc = hres_profiles(lat, lon, elev)
    index = K.radar_files("EPZ")
    et, e = K.era5_at(lat, lon, list(fc))
    rows = []
    for t, (fu, fv) in fc.items():
        assert K.day_ok(t)
        kb, ke = bt.get_indexer([t])[0], et.get_indexer([t])[0]
        rad = K.radar_uv("EPZ", t, elev, index=index)
        if kb < 0 or ke < 0 or rad is None:
            continue
        rows.append((t, diffs(b["u"][kb], b["v"][kb]), diffs(*rad), diffs(fu, fv), diffs(e["u"][ke], e["v"][ke])))
    lines = [f"C5 three-way referee at El Paso: {len(fc)} forecasts 2021-22, {len(rows)} with balloon + radar + ERA5 at the same hour"]
    kill = len(rows) < 30
    if rows:
        t = pd.DatetimeIndex([r[0] for r in rows])
        X = np.stack([np.stack(r[1:]) for r in rows])        # (days, 4 systems, 2, 9)
        for season, sm in (("all year", np.ones(len(t), bool)), ("Apr-Sep", (t.month >= 4) & (t.month <= 9)), ("Oct-Mar", (t.month < 4) | (t.month > 9))):
            for name, pm in PBANDS:
                x = X[sm][:, :, :, pm]
                x = x - np.nanmean(x, 0, keepdims=True)
                day = np.broadcast_to(np.arange(x.shape[0])[:, None, None], x[:, 0].shape)
                ok = np.isfinite(x).all(1)
                nd = int(ok.any((1, 2)).sum())
                if nd < 15:
                    lines.append(f"  {season:<9}{name:<9} only {nd} days with all three systems: not computed")
                    continue
                res = triple(*(x[:, j][ok] for j in range(4)), day[ok])
                lines.append(f"  {season:<9}{name:<9} days {nd:3d}, radar covered {ok.mean():.0%} of layer pairs: " + "; ".join(f"{k} {v[0]:.2f} [{v[1]:.2f}, {v[2]:.2f}]" for k, v in res.items()))
                if season == "all year" and name == "0.5-5 km":
                    lo = res["ratio lower bound"]
                    bad = min(res[k][0] for k in ("err var balloon", "err var radar", "err var forecast")) < 0 or not np.isfinite(lo[0])
                    kill = kill or bad or (lo[1] < 1.4 and lo[2] > 1.7)
                    ratio = lo[0]
    lines.append("VERDICT: C5 KILLED (too few days, a negative error variance, or bounds too wide). Use ratio 1.7 in b2_shear_target_fit.py." if kill else
                 f"VERDICT: C5 usable. Lower bound {ratio:.2f}: pass it as --ratio {min(ratio, 1.7):.2f} to b2_shear_target_fit.py (never above 1.7). Remember the lower bound is biased high (coarse forecast levels).")
    K.report("b1_c5_triple", lines)


def _selfcheck():
    rng = np.random.default_rng(0)
    n = 20000
    s = rng.standard_normal(n)
    b, r, f = s + 0.5 * rng.standard_normal(n), s + 0.8 * rng.standard_normal(n), 0.6 * s + 0.3 * rng.standard_normal(n)
    res = triple(b, r, f, 0.6 * s, np.arange(n) // 20, draws=50)
    assert abs(res["err var balloon"][0] - 0.25) < 0.05 and abs(res["err var radar"][0] - 0.64) < 0.06, res
    assert abs(res["ratio lower bound"][0] - np.sqrt(1 / 0.45)) < 0.08 and len(LV) == 10


_selfcheck()
if __name__ == "__main__":
    main()
