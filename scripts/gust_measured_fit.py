"""W8c: gust law for a MEASURED sustained wind (what `Launch.observe(wind_10m=...)` gives). The shipped law (Gumbel of G = max(gust, wind)) is a function of the
MODEL (ERA5) wind; fed a measured wind it overstates (median factor 1.15 vs 1.00 observed, 2.4-4.8 vs 1.4 at 16+ m/s; scripts/gust_factor_refit.py part B).
Candidate = a two-part law on the OBSERVED wind ws (ASOS TCS + MAF hourly routine reports, fitted 2000-2020 on ws >= 2 m/s):
  P(a gust is reported | ws, season, UTC hour, station): logistic in [1, min(ws, 20), min(ws, 20)^2 / 10, season, hour, station];
  excess E = gust - ws when reported: Gumbel with location and log-scale linear in [1, min(ws, 15), season, hour, station], drawn values clipped at 0;
  G = ws + B E (B ~ Bernoulli(P)), so G = ws (no gust) has the observed point mass.
Scored on validation 2021-23 (the decision set) and test 2024-25 (development window, reported only) in bands of the observed wind against the truth
G = max(gust, ws): CRPS, 90 % coverage, median and p90 factor, share of samples with G = ws. Prints the 14 + 16 coefficients for the runtime.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_measured_fit.py
"""
import os
import sys

import numpy as np
import xarray as xr
from scipy.optimize import minimize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_check import load   # noqa: E402
from tempest.gust import model as gm   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402


def standardise(X):
    mu, sd = X.mean(0), X.std(0)
    mu[0], sd[0] = 0.0, 1.0
    sd = np.where(sd > 0, sd, 1.0)
    return (X - mu) / sd, mu, sd


def to_raw(p, mu, sd):
    r = p / sd
    r[0] = p[0] - (p[1:] * mu[1:] / sd[1:]).sum()
    return r


def fit_logistic(X, y, l2=1e-4):
    Z, mu, sd = standardise(X)

    def nll(b):
        s = Z @ b
        return np.mean(np.logaddexp(0, s) - y * s) + l2 * np.sum(b[1:] ** 2)

    def grad(b):
        p = 1 / (1 + np.exp(-(Z @ b)))
        g = Z.T @ (p - y) / len(y)
        g[1:] += 2 * l2 * b[1:]
        return g
    b0 = np.zeros(X.shape[1])
    b0[0] = np.log(y.mean() / (1 - y.mean()))
    return to_raw(minimize(nll, b0, jac=grad, method="BFGS").x, mu, sd)


def fit_gumbel(X, e, l2=1e-3):
    k = X.shape[1]
    Z, mu, sd = standardise(X)

    def nll(p):
        loc, beta = Z @ p[:k], np.exp(np.clip(Z @ p[k:], -6, 4))
        z = (e - loc) / beta
        return np.mean(np.log(beta) + z + np.exp(-z)) + l2 * (np.sum(p[1:k] ** 2) + np.sum(p[k + 1:] ** 2))
    s = e.std() * np.sqrt(6) / np.pi
    p0 = np.zeros(2 * k)
    p0[0], p0[k] = e.mean() - 0.5772 * s, np.log(s)
    r = minimize(nll, p0, method="BFGS")
    return to_raw(r.x[:k], mu, sd), to_raw(r.x[k:], mu, sd)


def fit_censored(X, G, ws, cens, l2=1e-3):
    """Gumbel of the TOTAL gust G (location, log-scale linear in X) with the no-gust reports left-censored at the wind (they say only G <= ws): what the
    runtime's (gust_mu, gust_beta) format holds exactly once draws are clipped at the wind."""
    k = X.shape[1]
    Z, mu, sd = standardise(X)

    def nll(p):
        loc, beta = Z @ p[:k], np.exp(np.clip(Z @ p[k:], -6, 4))
        z = np.where(cens, (ws - loc) / beta, (G - loc) / beta)
        ll = np.where(cens, -np.exp(-z), -np.log(beta) - z - np.exp(-z))
        return -np.mean(ll) + l2 * (np.sum(p[1:k] ** 2) + np.sum(p[k + 1:] ** 2))
    p0 = np.zeros(2 * k)
    p0[0], p0[k] = np.median(G), np.log(G.std() * np.sqrt(6) / np.pi)
    r = minimize(nll, p0, method="BFGS")
    return to_raw(r.x[:k], mu, sd), to_raw(r.x[k:], mu, sd)


def gumbel_equivalent(law, ws, doy, hour, station):
    """(mu, beta) of the Gumbel whose draws clipped at ws have the mixture's no-gust share and the mixture's median gust among the reported ones."""
    Xp, Xe = feats(ws, doy, hour, station, law["excess"])
    p = np.clip(1 / (1 + np.exp(-(Xp @ law["p"]))), 1e-4, 1 - 1e-4)
    loc, beta_e = Xe @ law["loc"], np.exp(np.clip(Xe @ law["lbeta"], -6, 4))
    med_e = np.maximum(loc - beta_e * np.log(-np.log(0.5)), 0.05)
    L = lambda q: -np.log(-np.log(q))
    beta = med_e / (L(1 - p / 2) - L(1 - p))
    return ws - beta * L(1 - p), beta


def feats(ws, doy, hour, station, excess="add"):
    a, h = 2 * np.pi * doy / 365.25, 2 * np.pi * hour / 24.0
    one = np.ones(len(ws))
    w20, w15 = np.minimum(ws, 20.0), np.minimum(ws, 15.0)
    common = [np.sin(a), np.cos(a), np.sin(h), np.cos(h), station.astype(float)]
    xe = [one, w20, w20 ** 2 / 10.0] if excess == "add2" else [one, w15]
    return np.stack([one, w20, w20 ** 2 / 10.0] + common, 1), np.stack(xe + common, 1)


def sample_mixture(law, ws, doy, hour, station, m, rng):
    Xp, Xe = feats(ws, doy, hour, station, law["excess"])
    p = 1 / (1 + np.exp(-(Xp @ law["p"])))
    loc, beta = Xe @ law["loc"], np.exp(np.clip(Xe @ law["lbeta"], -6, 4))
    u = rng.random((len(ws), m)).clip(1e-12, 1 - 1e-12)
    e = np.maximum(loc[:, None] - beta[:, None] * np.log(-np.log(u)), 0.0)
    if law["excess"] == "mult":              # the Gumbel is of the excess FACTOR (gust - ws) / ws
        e = e * ws[:, None]
    b = rng.random((len(ws), m)) < p[:, None]
    return ws[:, None] + b * e, p


def main():
    surf = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))[["u10", "v10", "fg10"]].load()
    d = load(os.path.join(REPO, "data", "raw", "asos"), surf)
    wo, doy, hr, st = d.ws_obs.values, d.doy.values, d.hour.values, d.station.values
    ok = wo >= 2.0
    fit_m = (d.year.values <= 2020) & ok
    rep = d.reported.values & (d.gust_obs.values > wo)
    em = fit_m & rep
    print(f"fit rows {int(fit_m.sum())}, with a gust {int(em.sum())} ({rep[fit_m].mean():.2f})")
    laws = {}
    for excess in ("add", "add2", "mult"):
        Xp, Xe = feats(wo, doy, hr, st, excess)
        law = {"excess": excess, "p": fit_logistic(Xp[fit_m], rep[fit_m].astype(float))}
        ex = (d.gust_obs.values - wo)[em]
        law["loc"], law["lbeta"] = fit_gumbel(Xe[em], ex / wo[em] if excess == "mult" else ex)
        laws[excess] = law
        print(f"excess form {excess}:")
        for k_, v_ in law.items():
            if k_ != "excess":
                print(f"  {k_:6s} " + ", ".join(f"{x:.5f}" for x in v_))
    Xc = feats(wo, doy, hr, st, "add2")[1]
    cens_law = fit_censored(Xc[fit_m], d.G.values[fit_m], wo[fit_m], ~rep[fit_m])
    print("censored Gumbel of G (features 1, min(ws,20), min(ws,20)^2/10, season, hour, station):")
    print("  theta  " + ", ".join(f"{x:.5f}" for x in cens_law[0]))
    print("  phi    " + ", ".join(f"{x:.5f}" for x in cens_law[1]))

    def gumbel_draw(mu, beta, ws, m, rng):
        u = rng.random((len(ws), m)).clip(1e-12, 1 - 1e-12)
        return np.maximum(mu[:, None] - beta[:, None] * np.log(-np.log(u)), ws[:, None]), 1 - np.exp(-np.exp(-(ws - mu) / beta))

    def cens_sampler(ws, doy_, hr_, st_, m, rng):
        X = feats(ws, doy_, hr_, st_, "add2")[1]
        return gumbel_draw(X @ cens_law[0], np.exp(np.clip(X @ cens_law[1], -6, 4)), ws, m, rng)

    def eq_sampler(ws, doy_, hr_, st_, m, rng):
        mu, beta = gumbel_equivalent(laws["add2"], ws, doy_, hr_, st_)
        return gumbel_draw(mu, beta, ws, m, rng)
    samplers = {k_: (lambda law_: (lambda ws, a, b, c, m, rng: sample_mixture(law_, ws, a, b, c, m, rng)))(v_) for k_, v_ in laws.items()}
    samplers["censored Gumbel"] = cens_sampler
    samplers["add2 as Gumbel"] = eq_sampler
    shipped = gm.load("models/gust_model.npz") if hasattr(gm, "load") else None
    if shipped is None:
        z = np.load(os.path.join(REPO, "models", "gust_model.npz"))
        shipped = dict(theta=z["wind_theta"], phi=z["wind_phi"])
    rng = np.random.default_rng(0)
    for split, mask in (("validation 2021-23 (decision set)", (d.year >= 2021) & (d.year <= 2023)), ("test 2024-25 (development window)", (d.year >= 2024) & (d.year <= 2025))):
        m0 = mask.values & ok
        y, ws = d.G.values[m0], wo[m0]
        sl = gm.sample(shipped, gm.design(ws, doy[m0], hr[m0], station=st[m0]), 199, rng)
        sl_c = np.maximum(sl, ws[:, None])                                   # the shipped law clipped at the wind (G >= ws by definition)
        for excess, sampler in samplers.items():
            sm, p = sampler(ws, doy[m0], hr[m0], st[m0], 199, rng)
            print(f"\n{split}, candidate {excess}: input = OBSERVED sustained wind ({int(m0.sum())} reports with ws >= 2 m/s)")
            print("  band      n   CRPS shipped / shipped clipped / mixture | cov90 shipped / mixture | median factor obs / shipped / mixture | p90 obs / shipped / mixture | P(no gust) obs / mixture")
            for name, m in [("all", np.ones(len(y), bool))] + [(f"{lo}-{hi}", (ws >= lo) & (ws < hi)) for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 16), (16, 40))]:
                if m.sum() < 30:
                    continue
                c = [crps_ensemble(s_[m][..., None], y[m][:, None])[:, 0].mean() for s_ in (sl, sl_c, sm)]
                v = [coverage90(s_[m][..., None], y[m][:, None], 0.9)[:, 0].mean() for s_ in (sl, sm)]
                fo = y[m] / ws[m]
                med = [np.median(np.median(s_[m], 1) / ws[m]) for s_ in (sl, sm)]
                q = [np.quantile(s_[m] / ws[m][:, None], 0.9, axis=1).mean() for s_ in (sl, sm)]
                print(f"  {name:6s} {int(m.sum()):6d}   {c[0]:7.3f} / {c[1]:7.3f} / {c[2]:7.3f} |  {v[0]:.2f} / {v[1]:.2f} |  {np.median(fo):.2f} / {med[0]:.2f} / {med[1]:.2f} | "
                      f"{np.quantile(fo, .9):.2f} / {q[0]:.2f} / {q[1]:.2f} | {(y[m] <= ws[m]).mean():.2f} / {1 - p[m].mean():.2f}")


if __name__ == "__main__":
    main()
