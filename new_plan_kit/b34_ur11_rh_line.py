"""New_Plan 17 UR11: the RH station line above 5 km refitted on recent years. Changes nothing in the tool (maps built in memory).
Object scored: the past-mode hybrid's station correction (a + b ERA5 + leftover profile; models/station_map_mix.npz), as b3_rh_widen.py
scored it, at 00Z, both stations. AU-5 found the 2021-23 balloons 8-11 % drier aloft than the 1991-2020 line.
Arms on the same draws (199 rng streams per sounding, as b3_rh_widen):
  shipped   models/station_map_mix.npz as it is
  recent    the same map with the RH lines (a, b) at heights >= 5 km refitted per group on 2016-2022 00Z pairs (station.fit, lines only);
            every other line and the whole leftover pool (1991-2020) kept
  + tails   only if recent leaves RH 12-18 km cov99 under 0.97: UR1's tail table (tempest/forecast/tailcal.py) on the recent arm's RH columns,
            fitted on 2023 00Z soundings (outside the line fit years), information only
Test: 2024-25 00Z soundings. Skill = 1 - CRPS / CRPS(balloon climatology: 199 soundings of the same station and month, 2009-2023 = the 15 years
before the test); cov99 = the scorer's 99 % range (lowest to highest of 199); 21-day blocks.
Rule (set 2026-11-13 in New_Plan 17.2 before any run):
  PASS: RH 5-12 km skill above 0 (the README's balloon number is -0.015) AND RH 12-18 km cov99 up by at least 0.01, with the RH 5-18 km CRPS
        not worse by more than 0.5 %.  KILL: RH 5-18 km CRPS worse by more than 1.5 %.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b34_ur11_rh_line.py        # about 20-40 min
Result: docs/results/logs/kit_b34_ur11_rh_line.log
"""
import copy

import numpy as np

import kit_common as K
from tempest.calibrate import station
from tempest.forecast import modeP as P
from tempest.scoring.score import coverage90, crps_ensemble

NAME = "b34_ur11_rh_line"
M = 199
RH_I = 3                                           # station profiles are (u, v, T, RH) x 44 heights (station.read_igra)


def cols_of(band):
    return next(np.flatnonzero(s) for v, b, s in P.names() if v == "RH" and b == band)


def recent_map(tmap, d, years=(2016, 2022)):
    yr, hr = d["time"].year.to_numpy(), d["time"].hour.to_numpy()
    m = (yr >= years[0]) & (yr <= years[1]) & (hr == 0)
    g = station.group_id(d["station"][m], d["time"].month.to_numpy()[m], np.zeros(m.sum(), int))
    f = station.fit(d["era"][m], d["obs"][m], g, tmap["a"].shape[0], pool_max=50)
    new = copy.deepcopy(tmap)
    up = np.asarray(K.H) >= 5000
    for name in ("a", "b"):
        x = np.array(new[name], copy=True)
        x[:, RH_I, up] = f[name][:, RH_I, up]
        new[name] = x
    moved = np.abs(new["a"][:, RH_I, up] - np.asarray(tmap["a"])[:, RH_I, up]).mean()
    return new, float(moved), int(m.sum())


def draws(tmap, dd, cols):
    g = station.group_id(dd["station"], dd["time"].month.to_numpy(), np.zeros(len(dd["era"]), int))
    out = np.empty((len(dd["era"]), M, len(cols)), np.float32)
    for j in range(M):
        out[:, j] = station.apply(tmap, dd["era"], g, np.random.default_rng(j)).reshape(len(dd["era"]), -1)[:, cols]
    return out


def clim(d, dd, cols, rng):
    """balloon climatology draws (n, 199, c): soundings of the same station and month, 2009-2023."""
    yr = d["time"].year.to_numpy()
    obs = d["obs"].reshape(len(d["obs"]), -1)[:, cols]
    pool = (yr >= 2009) & (yr <= 2023) & np.isfinite(obs).all(1)
    out = np.empty((len(dd["era"]), M, len(cols)), np.float32)
    for i in range(len(dd["era"])):
        k = np.flatnonzero(pool & (d["station"] == dd["station"][i]) & (d["time"].month.to_numpy() == dd["time"].month[i]))
        out[i] = obs[rng.choice(k, M, replace=len(k) < M)]
    return out


def judge(sk512, dcov1218, crps_pct):
    if crps_pct > 1.5:
        return "KILL"
    return "PASS" if sk512 > 0 and dcov1218 >= 0.01 and crps_pct <= 0.5 else "MISS (record, no adoption)"


def main():
    K.ram_gate(4.0)
    d = P.load_pairs("data/pilot/profiles80.zarr", "data/raw/igra")
    yr, hr = d["time"].year.to_numpy(), d["time"].hour.to_numpy()
    tmap = station.load("models/station_map_mix.npz")
    new, moved, nfit = recent_map(tmap, d)
    lines = [f"UR11: RH station line >= 5 km refitted on {nfit} 2016-22 00Z pairs (mean |change of a| {moved:.2f} RH points); test 2024-25 00Z; 21-day blocks"]
    test = (yr >= 2024) & (yr <= 2025) & (hr == 0)
    dd = {k: v[test] for k, v in d.items()}
    day = (dd["time"].normalize() - np.datetime64("2024-01-01")).days.to_numpy() // 21
    rng = np.random.default_rng(5)
    res = {}
    for band in ("5-12 km", "12-18 km"):
        cols = cols_of(band)
        y = dd["obs"].reshape(len(dd["era"]), -1)[:, cols]
        ok = np.isfinite(y).all(1)
        c = clim(d, {k: v[ok] for k, v in dd.items()}, cols, rng)
        cc = crps_ensemble(c, y[ok]).mean(1)
        for arm, tm in (("shipped", tmap), ("recent", new)):
            x = draws(tm, {k: v[ok] for k, v in dd.items()}, cols)
            cr = crps_ensemble(x, y[ok]).mean(1)
            res[(arm, band)] = dict(crps=cr, clim=cc, cov=coverage90(x, y[ok], 0.99).mean(1), x=x, y=y[ok], day=day[ok])
    for band in ("5-12 km", "12-18 km"):
        a, b = res[("shipped", band)], res[("recent", band)]
        dm, lo, hi = K.block_boot(b["crps"] - a["crps"], a["day"], draws=1000)
        lines.append(f"  RH {band:<8}: skill vs balloon clim15 {1 - a['crps'].sum() / a['clim'].sum():+.4f} -> {1 - b['crps'].sum() / b['clim'].sum():+.4f}; "
                     f"cov99 {a['cov'].mean():.3f} -> {b['cov'].mean():.3f}; CRPS {a['crps'].mean():.3f} -> {b['crps'].mean():.3f} ({dm:+.3f} [{lo:+.3f}, {hi:+.3f}]); n {len(a['crps'])}")
    sk512 = 1 - res[("recent", "5-12 km")]["crps"].sum() / res[("recent", "5-12 km")]["clim"].sum()
    dcov = res[("recent", "12-18 km")]["cov"].mean() - res[("shipped", "12-18 km")]["cov"].mean()
    tot0 = sum(res[("shipped", b)]["crps"].sum() for b in ("5-12 km", "12-18 km"))
    tot1 = sum(res[("recent", b)]["crps"].sum() for b in ("5-12 km", "12-18 km"))
    pct = 100 * (tot1 / tot0 - 1)
    lines.append(f"  RH 5-18 km CRPS change {pct:+.2f} %")
    if res[("recent", "12-18 km")]["cov"].mean() < 0.97:                 # + tails (information)
        from tempest.forecast import tailcal as TC
        cols = cols_of("12-18 km")
        fitm = (yr == 2023) & (hr == 0)
        df = {k: v[fitm] for k, v in d.items()}
        yf = df["obs"].reshape(len(df["era"]), -1)[:, cols]
        okf = np.isfinite(yf).all(1)
        xf = draws(new, {k: v[okf] for k, v in df.items()}, cols)
        lab = np.full(len(cols), "RH")
        tab = TC.fit(xf, yf[okf], np.zeros(okf.sum(), int), lab, min_rows=50, smooth=False)
        r = res[("recent", "12-18 km")]
        x2 = TC.apply(tab, r["x"], np.zeros(len(r["y"]), int), lab)
        lines.append(f"  + tails (information): factors lo {tab['lo'][0, 0]:.2f} hi {tab['hi'][0, 0]:.2f} (fit 2023, {okf.sum()} soundings); RH 12-18 km cov99 "
                     f"{r['cov'].mean():.3f} -> {coverage90(x2, r['y'], 0.99).mean(1).mean():.3f}, CRPS {r['crps'].mean():.3f} -> {crps_ensemble(x2, r['y']).mean(1).mean():.3f}")
    lines.append("Rule (pre-set, New_Plan 17.2): PASS = RH 5-12 km skill > 0 and RH 12-18 km cov99 +0.01 with RH 5-18 km CRPS <= +0.5 %; KILL = CRPS > +1.5 %.")
    lines.append("Verdict: " + judge(sk512, dcov, pct))
    K.report(NAME, lines)


def _selfcheck():
    assert judge(0.001, 0.012, 0.3) == "PASS"
    assert judge(-0.01, 0.012, 0.3).startswith("MISS")
    assert judge(0.01, 0.02, 1.6) == "KILL"
    assert len(cols_of("12-18 km")) > 0


_selfcheck()
if __name__ == "__main__":
    main()
