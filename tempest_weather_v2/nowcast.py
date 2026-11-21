"""NOW2 nowcast (opt-in; new_plan_kit/b63): the next 1-6 hours of 10 m wind at one of the 9 ASOS stations in obs.STATIONS from that station's own last 6 hourly reports plus the
3 nearest stations' last 3. Per-station ridge (day / night apart) on month x UTC-hour anomalies. Judged on 2015-17: +8.3 / +8.5 / +8.2 / +7.0 % CRPS vs observe() at +1 / 2 / 3 / 6 h, all 9
stations better, cov90 0.908. Weights: data/nowcast.npz, rebuilt by scripts/build_nowcast_asset.py. Leads other than 1, 2, 3, 6 are refused (no interpolation measured).

    predict("TCS", t_utc, history, lead=3)      # history = {station: [(u, v), ...] hourly, newest last, ending at t_utc}; -> dict(u=(mean, sd), v=(mean, sd), gain, z_equiv)
"""
import functools
import math
import os
from datetime import timedelta

import numpy as np

LEADS = (1, 2, 3, 6)
OWN_LAGS, NB_LAGS = 6, 3


@functools.lru_cache(maxsize=1)
def _asset():
    p = os.path.join(os.path.dirname(__file__), "data", "nowcast.npz")
    if not os.path.exists(p):
        raise FileNotFoundError(f"{p} missing: run scripts/build_nowcast_asset.py")
    return dict(np.load(p))


def _clim(A, st, t):
    return A[f"{st}_mu"][t.month - 1, t.hour], A[f"{st}_sd"][t.month - 1, t.hour]


def predict(station, t_utc, history, lead):
    """Predictive mean and sd (m/s) of the station's u and v at t_utc + lead hours. `history[s]` = hourly (u, v) rows, newest last, the last row valid at t_utc; the station needs 6 rows,
    each of its 3 nearest stations (A['<st>_nbrs']) 3. Also returns the equivalent soft-observation gain and normalised anomaly (see Launch.observe_nowcast)."""
    from tempest_weather_v2 import obs as O
    A = _asset()
    if lead not in LEADS:
        raise ValueError(f"lead must be one of {LEADS} hours, got {lead!r}")
    if station not in set(A["stations"]):
        raise ValueError(f"{station!r} is not one of the nowcast stations {sorted(A['stations'])}")

    def z(st, k):
        row = np.asarray(history[st][-1 - k], float)
        if row.shape != (2,) or not np.isfinite(row).all():
            raise ValueError(f"{st}: the report {k} h before t_utc must be a finite (u, v)")
        mu, sd = _clim(A, st, t_utc - timedelta(hours=k))
        return (row - mu) / sd
    need = {station: OWN_LAGS, **{o: NB_LAGS for o in A[f"{station}_nbrs"]}}
    for st, n in need.items():
        if st not in history or len(history[st]) < n:
            raise ValueError(f"history needs {n} hourly (u, v) rows for {st}")
    x = np.concatenate([z(station, k) for k in range(OWN_LAGS)] + [z(o, k) for o in A[f"{station}_nbrs"] for k in range(NB_LAGS)] + [[1.0]])
    night = int(O.night_weight(t_utc.hour + O.STATIONS[station][1] / 15.0) > 0.5)
    pa, ps = x @ A[f"{station}_B_{lead}_{night}"], A[f"{station}_S_{lead}_{night}"]
    mu, sd = _clim(A, station, t_utc + timedelta(hours=lead))
    ps = np.minimum(ps, 1.0)
    g = float(np.clip(1.0 - float(np.mean(ps)) ** 2, 0.02, 1.0))        # observe() form: mean + g sd z, sd sqrt(1 - g)
    return {"u": (float(mu[0] + sd[0] * pa[0]), float(sd[0] * ps[0])), "v": (float(mu[1] + sd[1] * pa[1]), float(sd[1] * ps[1])), "gain": g,
            "anomaly": (float(pa[0]), float(pa[1])), "clim": (float(mu[0]), float(mu[1])), "clim_sd": (float(sd[0]), float(sd[1]))}


def _selfcheck():
    A = _asset()
    assert len(A["stations"]) == 9 and tuple(int(v) for v in A["leads"]) == LEADS and all(A[f"{s}_B_3_0"].shape == (31, 2) for s in A["stations"][:1])
