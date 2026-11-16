"""New_Plan 12.4 SV stage 1 (linear site vector, no network): the 10 m speed gap (balloon surface report minus ERA5, same hour) of a station = fixed offset c_s + day-to-day scatter.
Terrain-only guess c0 = ridge on ERA5 invariants at the station (elevation minus cell height, subgrid orography sdor, slope slor, land-sea mask, |lat|; lambda 1 on standardised features, not tuned).
Exact update from k readings: normal prior N(c0, tau2) (tau2 = scatter of the terrain guess over the fit stations), readings with variance w2 (within-station sd^2) -> posterior mean / variance (Bayes, closed form).
Predictive: real speed = ERA5 speed + c + N(0, w2 + posterior variance), Gaussian CRPS and 90 % interval coverage on the TEST year 2022 only; readings = the first k pairs of 2016-2021 (never 2022).
Leave-station-out: every station is predicted from a ridge / tau2 / w2 fitted on all the OTHER stations. Arms: none (c = 0, variance w2 + pooled between-station variance... plain w2 + mean_gap^2 is NOT used:
'no site term' = c = the mean gap of the other stations), k = 0, k = 10, k = 30, full (own mean of 2016-2021 pairs).
Gain = CRPS(none) - CRPS(arm), averaged over stations; intervals by a 1000-draw bootstrap over stations.
Rule (New_Plan 12.4 stage 1, set before any run): PASS = k = 0 gain > 0 with the interval excluding 0, AND k = 10 gain >= half of the full gain, AND coverage 0.85-0.95 at k = 0, 10, 30.
KILL = k = 30 gain under 30 % of the full gain (site terms stay by hand). Otherwise MISS.
Stations: those with >= 40 pairs in 2016-2021 and >= 40 in 2022 (at most 400, random seed 7).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b64_sv_stage1.py
Result: docs/results/logs/kit_b64_sv_stage1.log
"""
import glob
import math
import os

import numpy as np

import kit_common as K

NAME = "b64_sv_stage1"
G = 9.80665
MAXST = 400
LAM = 1.0


def crps_gauss(y, mu, sd):
    z = (y - mu) / sd
    return sd * (z * (2 * 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2))) - 1) + 2 * np.exp(-0.5 * z ** 2) / math.sqrt(2 * math.pi) - 1 / math.sqrt(math.pi))


def posterior(c0, tau2, w2, gaps):
    """normal prior N(c0, tau2), k readings with variance w2 -> (mean, variance)."""
    k = len(gaps)
    if k == 0:
        return c0, tau2
    prec = 1 / tau2 + k / w2
    return (c0 / tau2 + np.sum(gaps) / w2) / prec, 1 / prec


def ridge(X, y, lam=LAM):
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)


def judge(gain_ci, g10, gfull, g30, cov):
    k0, lo, hi = gain_ci
    if g30 < 0.3 * gfull:
        return f"KILL (k = 30 gain {g30:.4f} < 30 % of the full gain {gfull:.4f})"
    cov_ok = all(0.85 <= c <= 0.95 for c in cov)
    if lo > 0 and g10 >= 0.5 * gfull and cov_ok:
        return "PASS"
    return f"MISS (k = 0 gain {k0:.4f} [{lo:.4f}, {hi:.4f}]; k = 10 gain {g10:.4f} vs half of full {0.5 * gfull:.4f}; coverage {', '.join(f'{c:.2f}' for c in cov)})"


def pairs():
    """station -> array (n, 4): year, gap, real speed, ERA5 speed; plus lat, lon, elev."""
    root = K.REPO
    P = np.load(os.path.join(root, "data/raw/era5_global/points.npz"))
    ig = P["igra"]
    code = {c.split()[0]: (float(c.split()[1]), float(c.split()[2])) for c in P["code"]}
    files = {os.path.basename(f)[:-4]: f for f in glob.glob(os.path.join(root, "data/igra_heights/*.npz"))}
    ids = sorted(s for s in np.unique(ig[ig != ""]) if s in files)
    rng = np.random.default_rng(7)
    ids = [ids[i] for i in rng.permutation(len(ids))]
    meta, surf = {}, {}
    for s in ids:
        z = np.load(files[s])
        t = z["time"]
        m = (t >= np.datetime64("2016-01-01T00")) & (t < np.datetime64("2023-01-01T00"))
        u, v = z["u"][m, 0].astype(np.float32), z["v"][m, 0].astype(np.float32)
        ok = (u > -3200) & (v > -3200)
        if ok.sum() < 80:
            continue
        surf[s] = (t[m][ok], np.hypot(u[ok], v[ok]) / 10.0)
        meta[s] = (float(z["lat"][-1]), float(z["lon"][-1]), float(z["elev"][-1]))
        if len(surf) >= MAXST:
            break
    pt = {s: int(np.where(ig == s)[0][0]) for s in surf}
    acc = {s: [] for s in surf}
    for y in range(2016, 2023):
        for mo in range(1, 13):
            fn = os.path.join(root, "data/raw/era5_global", "%d-%02d.npz" % (y, mo))
            if not os.path.exists(fn):
                continue
            e = np.load(fn)
            ev = e["valid_time"]
            sc, o = code["u10"]
            sc2, o2 = code["v10"]
            for s in surf:
                eu = e["u10"][:, pt[s]].astype(np.float32) * sc + o
                evv = e["v10"][:, pt[s]].astype(np.float32) * sc2 + o2
                t, sp = surf[s]
                ix = np.searchsorted(t, ev)
                hit = (ix < t.size)
                hit[hit] = t[ix[hit]] == ev[hit]
                for r in np.where(hit)[0]:
                    es = float(np.hypot(eu[r], evv[r]))
                    acc[s].append((y, sp[ix[r]] - es, sp[ix[r]], es))
            e.close()
    return {s: np.array(v) for s, v in acc.items() if len(v)}, meta


def terrain(meta, ids):
    z = np.load(os.path.join(K.REPO, "data/raw/era5_static/era5_invariants.npz"))
    la, lo = z["lat"], z["lon"]
    rows = []
    for s in ids:
        lat, lon, el = meta[s]
        i, j = int(np.abs(la - lat).argmin()), int(np.abs(lo - (lon % 360)).argmin())
        rows.append([(el - z["z_sfc"][i, j] / G) / 100.0, np.log1p(z["sdor"][i, j]), z["slor"][i, j] * 100.0, float(z["lsm"][i, j]), abs(lat) / 90.0])
    return np.array(rows)


def main():
    acc, meta = pairs()
    ids = [s for s, v in acc.items() if (v[:, 0] <= 2021).sum() >= 40 and (v[:, 0] == 2022).sum() >= 40]
    X = terrain(meta, ids)
    fitp = {s: acc[s][acc[s][:, 0] <= 2021] for s in ids}
    testp = {s: acc[s][acc[s][:, 0] == 2022] for s in ids}
    mean_gap = np.array([fitp[s][:, 1].mean() for s in ids])
    w2_all = np.array([fitp[s][:, 1].var() for s in ids])
    arms = ("none", "k0", "k10", "k30", "full")
    cr = {a: [] for a in arms}
    cv = {a: [] for a in arms}
    for i, s in enumerate(ids):
        o = np.arange(len(ids)) != i
        mu_x, sd_x = X[o].mean(0), X[o].std(0) + 1e-9
        Z = np.column_stack([np.ones(o.sum()), (X[o] - mu_x) / sd_x])
        beta = ridge(Z, mean_gap[o])
        tau2 = max(np.var(mean_gap[o] - Z @ beta), 1e-4)
        w2 = float(np.mean(w2_all[o]))
        z0 = np.concatenate([[1.0], (X[i] - mu_x) / sd_x])
        c0 = float(z0 @ beta)
        gaps = fitp[s][:, 1]
        y = testp[s][:, 2]
        e = testp[s][:, 3]
        for a in arms:
            if a == "none":
                m, var = float(mean_gap[o].mean()), w2 + float(mean_gap[o].var())
            elif a == "k0":
                m, var = c0, w2 + tau2
            elif a == "full":
                m, var = float(gaps.mean()), w2 + w2 / len(gaps)
            else:
                m, v = posterior(c0, tau2, w2, gaps[:int(a[1:])])
                var = w2 + v
            sd = math.sqrt(var)
            cr[a].append(float(np.mean(crps_gauss(y, e + m, sd))))
            cv[a].append(float(np.mean(np.abs(y - e - m) <= 1.645 * sd)))
    cr = {a: np.array(v) for a, v in cr.items()}
    cv = {a: float(np.mean(v)) for a, v in cv.items()}
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(ids), (1000, len(ids)))

    def gain(a):
        d = cr["none"] - cr[a]
        bs = d[idx].mean(1)
        return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    g = {a: gain(a) for a in arms if a != "none"}
    lines = [f"SV stage 1: {len(ids)} stations (>= 40 pairs 2016-21 and 2022), leave-station-out, test 2022, 10 m speed; terrain features: elevation - cell height, sdor, slor, lsm, |lat|",
             f"  Gaussian CRPS (m/s), mean over stations: none {cr['none'].mean():.4f}, k0 {cr['k0'].mean():.4f}, k10 {cr['k10'].mean():.4f}, k30 {cr['k30'].mean():.4f}, full fit {cr['full'].mean():.4f}"]
    for a in ("k0", "k10", "k30", "full"):
        lines.append(f"  gain vs none, {a}: {g[a][0]:.4f} [{g[a][1]:.4f}, {g[a][2]:.4f}] ({100 * g[a][0] / g['full'][0]:.0f} % of the full-fit gain); 90 % interval coverage {cv[a]:.3f}")
    lines.append("Rule (pre-set): PASS = k0 gain > 0 interval excludes 0, k10 gain >= half of full gain, coverage 0.85-0.95 at k = 0, 10, 30; KILL = k30 gain < 30 % of full gain; else MISS.")
    lines.append("Verdict: " + judge(g["k0"], g["k10"][0], g["full"][0], g["k30"][0], (cv["k0"], cv["k10"], cv["k30"])))
    K.report(NAME, lines)


def _selfcheck():
    m, v = posterior(0.0, 1.0, 1.0, np.ones(4))
    assert abs(m - 0.8) < 1e-9 and abs(v - 0.2) < 1e-9
    assert abs(crps_gauss(np.array([0.0]), np.array([0.0]), 1.0)[0] - (2 / math.sqrt(2 * math.pi) - 1 / math.sqrt(math.pi))) < 1e-9
    Z = np.column_stack([np.ones(20), np.arange(20.0)])
    assert abs(ridge(Z, 3 + 2 * np.arange(20.0), 1e-9)[1] - 2) < 1e-6
    assert judge((1, 0.5, 1), 0.6, 1, 0.5, (0.9, 0.9, 0.9)) == "PASS" and judge((1, 0.5, 1), 0.6, 1, 0.2, (0.9,) * 3).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
