"""Nowcast trial stage 2 = NOW2 (follow-up of the stage-1 MISS, b62: pooled ar6n +5.4 / +5.3 / +5.0 / +4.5 % vs observe at +1 / 2 / 3 / 6 h on 2024-25,
cov90 ~0.905, but MAF -5.0 % at +1 h; reading: one pooled fit does not suit the windiest site).
Change: the same ar6n features (own anomalies lags 0-5 h + the 3 nearest stations' anomalies lags 0-2 h, as b62.features) fitted PER STATION
(ridge, separate day / night), nothing else changed. No main-model retraining.
Years: 2024-25 have been looked at, so the test moves to 2015-2017 (never a test year before) and everything is fitted on 2018-2025
(climatology month x UTC-hour and ridge weights). Never 2026. No arm choice: the per-station arm is fixed before the run.
Referee: the tool's observe() one-reading update (as b61 / b62), scored on the same cases. The pooled ar6n refitted on 2018-25 is printed for context only.
Rule (set 2026-11-14 before any stage-2 run, the stage-1 rule unchanged; commit time = the time of record):
  PASS: on 2015-17 the per-station arm beats observe on pooled mean CRPS by >= 2 % at each of +1, +2 and +3 h; no station worse than observe by more
        than 2 % at any lead; pooled cov90 within 0.87-0.93 at every lead.
  KILL: not better than observe (pooled) at any lead.
  Otherwise MISS. Adoption (an opt-in observe history option) would need the user in any case (ASK_LATER).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b63_nowcast_stage2.py
Result: docs/results/logs/kit_b63_nowcast_stage2.log
"""
import math

import numpy as np

import kit_common as K
from b61_nowcast_stage0 import LEADS, crps_gauss, ridge, station_series
from b62_nowcast_stage1 import NB, Z90, features, judge

NAME = "b63_nowcast_stage2"
FIT2, TEST2 = tuple(range(2018, 2026)), (2015, 2016, 2017)


def fit_one(S, nbrs, st, lead):
    """Per-station ridge, day / night -> {night: (B, residual sd)}."""
    i0, X = features(S, nbrs, st, lead, FIT2, True)
    W = {}
    for nt in (False, True):
        k = S[st][5][i0] == nt
        Xa, Y = np.column_stack([X[k], np.ones(k.sum())]), S[st][1][i0[k] + lead]
        B = ridge(Xa, Y)
        W[nt] = (B, (Y - Xa @ B).std(0))
    return W


def fit_pooled(S, nbrs, lead):
    W = {}
    for nt in (False, True):
        Xs, Ys = [], []
        for st in S:
            i0, X = features(S, nbrs, st, lead, FIT2, True)
            k = S[st][5][i0] == nt
            Xs.append(np.column_stack([X[k], np.ones(k.sum())])), Ys.append(S[st][1][i0[k] + lead])
        X, Y = np.vstack(Xs), np.vstack(Ys)
        B = ridge(X, Y)
        W[nt] = (B, (Y - X @ B).std(0))
    return W


def score(S, nbrs, st, lead, W):
    """-> (crps observe, crps arm, inside90 arm) on the TEST2 cases of station st, or None if < 500 cases."""
    from tempest_weather_v2.obs import persistence_gain
    g = persistence_gain(lead)
    uv, z, M, Sd, year, night = S[st]
    i0, X = features(S, nbrs, st, lead, TEST2, True)
    if len(i0) < 500:
        return None
    j = i0 + lead
    y, mu, sd = uv[j], M[j], Sd[j]
    Xa = np.column_stack([X, np.ones(len(i0))])
    pa, ps = np.empty_like(y), np.empty_like(y)
    for nt in (False, True):
        k = night[i0] == nt
        pa[k], ps[k] = Xa[k] @ W[nt][0], W[nt][1]
    m, s = mu + sd * pa, sd * ps
    return crps_gauss(mu + g * sd * z[i0], sd * math.sqrt(1 - g), y), crps_gauss(m, s, y), np.abs(y - m) <= Z90 * s


def main():
    from tempest_weather_v2.obs import STATIONS, haversine_km
    years = list(range(2015, 2026))
    S = {st: station_series(st, lon, years, fit_years=FIT2) for st, (lat, lon, el) in STATIONS.items()}
    nbrs = {st: sorted((o for o in STATIONS if o != st), key=lambda o: haversine_km(*STATIONS[st][:2], *STATIONS[o][:2]))[:NB] for st in STATIONS}
    lines = [f"NOW2 nowcast stage 2: ar6n fitted per station (ridge, day / night), fit + climatology {FIT2[0]}-{FIT2[-1]}, judged on {TEST2[0]}-{TEST2[-1]}; "
             "referee = the tool's observe(); pooled ar6n (same years) for context only"]
    gain, cov, worst = {}, {}, 1.0
    for lead in LEADS:
        Wp = fit_pooled(S, nbrs, lead)
        e = {st: r for st in S if (r := score(S, nbrs, st, lead, fit_one(S, nbrs, st, lead))) is not None}
        ep = {st: score(S, nbrs, st, lead, Wp) for st in e}
        o = np.concatenate([v[0].ravel() for v in e.values()]).mean()
        a = np.concatenate([v[1].ravel() for v in e.values()]).mean()
        p = np.concatenate([v[1].ravel() for v in ep.values()]).mean()
        gain[lead] = 1 - a / o
        cov[lead] = float(np.concatenate([v[2].ravel() for v in e.values()]).mean())
        ps = {st: 1 - v[1].mean() / v[0].mean() for st, v in e.items()}
        pp = {st: 1 - v[1].mean() / v[0].mean() for st, v in ep.items()}
        worst = min(worst, min(ps.values()))
        lines.append(f"  {TEST2[0]}-{TEST2[-1] % 100} +{lead} h ({sum(len(v[0]) for v in e.values())} cases, {len(e)} stations): observe {o:.3f}, "
                     f"per-station {a:.3f} ({gain[lead]:+.1%}), pooled {p:.3f} ({1 - p / o:+.1%}), cov90 {cov[lead]:.3f}")
        lines.append("      per station (per-station / pooled vs observe): " + ", ".join(f"{st} {ps[st]:+.1%}/{pp[st]:+.1%}" for st in e))
    lines.append("Rule (pre-set): PASS = >= +2 % vs observe at +1 / 2 / 3 h, no station below -2 % at any lead, cov90 0.87-0.93; KILL = not better at any lead; else MISS.")
    lines.append("NOW2 verdict: " + judge(gain, worst, cov))
    K.report(NAME, lines)


def _selfcheck():
    assert set(FIT2).isdisjoint(TEST2) and 2026 not in FIT2
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4000, 2))
    B = ridge(np.column_stack([x, np.ones(4000)]), x @ np.array([[0.4], [0.1]]) + 0.2)
    assert np.allclose(B[:, 0], [0.4, 0.1, 0.2], atol=0.01)


_selfcheck()
if __name__ == "__main__":
    main()
