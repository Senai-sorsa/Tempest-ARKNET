"""Shape and diagnostic report (AUTOPILOT.md MAIN TARGET S1-S8, metrics M1-M18) for one model on ERA5, development years.

    PYTHONPATH=. python scripts/diagnose.py MODEL.pt CALIB.npz DATA.npz [--rows 5000] [--first-year 2024] [--last-year 2025] [--m 199]
                                           [--shift F] [--shear-tail F] [--seasonal F] [--out stem]

Samples are the calibrated known-driver samples (what a query for a specific date gets). Writes <out>_diag2.csv (metric, var, band, value, goal) and prints the
worst ten against their goals. Balloon diagnostics are a follow-up (the sonde scorer needs the same hook). Needs the GPU for speed (--device cpu works).
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.features import FEATURES, drivers  # noqa: F401
from tempest.generator.sample import Sampler, clip_ranges, to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring import metrics_ext as M
from tempest.scoring.score import band_masks, group_keys

NH = len(HEIGHTS)
GOALS = {"pit_tv": 0.02, "cov_err_mean": 0.008, "skew_diff": 0.15, "kurt_diff": 0.4, "tail_rate_err": 0.2, "event_cov_gap": 0.05,
         "bias_month_max": None, "spread_skill_min": None, "vcorr_err": 0.05, "shear_ks": 0.03}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--first-year", type=int, default=2024)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--m", type=int, default=199)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device")
    ap.add_argument("--shift")
    ap.add_argument("--shear-tail")
    ap.add_argument("--seasonal")
    ap.add_argument("--shear-map")
    ap.add_argument("--pooled-template", action="store_true", help="shuffle templates pooled over grid points (month x 2-hour bin), as shipped in the tool")
    ap.add_argument("--shuffle", action="store_true", help="Schaake shuffle with real training-year profiles of the same group as the dependence template")
    ap.add_argument("--drivers", choices=["unknown", "known"], default="unknown", help="unknown (default, what a query for a future date gets): ONI/WWV/QBO copied together from a random "
                    "earlier-year row of the same grid point x month x hour bin; known: the observed target-month values (an upper bound, review 2.1)")
    ap.add_argument("--out")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device=a.device)
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    year, cond = d["year"], np.asarray(d["cond"])
    keys = group_keys(cond)
    idx = np.sort(rng.choice(np.flatnonzero((year >= a.first_year) & (year <= a.last_year)), a.rows, replace=False))
    y = to_physical(np.asarray(d["target"][idx]))
    month = (keys[idx] // 12) % 12 + 1
    hbin = keys[idx] % 12
    cal_idx = np.sort(rng.choice(np.flatnonzero((year >= 2021) & (year <= 2023)), 20000, replace=False))
    clim = to_physical(np.asarray(d["target"][cal_idx]))
    x = np.empty((len(idx), a.m, y.shape[1]), np.float32)
    dc = [FEATURES.index(k) for k in drivers()]
    tr = np.flatnonzero(year < a.first_year)
    tr = tr[np.argsort(keys[tr], kind="stable")]
    lo, hi = np.searchsorted(keys[tr], keys[idx], "left"), np.searchsorted(keys[tr], keys[idx], "right")
    draws = tr[np.minimum(lo[:, None] + (rng.random((len(idx), a.m)) * np.maximum(hi - lo, 1)[:, None]).astype(np.int64), len(tr) - 1)]
    nh = len(HEIGHTS)
    ri = PROFILE.index("RH") * nh
    pre = np.zeros(2)                                              # review 2.8: how often the calibrated RH leaves 0-100 % before the clip repairs it
    cnt = 0
    preclip = np.zeros((nh + 1,))
    for i in range(0, len(idx), 400):
        sl = slice(i, i + 400)
        rep = np.repeat(cond[idx[sl]], a.m, axis=0)
        if a.drivers == "unknown":
            rep[:, dc] = cond[draws[sl].ravel()][:, dc]
        raw = spread.apply(cal, sampler.profiles(rep).reshape(len(cond[idx[sl]]), a.m, -1), clip=False)
        rh = np.concatenate([raw[..., ri:ri + nh], raw[..., 4 * nh + 2:4 * nh + 3]], -1)           # 44 RH levels and rh2m
        preclip += ((rh < 0) | (rh > 100)).sum((0, 1))
        cnt += rh.shape[0] * rh.shape[1]
        x[sl] = clip_ranges(raw)
    preclip /= cnt
    if a.shuffle:
        from tempest.calibrate import shuffle as shuf_mod
        x = shuf_mod.apply(x, shuf_mod.group_template(d["target"], keys, year, idx, a.m, rng, a.first_year, pooled=a.pooled_template))
    if a.seasonal:
        from tempest.calibrate import seasonal
        x = seasonal.apply(dict(np.load(a.seasonal)), x, month)
    if a.shear_map:
        from tempest.calibrate import shear_map as smap
        x = smap.apply(dict(np.load(a.shear_map)), x)
    if a.shift:
        from tempest.calibrate import shift as sh
        x = sh.apply(dict(np.load(a.shift)), x)
    if a.shear_tail:
        from tempest.calibrate import shear_tail as st
        x = st.apply(dict(np.load(a.shear_tail)), x, np.random.default_rng(12345))
    pit = M.pit_values(x, y, rng)
    tv = M.pit_tv(pit)
    cov = M.coverage_levels(pit)
    levels = np.array([0.1, 0.25, 0.5, 0.75, 0.8, 0.9, 0.95, 0.99])
    cov_err = np.abs(cov - levels[:, None])
    mom = M.standardized_moments(x, y)
    obs_t, pred_t = M.tail_exceedance(x, y, clim)
    nominal = np.array([0.001, 0.01, 0.05, 0.05, 0.01, 0.001])
    tail_err = (np.abs(obs_t - pred_t) / nominal[:, None])[[0, 1, 4, 5]].mean(0)   # observed vs predicted tail frequency, in units of the nominal rate
    inside, ideal, n_ext = M.event_conditional_coverage(x, y, clim, rng=rng)
    bias = M.bias_by_group(x, y, month)
    ss = M.spread_skill(x, y, (month - 1) // 3)
    rows = []
    add = lambda metric, v, b, val: rows.append(dict(metric=metric, var=v, band=b, value=float(val), goal=GOALS.get(metric)))
    for v, b, sel in band_masks():
        add("pit_tv", v, b, tv[sel].mean())
        add("cov_err_mean", v, b, cov_err[:, sel].mean())
        add("skew_diff", v, b, np.abs(mom[sel, 0] - mom[sel, 1]).mean())
        add("kurt_diff", v, b, np.abs(mom[sel, 2] - mom[sel, 3]).mean())
        add("tail_rate_err", v, b, tail_err[sel].mean())
        add("event_cov_gap", v, b, np.nanmean(ideal[sel] - inside[sel]))
        sd = np.maximum(clim[:, sel].std(0), 1e-9)
        add("bias_month_max", v, b, max(np.abs(bias[g][sel] / sd).mean() for g in bias))
        add("spread_skill_min", v, b, min(ss[g][sel].mean() for g in ss))
    for name, sl in (("0-1 km", HEIGHTS <= 1000), ("1-5 km", (HEIGHTS > 1000) & (HEIGHTS <= 5000)), ("5-12 km", (HEIGHTS > 5000) & (HEIGHTS <= 12000)), ("12-18 km", HEIGHTS > 12000)):
        add("preclip_rate", "RH", name, preclip[:NH][sl].mean())
    add("preclip_rate", "rh2m", "surface", preclip[NH])
    for i, v in enumerate(PROFILE):
        cols = np.arange(i * NH, (i + 1) * NH)
        add("vcorr_err", v, "profile", M.vertical_corr_error(x, y, cols, rng=rng))
    for name, sl in (("0-1 km", HEIGHTS[1:] <= 1000), ("1-5 km", (HEIGHTS[1:] > 1000) & (HEIGHTS[1:] <= 5000)),
                     ("5-12 km", (HEIGHTS[1:] > 5000) & (HEIGHTS[1:] <= 12000)), ("12-18 km", HEIGHTS[1:] > 12000)):
        ks, w1 = M.shear_distance(x, y, sl)
        add("shear_ks", "shear", name, ks)
        add("shear_w1", "shear", name, w1)
    dt, ds = M.drift_proxy(y), M.drift_proxy(x)
    for j, top in enumerate((3, 10, 18)):
        mag_t, mag_s = np.hypot(dt[:, j, 0], dt[:, j, 1]), np.hypot(ds[..., j, 0], ds[..., j, 1])
        for q in (50, 95, 99):
            add(f"drift_p{q}_ratio", "drift", f"{top} km", np.percentile(mag_s, q) / max(np.percentile(mag_t, q), 1e-9))
    wind_u, wind_v = np.arange(NH), np.arange(NH, 2 * NH)
    add("dir_err_deg", "wind", "all", M.direction_error(x, y, wind_u, wind_v))
    sp = np.hypot(x[..., wind_u], x[..., wind_v])
    spt = np.hypot(y[:, wind_u], y[:, wind_v])
    hi = (HEIGHTS >= 8000) & (HEIGHTS <= 12000)
    ev = spt[:, hi].max(1) > 25
    p = (sp[..., hi].max(-1) > 25).mean(1)
    base = ev.mean()
    ref = ((base - ev) ** 2).mean()
    add("brier_skill_wind25_8_12km", "event", "8-12 km", 1 - ((p - ev) ** 2).mean() / ref if ref > 0 else np.nan)
    t2 = PROFILE.__len__() * NH
    for name, col, thr, above in (("t2m_below_0C", t2, 273.15, False), ("rh2m_above_90", t2 + 2, 90.0, True)):
        bss, _, _ = M.brier_skill(x, y, [col], thr, above)
        add(f"brier_skill_{name}", "event", "surface", bss)
    t = pd.DataFrame(rows)
    out = a.out or a.model.rsplit(".", 1)[0] + "_diag2"
    t.to_csv(out + ".csv", index=False)
    g = t.dropna(subset=["goal"]).copy()
    g["ratio"] = g.value / g.goal
    print(g.sort_values("ratio", ascending=False).head(10)[["metric", "var", "band", "value", "goal", "ratio"]].round(4).to_string(index=False))
    for m_ in ("pit_tv", "cov_err_mean", "skew_diff", "kurt_diff", "tail_rate_err", "event_cov_gap"):
        print(f"{m_:<16} mean over cells {t[t.metric == m_].value.mean():.4f}  goal {GOALS[m_]}")
    print(f"wrote {out}.csv")


if __name__ == "__main__":
    main()
