"""Ground-wind benchmark (GW): how good is the tool's 10 m wind against real station winds, and which cheap fixes help?

    PYTHONPATH=. TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore scripts/ground_wind_bench.py [--n-fit 300] [--n-test 300] [--m 100]

Truth: hourly ASOS reports (data/raw/asos/TCS, MAF), 10 m wind components u, v. Fit years 2021-2023, test years 2024-2025 (development years; never 2026). Each case asks the tool (climate mode, drivers
unknown = what a planner gets; and past mode) for m atmospheres at the station and hour and scores the 10 m u and v ensemble against the observation (CRPS, coverage of the 50 / 90 % interval, spread ratio).
Variants (all post-processing of the same ensembles, constants fitted on the fit years only):
  V0 tool as is (climate mode)         V2 past mode (ERA5 corrected to balloons, same hour)
  V1 spread recalibration: anomalies about the ensemble median scaled by k (one k per component)
  V3 persistence: condition on the ASOS report h hours earlier (h = 1, 3) with the lag correlation r(h) fitted on the fit years: x' = med + r (obs_prev - med_prev), spread * sqrt(1 - r^2)
  V4 local climatology blend: ensemble blended with the station's own month x hour distribution (2000-2020 ASOS) at weight w (rank-preserving, like the trust layer)
Writes data/ground_wind_bench.csv and prints a table; the verdict goes into docs/logs/LOOP3.md (rows GW-1..).
"""
import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather import api   # noqa: E402

STATIONS = {"TCS": (33.2369, -107.2672, 1479.0), "MAF": (31.9425, -102.2019, 872.0)}
KT = 0.514444
HOURS_OK = set(range(12, 24)) | set(range(0, 5))        # UTC hours the pilot store keeps (past mode needs them)


def valid_hour(st, h):
    """The store keeps UTC 12-23 and 00-04, and the tool serves 06-21 h mean solar time at the station."""
    sh = (h.hour + STATIONS[st][1] / 15.0) % 24.0
    return h.hour in HOURS_OK and 6.0 <= sh < 21.0


def load_asos(st, years):
    """-> dict {(hour-rounded UTC datetime): (u, v)} using the report nearest each hour (within 20 min); VRB and missing directions are skipped."""
    out = {}
    for y in years:
        path = os.path.join(REPO, "data", "raw", "asos", st, f"{y}.csv")
        if not os.path.exists(path):
            continue
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    kt = float(r["sknt"])
                    d = float(r["drct"]) if r["drct"] not in ("", None) else None
                except ValueError:
                    continue
                if kt > 0 and d is None:
                    continue
                h = (t + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
                if abs((t - h).total_seconds()) > 20 * 60 and (h - t).total_seconds() > 20 * 60:
                    continue
                if kt == 0:
                    uv = (0.0, 0.0)
                else:
                    uv = (-kt * KT * np.sin(np.radians(d)), -kt * KT * np.cos(np.radians(d)))
                if h not in out or abs((t - h).total_seconds()) < out[h][2]:
                    out[h] = (uv[0], uv[1], abs((t - h).total_seconds()))
    return {h: (v[0], v[1]) for h, v in out.items()}


def ensemble(st, hour, m, mode, seed):
    lat, lon, el = STATIONS[st]
    atm, _ = api.atmosphere_set(lat, lon, hour.isoformat(), n=m, mode=mode, seed=seed, elevation=el)
    return np.asarray(atm["u"][:, 0], float), np.asarray(atm["v"][:, 0], float)


def crps(x, y):
    """CRPS of an m-member ensemble x against y (exact sorted formula)."""
    x = np.sort(x)
    m = len(x)
    i = np.arange(1, m + 1)
    return float(2.0 / m ** 2 * np.sum((x - y) * (m * (y < x) - i + 0.5)))


def cover(x, y, p):
    lo, hi = np.quantile(x, [(1 - p) / 2, 1 - (1 - p) / 2])
    return float(lo <= y <= hi)


def score(ens, obs):
    """ens (N, m), obs (N,) -> dict crps, cov50, cov90, spread_ratio (member sd over rmse of the median), bias."""
    N = len(obs)
    return dict(crps=np.mean([crps(ens[i], obs[i]) for i in range(N)]), cov50=np.mean([cover(ens[i], obs[i], 0.5) for i in range(N)]), cov90=np.mean([cover(ens[i], obs[i], 0.9) for i in range(N)]),
                spread_ratio=float(np.sqrt(np.mean(ens.var(1))) / np.sqrt(np.mean((np.median(ens, 1) - obs) ** 2))), bias=float(np.mean(np.median(ens, 1) - obs)))


def sample_cases(rng, years, n, asos, st_list):
    cases = []
    for st in st_list:
        keys = [h for h in asos[st] if h.year in years and valid_hour(st, h) and (h - timedelta(hours=3)) in asos[st]]
        idx = rng.choice(len(keys), min(n // len(st_list), len(keys)), replace=False)
        cases += [(st, keys[i]) for i in idx]
    return cases


def run_set(cases, asos, m, seed0, with_past=True):
    res = dict(truth=[], ai=[], past=[], prev1=[], prev3=[], obs1=[], obs3=[], cases=cases)
    for k, (st, h) in enumerate(cases):
        res["truth"].append(asos[st][h])
        res["ai"].append(np.stack(ensemble(st, h, m, "ai", seed0 + k)))
        if with_past:
            res["past"].append(np.stack(ensemble(st, h, m, "past", seed0 + k)))
        for lag in (1, 3):
            hp = h - timedelta(hours=lag)
            res[f"prev{lag}"].append(np.stack(ensemble(st, hp, m, "ai", seed0 + k + 7919)) if valid_hour(st, hp) else None)
            res[f"obs{lag}"].append(asos[st].get(hp))
    return res


def climatology(asos, st, h, ref_years):
    """The station's own u, v sample for this month and UTC hour from the reference years."""
    pool = [asos[st][t] for t in asos[st] if t.year in ref_years and t.month == h.month and t.hour == h.hour]
    return np.array(pool) if len(pool) >= 20 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-fit", type=int, default=300)
    ap.add_argument("--n-test", type=int, default=300)
    ap.add_argument("--m", type=int, default=100)
    a = ap.parse_args()
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(REPO, "data", "pilot", "profiles.zarr")
    rng = np.random.default_rng(0)
    asos = {st: load_asos(st, range(2000, 2026)) for st in STATIONS}
    fit_cases = sample_cases(rng, {2021, 2022, 2023}, a.n_fit, asos, list(STATIONS))
    test_cases = sample_cases(rng, {2024, 2025}, a.n_test, asos, list(STATIONS))
    print(f"{len(fit_cases)} fit cases (2021-23), {len(test_cases)} test cases (2024-25), m = {a.m}", flush=True)
    fit = run_set(fit_cases, asos, a.m, 1000)
    test = run_set(test_cases, asos, a.m, 5000)
    out_rows = []

    def report(name, ens, truth):
        rows = []
        for c, comp in enumerate(("u", "v")):
            s = score(ens[:, c, :], truth[:, c])
            rows.append(s)
        mean = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
        out_rows.append(dict(variant=name, **mean))
        print(f"{name:46} CRPS {mean['crps']:.3f}  cov50 {mean['cov50']:.2f}  cov90 {mean['cov90']:.2f}  spread/rmse {mean['spread_ratio']:.2f}  bias {mean['bias']:+.2f}", flush=True)

    ft, tt = np.array(fit["truth"]), np.array(test["truth"])
    fa, ta = np.array(fit["ai"]), np.array(test["ai"])
    print("\nTEST years 2024-25, 10 m wind components against ASOS (CRPS in m/s, lower is better; ideal coverage 0.50 / 0.90, spread/rmse about 1):")
    report("V0 tool as is (climate mode)", ta, tt)
    if test["past"]:
        report("V2 past mode (ERA5 + balloon correction)", np.array(test["past"]), tt)
        report("V2 past mode fit-years check", np.array(fit["past"]), ft)
    # V1: spread scale k per component, fitted on the fit years to match the 90 % coverage (grid search minimising CRPS)
    ks = []
    for c in range(2):
        best = min((np.mean([crps(np.median(fa[i, c]) + k * (fa[i, c] - np.median(fa[i, c])), ft[i, c]) for i in range(len(ft))]), k) for k in np.arange(0.6, 2.6, 0.1))
        ks.append(best[1])
    print(f"   V1 fitted spread scale k (u, v) = {ks[0]:.1f}, {ks[1]:.1f}")
    v1 = np.stack([np.median(ta[:, c, :], 1, keepdims=True) + ks[c] * (ta[:, c, :] - np.median(ta[:, c, :], 1, keepdims=True)) for c in range(2)], 1)
    report("V1 spread recalibration (k fitted 2021-23)", v1, tt)
    # V3: persistence from the report h hours earlier
    for lag in (1, 3):
        def lag_pairs(res):
            idx = [i for i in range(len(res["truth"])) if res[f"prev{lag}"][i] is not None and res[f"obs{lag}"][i] is not None]
            return idx
        fi, ti = lag_pairs(fit), lag_pairs(test)
        if len(fi) < 30 or len(ti) < 30:
            continue
        rr = []
        for c in range(2):
            dm = np.array([np.median(fit["prev" + str(lag)][i][c]) for i in fi])
            obs_prev = np.array([fit[f"obs{lag}"][i][c] for i in fi])
            now_med = np.array([np.median(fit["ai"][i][c]) for i in fi])
            tru = np.array([fit["truth"][i][c] for i in fi])
            x, y = obs_prev - dm, tru - now_med
            rr.append(float(np.clip((x * y).sum() / max((x * x).sum(), 1e-9), 0.0, 0.99)))      # regression of today's anomaly on the earlier anomaly = the useful persistence gain
        ens = []
        for i in ti:
            e = np.empty((2, ta.shape[2]))
            for c in range(2):
                med = np.median(test["ai"][i][c])
                prev_med = np.median(test[f"prev{lag}"][i][c])
                shift = rr[c] * (test[f"obs{lag}"][i][c] - prev_med)
                sd_cut = np.sqrt(max(1 - rr[c] ** 2, 0.05))
                e[c] = med + shift + sd_cut * (test["ai"][i][c] - med)
            ens.append(e)
        report(f"V3 persistence: ASOS report {lag} h earlier (r = {rr[0]:.2f}, {rr[1]:.2f})", np.array(ens), tt[ti])
        report(f"   same cases, V0 for comparison", ta[ti], tt[ti])
    # V4: local climatology blend at weight w (rank-preserving): sort the ensemble and the climatology samples, mix their quantiles
    ref = set(range(2000, 2021))
    best_w = None
    for w in (0.0, 0.2, 0.4, 0.6):
        sc = []
        for i, (st, h) in enumerate(fit_cases):
            cl = climatology(asos, st, h, ref)
            if cl is None:
                continue
            e = np.empty((2, fa.shape[2]))
            for c in range(2):
                q = np.quantile(cl[:, c], (np.arange(fa.shape[2]) + 0.5) / fa.shape[2])
                srt = np.sort(fa[i, c])
                e[c] = (1 - w) * srt + w * q
            sc.append(np.mean([crps(e[0], ft[i, 0]), crps(e[1], ft[i, 1])]))
        if sc and (best_w is None or np.mean(sc) < best_w[0]):
            best_w = (float(np.mean(sc)), w)
    w = best_w[1] if best_w else 0.0
    ens = []
    for i, (st, h) in enumerate(test_cases):
        cl = climatology(asos, st, h, ref)
        e = np.sort(ta[i], axis=1)
        if cl is not None:
            for c in range(2):
                q = np.quantile(cl[:, c], (np.arange(ta.shape[2]) + 0.5) / ta.shape[2])
                e[c] = (1 - w) * e[c] + w * q
        ens.append(e)
    report(f"V4 local ASOS climatology blend (w = {w:.1f} fitted)", np.array(ens), tt)
    with open(os.path.join(REPO, "data", "ground_wind_bench.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, list(out_rows[0]))
        wr.writeheader()
        wr.writerows(out_rows)


if __name__ == "__main__":
    main()
