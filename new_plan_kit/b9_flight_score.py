"""Score the flight-impact comparison (flight_sim_trial/gram_flights.py): how well each atmosphere source predicts the flight that the REAL
(balloon) atmosphere gives. REPORT ONLY. Sol Invictus launched at each balloon station, dry, no vertical wind; 2024-25 cases (development set, reused).
Per case and flight output (apogee, drift, landing east/north, max q, max Mach, flight time): the source's member flights are a forecast of the
balloon flight -> CRPS, PIT, inside the central 90 %, bias of the member mean, spread-skill (SD / RMSE of mean, finite-m corrected).
Landing point (east, north) jointly: energy score, and inside the 90 % Gaussian ellipse (Mahalanobis^2 <= 4.605).
Paired differences to the tool with day-block 95 % intervals.

    .venv/Scripts/python -W ignore new_plan_kit/b9_flight_score.py
"""
import glob
import os

import numpy as np
import pandas as pd

import kit_common as K

OUTS = ("apogee_agl_m", "drift_m", "east_m", "north_m", "max_q_pa", "max_mach", "flight_time_s")
RES = os.path.join(K.REPO, "flight_sim_trial", "results")


def energy(e, y):
    """Energy score of points e (m, 2) for the outcome y (2,)."""
    return np.linalg.norm(e - y, axis=1).mean() - 0.5 * np.linalg.norm(e[:, None] - e[None], axis=2).mean()


def in_ellipse(e, y, chi2=4.605):
    d = y - e.mean(0)
    return float(d @ np.linalg.solve(np.cov(e.T), d) <= chi2)


def main():
    files = sorted(f for f in glob.glob(os.path.join(RES, "gram_flights_*.csv")) if "smoke" not in f)
    df = pd.concat([pd.read_csv(f) for f in files])
    truth = df[df.source == "truth"].set_index("case")
    srcs = [s for s in df.source.unique() if s != "truth"]
    rows, rng = [], np.random.default_rng(0)
    for (case, s), g in df[df.source != "truth"].groupby(["case", "source"]):
        y = truth.loc[case]
        r = dict(case=case, source=s, station=y.station, day=case.split("|")[1][:10], m=len(g))
        for o in OUTS:
            e = g[o].to_numpy(float)
            r[f"{o}_crps"] = K.crps1(e, y[o])
            r[f"{o}_pit"] = ((e < y[o]).sum() + rng.uniform() * ((e == y[o]).sum() + 1)) / (len(e) + 1)
            lo, hi = np.percentile(e, [5, 95])
            r[f"{o}_in90"] = float(lo <= y[o] <= hi)
            r[f"{o}_err"] = e.mean() - y[o]
            r[f"{o}_sd"] = e.std(ddof=1)
        en, yn = g[["east_m", "north_m"]].to_numpy(float), y[["east_m", "north_m"]].to_numpy(float)
        r["land_es"], r["land_in90"] = energy(en, yn), in_ellipse(en, yn)
        rows.append(r)
    R = pd.DataFrame(rows)
    n, m = R.case.nunique(), int(R.m.median())
    T = truth
    L = [f"Flight-impact comparison: Sol Invictus (flight_sim example rocket) flown through each source's atmospheres at the balloon station, {n} cases "
         f"({', '.join(f'{k} {v}' for k, v in R.drop_duplicates('case').station.value_counts().items())}), {m} member flights per source per case, plus one flight "
         "through the observed balloon profile (the truth). 2024-25 balloons: development set, reused. Dry air and no vertical wind for every source.",
         f"Truth flights: apogee {T.apogee_agl_m.median():.0f} m above the pad (p5-p95 {T.apogee_agl_m.quantile(.05):.0f}-{T.apogee_agl_m.quantile(.95):.0f}), "
         f"drift {T.drift_m.median():.0f} m ({T.drift_m.quantile(.05):.0f}-{T.drift_m.quantile(.95):.0f}), max q {T.max_q_pa.median() / 1000:.1f} kPa, "
         f"max Mach {T.max_mach.median():.3f}.", ""]
    for title, key, fmt in (("CRPS (lower is better; m, m, m, m, Pa, -, s)", "crps", "{:9.2f}"), ("90 % COVERAGE (target 0.90)", "in90", "{:9.3f}"),
                            ("MEAN ERROR of the member mean (source - truth)", "err", "{:+9.2f}")):
        L.append(title + ":  " + " ".join(f"{o[:9]:>9s}" for o in OUTS))
        for s in srcs:
            sub = R[R.source == s]
            L.append(f"  {s:18s} " + " ".join(fmt.format(sub[f'{o}_{key}'].mean()) for o in OUTS))
        L.append("")
    L.append("SPREAD-SKILL (member SD / RMSE of the member mean x sqrt((m+1)/m); 1 = right spread, below 1 = too narrow) and 12 x PIT variance (1; above 1 = too narrow):")
    for s in srcs:
        sub = R[R.source == s]
        ss = [np.sqrt((sub[f"{o}_sd"] ** 2).mean() / (sub[f"{o}_err"] ** 2).mean() * (m + 1) / m) for o in OUTS]
        pv = [12 * sub[f"{o}_pit"].var() for o in OUTS]
        L.append(f"  {s:18s} SS " + " ".join(f"{x:5.2f}" for x in ss) + "   PITvar " + " ".join(f"{x:5.2f}" for x in pv))
    L.append("")
    L.append("LANDING POINT (east, north jointly): energy score (m, lower better) and inside the 90 % ellipse (target 0.90)")
    for s in srcs:
        sub = R[R.source == s]
        L.append(f"  {s:18s} ES {sub.land_es.mean():7.1f}   in90 {sub.land_in90.mean():.3f}")
    L.append("")
    L.append("PAIRED source minus tool (day-block 95 % interval; below 0 = source better), CRPS in % of the tool's:")
    base = R[R.source == "tool"].set_index("case")
    for s in srcs:
        if s == "tool":
            continue
        sub = R[R.source == s].set_index("case").loc[base.index]
        parts = []
        for o in ("apogee_agl_m", "drift_m", "east_m", "north_m", "max_q_pa"):
            d = (sub[f"{o}_crps"] - base[f"{o}_crps"]).to_numpy()
            mu, lo, hi = K.block_boot(d, base.day.values, draws=2000)
            b = base[f"{o}_crps"].mean()
            parts.append(f"{o.split('_')[0]} {100 * mu / b:+5.1f} [{100 * lo / b:+5.1f},{100 * hi / b:+5.1f}]")
        d = (sub.land_es - base.land_es).to_numpy()
        mu, lo, hi = K.block_boot(d, base.day.values, draws=2000)
        parts.append(f"landing ES {100 * mu / base.land_es.mean():+5.1f} [{100 * lo / base.land_es.mean():+5.1f},{100 * hi / base.land_es.mean():+5.1f}]")
        L.append(f"  {s:18s} " + "  ".join(parts))
    L.append("")
    L.append("BY STATION: drift CRPS and drift / landing 90 % coverage")
    for st, g in R.groupby("station"):
        L.append(f"  {st}: " + "   ".join(f"{s} {g[g.source == s].drift_m_crps.mean():.1f} / {g[g.source == s].drift_m_in90.mean():.2f} / {g[g.source == s].land_in90.mean():.2f}" for s in srcs))
    L.append("Notes: the truth flight uses the balloon profile on the 44 model heights (same interpolation as the sources). The tool is balloon-corrected at these "
             "stations (not a blind test). A rocket of this class reaches about 3.5 km, so the scores reflect the 0-5 km atmosphere. "
             "The landing ellipse is Gaussian (from the member covariance). Files: flight_sim_trial/results/gram_flights_*.csv.")
    R.to_csv(os.path.join(K.OUT, "flight_scores.csv"), index=False)
    K.report("b9_flight_score", L)


if __name__ == "__main__":
    e = np.array([[0.0, 0], [2, 0], [0, 2], [2, 2]])
    assert abs(energy(e, np.array([1.0, 1])) - (np.sqrt(2) - 0.5 * (16 + 8 * np.sqrt(2)) / 16)) < 1e-12
    assert in_ellipse(np.random.default_rng(0).normal(size=(500, 2)), np.zeros(2)) == 1.0
    main()
