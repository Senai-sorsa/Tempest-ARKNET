"""New_Plan 14.3 SIGMA stage 1 (13.5 step 1): arm B0, no training. Measurement only (the plan sets no PASS/KILL here; B0 is the bar SIGMA stage 2 must beat).

B0 member = climate mean + beta(lead) x (forecast - climate mean) + s(lead) x N(0, 1), per height and variable (176 columns).
  Improvement 1: one smooth curve per column, two numbers each, so any lead works:
      beta(L) = b x exp(-L / tau_b)                         (trust in the forecast fades to 0)
      s(L)    = csd x sqrt(1 - q x exp(-L / tau_s))         (spread grows to the climate spread)
  both fitted on 2016-2019 rows (per-lead-day regression values, then a log-linear fit), scored on 2020 (all leads 0.25-10 d).
  Climate mean and spread here come from the box's own 2016-2019 truth (mean per place x month x UTC hour, spread per month x column);
  the plan's improvement 2 (the climate generator's pool) is for stage 2. Improvement 5 (g signals) not in B0.
Reference arms on the same 2020 rows (all bell curves, all fit on 2016-2019):
  FC    = forecast + mean error, sd of the error, tabled per lead day (1..10) and column: today's target with a plain draw
  B0tab = B0 with beta and s tabled per lead day instead of the curves (what the two-number curves cost)
  CL    = climate mean, climate spread (what the tool serves beyond 7.5 d)
Metric: Gaussian CRPS per column, averaged into the 16 variable x band cells (modeP.names), then the mean of the 16 per row, as Mode F;
intervals = paired day-block bootstrap (valid day). RH is scored unclipped (shortcut: no 0-100 % hold, fine for a bar; stage 2 uses to_physical).
Rows: data/modeF_v2 (NM/TX) and data/modeF_v2_denver; years 2016-2020 only (never 2022, never 2026).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b8_sigma_stage1.py
Result: docs/results/logs/kit_b8_sigma_stage1.log
"""
import os

import numpy as np
from scipy.stats import norm

import kit_common as K
from tempest.forecast import modeP as P
from tempest.forecast.modeF import lead_bin

FIT, TEST = range(2016, 2020), 2020
DAYS = np.arange(1, 11)
SHOW = [(0, 10), (0, 1500), (0, 5000), (0, 12000), (2, 10), (2, 1500), (2, 5000), (2, 12000)]   # (variable index, height m) for the curve printout


def loglin(L, y, w):
    """Weighted fit of log y = log c - L / tau over the lead days -> (c, tau); y held to (1e-3, 1]."""
    y = np.clip(y, 1e-3, 1.0)
    A = np.stack([np.ones_like(L), -L], 1) * np.sqrt(w)[:, None]
    (lc, inv_tau), *_ = np.linalg.lstsq(A, np.log(y) * np.sqrt(w), rcond=None)
    return np.exp(lc), 1.0 / max(inv_tau, 1e-3)


def crps_gauss(mu, sd, x):
    z = (x - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def load(rows_dir, years):
    ds = [np.load(os.path.join(K.REPO, rows_dir, f"{y}.npz")) for y in years]
    out = {k: np.concatenate([d[k] for d in ds]) for k in ("lead_days", "valid", "lat", "lon", "valid_utc_hour")}
    for k in ("hres", "obs"):
        out[k] = np.concatenate([d[k].reshape(len(d[k]), -1) for d in ds]).astype(np.float64)
    return out


def keys(d):
    vt = d["valid"].astype("datetime64[h]")
    month = (vt.astype("datetime64[M]").astype(np.int64) % 12).astype(np.int64)
    place = np.round(d["lat"], 3) * 1e4 + np.round(d["lon"], 3)
    return place, month, d["valid_utc_hour"].astype(np.int64), vt.astype("datetime64[D]").astype(np.int64)


def climate(tr, te):
    """Mean per place x month x hour (fallback month x hour) and spread per month x column, from the fit rows only."""
    (pt, mt, ht, _), (pe, me, he, _) = keys(tr), keys(te)
    ct, ce = [f"{p}_{m}_{h}" for p, m, h in zip(pt, mt, ht)], [f"{p}_{m}_{h}" for p, m, h in zip(pe, me, he)]
    u, inv = np.unique(ct, return_inverse=True)
    mean = np.zeros((len(u), tr["obs"].shape[1]))
    np.add.at(mean, inv, tr["obs"])
    mean /= np.bincount(inv)[:, None]
    mh, mhi = np.unique(mt * 100 + ht, return_inverse=True)
    mmh = np.zeros((len(mh), tr["obs"].shape[1]))
    np.add.at(mmh, mhi, tr["obs"])
    mmh /= np.bincount(mhi)[:, None]
    pos = {c: i for i, c in enumerate(u)}
    pmh = {c: i for i, c in enumerate(mh)}
    mte = np.array([mean[pos[c]] if c in pos else mmh[pmh[m * 100 + h]] for c, m, h in zip(ce, me, he)])
    a_tr = tr["obs"] - mean[inv]
    csd = np.array([a_tr[mt == m].std(0) for m in range(12)])          # (12, 176)
    return mean[inv], mte, np.maximum(csd, 1e-6), mt, me


def fit_tables(fa, a, err, lday, csd_row):
    """Per lead day and column: beta (regression of truth anomaly on forecast anomaly), s / csd, FC bias and sd."""
    nD, C = len(DAYS), fa.shape[1]
    beta, srel, bias, esd, n = tuple(np.zeros((nD, C)) for _ in range(4)) + (np.zeros(nD),)
    for i, d in enumerate(DAYS):
        k = lday == d
        n[i] = k.sum()
        x, y = fa[k], a[k]
        beta[i] = np.clip((x * y).mean(0) / np.maximum((x * x).mean(0), 1e-9), 0, 1.2)
        srel[i] = np.sqrt(((y - beta[i] * x) ** 2).mean(0) / (csd_row[k] ** 2).mean(0))
        bias[i], esd[i] = err[k].mean(0), err[k].std(0)
    return beta, srel, bias, esd, n


def curves(beta, srel, n):
    C = beta.shape[1]
    out = np.zeros((C, 4))                                               # b, tau_b, q, tau_s
    for j in range(C):
        out[j, :2] = loglin(DAYS.astype(float), beta[:, j], n)
        out[j, 2:] = loglin(DAYS.astype(float), 1 - np.minimum(srel[:, j], 0.999) ** 2, n)
    out[:, 0] = np.minimum(out[:, 0], 1.2)
    out[:, 2] = np.minimum(out[:, 2], 1.0)
    return out


def cell_mean(cr, masks):
    return (cr @ masks / masks.sum(0)).mean(1)                           # (n,) mean over the 16 variable x band cells


def run_box(name, rows_dir, lines):
    tr, te = load(rows_dir, FIT), load(rows_dir, [TEST])
    cm_tr, cm_te, csd, mt, me = climate(tr, te)
    ld_tr = np.clip(np.ceil(tr["lead_days"] - 1e-6), 1, 10).astype(int)
    ld_te = np.clip(np.ceil(te["lead_days"] - 1e-6), 1, 10).astype(int)
    beta, srel, bias, esd, n = fit_tables(tr["hres"] - cm_tr, tr["obs"] - cm_tr, tr["obs"] - tr["hres"], ld_tr, csd[mt])
    cv = curves(beta, srel, n)
    del tr
    L, fa, x, cs = te["lead_days"].astype(float)[:, None], te["hres"] - cm_te, te["obs"], csd[me]
    b_c = cv[:, 0] * np.exp(-L / cv[:, 1])
    s_c = cs * np.sqrt(np.clip(1 - cv[:, 2] * np.exp(-L / cv[:, 3]), 1e-4, 1))
    i = ld_te - 1
    masks = np.stack([s for _, _, s in P.names()], 1).astype(float)
    arms = {"B0": (cm_te + b_c * fa, s_c),
            "B0tab": (cm_te + beta[i] * fa, np.maximum(srel[i] * cs, 1e-6)),
            "FC": (te["hres"] + bias[i], np.maximum(esd[i], 1e-6)),
            "CL": (cm_te, cs)}
    sc, cov = {}, {}
    for k, (mu, sd) in arms.items():
        sc[k] = cell_mean(crps_gauss(mu, sd, x), masks)
        cov[k] = cell_mean((np.abs(x - mu) <= norm.ppf(0.995) * sd).astype(float), masks)
    day = keys(te)[3]
    lb = np.where(lead_bin(te["lead_days"]) == 0, 9, lead_bin(te["lead_days"]))
    lines.append(f"{name}: {len(x)} test rows (2020), fit 2016-2019. Mean CRPS (16-cell mean) by Mode F lead bin 1 / 3 / 5 / 7 / 9 (9 = beyond 7.5 d):")
    for k in arms:
        lines.append(f"    {k:<6} " + " / ".join(f"{sc[k][lb == b].mean():.3f}" for b in (1, 3, 5, 7, 9))
                     + "   cov99 " + " / ".join(f"{cov[k][lb == b].mean():.3f}" for b in (1, 3, 5, 7, 9)))
    for ref in ("FC", "B0tab", "CL"):
        parts = []
        for b in (1, 3, 5, 7, 9):
            k = lb == b
            m, lo, hi = K.block_boot(sc["B0"][k] - sc[ref][k], list(day[k]), draws=1000)
            parts.append(f"{b} {100 * m / sc[ref][k].mean():+.1f} % [{lo:+.3f}, {hi:+.3f}]")
        lines.append(f"  B0 minus {ref:<5}: " + "; ".join(parts))
    lines.append("  B0 curves (beta at 1 / 5 / 10 d; s / climate spread at 1 / 5 / 10 d):")
    for v, h in SHOW:
        j = v * P.NH + int(np.abs(np.asarray(P.HEIGHTS, float) - h).argmin())
        bb = [cv[j, 0] * np.exp(-t / cv[j, 1]) for t in (1, 5, 10)]
        ss = [np.sqrt(max(1 - cv[j, 2] * np.exp(-t / cv[j, 3]), 0)) for t in (1, 5, 10)]
        lines.append(f"    {P.PROFILE[v]:<2} {h:>5} m: beta " + " / ".join(f"{t:.2f}" for t in bb) + "; s " + " / ".join(f"{t:.2f}" for t in ss)
                     + f"   (table beta 1 d {beta[0, j]:.2f}, 10 d {beta[-1, j]:.2f})")


def main():
    lines = ["SIGMA stage 1, arm B0 (formula + bell-curve draw, no training) vs FC (forecast + tabled bias / sd), B0tab, CL (climate); 2020 rows"]
    for name, d in (("NM/TX", "data/modeF_v2"), ("Denver", "data/modeF_v2_denver")):
        run_box(name, d, lines)
    K.report("b8_sigma_stage1", lines)


def _selfcheck():
    c, t = loglin(DAYS.astype(float), 0.9 * np.exp(-DAYS / 4.0), np.ones(10))
    assert abs(c - 0.9) < 1e-6 and abs(t - 4.0) < 1e-6
    assert abs(crps_gauss(0.0, 1.0, 0.0) - (2 * norm.pdf(0) - 1 / np.sqrt(np.pi))) < 1e-12
    assert TEST < 2022 and max(FIT) < TEST


_selfcheck()
if __name__ == "__main__":
    main()
