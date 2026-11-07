"""Scorecard: generator vs climatology on the held-out years, in physical units.

    python -m tempest.scoring.score --model models/generator_pilot.pt --data data/train/pilot.npz
                                    [--rows 5000] [--m 50] [--device cpu]

For each held-out row (the last `val_years` years, as in training) it draws m samples four ways:
- climatology: real training-year rows from the same grid point, calendar month and 2-hour solar-time bin
- gauss: monthly mean + correlated bell-curve spread per grid point, the way NASA Earth-GRAM / Range Reference
  Atmospheres build dispersions (the tool aerospace uses today; the bar to clear)
  (per grid point x month x 2-hour bin; month only where a bin has < 600 training rows)
- recent climatology (headline only): as climatology but from the 15 years before the test, so warming is in the bar
The HEADLINE table gives skill, best-guess error (median) and 99 % coverage with 95 % day-block bootstrap intervals.
- generator, drivers known: ONI, WWV, QBO as observed (upper bound, like a perfect seasonal forecast)
- generator, drivers unknown: drivers copied from random training rows of the same group (what a query
  years ahead gets: the model's spread then also covers ENSO/QBO uncertainty)
Per column: CRPS (lower is better), 90 % interval coverage (should be ~0.90) and skill = 1 - CRPS / CRPS_clim
(> 0 beats climatology). Variogram score (p = 0.5, Scheuerer & Hamill 2015) per variable checks profile shape:
shear and differences between heights, which CRPS per value cannot see. Truth is ERA5, not radiosondes: coverage against real soundings will be lower until the
phase 6 correction. Writes <model>.score.csv (every column), prints a summary by variable and height band, and saves
charts + tables in <model>_report/ (see scoring.report).
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread, trust
from tempest.generator.features import FEATURES, drivers
from tempest.generator.sample import SURFACE, Sampler, clip_ranges, to_physical
from tempest.generator.train import load_npz
from tempest.scoring import diag
from tempest.scoring.report import report
from tempest.profiles.to_heights import HEIGHTS, PROFILE

DRIVERS = ["oni", "wwv", "qbo30", "qbo50"]
BANDS = [(0, 1000), (1000, 5000), (5000, 12000), (12000, 18001)]


def crps_ensemble(x, y):
    """x (N, m, D) samples, y (N, D) truth -> (N, D) CRPS, exact for the m-member ensemble (sorted formula)."""
    x = np.sort(x, axis=1)
    m = x.shape[1]
    i = np.arange(1, m + 1)[None, :, None]
    return 2 / m ** 2 * ((x - y[:, None]) * (m * (y[:, None] < x) - i + 0.5)).sum(1)


def coverage90(x, y, p=0.9):
    """Truth inside the ensemble's central p range: the k-th lowest to k-th highest of m samples, k = (1-p)/2 (m+1).
    A perfect ensemble then holds the truth (m+1-2k)/(m+1) of the time (= p when (1-p)/2 (m+1) is whole, e.g.
    m = 199 for 90 % and 99 %); interpolated quantiles undercount (a perfect m = 100 ensemble scores 0.97 at 99 %)."""
    m = x.shape[1]
    k = max(1, int(round((1 - p) / 2 * (m + 1))))
    s = np.partition(x, [k - 1, m - k], axis=1)
    return (y >= s[:, k - 1]) & (y <= s[:, m - k])


def variogram_score(x, y, p=0.5, chunk=200):
    """x (N, m, H) samples, y (N, H) truth -> (N,) variogram score over all height pairs. Lower is better."""
    out = np.empty(len(y))
    for i in range(0, len(y), chunk):
        xs, ys = x[i:i + chunk], y[i:i + chunk]
        vy = np.abs(ys[:, :, None] - ys[:, None, :]) ** p
        vx = (np.abs(xs[:, :, :, None] - xs[:, :, None, :]) ** p).mean(1)
        out[i:i + chunk] = ((vy - vx) ** 2).sum((1, 2)) / 2
    return out


def gaussian_samples(x, n, m, rng):
    """x (R, D) physical training rows of one group -> (n, m, D) draws from their mean + full covariance."""
    mu, sd = x.mean(0), x.std(0) + 1e-9
    L = np.linalg.cholesky(np.corrcoef((x - mu) / sd, rowvar=False) + 1e-6 * np.eye(x.shape[1]))
    return clip_ranges(mu + (rng.standard_normal((n, m, x.shape[1])) @ L.T) * sd)


def group_keys(cond):
    """Grid point x calendar month x 2-hour solar-time bin, from the feature columns."""
    c = {k: cond[:, FEATURES.index(k)] for k in FEATURES}
    _, point = np.unique(np.round(np.stack([c["lat"], c["lon"]], 1), 3), axis=0, return_inverse=True)
    month = (np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    hbin = (np.arctan2(c["hour_sin"], c["hour_cos"]) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    return point.ravel().astype(np.int64) * 144 + month * 12 + hbin


def band_masks():
    """(var, band label, boolean mask over the physical columns) for every variable x height band and surface field."""
    n, names = len(HEIGHTS), physical_names()
    out = []
    for i, v in enumerate(PROFILE):
        for b0, b1 in BANDS:
            sel = np.zeros(len(names), bool)
            sel[i * n:(i + 1) * n] = (HEIGHTS >= b0) & (HEIGHTS < b1)
            out.append((v, f"{b0 / 1000:g}-{min(b1, 18000) / 1000:g} km", sel))
    return out + [(s, "surface", np.array([c == s for c in names])) for s in SURFACE]


def var_slices():
    n = len(HEIGHTS)
    return [(v, slice(i * n, (i + 1) * n)) for i, v in enumerate(PROFILE)] + [(s, slice(len(PROFILE) * n + j, len(PROFILE) * n + j + 1)) for j, s in enumerate(SURFACE)]


def physical_names():
    return [f"{v}_{int(h)}" for v in PROFILE for h in HEIGHTS] + SURFACE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--m", type=int, help="samples per row (default: the calibration's m, else 50)")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--calib", help="range calibration from tempest.calibrate.spread (outputs get a _cal suffix)")
    ap.add_argument("--first-test-year", type=int, help="score only from this year (keep the calibration year out)")
    ap.add_argument("--last-test-year", type=int, help="score only up to this year; later years are not used at all")
    ap.add_argument("--seasonal", help="monthly width factors from tempest.calibrate.seasonal (needs --calib); outputs get a _seas suffix")
    ap.add_argument("--pooled-template", action="store_true", help="with --shuffle: dependence templates pooled over grid points (month x 2-hour bin) instead of the same grid point")
    ap.add_argument("--pit-damp", type=float, default=1.0, help="strength of --pit-recal in (0, 1]")
    ap.add_argument("--pit-recal", help="full PIT recalibration table (scripts/il86_fit.py): applied right after the range map; outputs get a _pit suffix")
    ap.add_argument("--template-cell", type=int, default=0, help="with --shuffle: dependence templates per block of N x N grid points (8 = 2 degrees)")
    ap.add_argument("--shuffle", action="store_true", help="Schaake shuffle: keep every column's samples, take the order across columns from the real climatology draws of the same group; outputs get a _shuf suffix")
    ap.add_argument("--shear-map", help="shear-space quantile map from tempest.calibrate.shear_map (needs --calib); outputs get a _smap suffix")
    ap.add_argument("--shift", help="median bias shift from tempest.calibrate.shift (needs --calib); outputs get a _shift suffix")
    ap.add_argument("--shear-tail", help="rare wind-shear patches from tempest.calibrate.shear_tail (needs --calib); outputs get a _stail suffix")
    ap.add_argument("--trust", help="trust-layer weights from tempest.calibrate.trust (needs --calib); blends the calibrated "
                    "samples toward the 15-year climatology where the model has no skill (outputs get a _trust suffix)")
    ap.add_argument("--driver-mode", choices=["analog", "ridge"], default="analog", help="how the 'unknown' set draws ONI/WWV/QBO: copied from random training rows of the "
                    "group (analog, default) or from the ridge index forecast made --driver-lead months earlier (what the tool serves)")
    ap.add_argument("--driver-lead", type=int, default=6, help="lead in months for --driver-mode ridge")
    ap.add_argument("--extras", action="store_true", help="also write PIT histograms, coverage at 50/80/90/99 %%, wind speed/"
                    "direction error and the worst months/columns to <stem>_extras_*.csv (old outputs unchanged)")
    ap.add_argument("--mc", action="store_true", help="also write the Monte Carlo checks of GLOBAL_PLAN §9 (tempest.scoring.mc) to <stem>_mc.csv")
    ap.add_argument("--stress", action="store_true", help="also write the season x ENSO x time-of-day stress table "
                    "(<stem>_stress.csv) and print the worst cells; read-only")
    ap.add_argument("--joint", help="joint-band widths from tempest.calibrate.joint (needs --calib): also reports the "
                    "whole-profile coverage of the simultaneous 99 %% band (output only; samples are not changed)")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)  # the generator draws its noise with torch; unseeded, reruns differ by ~0.001 skill

    ckpt = torch.load(a.model, map_location="cpu", weights_only=True)
    sampler = Sampler(ckpt, device=a.device)
    histories = [c.get("history") for c in ckpt.get("members", [ckpt])]
    ckpt = ckpt.get("members", [ckpt])[0]
    d = load_npz(a.data)
    cond, year = d["cond"], d["year"]
    held = (year > year.max() - ckpt["cfg"]["val_years"]) & (year >= (a.first_test_year or 0)) & (year <= (a.last_test_year or 9999))
    if a.first_test_year:  # an explicit test window is used as given (walk-forward folds earlier than the last val_years); same result when it lies inside them
        held = (year >= a.first_test_year) & (year <= (a.last_test_year or 9999))
    cal = spread.load(a.calib, a.model)
    a.m = a.m or (int(cal["m"]) if cal else 50)
    keys = group_keys(cond)

    tr = np.flatnonzero(~held & (year <= (a.last_test_year or 9999)))
    tr = tr[np.argsort(keys[tr], kind="stable")]
    trk = keys[tr]
    va = rng.choice(np.flatnonzero(held), min(a.rows, int(held.sum())), replace=False)
    lo, hi = np.searchsorted(trk, keys[va], "left"), np.searchsorted(trk, keys[va], "right")
    ok = hi > lo
    va, lo, hi = va[ok], lo[ok], hi[ok]
    print(f"{len(va):,} held-out rows ({int((~ok).sum())} without a climatology group dropped), m = {a.m}", flush=True)

    draws = tr[lo[:, None] + (rng.random((len(va), a.m)) * (hi - lo)[:, None]).astype(np.int64)]  # (N, m)
    target = d["target"]
    truth = to_physical(target[va])
    clim = to_physical(target[draws.ravel()].reshape(*draws.shape, -1))
    # fair baseline with warming: same groups, only the last 15 years before the test (all years if a group is empty)
    first = a.first_test_year or int(year[va].min())
    rec = tr[year[tr] >= first - 15]  # tr is sorted by key, so the subset is too
    lo2, hi2 = np.searchsorted(keys[rec], keys[va], "left"), np.searchsorted(keys[rec], keys[va], "right")
    d2 = rec[np.minimum(lo2[:, None] + (rng.random((len(va), a.m)) * (hi2 - lo2)[:, None]).astype(np.int64), len(rec) - 1)]
    d2 = np.where((hi2 > lo2)[:, None], d2, draws)
    clim15 = to_physical(target[d2.ravel()].reshape(*d2.shape, -1))
    print(f"recent climatology {first - 15}-{first - 1}: {int((hi2 > lo2).mean() * 100)} % of rows have a group", flush=True)

    # grid point x month x 2-hour bin: a reference atmosphere also knows the hour; month only if the bin is thin
    gk = np.where(np.bincount(keys[tr], minlength=keys.max() + 1)[keys] >= 600, keys, -1 - keys // 12)
    trg = tr[np.argsort(gk[tr], kind="stable")]
    gauss = np.empty_like(clim)
    for g in np.unique(gk[va]):
        rows = (trg[np.searchsorted(gk[trg], g, "left"):np.searchsorted(gk[trg], g, "right")] if g >= 0
                else tr[keys[tr] // 12 == -1 - g])
        rows = np.sort(rng.choice(rows, min(len(rows), 3000), replace=False))
        sel = np.flatnonzero(gk[va] == g)
        gauss[sel] = gaussian_samples(to_physical(target[rows]).astype(np.float64), len(sel), a.m, rng)

    rep = np.repeat(cond[va], a.m, axis=0)
    known = sampler.profiles(rep).reshape(len(va), a.m, -1)
    if cal:
        known = spread.apply(cal, known)
    dc = [FEATURES.index(k) for k in drivers()]  # oni, wwv, qbo (+ the ONI hinges and lag when the dataset has them)
    if a.driver_mode == "ridge":
        from tempest.scoring import ridge_drivers
        ridge_drivers.fill(rep, cond[va], year[va], a.m, a.driver_lead, rng)
    else:
        rep[:, dc] = cond[draws.ravel()][:, dc]
    unknown = sampler.profiles(rep).reshape(len(va), a.m, -1)
    if cal:
        unknown = spread.apply(cal, unknown)
    if a.pit_recal:
        from tempest.calibrate import pit_recal
        pt = dict(np.load(a.pit_recal))
        known, unknown = pit_recal.apply(pt, known, a.pit_damp), pit_recal.apply(pt, unknown, a.pit_damp)
    if a.seasonal:
        if not cal:
            raise SystemExit("--seasonal needs --calib")
        from tempest.calibrate import seasonal
        sw = dict(np.load(a.seasonal))
        mon = (keys[va] // 12) % 12 + 1
        known, unknown = seasonal.apply(sw, known, mon), seasonal.apply(sw, unknown, mon)
    if a.trust:  # L3-33: before the shuffle and the shear-space maps, so they repair the joint shape the per-column blend breaks
        if not cal:
            raise SystemExit("--trust needs --calib")
        tw = trust.load(a.trust, a.model, a.calib)
        qpool = trust.ClimPool(keys, year, target, (first - int(tw["clim_years"]), first - 1), a.m)  # same window as clim15 above
        q = qpool.quantiles(keys[va])
        known, unknown = trust.apply_full(tw, known, q), trust.apply_full(tw, unknown, q)
    if a.shuffle:
        from tempest.calibrate import shuffle as shuf_mod
        tpl = clim
        if a.template_cell:                                                          # IL-95: templates per block of N x N grid points, as shipped in the tool
            tpl = shuf_mod.group_template(target, keys, year, va, a.m, np.random.default_rng(a.seed + 5), a.first_test_year or int(year[va].min()), cell=a.template_cell)
        if a.pooled_template:                                                        # IL-94: templates pooled over grid points, as shipped in the tool
            tpl = shuf_mod.group_template(target, keys, year, va, a.m, np.random.default_rng(a.seed + 5), a.first_test_year or int(year[va].min()), pooled=True)
        known, unknown = shuf_mod.apply(known, tpl), shuf_mod.apply(unknown, tpl)
    if a.shear_map:
        if not cal:
            raise SystemExit("--shear-map needs --calib")
        from tempest.calibrate import shear_map
        smt = dict(np.load(a.shear_map))
        known, unknown = shear_map.apply(smt, known), shear_map.apply(smt, unknown)
    if a.shift:
        if not cal:
            raise SystemExit("--shift needs --calib")
        from tempest.calibrate import shift as shift_mod
        sh = dict(np.load(a.shift))
        mon_s = (keys[va] // 12) % 12 + 1
        known, unknown = shift_mod.apply(sh, known, mon_s), shift_mod.apply(sh, unknown, mon_s)
    if a.shear_tail:
        if not cal:
            raise SystemExit("--shear-tail needs --calib")
        from tempest.calibrate import shear_tail
        st, prng = dict(np.load(a.shear_tail)), np.random.default_rng(12345)
        known, unknown = shear_tail.apply(st, known, prng), shear_tail.apply(st, unknown, prng)
    res = pd.DataFrame({"column": physical_names()})
    sets = [("clim", clim), ("gauss", gauss), ("known", known), ("unknown", unknown)]
    n = len(HEIGHTS)
    vs = pd.DataFrame([{"var": v, **{f"vs_{name}": variogram_score(x[..., i * n:(i + 1) * n], truth[:, i * n:(i + 1) * n]).mean()
                                     for name, x in sets}} for i, v in enumerate(PROFILE)])
    for name in ("gauss", "known", "unknown"):
        vs[f"vs_skill_{name}"] = 1 - vs[f"vs_{name}"] / vs["vs_clim"]
    for name, x in sets:
        res[f"crps_{name}"] = crps_ensemble(x, truth).mean(0)
        res[f"cov90_{name}"] = coverage90(x, truth).mean(0)
        res[f"cov99_{name}"] = coverage90(x, truth, 0.99).mean(0)
        med = np.median(x, 1)
        res[f"mae_{name}"] = np.abs(med - truth).mean(0)
        res[f"rmse_{name}"] = np.sqrt(((med - truth) ** 2).mean(0))
    for name in ("gauss", "known", "unknown"):
        res[f"skill_{name}"] = 1 - res[f"crps_{name}"] / res["crps_clim"]
    stem = a.model.rsplit(".", 1)[0] + ("_cal" + a.calib.rsplit(".calib", 1)[-1].removesuffix(".npz") if cal else "") + ("_trust" if a.trust else "") + ("_seas" if a.seasonal else "") + ("_stail" if a.shear_tail else "") + ("_shift" if a.shift else "") + ("_smap" if a.shear_map else "") + ("_shuf" if a.shuffle else "") + ("pool" if a.shuffle and a.pooled_template else "") + (f"c{a.template_cell}" if a.shuffle and a.template_cell else "") + ("_ridge" if a.driver_mode == "ridge" else "") + ("_pit" if a.pit_recal else "")
    out = stem + ".score.csv"
    res.to_csv(out, index=False)

    rows = [(v, b, res[sel]) for v, b, sel in band_masks()]
    summary = pd.DataFrame([dict(var=v, band=b, crps_clim=r.crps_clim.mean(), crps_known=r.crps_known.mean(),
                                 skill_gauss=1 - r.crps_gauss.mean() / r.crps_clim.mean(),
                                 skill_known=1 - r.crps_known.mean() / r.crps_clim.mean(),
                                 skill_unknown=1 - r.crps_unknown.mean() / r.crps_clim.mean(),
                                 cov90_known=r.cov90_known.mean(), cov90_unknown=r.cov90_unknown.mean(),
                                 cov90_clim=r.cov90_clim.mean(), cov90_gauss=r.cov90_gauss.mean(),
                                 cov99_known=r.cov99_known.mean(), cov99_unknown=r.cov99_unknown.mean(),
                                 cov99_clim=r.cov99_clim.mean(), cov99_gauss=r.cov99_gauss.mean()) for v, b, r in rows])
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(summary.to_string(index=False))
        print("\nbest-guess error (median of the samples vs the truth; physical units, lower is better):")
        print(pd.DataFrame([dict(var=v, band=b, mae_clim=r.mae_clim.mean(), mae_known=r.mae_known.mean(),
                                 rmse_clim=np.sqrt((r.rmse_clim ** 2).mean()), rmse_known=np.sqrt((r.rmse_known ** 2).mean()),
                                 mae_skill=1 - r.mae_known.mean() / r.mae_clim.mean()) for v, b, r in rows]).to_string(index=False))
        print("\nprofile shape (variogram score, skill vs climatology):")
        print(vs.to_string(index=False))
        # per-column 99 % coverage says nothing about whole profiles: share of rows with every height inside
        print("\nwhole-profile 99 % coverage (all 44 heights inside at once):  " + "  ".join(
            f"{v} {coverage90(known[..., i * n:(i + 1) * n], truth[:, i * n:(i + 1) * n], 0.99).all(1).mean():.3f}"
            f" (clim {coverage90(clim[..., i * n:(i + 1) * n], truth[:, i * n:(i + 1) * n], 0.99).all(1).mean():.3f})"
            for i, v in enumerate(PROFILE)))
    if a.joint:
        from tempest.calibrate import joint  # late import, only for the flag
        jt = joint.load(a.joint, a.model, a.calib)
        for mode, x in (("known", known), ("unknown", unknown)):
            lo_j, hi_j = joint.apply(jt[f"scale_{mode}"], x)
            ok = (truth[:, :lo_j.shape[1]] >= lo_j) & (truth[:, :lo_j.shape[1]] <= hi_j)
            print(f"JOINT band ({mode} drivers) whole-profile 99 % coverage: " + "  ".join(
                f"{v} {ok[:, i * n:(i + 1) * n].all(1).mean():.3f}" for i, v in enumerate(PROFILE)) +
                "   per-height coverage inside it: " + "  ".join(
                f"{v} {ok[:, i * n:(i + 1) * n].mean():.4f}" for i, v in enumerate(PROFILE)))
    print(f"wrote {out}")
    c = {k: cond[va, FEATURES.index(k)] for k in ("doy_sin", "doy_cos")}
    day = year[va].astype(np.int64) * 1000 + np.round(np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi) / (2 * np.pi) * 365.25).astype(np.int64)
    diag.print_headline(diag.headline(dict(sets, clim15=clim15), truth, day, band_masks()), stem + "_headline.csv")
    diag.report(stem, known, truth, physical_names(), band_masks(), (keys[va] // 12) % 12 + 1, var_slices())
    if a.extras:
        from tempest.scoring import extras  # late import, only for the flag
        extras.write(stem, unknown, truth, band_masks(), (keys[va] // 12) % 12 + 1, physical_names(), "unknown")
    if a.mc:
        from tempest.scoring import mc  # late import, only for the flag
        mc.write(stem, unknown, clim15, truth, cond[va], list(FEATURES), band_masks())
    if a.stress:
        from tempest.scoring import stress  # late import, only for the flag
        stress.write(stem, unknown, clim15, truth, cond[va], list(FEATURES), band_masks())
    rdir = stem + "_report"
    report(rdir, res, vs, (known < truth[:, None]).sum(1), (truth[:3], known[:3]), histories, PROFILE, HEIGHTS, SURFACE)
    summary.to_csv(f"{rdir}/summary.csv", index=False)
    print(f"wrote charts to {rdir}/")


if __name__ == "__main__":
    main()
