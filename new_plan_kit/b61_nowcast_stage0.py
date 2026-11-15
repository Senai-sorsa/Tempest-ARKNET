"""Nowcast trial stage 0 (user request 2026-11-14: use what happened in the last hours to predict the next hours, without retraining the main model).
Measurement only, NO rule: how much skill is there at 1 / 2 / 3 / 6 h ahead in the 10 m wind at a station, from that station's own recent reports?
Stations: the 9 ASOS sites of tempest_weather_v2.obs.STATIONS (data/raw/asos, hourly via scripts/ground_wind_bench.load_asos). Fit years 2015-2022,
measured on 2023 ONLY (dev year); 2024-25 stay untouched for the stage-1 verdict. Never 2026.
Arms (Gaussian predictive for u and v separately; anomalies against the station's month x UTC-hour climatology of the fit years, in units of its sd):
  clim     climatology mean and sd (what the tool knows with no observation, at the station itself: a best case for the tool's prior)
  observe  the tool's current one-reading update (tempest_weather_v2 obs.persistence_gain, own station): mean + g sd z0, sd sqrt(1 - g), g = exp(-h / 6.3)
  ar6      ridge on the last 6 hourly anomalies (u and v, lags 0-5 h), pooled over stations, separate day / night (obs.night_weight of the report hour)
Score: mean Gaussian CRPS (m/s) over cases with all 6 past hours and the target hour present; skill vs clim.
Caveat: the ASOS wind is reported in whole knots, calm as 0, so it is not Gaussian; the same for every arm.
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore new_plan_kit/b61_nowcast_stage0.py
Result: docs/results/logs/kit_b61_nowcast_stage0.log
"""
import math
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.stats import norm

import kit_common as K

NAME = "b61_nowcast_stage0"
FIT, DEV = range(2015, 2023), (2023,)
LEADS, LAGS = (1, 2, 3, 6), 6
T0 = datetime(2015, 1, 1, tzinfo=timezone.utc)


def crps_gauss(mu, sd, y):
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi))


def ridge(X, Y, lam=1.0):
    A = X.T @ X + lam * np.eye(X.shape[1])
    A[-1, -1] -= lam                                   # no penalty on the intercept (last column)
    return np.linalg.solve(A, X.T @ Y)


def station_series(st, lon, years=None):
    import ground_wind_bench as gw
    years = list(years or (list(FIT) + list(DEV)))
    obs = gw.load_asos(st, years)
    n = int((datetime(years[-1] + 1, 1, 1, tzinfo=timezone.utc) - T0).total_seconds() // 3600)
    uv = np.full((n, 2), np.nan)
    for t, r in obs.items():
        i = int((t - T0).total_seconds() // 3600)
        if 0 <= i < n:
            uv[i] = r[:2]
    times = [T0 + timedelta(hours=i) for i in range(n)]
    year = np.array([t.year for t in times])
    mon = np.array([t.month for t in times]) - 1
    hr = np.array([t.hour for t in times])
    fit = np.isin(year, list(FIT))
    mu, sd = np.full((12, 24, 2), np.nan), np.full((12, 24, 2), np.nan)
    for m in range(12):
        for h in range(24):
            k = fit & (mon == m) & (hr == h) & np.isfinite(uv[:, 0])
            mu[m, h], sd[m, h] = uv[k].mean(0), np.maximum(uv[k].std(0), 0.3)
    M, S = mu[mon, hr], sd[mon, hr]
    night = np.array([__import__("tempest_weather_v2.obs", fromlist=["x"]).night_weight(h + lon / 15.0) for h in hr]) > 0.5
    return uv, (uv - M) / S, M, S, year, night


def cases(z, year, lead, years):
    n = len(z)
    i0 = np.arange(LAGS - 1, n - lead)
    lags = np.stack([z[i0 - k] for k in range(LAGS)], 1)       # (cases, lag, 2)
    ok = np.isfinite(lags).all((1, 2)) & np.isfinite(z[i0 + lead]).all(1) & np.isin(year[i0], list(years))
    return i0[ok], lags[ok].reshape(ok.sum(), -1)


def main():
    from tempest_weather_v2.obs import STATIONS, persistence_gain
    S = {st: station_series(st, lon) for st, (lat, lon, el) in STATIONS.items()}
    lines = [f"Nowcast stage 0 (measurement, no rule): 10 m wind at the station from its own last reports; fit {FIT[0]}-{FIT[-1]}, measured on {DEV[0]} only; "
             f"{len(S)} ASOS stations; mean Gaussian CRPS of u and v (m/s), skill vs climatology"]
    for lead in LEADS:
        W = {}
        for nt in (False, True):
            Xs, Ys = [], []
            for st, (uv, z, M, Sd, year, night) in S.items():
                i0, X = cases(z, year, lead, FIT)
                k = night[i0] == nt
                Xs.append(np.column_stack([X[k], np.ones(k.sum())])), Ys.append(z[i0[k] + lead])
            X, Y = np.vstack(Xs), np.vstack(Ys)
            B = ridge(X, Y)
            W[nt] = (B, (Y - X @ B).std(0))
        g = persistence_gain(lead)
        tot = {"clim": [], "observe": [], "ar6": []}
        per = []
        for st, (uv, z, M, Sd, year, night) in S.items():
            i0, X = cases(z, year, lead, DEV)
            if len(i0) < 500:
                continue
            j = i0 + lead
            y, mu, sd = uv[j], M[j], Sd[j]
            c = {"clim": crps_gauss(mu, sd, y), "observe": crps_gauss(mu + g * sd * z[i0], sd * math.sqrt(1 - g), y)}
            Xa = np.column_stack([X, np.ones(len(i0))])
            pa, ps = np.empty_like(y), np.empty_like(y)
            for nt in (False, True):
                k = night[i0] == nt
                B, r = W[nt]
                pa[k], ps[k] = Xa[k] @ B, r
            c["ar6"] = crps_gauss(mu + sd * pa, sd * ps, y)
            for a in tot:
                tot[a].append(c[a])
            per.append(f"{st} {c['clim'].mean():.3f}/{c['observe'].mean():.3f}/{c['ar6'].mean():.3f}")
        m = {a: np.concatenate(v).mean() for a, v in tot.items()}
        n = sum(len(v) for v in tot["clim"])
        lines.append(f"  +{lead} h ({n} cases x u,v): clim {m['clim']:.3f}, observe {m['observe']:.3f} (skill {1 - m['observe'] / m['clim']:+.1%}), "
                     f"ar6 {m['ar6']:.3f} (skill {1 - m['ar6'] / m['clim']:+.1%}; vs observe {1 - m['ar6'] / m['observe']:+.1%})")
        lines.append("      per station clim/observe/ar6: " + ", ".join(per))
    lines.append("Stage 0 is a measurement (no rule). Stage 1 (rule pre-set before it runs) is judged on 2024-25.")
    K.report(NAME, lines)


def _selfcheck():
    assert abs(crps_gauss(0.0, 1.0, 0.0) - (2 * norm.pdf(0) - 1 / math.sqrt(math.pi))) < 1e-12
    rng = np.random.default_rng(0)
    x = rng.standard_normal((5000, 3))
    y = x @ np.array([[0.5], [-0.2], [0.0]]) + 0.3 + 0.1 * rng.standard_normal((5000, 1))
    B = ridge(np.column_stack([x, np.ones(5000)]), y)
    assert np.allclose(B[:, 0], [0.5, -0.2, 0.0, 0.3], atol=0.01)
    z = np.arange(20, dtype=float)[:, None].repeat(2, 1)
    i0, X = cases(z, np.full(20, 2023), 2, (2023,))
    assert i0[0] == LAGS - 1 and X[0, 0] == LAGS - 1 and X[0, 2] == LAGS - 2


_selfcheck()
if __name__ == "__main__":
    main()
