"""New_Plan 17 UR12: a forecast's own doubt moves the CENTRE, not the spread. No network: SIGMA stage 1's arm B0tab (climate + beta x forecast
anomaly + s x N(0, 1), beta and s tabled per lead day and column; tempest/forecast/sigma.py fit on 2016-2020) against the same with
    beta' = beta x h(d),   h(d) = clip(a - b x d / median(d | lead day, cell), 0.7, 1.0)
in the four cells where run disagreement ranked the error (C6 premise: wind 0-1 / 1-5 / 5-12 km, T 5-12 km); other cells h = 1, and h = 1 where
the row has no signal. Two signals, judged as two arms (a new parent, not a fourth C6 variation; forking paths n = 2):
    d36   RMS(newest run - the run 36 h older) in the cell        (data/ur2_<box>_signals, scripts/ur2_mix_rows.py)
    c6    RMS(the same run 6 h later - newest) in the cell         (needs no second run)
a, b per cell on a grid (a 0.8 ... 1.2, b 0 ... 0.3), the pair with the lowest Gaussian CRPS on the 2016-2020 rows; s is kept from the table.
Judged on 2021 + 2022 (rows data/modeF_v2{,_denver}); Gaussian CRPS per column, mean of the 16 variable x band cells (as Mode F); PIT distance =
mean over columns of the total-variation distance of the 10-bin PIT histogram from flat; 21-day blocks (1000 draws for CRPS, 300 for PIT).
Rule (set 2026-11-13 in New_Plan 17.2 before any run), per arm:
  PASS: CRPS better than B0tab with the interval below 0 at leads 3, 5 and 7 d AND the PIT distance change interval includes 0 or lies below,
        both boxes.  KILL: no lead better in either box.  Otherwise MISS.
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b35_ur12_beta_signal.py        # needs scripts/ur2_mix_rows.py <box> first; ~30-60 min
Result: docs/results/logs/kit_b35_ur12_beta_signal.log
"""
import os

import numpy as np
from scipy.stats import norm

import kit_common as K
from tempest.forecast import modeF as F
from tempest.forecast import sigma as SG
from ur_common import BLOCK, NEAR, masks

NAME = "b35_ur12_beta_signal"
FIT, TEST = range(2016, 2021), (2021, 2022)
CELLS = (0, 1, 2, 6)                         # wind 0-1 / 1-5 / 5-12 km, T 5-12 km (ur2_mix_rows CELL_BANDS order: wind x 4, then T x 4)
A_GRID, B_GRID = np.round(np.arange(0.8, 1.2001, 0.05), 2), np.round(np.arange(0.0, 0.3001, 0.05), 2)
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def cell_columns():
    """cell index (0-7) -> boolean (176,) columns: wind = u and v of the band, T = T of the band."""
    H = np.asarray(F.HEIGHTS, float)
    var = np.repeat(np.asarray(F.PROFILE), len(H))
    hh = np.tile(H, len(F.PROFILE))
    out = {}
    for j, (lo, hi) in enumerate(BANDS):
        band = (hh >= lo) & (hh < hi)
        out[j] = band & np.isin(var, ["u", "v"])
        out[4 + j] = band & (var == "T")
    return out


def crps_gauss(mu, sd, x):
    z = (x - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def load(rows_dir, sig_dir, years):
    ds = [dict(np.load(os.path.join(K.REPO, rows_dir, f"{y}.npz"))) for y in years]
    ss = [dict(np.load(os.path.join(K.REPO, sig_dir, f"{y}.npz"))) for y in years]
    d = {k: np.concatenate([x[k] for x in ds]) for k in ("obs", "hres", "valid", "lat", "lon", "valid_utc_hour", "lead_days", "year")}
    for x, s in zip(ds, ss):
        assert (x["valid"] == s["valid"]).all() and np.allclose(x["lead_days"], s["lead_days"]), "signals are not aligned with the rows"
    d["d36"] = np.concatenate([np.where(s["have_old"][:, None], s["d36"], np.nan) for s in ss])
    d["c6"] = np.concatenate([np.where(s["have_next"][:, None], s["c6"], np.nan) for s in ss])
    keep = (d["lead_days"] > 0) & (d["lead_days"] <= 10)
    return {k: v[keep] for k, v in d.items()}


def parts(tab, d):
    """-> climate mean cm (n, C), beta (n, C), s (n, C), forecast (n, C), truth (n, C), lead day (n,)."""
    cm, month = SG._climate_mean(tab, d)
    i = SG.lead_day(d["lead_days"]) - 1
    return cm, tab["beta"][i], tab["srel"][i] * tab["csd"][month], d["hres"].reshape(len(cm), -1), d["obs"].reshape(len(cm), -1), i + 1


def h_of(sig, ld, med, a, b):
    """signal (n,), lead day (n,), median per lead day (11,) -> h (n,) in [0.7, 1]; 1 where the signal is missing."""
    r = sig / np.maximum(med[ld], 1e-9)
    return np.where(np.isfinite(r), np.clip(a - b * r, 0.7, 1.0), 1.0)


def medians(sig, ld):
    m = np.full(11, np.nan)
    for L in range(1, 11):
        k = (ld == L) & np.isfinite(sig)
        if k.any():
            m[L] = np.median(sig[k])
    return np.where(np.isfinite(m), m, np.nanmedian(sig))


def fit_ab(p, sig_all, cc, n_max=60000):
    """fit rows: per cell the (a, b) with the lowest Gaussian CRPS over that cell's columns (on a fixed random n_max-row subset, for speed;
    the signal medians use all fit rows)."""
    pick = np.sort(np.random.default_rng(11).choice(len(sig_all), min(n_max, len(sig_all)), replace=False))
    cm, beta, s, fc, y, ld_all = p
    cm, beta, s, fc, y, ld, sig_sub = cm[pick], beta[pick], s[pick], fc[pick], y[pick], ld_all[pick], sig_all[pick]
    out = {}
    for c in CELLS:
        col = cc[c]
        med = medians(sig_all[:, c], ld_all)
        sig = sig_sub[:, c]
        best = (np.inf, 1.0, 0.0)
        for a in A_GRID:
            for b in B_GRID:
                h = h_of(sig, ld, med, a, b)[:, None]
                mu = cm[:, col] + beta[:, col] * h * (fc[:, col] - cm[:, col])
                v = crps_gauss(mu, s[:, col], y[:, col]).mean()
                if v < best[0]:
                    best = (v, a, b)
        out[c] = (best[1], best[2], med)
    return out


def predict(p, sig_all, ab, cc):
    cm, beta, s, fc, y, ld = p
    mu = cm + beta * (fc - cm)
    for c, (a, b, med) in ab.items():
        col = cc[c]
        h = h_of(sig_all[:, c], ld, med, a, b)[:, None]
        mu[:, col] = cm[:, col] + beta[:, col] * h * (fc[:, col] - cm[:, col])
    return mu


def pit_tv(pit):
    hist = np.stack([np.histogram(pit[:, j], bins=10, range=(0, 1))[0] for j in range(pit.shape[1])], 1) / len(pit)
    return float(0.5 * np.abs(hist - 0.1).sum(0).mean())


def run_box(name, rows_dir, sig_dir, lines):
    cc = cell_columns()
    w = masks()
    fit = load(rows_dir, sig_dir, FIT)
    tab = SG.fit(fit)
    pf = parts(tab, fit)
    te = load(rows_dir, sig_dir, TEST)
    pt = parts(tab, te)
    cm, beta, s, fc, y, ld = pt
    lb = np.where(F.lead_bin(te["lead_days"]) == 0, 9, F.lead_bin(te["lead_days"]))
    day = te["valid"].astype("datetime64[D]").astype(np.int64) // BLOCK
    mu0 = cm + beta * (fc - cm)
    c0 = crps_gauss(mu0, s, y) @ w
    pit0 = norm.cdf((y - mu0) / s)
    res = {}
    for arm in ("d36", "c6"):
        ab = fit_ab(pf, fit[arm], cc)
        mu1 = predict(pt, te[arm], ab, cc)
        c1 = crps_gauss(mu1, s, y) @ w
        pit1 = norm.cdf((y - mu1) / s)
        per = {}
        for L in NEAR:
            k = lb == L
            dm, lo, hi = K.block_boot((c1 - c0)[k].mean(1), list(day[k]), draws=1000)
            per[L] = (100 * dm / c0[k].mean(), lo, hi)
        ub = np.unique(day)
        rng = np.random.default_rng(3)
        idx = {u: np.flatnonzero(day == u) for u in ub}
        boot = []
        for _ in range(300):
            r = np.concatenate([idx[u] for u in rng.choice(ub, len(ub))])
            boot.append(pit_tv(pit1[r]) - pit_tv(pit0[r]))
        dp = pit_tv(pit1) - pit_tv(pit0)
        plo, phi = np.percentile(boot, [2.5, 97.5])
        res[arm] = dict(per=per, pit=(dp, plo, phi))
        lines.append(f"  {name} {arm}: (a, b) per cell " + ", ".join(f"{c} ({v[0]:.2f}, {v[1]:.2f})" for c, v in ab.items()) + "; CRPS change vs B0tab "
                     + ", ".join(f"{L}d {p[0]:+.2f} % [{p[1]:+.4f}, {p[2]:+.4f}]" for L, p in per.items()) + f"; PIT distance change {dp:+.4f} [{plo:+.4f}, {phi:+.4f}]; "
                     f"rows with the signal {np.isfinite(te[arm][:, 0]).mean():.0%}")
    return res


def judge(res):
    """res[box][arm] -> {arm: verdict}."""
    out = {}
    for arm in ("d36", "c6"):
        rb = [res[b][arm] for b in res]
        if all(not any(p[2] < 0 for p in r["per"].values()) and not any(p[0] < 0 for p in r["per"].values()) for r in rb):
            out[arm] = "KILL"
        elif all(all(r["per"][L][2] < 0 for L in (3, 5, 7)) and r["pit"][1] <= 0 for r in rb):
            out[arm] = "PASS"
        else:
            out[arm] = "MISS (record, no adoption)"
    return out


def main():
    K.ram_gate(6.0)
    lines = [f"UR12 beta x h(signal) vs B0tab: fit {FIT[0]}-{FIT[-1]}, judged {TEST}; Gaussian CRPS, 16-cell mean, {BLOCK}-day blocks"]
    res = {}
    for box, rows_dir, sig_dir in (("NM/TX", "data/modeF_v2", "data/ur2_nmtx_signals"), ("Denver", "data/modeF_v2_denver", "data/ur2_denver_signals")):
        if not os.path.exists(os.path.join(K.REPO, sig_dir, "2022.npz")):
            lines.append(f"  {box}: signals missing (run scripts/ur2_mix_rows.py {'nmtx' if box == 'NM/TX' else 'denver'})")
            continue
        res[box] = run_box(box, rows_dir, sig_dir, lines)
    if len(res) == 2:
        lines.append("Rule (pre-set, New_Plan 17.2): PASS = interval < 0 at 3, 5, 7 d and PIT change interval includes 0 or below, both boxes; KILL = no lead better in either box.")
        lines.append("Verdict: " + "; ".join(f"{a} {v}" for a, v in judge(res).items()) + " (forking paths: 2 arms)")
    K.report(NAME, lines)


def _selfcheck():
    ld = np.array([1, 1, 5, 5])
    sig = np.array([1.0, 3.0, 2.0, np.nan])
    med = medians(sig, ld)
    h = h_of(sig, ld, med, 1.0, 0.2)
    assert h[3] == 1.0 and 0.7 <= h.min() and h[1] < h[0]
    cc = cell_columns()
    assert cc[0].sum() == 2 * (np.asarray(F.HEIGHTS) < 1000).sum() and not (cc[0] & cc[4]).any()
    rng = np.random.default_rng(0)
    pit = rng.uniform(size=(5000, 3))
    assert pit_tv(pit) < 0.03 and pit_tv(pit ** 3) > 0.2
    good = dict(per={L: (-1.0, -0.02, -0.01) for L in NEAR}, pit=(-0.001, -0.003, 0.001))
    bad = dict(per={L: (0.5, 0.01, 0.02) for L in NEAR}, pit=(0.0, -0.01, 0.01))
    assert judge({"A": {"d36": good, "c6": bad}, "B": {"d36": good, "c6": bad}}) == {"d36": "PASS", "c6": "KILL"}


_selfcheck()
if __name__ == "__main__":
    main()
