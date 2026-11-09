"""Flight-condition ranking: order whole atmospheres from worst to best and pick one at a percentile of THAT order.

    flight_score(atm) -> (n,) higher = worse. Default: a weighted sum of four things that hurt a rocket flight, each divided by a reference size so they
    can be added:
        mean wind speed 0-3 km          reference 5 m/s       weight 1.0   (drift)
        largest wind-vector shear 0-5 km  reference 10 m/s per km  weight 0.5   (loads, weathercocking)
        peak gust at 10 m               reference 5 m/s       weight 0.5   (rail departure)
        low air density                 (1.225 - rho_sfc) / 0.1  weight 0.25  (thinner air = less stability and more altitude)
These weights are placeholders for the user's own go/no-go limits (docs/agent/ASK_LATER.md item 3); `atmosphere(..., score_fn=...)` takes any function of the
atmosphere arrays. `pick(order, p)` : p = 0 is the worst atmosphere of the set, p = 100 the best, so p = 15 is a bad but plausible day and p = 85 a good one.
Ranking uses the whole sample, never a variable on its own, so the picked atmosphere is internally consistent.
"""
import numpy as np

from tempest_weather._core import HEIGHTS

REFERENCE = dict(wind=5.0, shear=10.0, gust=5.0, density=0.1)
WEIGHTS = dict(wind=1.0, shear=0.5, gust=0.5, density=0.25)


def components(atm, rng=None):
    rng = rng or np.random.default_rng(0)
    speed = np.hypot(atm["u"], atm["v"])
    low = HEIGHTS <= 3000
    wind = speed[:, low].mean(1)
    z5 = HEIGHTS <= 5000
    du, dv = np.diff(atm["u"][:, z5], axis=1), np.diff(atm["v"][:, z5], axis=1)
    shear = (np.hypot(du, dv) / (np.diff(HEIGHTS[z5]) / 1000.0)).max(1)
    if atm.get("gust_mu") is not None:
        u = np.clip(rng.random(len(wind)), 1e-12, 1 - 1e-12)
        gust = np.maximum(atm["gust_mu"] - atm["gust_beta"] * np.log(-np.log(u)), 0.0)
    else:
        gust = 1.3 * speed[:, 0]                      # no gust model: a plain gust factor on the 10 m wind
    return dict(wind=wind, shear=shear, gust=gust, density=1.225 - atm["rho"][:, 0])


def flight_score(atm, weights=None, reference=None, rng=None):
    w, r = {**WEIGHTS, **(weights or {})}, {**REFERENCE, **(reference or {})}
    c = components(atm, rng)
    return sum(w[k] * c[k] / r[k] for k in w)


def order_worst_to_best(score):
    """Indices of atmospheres, worst first."""
    return np.argsort(-np.asarray(score), kind="stable")


def pick(score, percentile):
    """Index of the atmosphere at `percentile` along the worst-to-best order (0 = worst, 100 = best)."""
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    order = order_worst_to_best(score)
    return int(order[int(round(percentile / 100.0 * (len(order) - 1)))])
