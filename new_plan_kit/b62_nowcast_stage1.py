"""Nowcast trial stage 1 (user request 2026-11-14; stage 0 = b61, 2023 only: the tool's one-reading observe() already gives +37 / +27 / +21 / +11 %
CRPS skill over climatology at +1 / 2 / 3 / 6 h; the station's own last 6 hours (ar6) add only +4.0 / +3.1 / +2.7 / +2.1 % over observe).
Question: do the recent reports of NEIGHBOURING stations add to the station's own history, enough to be worth an opt-in add-on? No main-model retraining.
Arms (as b61: Gaussian u / v, month x UTC-hour anomalies, ridge pooled over the 9 ASOS stations, separate day / night, fit 2015-2022):
  observe  the tool's current one-reading update (referee)
  ar6      own station, lags 0-5 h
  ar6n     ar6 + the 3 nearest other stations' anomalies at lags 0-2 h, ordered by distance (cases need all of them present)
The arm proposed is the better of ar6 / ar6n on 2023 mean CRPS over the four leads (dev year, already seen in b61); it is judged ONLY on 2024-2025 (never seen).
cov90 = fraction of truth values inside the Gaussian 5-95 % range, u and v pooled.
Rule (set 2026-11-14 22:50, before any stage-1 run, unchanged after):
  PASS: on 2024-25 the proposed arm beats observe on pooled mean CRPS by >= 2 % at each of +1, +2 and +3 h; no station worse than observe by more than 2 %
        at any lead; pooled cov90 within 0.87-0.93 at every lead.
  KILL: the proposed arm is not better than observe (pooled) at any lead.
  Otherwise MISS. Adoption (an opt-in Launch.observe history option) would need the user in any case (ASK_LATER).
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b62_nowcast_stage1.py
Result: docs/results/logs/kit_b62_nowcast_stage1.log
"""
import math

import numpy as np
from scipy.stats import norm

import kit_common as K
from b61_nowcast_stage0 import FIT, LAGS, LEADS, crps_gauss, ridge, station_series

NAME = "b62_nowcast_stage1"
DEV, TEST = (2023,), (2024, 2025)
NB, NB_LAGS = 3, 3
Z90 = norm.ppf(0.95)


def judge(gain, worst_station, cov):
    """gain: {lead: 1 - crps_arm / crps_observe} pooled; worst_station: min over stations and leads of the same; cov: {lead: pooled cov90}."""
    if all(gain[h] <= 0 for h in gain):
        return "KILL (not better than observe at any lead)"
    ok = all(gain[h] >= 0.02 for h in (1, 2, 3)) and worst_station >= -0.02 and all(0.87 <= c <= 0.93 for c in cov.values())
    txt = ", ".join(f"+{h} h {gain[h]:+.1%}" for h in gain) + f"; worst station {worst_station:+.1%}; cov90 " + ", ".join(f"{c:.3f}" for c in cov.values())
    return ("PASS (" if ok else "MISS (needs >= +2 % at 1-3 h, no station below -2 %, cov90 0.87-0.93: ") + txt + ")"


def features(S, nbrs, st, lead, years, with_nb):
    uv, z, M, Sd, year, night = S[st]
    n = len(z)
    i0 = np.arange(LAGS - 1, n - lead)
    cols = [z[i0 - k] for k in range(LAGS)]
    if with_nb:
        cols += [S[o][1][i0 - k] for o in nbrs[st] for k in range(NB_LAGS)]
    X = np.stack(cols, 1)
    ok = np.isfinite(X).all((1, 2)) & np.isfinite(z[i0 + lead]).all(1) & np.isin(year[i0], list(years))
    return i0[ok], X[ok].reshape(ok.sum(), -1)


def fit(S, nbrs, lead, with_nb):
    W = {}
    for nt in (False, True):
        Xs, Ys = [], []
        for st in S:
            i0, X = features(S, nbrs, st, lead, FIT, with_nb)
            k = S[st][5][i0] == nt
            Xs.append(np.column_stack([X[k], np.ones(k.sum())])), Ys.append(S[st][1][i0[k] + lead])
        X, Y = np.vstack(Xs), np.vstack(Ys)
        B = ridge(X, Y)
        W[nt] = (B, (Y - X @ B).std(0))
    return W


def evaluate(S, nbrs, lead, years, W, with_nb):
    """-> {station: (crps observe, crps arm, inside90 arm)} on the cases the arm can use (observe scored on the same cases)."""
    from tempest_weather_v2.obs import persistence_gain
    g, out = persistence_gain(lead), {}
    for st in S:
        uv, z, M, Sd, year, night = S[st]
        i0, X = features(S, nbrs, st, lead, years, with_nb)
        if len(i0) < 500:
            continue
        j = i0 + lead
        y, mu, sd = uv[j], M[j], Sd[j]
        Xa = np.column_stack([X, np.ones(len(i0))])
        pa, ps = np.empty_like(y), np.empty_like(y)
        for nt in (False, True):
            k = night[i0] == nt
            pa[k], ps[k] = Xa[k] @ W[nt][0], W[nt][1]
        m, s = mu + sd * pa, sd * ps
        out[st] = (crps_gauss(mu + g * sd * z[i0], sd * math.sqrt(1 - g), y), crps_gauss(m, s, y), np.abs(y - m) <= Z90 * s)
    return out


def main():
    from tempest_weather_v2.obs import STATIONS, haversine_km
    years = list(FIT) + list(DEV) + list(TEST)
    S = {st: station_series(st, lon, years) for st, (lat, lon, el) in STATIONS.items()}
    nbrs = {st: sorted((o for o in STATIONS if o != st), key=lambda o: haversine_km(*STATIONS[st][:2], *STATIONS[o][:2]))[:NB] for st in STATIONS}
    lines = [f"Nowcast stage 1: own history (ar6) vs + {NB} nearest stations' last {NB_LAGS} h (ar6n), referee = the tool's observe(); fit {FIT[0]}-{FIT[-1]}, "
             f"arm chosen on {DEV[0]}, judged on {TEST[0]}-{TEST[-1]}",
             "  neighbours: " + ", ".join(f"{st}: {'/'.join(v)}" for st, v in nbrs.items())]
    W = {(lead, nb): fit(S, nbrs, lead, nb) for lead in LEADS for nb in (False, True)}
    dev = {}
    for nb in (False, True):
        r = [evaluate(S, nbrs, lead, DEV, W[(lead, nb)], nb) for lead in LEADS]
        dev[nb] = np.mean([np.concatenate([v[1].ravel() for v in e.values()]).mean() for e in r])
        lines.append(f"  2023 (dev) {'ar6n' if nb else 'ar6 '} mean CRPS over leads {dev[nb]:.4f}")
    nb = bool(dev[True] < dev[False])
    arm = "ar6n" if nb else "ar6"
    lines.append(f"  proposed arm: {arm}")
    gain, cov, worst = {}, {}, 1.0
    for lead in LEADS:
        e = evaluate(S, nbrs, lead, TEST, W[(lead, nb)], nb)
        o = np.concatenate([v[0].ravel() for v in e.values()]).mean()
        a = np.concatenate([v[1].ravel() for v in e.values()]).mean()
        gain[lead] = 1 - a / o
        cov[lead] = float(np.concatenate([v[2].ravel() for v in e.values()]).mean())
        ps = {st: 1 - v[1].mean() / v[0].mean() for st, v in e.items()}
        worst = min(worst, min(ps.values()))
        lines.append(f"  2024-25 +{lead} h ({sum(len(v[0]) for v in e.values())} cases): observe {o:.3f}, {arm} {a:.3f} ({gain[lead]:+.1%}), cov90 {cov[lead]:.3f}; "
                     "per station " + ", ".join(f"{st} {g:+.1%}" for st, g in ps.items()))
    lines.append("Rule (pre-set): PASS = >= +2 % vs observe at +1 / 2 / 3 h, no station below -2 % at any lead, cov90 0.87-0.93; KILL = not better at any lead; else MISS.")
    lines.append("Nowcast stage 1 verdict: " + judge(gain, worst, cov))
    K.report(NAME, lines)


def _selfcheck():
    c = {1: 0.9, 2: 0.9, 3: 0.9, 6: 0.9}
    assert judge({1: 0.03, 2: 0.025, 3: 0.02, 6: 0.0}, -0.01, c).startswith("PASS")
    assert judge({1: 0.03, 2: 0.025, 3: 0.019, 6: 0.0}, -0.01, c).startswith("MISS")
    assert judge({1: 0.03, 2: 0.025, 3: 0.02, 6: 0.0}, -0.03, c).startswith("MISS")
    assert judge({1: 0.03, 2: 0.025, 3: 0.02, 6: 0.0}, -0.01, {**c, 6: 0.94}).startswith("MISS")
    assert judge({1: 0.0, 2: -0.01, 3: -0.02, 6: -0.03}, -0.05, c).startswith("KILL")


_selfcheck()
if __name__ == "__main__":
    main()
