"""22.V0 (New_Plan 22.2): where does the tool's vertical-correlation error (b9: tool 0.056-0.061 vs balloons) come from? REPORT ONLY, changes nothing.
Cases: the b9 list (EPZ / MAF, 00Z / 12Z, 2024-25, 200 per group). One random member per case (departure from the 1991-2020 balloon mean of that station / month / hour), pooled
over cases, correlation over the 44 heights, compared with the balloons' correlation exactly as b9 does (error = mean |corr source - corr balloons| over off-diagonal).
Split: (a) variable u / v / T; (b) separation band of the pair: near < 1 km, mid 1-5 km, far > 5 km; (c) signed mean (source - balloons; + = source too correlated);
(d) stack stage: kit_common.STAGES (range map only, + shuffle, + shear map, + lapse map = shipped); (e) ERA5 bank: ERA5 profiles at the nearest store point, same month and UTC hour,
1991-2020, one random one per case; (f) mean structure: the same error from the tool's ENSEMBLE-MEAN departure (case-to-case mean part only; 20 members).
PRE-SET RULE (written before the run; New_Plan 22.2 'Decides'):
  SHUFFLE: the shuffle stage (range map only -> + shuffle) moves the error by more than 0.010, or the ERA5 bank error is within 0.010 of the shipped tool's -> run V1 (templates set the cap).
  MAPS: the error changes by more than 0.010 at the shear or lapse stage -> fix there, V1 dropped.
  NEAR: near-band signed mean > 0 and the near-band |error| exceeds the far-band |error| -> V4 arm.
  MEAN: the ensemble-mean-only error (f) is at least as large as the one-member shipped error -> error is in the mean; stop, none of V1-V5 helps.
  Several can hold; every one that holds is reported. A stage difference under 0.010 is read as no change (single values carry sampling noise, about 0.03 at 600 cases).
    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b70_v0_split.py      # KIT_SMOKE=1 ... --per-group 4 for a test
Result: docs/results/logs/kit_b70_v0_split.log
"""
import argparse

import numpy as np
import pandas as pd

import kit_common as K
import b9_gram_compare as B9

VARS = ("u", "v", "T")
M = 20
SEP = np.abs(K.H[:, None] - K.H[None, :])
BANDS = {"near<1km": (SEP > 0) & (SEP < 1000), "mid1-5km": (SEP >= 1000) & (SEP < 5000), "far>5km": SEP >= 5000}
_E = {}


def era5_pool(sid, month, hour):
    key = (sid, month, hour)
    if key not in _E:
        lat, lon, _ = K.station_pos(sid)
        t = pd.date_range("1991-01-01", "2020-12-31", freq="D") + pd.Timedelta(hours=hour)
        t = t[t.month == month]
        _, d = K.era5_at(lat, lon, t)
        _E[key] = d
    return _E[key]


def corr_err(src, tru):
    """src, tru: dict q -> (n, 44) departures -> {(q, band): (abs err, signed err)}; the source is hidden where the balloon is."""
    out = {}
    for q in VARS:
        s = np.where(np.isfinite(tru[q]), src[q], np.nan)
        d = pd.DataFrame(s).corr(min_periods=30).values - pd.DataFrame(tru[q]).corr(min_periods=30).values
        for b, m in BANDS.items():
            x = d[m]
            out[(q, b)] = (float(np.nanmean(np.abs(x))), float(np.nanmean(x)))
        m = ~np.eye(K.NH, dtype=bool)
        out[(q, "all")] = (float(np.nanmean(np.abs(d[m]))), float(np.nanmean(d[m])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-group", type=int, default=200)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    todo = B9.cases(a.per_group, rng)
    srcs = list(K.STAGES) + ["era5 bank", "tool ensemble mean"]
    pick = {s: {q: [] for q in VARS} for s in srcs + ["balloons"]}
    skipped = 0
    for cid, sid, t, b in todo:
        lat, lon, elev = K.station_pos(sid)
        mu, _ = B9.clim_stats(sid, t.month, t.hour)
        try:
            runs = {s: K.tool(lat, lon, t, seed=1000 * t.year + int(t.dayofyear), n=M, elevation=elev, stage=s) for s in K.STAGES}
        except ValueError:
            skipped += 1
            continue
        e = era5_pool(sid, t.month, t.hour)
        k = int(rng.integers(len(e["u"])))
        for q in VARS:
            pick["balloons"][q].append(b[q] - mu[q])
            for s, atm in runs.items():
                pick[s][q].append(np.asarray(atm[q], float)[int(rng.integers(M))] - mu[q])
            pick["era5 bank"][q].append(e[q][k] - mu[q])
            pick["tool ensemble mean"][q].append(np.asarray(runs["+ lapse map (shipped)"][q], float).mean(0) - mu[q])
    pick = {s: {q: np.array(v) for q, v in d.items()} for s, d in pick.items()}
    n = len(pick["balloons"]["u"])
    assert n >= 8, f"only {n} cases"
    E = {s: corr_err(pick[s], pick["balloons"]) for s in srcs}
    cols = ["all"] + list(BANDS)
    tot = lambda D, c="all": float(np.mean([D[(q, c)][0] for q in VARS]))
    sgn = lambda D, c="all": float(np.mean([D[(q, c)][1] for q in VARS]))
    L = [f"22.V0 vertical-correlation error split: {n} cases ({skipped} skipped), one member per case ({M} members for the ensemble-mean row), source vs balloons, mean |corr diff| (signed mean in brackets, + = source too correlated)",
         "source                        " + "   ".join(f"{c:<16}" for c in cols)]
    for s in srcs:
        L.append(f"  {s:<28}" + "   ".join(f"{tot(E[s], c):.3f} [{sgn(E[s], c):+.3f}]  " for c in cols))
    L.append("by variable (all pairs): " + "; ".join(f"{s}: " + " ".join(f"{q} {E[s][(q, 'all')][0]:.3f}" for q in VARS) for s in srcs))
    sh, rm, pre, shr = E["+ lapse map (shipped)"], E["range map only"], E["+ shuffle"], E["+ shear map"]
    stepd = {"range map -> + shuffle": tot(pre) - tot(rm), "+ shuffle -> + shear map": tot(shr) - tot(pre), "+ shear map -> + lapse map": tot(sh) - tot(shr)}
    L.append("stage steps (error change): " + "; ".join(f"{k} {v:+.3f}" for k, v in stepd.items()))
    cond = {"SHUFFLE": abs(stepd["range map -> + shuffle"]) > 0.010 or abs(tot(E["era5 bank"]) - tot(sh)) <= 0.010,
            "MAPS": abs(stepd["+ shuffle -> + shear map"]) > 0.010 or abs(stepd["+ shear map -> + lapse map"]) > 0.010,
            "NEAR": sgn(sh, "near<1km") > 0 and tot(sh, "near<1km") > tot(sh, "far>5km"),
            "MEAN": tot(E["tool ensemble mean"]) >= tot(sh)}
    L.append("RULE: " + "; ".join(f"{k} {'HOLDS' if v else 'no'}" for k, v in cond.items()))
    L.append("Notes: single values carry sampling noise (about 0.03 at 600 cases); read differences between stages, which share the cases. 'range map only' = shuffle, shear and lapse maps off, "
             f"the earliest stage the kit can reach (no raw-net row). ERA5 bank = ERA5 profiles at the nearest store point, same month and UTC hour, 1991-2020. The ensemble-mean row has {M} members, so its spread part is only partly removed.")
    K.report("b70_v0_split", L)


if __name__ == "__main__":
    main()
