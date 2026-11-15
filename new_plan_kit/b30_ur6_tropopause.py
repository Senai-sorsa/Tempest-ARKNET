"""New_Plan 17 UR6: the 12-18 km package in a tropopause coordinate (tempest/calibrate/tropo.py). Nothing in the tool changes.
  --step 0  E4's step 0 (New_Plan 16.4), balloons only: Santa Teresa / El Paso and Midland soundings (IGRA, data/igra_heights, full height grid),
            each sounding's lapse-rate tropopause. (i) Spread of T at fixed heights 10-16 km (every 1 km) against the spread at fixed distance
            from the tropopause (-3 ... +3 km, every 1 km), both after removing the station x month mean (so season does not count as spread),
            1991-2020. (ii) Is the change after 2020 a height shift? 2021-25 minus 1991-2020: mean tropopause height, and the mean T change at
            fixed heights against at fixed distance from the tropopause (10-16 km).
  --step 1  the full run (only if step 0 passes): the shipped tool's climate-mode members at balloon times (00Z) are corrected at 9-18 km by a
            quantile map per 500 m distance bin from each MEMBER's own tropopause to the balloon values at the same distance from the BALLOON's
            tropopause, for T and RH separately; fit on <= 2020 balloons (a random 600 soundings per station, 2011-2020), scored on all 2024-25 00Z.
            Below 9 km nothing changes (asserted). Scores per band: CRPS skill against a balloon climatology of the same station and month from the
            15 years before the test (2009-2023), and the 99 % range coverage.
Shortcut stated before the run: the plan names three maps (range map, station line, shear map); this tests ONE map in the new coordinate,
applied after the shipped stack, which answers whether the coordinate carries the gain. The others follow only if this passes.
Rule (set 2026-11-13 in New_Plan 17.1 before any run):
  step 0 PASS: tropopause-relative spread under 70 % of the fixed-height spread at 3 or more of the levels compared; KILL: over 90 % at all
         (the coordinate adds nothing: UR6 and E4 close).
  step 1 PASS: T 12-18 km skill better by at least 0.010 with the 21-day block interval below 0 (on balloons), RH 12-18 km cov99 at or above 0.97,
         no band below 9 km changed, the mean skill over all bands not worse by more than 0.0009. KILL: T 12-18 km skill worse. Otherwise MISS.
UR11 (RH station line) should run first; AV16 / AV17 are judged again on top if this passes.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b30_ur6_tropopause.py --step 0      # minutes
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b30_ur6_tropopause.py --step 1      # ~2-3 h (tool calls)
Result: docs/results/logs/kit_b30_ur6_tropopause.log
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K
from tempest.calibrate import tropo

NAME = "b30_ur6_tropopause"
FIX = np.arange(10000.0, 16001.0, 1000.0)
REL = np.arange(-3000.0, 3001.0, 1000.0)
BAND_ROWS = [("T", "1-5 km", 1000, 5000), ("T", "5-12 km", 5000, 12000), ("T", "12-18 km", 12000, 18001), ("RH", "5-12 km", 5000, 12000), ("RH", "12-18 km", 12000, 18001)]


def raw_balloon(sid):
    """full-grid IGRA heights file -> (times, heights (k,) m above the station, T (n, k) K, RH (n, k) %)."""
    d = np.load(os.path.join(K.REPO, "data", "igra_heights", sid + ".npz"))
    out = {}
    for k in ("T", "RH"):
        x = d[k].astype(float) * 0.1
        x[d[k] == -32768] = np.nan
        out[k] = x
    return pd.DatetimeIndex(d["time"].astype("datetime64[ns]")), d["heights"].astype(float), out["T"], out["RH"]


def anomalies(x, t, sid_idx):
    """remove the station x month mean (per column)."""
    out = np.full_like(x, np.nan)
    for s in np.unique(sid_idx):
        for m in range(1, 13):
            k = (sid_idx == s) & (t.month == m)
            if k.sum() > 5:
                out[k] = x[k] - np.nanmean(x[k], 0)
    return out


def to_rel(T, z, zt, rel):
    """T (n, k) on z -> values at fixed distances rel from each row's tropopause zt (n,), linear in height."""
    out = np.full((len(T), len(rel)), np.nan)
    for i in range(len(T)):
        if not np.isfinite(zt[i]):
            continue
        ok = np.isfinite(T[i])
        if ok.sum() > 5:
            out[i] = np.interp(zt[i] + rel, z[ok], T[i, ok], left=np.nan, right=np.nan)
    return out


def judge0(ratios):
    r = np.asarray(ratios)
    if (r > 0.90).all():
        return "KILL (the coordinate adds nothing; UR6 and E4 close)"
    return "PASS" if (r < 0.70).sum() >= 3 else "MISS"


def step0(lines):
    Ts, Zt, tt, sidx, zgrid = [], [], [], [], None
    for i, sid in enumerate((K.EPZ, K.MAF)):
        t, z, T, _ = raw_balloon(sid)
        keep = (t.year >= 1991) & (t.year <= 2025)
        t, T = t[keep], T[keep]
        zgrid = z if zgrid is None else zgrid
        assert np.allclose(z, zgrid), "the two stations' height grids differ"
        Ts.append(T), Zt.append(tropo.tropopause(T, z)), tt.append(t), sidx.append(np.full(len(t), i))
    T, zt, t, sidx = np.concatenate(Ts), np.concatenate(Zt), pd.DatetimeIndex(np.concatenate([x.values for x in tt])), np.concatenate(sidx)
    base, late = t.year <= 2020, t.year >= 2021
    lines.append(f"  step 0: {len(T)} soundings 1991-2025, tropopause found for {np.isfinite(zt).mean():.1%}; median height {np.nanmedian(zt):.0f} m above the station")
    fixed = to_rel(T, zgrid, np.zeros(len(T)), FIX)                          # fixed heights = distances from 0, missing levels skipped
    rel = to_rel(T, zgrid, zt, REL)
    sf = np.nanstd(anomalies(fixed[base], t[base], sidx[base]), 0)
    sr = np.nanstd(anomalies(rel[base], t[base], sidx[base]), 0)
    lines.append("  (i) T spread after removing station x month means, 1991-2020: fixed height " + ", ".join(f"{h / 1000:.0f} km {s:.2f}" for h, s in zip(FIX, sf))
                 + " | from the tropopause " + ", ".join(f"{d / 1000:+.0f} km {s:.2f}" for d, s in zip(REL, sr)) + " K"
                 + f"; median fixed {np.median(sf):.2f} vs median relative {np.median(sr):.2f}")
    dz = np.nanmean(zt[late]) - np.nanmean(zt[base])
    dT_fix, dT_rel = np.nanmean(fixed[late], 0) - np.nanmean(fixed[base], 0), np.nanmean(rel[late], 0) - np.nanmean(rel[base], 0)
    lines.append(f"  (ii) 2021-25 minus 1991-2020: tropopause height {dz:+.0f} m; mean T change at fixed heights " + ", ".join(f"{x:+.2f}" for x in dT_fix)
                 + " K; at fixed distance from the tropopause " + ", ".join(f"{x:+.2f}" for x in dT_rel) + " K")
    lines.append("  (ii) reading: a height shift if the relative-coordinate change is clearly smaller than the fixed-height change (|mean| "
                 f"{np.nanmean(np.abs(dT_rel)):.2f} vs {np.nanmean(np.abs(dT_fix)):.2f} K)")
    # the rule compares the spreads at the same physical levels: map each fixed level to its typical distance from the tropopause
    med = np.nanmedian(zt)
    paired = []
    for h, s in zip(FIX, sf):
        j = int(np.argmin(np.abs(REL - (h - med))))
        paired.append(sr[j] / s)
    lines.append("      same physical level (fixed height vs the distance it typically has from the tropopause): " + ", ".join(f"{h / 1000:.0f} km {x:.2f}" for h, x in zip(FIX, paired)))
    lines.append("  step 0 verdict (rule on the same-physical-level ratios): " + judge0(paired))


def step1(lines):
    from tempest.scoring.score import coverage90, crps_ensemble
    rng = np.random.default_rng(0)
    H = K.H
    rows = {"fit": [], "test": []}
    bal = {}                                                                 # per station: balloon arrays, for the climatology draws at scoring time
    for sid in (K.EPZ, K.MAF):
        t, b = K.balloon(sid)
        bal[sid] = b
        lat, lon, elev = K.station_pos(sid)
        ok = (t.hour == 0) & np.isfinite(b["T"]).all(1)
        fit_i = np.flatnonzero(ok & (t.year >= 2011) & (t.year <= 2020))
        fit_i = rng.choice(fit_i, min(600, len(fit_i)), replace=False)
        test_i = np.flatnonzero(ok & (t.year >= 2024) & (t.year <= 2025))
        clim_pool = {m: np.flatnonzero(ok & (t.year >= 2009) & (t.year <= 2023) & (t.month == m)) for m in range(1, 13)}
        for part, idx in (("fit", fit_i), ("test", test_i)):
            for i in idx:
                assert K.day_ok(t[i])
                try:
                    atm = K.tool(lat, lon, t[i], seed=int(i) % 1000, n=199, elevation=elev)
                except Exception:   # noqa: BLE001 (an hour the tool cannot serve is skipped)
                    continue
                rows[part].append(dict(t=t[i], T=np.asarray(atm["T"], float), RH=np.asarray(atm["RH"], float), yT=b["T"][i], yRH=b["RH"][i],
                                       sid=sid, pool=clim_pool[t[i].month]))
        lines.append(f"  {sid}: fit {len([r for r in rows['fit']])} / test {len(rows['test'])} soundings so far")
    fit, test = rows["fit"], rows["test"]
    up = (H >= 9000) & (H < 18001)
    maps = {}
    for var in ("T", "RH"):
        X = np.stack([r[var] for r in fit])                                  # (n, m, 44)
        zt_x = np.stack([tropo.tropopause(r["T"], H) for r in fit])         # (n, m) member tropopause
        zt_y = tropo.tropopause(np.stack([r["yT"] for r in fit]), H)
        Y = np.stack([r["y" + var] for r in fit])
        relx = H[None, None, :] - zt_x[:, :, None]                          # (n, m, 44)
        rely = H[None, :] - zt_y[:, None]
        Xu, relxu = X[:, :, up], relx[:, :, up]
        # member-wise distances: flatten members into rows for the map fit
        qm = tropo.fit_qmap(Xu.reshape(-1, 1, up.sum()), Y[:, up], relxu.reshape(-1, up.sum()), rely[:, up])
        maps[var] = qm
        lines.append(f"  map {var}: {qm['ok'].sum()} of {len(qm['ok'])} distance bins fitted (>= 200 values each)")
    res = {}
    for name in ("shipped", "tropopause map"):
        for vb in BAND_ROWS:
            res[(name, vb[0], vb[1])] = []
    days = []
    for r in test:
        zt_x = tropo.tropopause(r["T"], H)
        for var in ("T", "RH"):
            x = r[var]
            x2 = x.copy()
            rel = H[None, :] - zt_x[:, None]
            xu = tropo.apply_qmap(maps[var], x[:, None, up], rel[:, up]).reshape(len(x), up.sum())
            x2[:, up] = xu
            if var == "RH":
                x2[:, up] = np.clip(x2[:, up], 0, 100)                           # only the mapped band is held to 0-100 %
            assert np.array_equal(x2[:, ~up], x[:, ~up]), "a band below 9 km changed"
            y, pool = r["y" + var], bal[r["sid"]][var][r["pool"]]
            for v, bname, lo, hi in BAND_ROWS:
                if v != var:
                    continue
                k = (H >= lo) & (H < hi) & np.isfinite(y)
                if not k.any():
                    for nm in ("shipped", "tropopause map"):
                        res[(nm, v, bname)].append((np.nan, np.nan, np.nan))
                    continue
                cand = pool[np.isfinite(pool[:, k]).all(1)]                       # climatology from soundings complete in this band (same station and month)
                if len(cand) < 20:
                    for nm in ("shipped", "tropopause map"):
                        res[(nm, v, bname)].append((np.nan, np.nan, np.nan))
                    continue
                c = cand[rng.choice(len(cand), 199, replace=len(cand) < 199)]
                cc = crps_ensemble(c[None][:, :, k], y[None, k]).mean()
                for nm, xx in (("shipped", x), ("tropopause map", x2)):
                    cr = crps_ensemble(xx[None][:, :, k], y[None, k]).mean()
                    cov = coverage90(xx[None][:, :, k], y[None, k], 0.99).mean()
                    res[(nm, v, bname)].append((cr, cc, cov))
        days.append(r["t"])
    day = pd.DatetimeIndex(days)
    blk = ((day.normalize() - pd.Timestamp("2024-01-01")).days // 21).astype(int)
    out = {}
    for v, bname, *_ in BAND_ROWS:
        a, b = np.array(res[("shipped", v, bname)]), np.array(res[("tropopause map", v, bname)])
        ok = np.isfinite(a[:, 0]) & np.isfinite(b[:, 0])
        sk_a, sk_b = 1 - a[ok, 0].sum() / a[ok, 1].sum(), 1 - b[ok, 0].sum() / b[ok, 1].sum()
        dm, lo, hi = K.block_boot((b[ok, 0] - a[ok, 0]) / a[ok, 1].mean(), blk[ok], draws=1000)   # skill change = -(CRPS change) / clim CRPS
        out[(v, bname)] = dict(dsk=sk_b - sk_a, lo=-hi, hi=-lo, cov=b[ok, 2].mean(), cov0=a[ok, 2].mean())
        lines.append(f"  {v} {bname:<8}: skill vs balloon clim15 {sk_a:+.4f} -> {sk_b:+.4f} (change {sk_b - sk_a:+.4f} [{-hi:+.4f}, {-lo:+.4f}]); cov99 {a[ok, 2].mean():.3f} -> {b[ok, 2].mean():.3f}; n {ok.sum()}")
    return out


def judge1(out):
    t = out[("T", "12-18 km")]
    if t["dsk"] < 0:
        return "KILL (T 12-18 km skill worse)"
    lower_same = abs(out[("T", "1-5 km")]["dsk"]) < 1e-12
    mean_change = np.mean([v["dsk"] for v in out.values()])
    ok = t["dsk"] >= 0.010 and t["lo"] > 0 and out[("RH", "12-18 km")]["cov"] >= 0.97 and lower_same and mean_change >= -0.0009
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, choices=(0, 1), required=True)
    a = ap.parse_args()
    K.ram_gate(4.0)
    lines = [f"UR6 tropopause coordinate, step {a.step}"]
    if a.step == 0:
        step0(lines)
    else:
        lines.append("Verdict: " + judge1(step1(lines)))
    lines.append("Rule (pre-set, New_Plan 17.1): step 0 PASS = relative spread < 70 % of fixed-height spread at >= 3 levels, KILL = > 90 % at all; "
                 "step 1 PASS = T 12-18 km skill +0.010 with interval > 0, RH 12-18 km cov99 >= 0.97, no band below 9 km changed, mean skill not worse by > 0.0009.")
    K.report(NAME, lines)


def _selfcheck():
    z = np.arange(0.0, 20001.0, 250.0)
    zt_true = np.array([11000.0, 15000.0])
    T = np.stack([np.where(z < h, 288.0 - 6.5 * z / 1000, 288.0 - 6.5 * h / 1000 + 0.5 * (z - h) / 1000) for h in zt_true])
    zt = tropo.tropopause(T, z)
    assert np.allclose(zt, zt_true, atol=250.0), zt
    rel = to_rel(T, z, zt, REL)
    assert np.allclose(rel[:, REL == 0].ravel(), 288.0 - 6.5 * zt / 1000, atol=0.2)
    assert judge0([0.5, 0.6, 0.65, 0.95]) == "PASS" and judge0([0.95, 0.99]).startswith("KILL") and judge0([0.5, 0.8, 0.85]) == "MISS"
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, (400, 20, 6))
    y = rng.normal(1, 1, (400, 6))
    r = np.tile(np.linspace(-2000, 2000, 6), (400, 1))
    qm = tropo.fit_qmap(x, y, r, r)
    x2 = tropo.apply_qmap(qm, x, r)
    assert abs(x2.mean() - 1.0) < 0.1 and abs(x.mean()) < 0.1
    assert np.array_equal(np.argsort(x2[0, :, 0]), np.argsort(x[0, :, 0]))


_selfcheck()
if __name__ == "__main__":
    main()
