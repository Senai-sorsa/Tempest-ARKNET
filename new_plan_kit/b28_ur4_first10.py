"""New_Plan 17 UR4 FIRST-10: a pad's own 10 m wind offset from its first days of readings, shrunk toward the regional value. Changes nothing.
Data (as SV step 0, b6_ideas_step0 part c, all stations instead of 90): 10 m wind of the balloon surface report (IGRA, data/igra_heights level 0)
against the ERA5 10 m wind at the station's grid point (data/raw/era5_global), every matching time 2016-2025 (never 2026).
Two folds of stations by a fixed crc32 hash; everything fitted on one fold (years 2016-21) is used on the other, then the folds swap, so every
station is a "new pad" for numbers it never helped fit:
  regional offset mu, between-station sd s_b, reading scatter s_r (sd of single readings around the station mean), and
  k = (variance of one day's mean offset around the station mean) / s_b^2 (in days): the shrinkage weight is w = n / (n + k).
Replay per held-out station: the first n days with a report in 2022 (n = 3, 5, 10, 30) give the plain average m_n; test reports 2023-25.
Predictive for the station's 10 m speed = Gaussian around ERA5 speed + offset (offset form; SV measured the offset in m/s; a ratio form is
--form ratio): arms
  none            mu,                       sd sqrt(s_r^2 + s_b^2)     (no site term: the regional value and the full between-station spread)
  plain           m_n,                      sd s_r
  shrink          w m_n + (1 - w) mu,       sd s_r
  shrink+spread   w m_n + (1 - w) mu,       sd sqrt(s_r^2 + (1 - w) s_b^2)   (the leftover uncertainty of the offset kept as spread)
Gaussian CRPS (closed form), 90 % coverage of the central Gaussian interval.
Step 0 (fold-out, n = 10): share of the variance of a station's later offset (2023-25 mean) explained by the shrunk 10-day estimate; STOP if under 0.40.
Rule (set 2026-11-13 in New_Plan 17.1 before any run), arm shrink+spread at n = 10:
  PASS: CRPS better than 'none' with the interval below 0 (blocks = station x 21 days), at least 75 % of stations better, no station worse by
        more than 0.03, coverage 0.85-0.95; and at n = 3 'shrink' not worse than 'plain'.
  KILL: not better than 'none' at n = 30.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b28_ur4_first10.py [--form offset|ratio]
Correction 2026-11-14 23:30 (input step only, rule unchanged): the first run (23:16) crashed on a station with no 2016-25 balloon report;
such stations are now skipped (they had no pairs, so the >= 100-pair filter dropped them anyway).
Result: docs/results/logs/kit_b28_ur4_first10.log
"""
import argparse
import glob
import os
import zlib

import numpy as np
from scipy.stats import norm

import kit_common as K

NS = (3, 5, 10, 30)
FIT_YEARS, FEED_YEAR, TEST_YEARS = (2016, 2021), 2022, (2023, 2025)
Z90 = 1.6448536
NAME = "b28_ur4_first10"


def crps_gauss(mu, sd, x):
    z = (x - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def load_pairs():
    """-> {station: (times datetime64[h], obs speed, ERA5 speed)} for every matching time 2016-2025."""
    HRES, ERA5 = os.path.join(K.REPO, "data/raw/wb2_hres_global"), os.path.join(K.REPO, "data/raw/era5_global")
    P = np.load(os.path.join(HRES, "points.npz"))
    ig = P["igra"]
    ecode = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in np.load(os.path.join(ERA5, "points.npz"))["code"]}
    files = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(K.REPO, "data/igra_heights/*.npz"))}
    ids = sorted(s for s in np.unique(ig[ig != ""]) if s in files)
    pt = np.array([np.where(ig == s)[0][0] for s in ids])
    bal = {}
    for s in ids:
        z = np.load(files[s])
        t = z["time"].astype("datetime64[h]")
        m = (t >= np.datetime64("2016-01-01T00")) & (t < np.datetime64("2026-01-01T00"))
        u, v = z["u"][m, 0].astype(np.float32), z["v"][m, 0].astype(np.float32)
        ok = (u > -32000) & (v > -32000)
        bal[s] = (t[m][ok], np.hypot(u[ok], v[ok]) / 10.0)
    acc = {s: ([], [], []) for s in ids}
    for y in range(2016, 2026):
        for mo in range(1, 13):
            fn = os.path.join(ERA5, f"{y}-{mo:02d}.npz")
            if not os.path.exists(fn):
                continue
            e = np.load(fn)
            ev = e["valid_time"].astype("datetime64[h]")
            (su, ou), (sv, ov) = ecode["u10"], ecode["v10"]
            eu, evv = e["u10"][:, pt].astype(np.float32) * su + ou, e["v10"][:, pt].astype(np.float32) * sv + ov
            for k, s in enumerate(ids):
                t, w = bal[s]
                if not len(t):                     # station without 2016-25 balloon reports (crashed the first run, 2026-11-14 23:17)
                    continue
                ix = np.searchsorted(t, ev)
                hit = (ix < len(t)) & (t[np.minimum(ix, len(t) - 1)] == ev)
                r = np.flatnonzero(hit)
                acc[s][0].extend(ev[r]), acc[s][1].extend(w[ix[r]]), acc[s][2].extend(np.hypot(eu[r, k], evv[r, k]))
            e.close()
    return {s: tuple(np.asarray(x) for x in v) for s, v in acc.items() if len(v[0]) >= 100}


def offset(obs, era, form):
    return obs - era if form == "offset" else obs / np.maximum(era, 0.5)


def predict(era, off, form):
    return era + off if form == "offset" else era * off


def fit_fold(pairs, form):
    """stations' fit-year pairs -> dict mu, s_b, s_r, k."""
    means, wvar, dayvar, nread = [], [], [], []
    for t, o, e in pairs.values():
        y = t.astype("datetime64[Y]").astype(int) + 1970
        k = (y >= FIT_YEARS[0]) & (y <= FIT_YEARS[1])
        if k.sum() < 50:
            continue
        x, d = offset(o[k], e[k], form), t[k].astype("datetime64[D]")
        ud, inv = np.unique(d, return_inverse=True)
        dm = np.bincount(inv, x) / np.bincount(inv)
        means.append(x.mean()), wvar.append(x.var()), dayvar.append(dm.var()), nread.append(len(x))
    means = np.asarray(means)
    se2 = np.mean(np.asarray(wvar) / np.asarray(nread))
    s_b2 = max(means.var() - se2, 1e-6)
    return dict(mu=float(means.mean()), s_b=float(np.sqrt(s_b2)), s_r=float(np.sqrt(np.mean(wvar))), k=float(np.mean(dayvar) / s_b2), n_st=len(means))


def replay(pairs, fit, form):
    """held-out stations -> {n: {arm: per-report (crps, covered, station, block)}} and step 0 numbers."""
    out = {n: {a: [] for a in ("none", "plain", "shrink", "shrink+spread")} for n in NS}
    est10, later = [], []
    for s, (t, o, e) in pairs.items():
        y = t.astype("datetime64[Y]").astype(int) + 1970
        feed, test = y == FEED_YEAR, (y >= TEST_YEARS[0]) & (y <= TEST_YEARS[1])
        if feed.sum() < 2 or test.sum() < 20:
            continue
        xf, df = offset(o[feed], e[feed], form), t[feed].astype("datetime64[D]")
        ud, inv = np.unique(df, return_inverse=True)
        dm = np.bincount(inv, xf) / np.bincount(inv)
        blk = (t[test].astype("datetime64[D]").astype(int) // 21).astype(str)
        later_mean = offset(o[test], e[test], form).mean()
        for n in NS:
            if len(dm) < n:
                continue
            m_n = dm[:n].mean()
            w = n / (n + fit["k"])
            sh = w * m_n + (1 - w) * fit["mu"]
            arms = {"none": (fit["mu"], np.hypot(fit["s_r"], fit["s_b"])), "plain": (m_n, fit["s_r"]), "shrink": (sh, fit["s_r"]),
                    "shrink+spread": (sh, np.sqrt(fit["s_r"] ** 2 + (1 - w) * fit["s_b"] ** 2))}
            for a, (off, sd) in arms.items():
                mu = predict(e[test], off, form)
                sdv = sd if form == "offset" else sd * np.maximum(e[test], 0.5)
                c = crps_gauss(mu, sdv, o[test])
                cov = np.abs(o[test] - mu) <= Z90 * sdv
                out[n][a] += [(cc, vv, s, s + b) for cc, vv, b in zip(c, cov, blk)]
            if n == 10:
                est10.append(sh), later.append(later_mean)
    est10, later = np.asarray(est10), np.asarray(later)
    explained = 1 - np.mean((later - est10) ** 2) / max(np.var(later), 1e-12) if len(later) > 2 else np.nan
    return out, explained


def summarise(res, n, arm, ref="none"):
    a, r = res[n][arm], res[n][ref]
    c, cr = np.array([x[0] for x in a]), np.array([x[0] for x in r])
    st, blk = np.array([x[2] for x in a]), np.array([x[3] for x in a])
    dm, lo, hi = K.block_boot(c - cr, blk, draws=1000)
    per = {s: (c[st == s] - cr[st == s]).mean() for s in np.unique(st)}
    return dict(diff=dm, lo=lo, hi=hi, share_better=np.mean([v < 0 for v in per.values()]), worst=max(per.values()), cov=float(np.mean([x[1] for x in a])),
                crps=float(c.mean()), n_st=len(per))


def judge(s10, s30, s3_shrink_vs_plain, explained):
    if explained < 0.40:
        return "STOP at step 0 (the shrunk 10-day estimate explains under 40 % of the later offset)"
    if s30["diff"] >= 0:                                        # not better than 'none' even with 30 days of readings
        return "KILL"
    ok = s10["hi"] < 0 and s10["share_better"] >= 0.75 and s10["worst"] <= 0.03 and 0.85 <= s10["cov"] <= 0.95 and s3_shrink_vs_plain["diff"] <= 0
    return "PASS" if ok else "MISS (record, no adoption)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", choices=("offset", "ratio"), default="offset")
    a = ap.parse_args()
    K.ram_gate(4.0)
    pairs = load_pairs()
    fold = {s: zlib.crc32(s.encode()) % 2 for s in pairs}
    lines = [f"UR4 FIRST-10 ({a.form} form): {len(pairs)} stations with >= 100 balloon-ERA5 10 m pairs 2016-25; fit {FIT_YEARS}, feed {FEED_YEAR}, test {TEST_YEARS}"]
    res, expl = {n: {} for n in NS}, []
    for f in (0, 1):
        fit = fit_fold({s: v for s, v in pairs.items() if fold[s] == f}, a.form)
        r, e = replay({s: v for s, v in pairs.items() if fold[s] != f}, fit, a.form)
        expl.append(e)
        lines.append(f"  fold {f} fit ({fit['n_st']} stations): mu {fit['mu']:+.3f}, s_b {fit['s_b']:.3f}, s_r {fit['s_r']:.3f}, k {fit['k']:.1f} days "
                     f"(w at n = 10: {10 / (10 + fit['k']):.2f}); step 0 on the other fold: explained {e:.2f}")
        for n in NS:
            for arm, v in r[n].items():
                res[n].setdefault(arm, []).extend(v)
    S = {n: {arm: summarise(res, n, arm) for arm in ("plain", "shrink", "shrink+spread")} for n in NS if res[n].get("none")}
    for n, d in S.items():
        lines.append(f"  n = {n:>2} days: " + "; ".join(f"{arm} minus none {v['diff']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}], better at {v['share_better']:.0%} of "
                                                     f"{v['n_st']} stations, worst {v['worst']:+.3f}, coverage {v['cov']:.2f}" for arm, v in d.items()))
    s3 = summarise(res, 3, "shrink", ref="plain")
    lines.append(f"  n = 3: shrink minus plain {s3['diff']:+.4f} [{s3['lo']:+.4f}, {s3['hi']:+.4f}]")
    lines.append("Rule (pre-set, New_Plan 17.1): step 0 explained >= 0.40; PASS = shrink+spread at n = 10 better than none (interval < 0), >= 75 % of stations "
                 "better, none worse by > 0.03, coverage 0.85-0.95, and shrink not worse than plain at n = 3; KILL = not better than none at n = 30.")
    lines.append("Verdict: " + judge(S[10]["shrink+spread"], S[30]["shrink+spread"], s3, float(np.nanmin(expl))))
    K.report(NAME, lines)


def _selfcheck():
    assert abs(crps_gauss(0.0, 1.0, 0.0) - 0.2337) < 1e-3
    rng = np.random.default_rng(0)
    pairs = {}
    for i in range(60):                                         # stations with a true offset (sd 1) and reading scatter 2, two reports a day
        off = rng.normal(0, 1.0)
        t = np.arange(np.datetime64("2016-01-01T00"), np.datetime64("2025-12-31T00"), np.timedelta64(12, "h"))
        e = rng.uniform(2, 8, len(t))
        pairs[f"S{i}"] = (t, e + off + rng.normal(0, 2.0, len(t)), e)
    fit = fit_fold(pairs, "offset")
    assert abs(fit["s_b"] - 1.0) < 0.25 and abs(fit["s_r"] - 2.0) < 0.2 and 1.0 < fit["k"] < 4.5, fit    # day mean of 2 reports: k = (4 / 2) / 1 = 2
    r, e = replay(pairs, fit, "offset")
    assert e > 0.6
    s = summarise(r, 10, "shrink+spread")
    assert s["hi"] < 0 and 0.85 <= s["cov"] <= 0.95 and summarise(r, 3, "shrink", "plain")["diff"] < 0
    # note (2026-11-13, synthetic stations, offset sd 1 vs reading scatter 2): the method gains everywhere on average, but stations near the
    # regional value lose up to ~0.08 at n = 10, so the pre-set "no station worse by more than 0.03" clause is demanding; the rule is not changed.
    good = dict(diff=-0.05, lo=-0.06, hi=-0.04, share_better=0.8, worst=0.02, cov=0.9)
    assert judge(good, good, dict(diff=-0.01), 0.5) == "PASS"
    assert judge({**good, "worst": 0.08}, good, dict(diff=-0.01), 0.5).startswith("MISS")
    assert judge(good, {**good, "diff": 0.01}, dict(diff=-0.01), 0.5) == "KILL"
    assert judge(good, good, dict(diff=-0.01), 0.3).startswith("STOP")


if __name__ == "__main__":
    _selfcheck()
    main()
