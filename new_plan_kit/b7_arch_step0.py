"""Step 0 for the three architecture ideas of New_Plan section 14 (SIGMA, CHORUS, STRAND). Read-only.

Rows: data/modeF_v2/<year>.npz (HRES forecast profile + ERA5 truth on 44 heights, NM/TX box), fit years only
(default 2016-2019; never the 2022 test year, never 2026). Nothing is trained and nothing in the tool changes.

Part 1 (SIGMA): how large is the target "truth - forecast" per lead, against the climate spread, and how much smaller
        is "truth anomaly - beta x forecast anomaly" (beta fitted on the earlier years, applied to the last year)?
Part 2 (CHORUS): two runs for the same hour and place: how alike are their errors, what does the best fixed mix gain,
        and does the same run's own change over 6 h say how wrong it is?
Part 3 (STRAND): errors of ONE run at two leads: how alike are they (the "noise ageing" curve)?
Part 4 (ECHO): does the place's own past (or the most similar past forecasts) say something about today's error?

Run: .venv/Scripts/python -I -W ignore new_plan_kit/b7_arch_step0.py . [first_year last_year]
"""
import os
import sys

import numpy as np
import pandas as pd

root = sys.argv[1]
Y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2016
Y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2019
assert Y1 <= 2021, "2022 is the Mode F test year; this script uses fit years only"

HEIGHTS = None
parts = []
for y in range(Y0, Y1 + 1):
    z = np.load(os.path.join(root, "data/modeF_v2/%d.npz" % y))
    if HEIGHTS is None:
        sys.path.insert(0, root)
        from tempest.profiles.to_heights import HEIGHTS as _H
        HEIGHTS = np.asarray(_H, float)
        want = [10, 500, 1500, 3000, 5000, 9000, 12000, 15000]
        HI = [int(np.abs(HEIGHTS - w).argmin()) for w in want]
    d = dict(year=z["year"], valid=z["valid"].astype("datetime64[h]").astype(np.int64), lead=z["lead_hours"].astype(np.int64),
             lat=z["lat"], lon=z["lon"], hres=z["hres"][:, :3][:, :, HI].astype(np.float32), obs=z["obs"][:, :3][:, :, HI].astype(np.float32))
    parts.append(d)
    z.close()
R = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
del parts
n = len(R["year"])
hts = HEIGHTS[HI]
print("rows %d, years %d-%d, heights used (m): %s" % (n, Y0, Y1, " ".join("%d" % h for h in hts)))
print("leads (h): %s" % " ".join(str(x) for x in np.unique(R["lead"])))

# place id and climate mean per (place, month, UTC hour) of the truth
pid = pd.factorize(pd.Series(np.round(R["lat"], 3)).astype(str) + "_" + pd.Series(np.round(R["lon"], 3)).astype(str))[0]
vt = R["valid"].astype("datetime64[h]")
month = vt.astype("datetime64[M]").astype(np.int64) % 12
hour = R["valid"] % 24
cell = pid.astype(np.int64) * 10000 + month * 100 + hour
ci, cinv = np.unique(cell, return_inverse=True)
cnt = np.bincount(cinv, minlength=len(ci)).astype(np.float64)
clim = np.zeros((len(ci),) + R["obs"].shape[1:], np.float64)
np.add.at(clim, cinv, R["obs"])
clim /= cnt[:, None, None]
a = R["obs"] - clim[cinv]          # truth anomaly
fa = R["hres"] - clim[cinv]        # forecast anomaly
err = R["obs"] - R["hres"]         # today's Mode F target
print("places %d, climate cells %d (median rows per cell %d; the anomaly spread is slightly low because of it)" % (pid.max() + 1, len(ci), np.median(cnt)))

LB = [(6, 24, "0.25-1 d"), (30, 48, "1-2 d"), (54, 96, "2-4 d"), (102, 144, "4-6 d"), (150, 180, "6-7.5 d"), (186, 240, "7.5-10 d")]
VARS = [("wind", [0, 1]), ("T", [2])]
fit = R["year"] < Y1
tst = R["year"] == Y1

print()
print("PART 1 (SIGMA). Size of the training target per lead, as a share of the climate spread (variance ratio).")
print("  'raw' = truth - forecast (today's target). 'skip' = truth anomaly - beta x forecast anomaly, beta fitted on %d-%d, shown on %d." % (Y0, Y1 - 1, Y1))
print("%-9s %-5s %7s | %s" % ("lead", "var", "rows", "  ".join("%5dm raw/beta/skip" % h for h in hts[[0, 2, 4, 5, 7]])))
tot_raw, tot_skip, shares = {}, {}, {}
for lo, hi, name in LB:
    m_f = fit & (R["lead"] >= lo) & (R["lead"] <= hi)
    m_t = tst & (R["lead"] >= lo) & (R["lead"] <= hi)
    for vn, vi in VARS:
        cells = []
        raw_all, skip_all = [], []
        for j in range(len(hts)):
            x, yv = fa[m_f][:, vi, j].ravel().astype(np.float64), a[m_f][:, vi, j].ravel().astype(np.float64)
            beta = float((x * yv).sum() / (x * x).sum())
            sc2 = float((a[tst][:, vi, j].astype(np.float64) ** 2).mean())
            raw = float((err[m_t][:, vi, j].astype(np.float64) ** 2).mean()) / sc2
            skip = float(((a[m_t][:, vi, j] - beta * fa[m_t][:, vi, j]).astype(np.float64) ** 2).mean()) / sc2
            raw_all.append(raw), skip_all.append(skip)
            if j in (0, 2, 4, 5, 7):
                cells.append("%5.2f/%4.2f/%4.2f     " % (raw, beta, skip))
        tot_raw[(name, vn)], tot_skip[(name, vn)] = float(np.mean(raw_all)), float(np.mean(skip_all))
        print("%-9s %-5s %7d | %s" % (name, vn, int(m_t.sum()), "  ".join(cells)))
print("  Mean over the 8 heights: target size raw -> skip, and the largest-to-smallest ratio across leads.")
for vn, _ in VARS:
    r = [tot_raw[(nm, vn)] for _, _, nm in LB]
    s = [tot_skip[(nm, vn)] for _, _, nm in LB]
    print("  %-5s raw  %s | max/min %.1f" % (vn, " ".join("%5.2f" % x for x in r), max(r) / min(r)))
    print("  %-5s skip %s | max/min %.1f ; divided by its own size per lead it is 1.0 at every lead by construction" % (vn, " ".join("%5.2f" % x for x in s), max(s) / min(s)))
    w = np.array(r) * np.array([int((tst & (R["lead"] >= lo) & (R["lead"] <= hi)).sum()) for lo, hi, _ in LB])
    rows = np.array([int((tst & (R["lead"] >= lo) & (R["lead"] <= hi)).sum()) for lo, hi, _ in LB], float)
    print("  %-5s share of the squared loss by lead bin today: %s | share of rows: %s" % (vn, " ".join("%4.2f" % x for x in w / w.sum()), " ".join("%4.2f" % x for x in rows / rows.sum())))

# pairing helpers
band = {"10 m": [0], "0.5-3 km": [1, 2, 3], "5-9 km": [4, 5], "12-15 km": [6, 7]}
df = pd.DataFrame(dict(i=np.arange(n), pid=pid, valid=R["valid"], lead=R["lead"], init=R["valid"] - R["lead"]))
df = df[fit | tst]


def corr(x, y):
    x, y = x - x.mean(), y - y.mean()
    return float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum()))


def spearman(x, y):
    return corr(pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy())


print()
print("PART 2 (CHORUS). Two runs for the same hour and place (newer run lead L1, older run lead L2 = L1 + gap).")
lag = df.merge(df, on=["pid", "valid"], suffixes=("1", "2"))
lag = lag[(lag["lead2"] > lag["lead1"])]
lag["gap"] = lag["lead2"] - lag["lead1"]
print("  matched pairs %d" % len(lag))
print("  %-9s %-5s %-9s %7s %8s %8s %10s %10s" % ("newer", "gap", "band", "pairs", "err corr", "best w", "MSE gain %", "rho d~|e|"))
for lo, hi, name in LB[:5]:
    for glo, ghi, gap in ((6, 24, "6-24"), (30, 72, "30-72")):
        g = lag[(lag["lead1"] >= lo) & (lag["lead1"] <= hi) & (lag["gap"] >= glo) & (lag["gap"] <= ghi)]
        if len(g) < 150:
            continue
        i1, i2 = g["i1"].to_numpy(), g["i2"].to_numpy()
        for bn, bj in band.items():
            if bn == "10 m":
                continue
            e1 = err[i1][:, :2][:, :, bj].reshape(len(g), -1).astype(np.float64)
            e2 = err[i2][:, :2][:, :, bj].reshape(len(g), -1).astype(np.float64)
            c = corr(e1.ravel(), e2.ravel())
            v1, v2, c12 = (e1 ** 2).mean(), (e2 ** 2).mean(), (e1 * e2).mean()
            w = float(np.clip((v2 - c12) / (v1 + v2 - 2 * c12), 0, 1))          # weight of the newer run in w f1 + (1 - w) f2
            mix = w * w * v1 + (1 - w) ** 2 * v2 + 2 * w * (1 - w) * c12
            dis = np.sqrt(((R["hres"][i1][:, :2][:, :, bj] - R["hres"][i2][:, :2][:, :, bj]).reshape(len(g), -1).astype(np.float64) ** 2).mean(1))
            rho = spearman(dis, np.sqrt((e1 ** 2).mean(1)))
            print("  %-9s %-5s %-9s %7d %8.2f %8.2f %10.1f %10.2f" % (name, gap, bn, len(g), c, w, 100 * (1 - mix / v1), rho))

print("  Same run, its own change over the next 6 h (|f(L+6) - f(L)|) against its error at L, rank correlation within the lead bin:")
run = df.merge(df, on=["pid", "init"], suffixes=("1", "2"))
run = run[run["lead2"] > run["lead1"]]
run["gap"] = run["lead2"] - run["lead1"]
print("  matched same-run pairs %d" % len(run))
for lo, hi, name in LB[:5]:
    g = run[(run["lead1"] >= lo) & (run["lead1"] <= hi) & (run["gap"] == 6)]
    if len(g) < 400:
        continue
    i1, i2 = g["i1"].to_numpy(), g["i2"].to_numpy()
    out = []
    for bn, bj in band.items():
        ten = np.sqrt(((R["hres"][i2][:, :2][:, :, bj] - R["hres"][i1][:, :2][:, :, bj]).reshape(len(g), -1).astype(np.float64) ** 2).mean(1))
        e1 = np.sqrt((err[i1][:, :2][:, :, bj].reshape(len(g), -1).astype(np.float64) ** 2).mean(1))
        out.append("%s %.2f" % (bn, spearman(ten, e1)))
    print("  %-9s pairs %6d | %s" % (name, len(g), " | ".join(out)))

print()
print("PART 3 (STRAND). ONE run at two leads, same place: correlation of its two wind errors, and of the two truth anomalies.")
print("  %-9s %-5s %7s | %s" % ("first", "apart", "pairs", " | ".join("%-9s err / truth" % b for b in band)))
for lo, hi, name in LB[:5]:
    for gap in (6, 12, 24, 48):
        g = run[(run["lead1"] >= lo) & (run["lead1"] <= hi) & (run["gap"] == gap)]
        if len(g) < 400:
            continue
        i1, i2 = g["i1"].to_numpy(), g["i2"].to_numpy()
        out = []
        for bn, bj in band.items():
            e1 = err[i1][:, :2][:, :, bj].astype(np.float64).ravel()
            e2 = err[i2][:, :2][:, :, bj].astype(np.float64).ravel()
            a1 = a[i1][:, :2][:, :, bj].astype(np.float64).ravel()
            a2 = a[i2][:, :2][:, :, bj].astype(np.float64).ravel()
            out.append("%9s %.2f / %.2f" % ("", corr(e1, e2), corr(a1, a2)))
        print("  %-9s %-5d %7d | %s" % (name, gap, len(g), " | ".join(out)))
print("  A pool that draws each lead on its own has error correlation 0.00 between leads by construction.")

print()
print("PART 4 (ECHO). Memory of past forecast errors, fit years %d-%d, shown on %d. Change of the squared wind / T error, %% (negative = better)." % (Y0, Y1 - 1, Y1))
print("  site mean = subtract the place's own mean error of that lead bin. analog = subtract the mean error of the 40 most similar past forecasts")
print("  (same lead bin; similarity = forecast wind anomaly at the 8 heights), searched in ALL places or only in the SAME place (20 nearest).")
rng = np.random.default_rng(0)
sd_f = fa[fit][:, :2].reshape(int(fit.sum()), -1).std(0).astype(np.float32) + 1e-6
print("  %-9s %-9s %10s %12s %12s %14s" % ("lead", "band", "site mean", "analog all", "analog same", "rho sd~|res|"))
for lo, hi, name in LB[:5]:
    mf = np.where(fit & (R["lead"] >= lo) & (R["lead"] <= hi))[0]
    mt = np.where(tst & (R["lead"] >= lo) & (R["lead"] <= hi))[0]
    mt = rng.choice(mt, size=min(2500, len(mt)), replace=False)
    # site mean
    S = np.zeros((pid.max() + 1,) + err.shape[1:], np.float64)
    C = np.bincount(pid[mf], minlength=pid.max() + 1).astype(np.float64)
    np.add.at(S, pid[mf], err[mf])
    S /= np.maximum(C, 1)[:, None, None]
    e_t = err[mt].astype(np.float64)
    e_site = e_t - S[pid[mt]]
    # analogs
    Xf = (fa[mf][:, :2].reshape(len(mf), -1) / sd_f).astype(np.float32)
    Xt = (fa[mt][:, :2].reshape(len(mt), -1) / sd_f).astype(np.float32)
    f2 = (Xf * Xf).sum(1)
    corr_all = np.zeros_like(e_t)
    corr_same = np.zeros_like(e_t)
    sd_all = np.zeros(len(mt))
    for a0 in range(0, len(mt), 500):
        xt = Xt[a0:a0 + 500]
        d2 = f2[None, :] - 2.0 * xt @ Xf.T
        idx = np.argpartition(d2, 40, axis=1)[:, :40]
        ne = err[mf[idx]].astype(np.float64)                      # (b, 40, var, h)
        corr_all[a0:a0 + 500] = ne.mean(1)
        sd_all[a0:a0 + 500] = np.sqrt((ne[:, :, :2] - ne[:, :, :2].mean(1, keepdims=True)).var(1).mean((1, 2)))
        same = pid[mf][None, :] == pid[mt[a0:a0 + 500]][:, None]
        d2s = np.where(same, d2, np.inf)
        idx = np.argpartition(d2s, 20, axis=1)[:, :20]
        okk = np.isfinite(np.take_along_axis(d2s, idx, 1))
        ne = err[mf[idx]].astype(np.float64) * okk[:, :, None, None]
        corr_same[a0:a0 + 500] = ne.sum(1) / np.maximum(okk.sum(1), 1)[:, None, None]
    e_all, e_same = e_t - corr_all, e_t - corr_same
    for bn, bj in band.items():
        for vn, vi in VARS:
            base = (e_t[:, vi][:, :, bj] ** 2).mean()
            res = np.sqrt((e_all[:, :2][:, :, bj] ** 2).mean((1, 2)))
            print("  %-9s %-9s %-4s %+9.1f %+12.1f %+12.1f %14s" % (name, bn, vn, 100 * ((e_site[:, vi][:, :, bj] ** 2).mean() / base - 1), 100 * ((e_all[:, vi][:, :, bj] ** 2).mean() / base - 1),
                  100 * ((e_same[:, vi][:, :, bj] ** 2).mean() / base - 1), ("%.2f" % spearman(sd_all, res)) if vn == "wind" else ""))
