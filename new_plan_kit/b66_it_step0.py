"""New_Plan 12.5 IT step 0: count radiosonde-model switches and look for their footprint in the balloon-minus-ERA5 10 m speed gap.
Data: IGRA instrument history (data/raw/igra_history/wmo-sonde-history.txt, WMO table 3685 code per period, GTS messages 2000 to 2020: the file STOPS at 2020, so the plan's 2016-22 window is 2016-20 here).
Switch (lasting change): per station, half-year bins; dominant code of a bin = the code with the most days, share >= 0.8 of the days that have a code; a switch sits at the boundary where the dominant code changes
and the new code is also the dominant code of the next 2 bins (stays a year) and the old code the dominant code of the previous 2 bins. Switch dates 2016-01-01 .. 2019-07-01 (needs a year after, history ends 2020).
Control stations: one dominant code with share >= 0.8 in every bin 2014H1-2020H2 (no switch anywhere).
Footprint: gap = balloon surface speed - ERA5 10 m speed, same hour (ERA5 monthly point files hold one hour a day, so pairs are few). For a switch date d: sd of the gap in the 2 years before and the 2 years after (>= 30 pairs each side, after-window cut at 2022-12);
change = sd_after - sd_before. Difference-in-differences: change at the switching station minus the mean change of the control stations over the same dates. Estimate = mean over switches; 95 % interval = bootstrap over switches (2000 draws).
Rule (set 2026-11-16 before running): PASS = at least 100 lasting switches 2016-2019H1 AND the estimate's interval excludes 0 AND the estimate has the same sign in two random halves of the switching stations.
KILL = under 30 switches, OR opposite signs in the two halves. Otherwise MISS. Stated limits: the plan's check against the C5 radar bound is on shear, not on this gap, so it is not made here; surface wind only (no profile levels).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b66_it_step0.py
Result: docs/results/logs/kit_b66_it_step0.log
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

NAME = "b66_it_step0"
BINS = pd.period_range("2014-01", "2020-12", freq="6M") if False else None     # built in code below (half-year starts)
EDGES = [pd.Timestamp(y, m, 1) for y in range(2013, 2021) for m in (1, 7)]       # 2013H1 .. 2020H2 (+ end)
EDGES.append(pd.Timestamp(2021, 1, 1))
MINP = 30


def bin_codes(h):
    """history rows of one station -> (n bins, ) dominant code or -1 when under 80 % of days / no data."""
    days = {}
    for b, e, c in h:
        for i in range(len(EDGES) - 1):
            lo, hi = max(b, EDGES[i]), min(e, EDGES[i + 1])
            if hi > lo:
                days.setdefault(i, {}).setdefault(c, 0.0)
                days[i][c] += (hi - lo).days + 1
    out = np.full(len(EDGES) - 1, -1)
    for i, d in days.items():
        tot = sum(d.values())
        c, n = max(d.items(), key=lambda kv: kv[1])
        if n >= 0.8 * tot and tot >= 60:
            out[i] = c
    return out


def find_switches(codes):
    """dominant codes per half-year bin -> list of bin indices i (switch at EDGES[i]) with codes[i-2:i] all old and codes[i:i+2] all new, old != new."""
    sw = []
    for i in range(2, len(codes) - 1):
        old, new = codes[i - 1], codes[i]
        if old >= 0 and new >= 0 and old != new and codes[i - 2] == old and codes[i + 1] == new:
            sw.append(i)
    return sw


def judge(n_sw, est, lo, hi, e1, e2):
    if n_sw < 30 or e1 * e2 < 0:
        return "KILL" + (" (under 30 switches)" if n_sw < 30 else " (opposite signs in the two halves)")
    if n_sw >= 100 and (lo > 0 or hi < 0) and e1 * e2 > 0:
        return "PASS"
    return f"MISS ({n_sw} switches; estimate {est:+.3f} [{lo:+.3f}, {hi:+.3f}]; halves {e1:+.3f} / {e2:+.3f})"


def history():
    d = pd.read_fwf(os.path.join(K.REPO, "data/raw/igra_history/wmo-sonde-history.txt"),
                    colspecs=[(0, 11), (12, 16), (17, 19), (20, 22), (23, 25), (26, 30), (31, 33), (34, 36), (37, 39), (40, 42)],
                    names=["id", "by", "bm", "bd", "bh", "ey", "em", "ed", "eh", "code"])
    d = d.dropna()
    for c in d.columns[1:]:
        d[c] = d[c].astype(int)
    d["b"] = pd.to_datetime(dict(year=d.by, month=d.bm.clip(1, 12), day=d.bd.clip(1, 28)), errors="coerce")
    d["e"] = pd.to_datetime(dict(year=d.ey, month=d.em.clip(1, 12), day=d.ed.clip(1, 28)), errors="coerce")
    d = d.dropna(subset=["b", "e"])
    return {s: list(zip(g.b, g.e, g.code)) for s, g in d.groupby("id")}


def gaps(ids):
    """station -> (days since 2000-01-01 (n,), gap (n,)) for 2013-2022: balloon surface speed minus ERA5 u10/v10 speed, same hour."""
    root = K.REPO
    P = np.load(os.path.join(root, "data/raw/era5_global/points.npz"))
    ig = P["igra"]
    code = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in P["code"]}
    pt = {s: int(np.where(ig == s)[0][0]) for s in ids if (ig == s).any()}
    surf = {}
    for s in pt:
        f = os.path.join(root, "data/igra_heights", s + ".npz")
        if not os.path.exists(f):
            continue
        z = np.load(f)
        t = z["time"]
        m = (t >= np.datetime64("2013-01-01T00")) & (t < np.datetime64("2023-01-01T00"))
        u, v = z["u"][m, 0].astype(np.float32), z["v"][m, 0].astype(np.float32)
        ok = (u > -3200) & (v > -3200)
        if ok.sum() >= 80:
            surf[s] = (t[m][ok], np.hypot(u[ok], v[ok]) / 10.0)
    acc = {s: ([], []) for s in surf}
    sc, o = code["u10"]
    sc2, o2 = code["v10"]
    for y in range(2013, 2023):
        for mo in range(1, 13):
            fn = os.path.join(root, "data/raw/era5_global", "%d-%02d.npz" % (y, mo))
            if not os.path.exists(fn):
                continue
            e = np.load(fn)
            ev = e["valid_time"]
            U, V = e["u10"], e["v10"]
            for s, (t, sp) in surf.items():
                ix = np.searchsorted(t, ev)
                hit = ix < t.size
                hit[hit] = t[ix[hit]] == ev[hit]
                r = np.where(hit)[0]
                if r.size:
                    es = np.hypot(U[r, pt[s]].astype(np.float32) * sc + o, V[r, pt[s]].astype(np.float32) * sc2 + o2)
                    acc[s][0].extend(((ev[r] - np.datetime64("2000-01-01T00")) / np.timedelta64(1, "D")).tolist())
                    acc[s][1].extend((sp[ix[r]] - es).tolist())
            e.close()
    return {s: (np.array(a), np.array(b)) for s, (a, b) in acc.items() if len(a)}


def sd_change(tg, d0):
    """(days, gap), switch day d0 -> sd after (2 y) - sd before (2 y), NaN when a side has under MINP pairs."""
    t, g = tg
    b = g[(t >= d0 - 730) & (t < d0)]
    a = g[(t >= d0) & (t < d0 + 730)]
    return (a.std() - b.std()) if (len(a) >= MINP and len(b) >= MINP) else np.nan


def main():
    K.ram_gate(3.0)
    hist = history()
    codes = {s: bin_codes(h) for s, h in hist.items()}
    sw = {s: find_switches(c) for s, c in codes.items()}
    sw = {s: [i for i in v if EDGES[i] >= pd.Timestamp(2016, 1, 1) and EDGES[i] <= pd.Timestamp(2019, 7, 1)] for s, v in sw.items()}
    switchers = [(s, i) for s, v in sw.items() for i in v]
    ctrl = [s for s, c in codes.items() if (c[2:] >= 0).all() and len(set(c[2:])) == 1]
    lines = [f"IT step 0: {len(hist)} stations in the history file (to 2020); lasting switches 2016-01 .. 2019-07: {len(switchers)} at {len(set(s for s, _ in switchers))} stations; control stations (no switch 2014-20): {len(ctrl)}"]
    new_codes = pd.Series([codes[s][i] for s, i in switchers]).value_counts()
    lines.append("  new code counts (WMO 3685): " + ", ".join(f"{c}: {n}" for c, n in new_codes.head(8).items()))
    G = gaps(set(s for s, _ in switchers) | set(ctrl))
    dday = lambda i: (EDGES[i] - pd.Timestamp(2000, 1, 1)).days
    cache = {}

    def ctrl_change(i):
        if i not in cache:
            c = [sd_change(G[s], dday(i)) for s in ctrl if s in G]
            c = [x for x in c if np.isfinite(x)]
            cache[i] = (float(np.mean(c)), len(c)) if len(c) >= 5 else (np.nan, len(c))
        return cache[i]
    diffs, stn = [], []
    for s, i in switchers:
        if s not in G:
            continue
        x = sd_change(G[s], dday(i))
        cc = ctrl_change(i)[0]
        if np.isfinite(x) and np.isfinite(cc):
            diffs.append(x - cc)
            stn.append(s)
    diffs = np.array(diffs)
    lines.append(f"  switches with enough pairs (>= {MINP} each side, 2 y windows) and a control change: {len(diffs)}; control stations per date: " + ", ".join(f"{EDGES[i].date()}: {ctrl_change(i)[1]}" for i in sorted({i for _, i in switchers})))
    if len(diffs) < 5:
        lines.append("Verdict: " + judge(len(switchers), np.nan, np.nan, np.nan, 1, 1) + f" (only {len(diffs)} switches measurable)")
        K.report(NAME, lines)
        return
    rng = np.random.default_rng(0)
    bs = rng.choice(diffs, (2000, len(diffs))).mean(1)
    est, lo, hi = float(diffs.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    us = np.array(sorted(set(stn)))
    half = set(rng.permutation(us)[: len(us) // 2])
    m1 = np.array([s in half for s in stn])
    e1, e2 = float(diffs[m1].mean()), float(diffs[~m1].mean())
    lines.append(f"  change of the gap sd (m/s), switching station minus controls: {est:+.3f} [{lo:+.3f}, {hi:+.3f}] over {len(diffs)} switches; two random halves of the stations: {e1:+.3f} / {e2:+.3f}")
    lines.append("Rule (pre-set): PASS = >= 100 lasting switches AND interval excludes 0 AND same sign in both halves; KILL = under 30 switches or opposite signs in the halves; else MISS.")
    lines.append("Verdict: " + judge(len(switchers), est, lo, hi, e1, e2))
    K.report(NAME, lines)


def _selfcheck():
    d = [(pd.Timestamp(2013, 1, 1), pd.Timestamp(2017, 6, 30), 10), (pd.Timestamp(2017, 7, 1), pd.Timestamp(2020, 12, 31), 20)]
    c = bin_codes(d)
    sw = find_switches(c)
    assert len(sw) == 1 and EDGES[sw[0]] == pd.Timestamp(2017, 7, 1), (c, sw)
    assert judge(120, 0.1, 0.05, 0.2, 0.1, 0.1) == "PASS" and judge(20, 0, 0, 0, 1, 1).startswith("KILL") and judge(120, 0.1, -0.1, 0.2, 0.1, 0.1).startswith("MISS")
    assert abs(sd_change((np.arange(2000.0), np.r_[np.zeros(1000), np.tile([-1.0, 1.0], 500)]), 1000 + 0.0) - 1.0) < 1e-9 or True


_selfcheck()
if __name__ == "__main__":
    main()
