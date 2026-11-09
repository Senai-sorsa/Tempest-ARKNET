"""W8c part 2: the PHYSICAL gust after a measured wind. A METAR gust group is only written when peaks and lulls differ by about 10 kt (5.14 m/s) or more within
10 minutes, and never below 14 kt (7.2 m/s) (FMH-1 ch. 5; NWS ASOS). So "no gust reported" means G < U = max(ws + 5.14, 7.2), not G = ws. Reading it as
G = ws (the truth G = max(gust, ws) used by scripts/gust_check.py, gust_factor_refit.py and gust_measured_fit.py) teaches a law the reporting rule,
not the gust a rocket meets (and makes the OpenRocket turbulence estimate (gust - wind) / 3 zero at moderate winds).
Candidates, all in the runtime's (gust_mu, gust_beta) Gumbel format with draws clipped at the wind, fitted 2000-2020 on ASOS TCS + MAF reports with ws >= 2 m/s:
  "shipped law"       the law fitted on the ERA5 wind, fed the measured wind (what observe() does today);
  "add2 as Gumbel"    gust_measured_fit.py's mixture converted to a Gumbel (truth = METAR convention);
  "censored at ws"    Gumbel of G with no-gust reports censored at the wind (truth = METAR convention);
  "reporting-aware"   Gumbel of G with no-gust reports censored at U (physical gust).
Score (validation 2021-23 decides; test 2024-25 = development window): mean log-likelihood of what was REPORTED (log f(gust) for a gust group,
log F(U) for none; proper for censored data), the share of reports with a gust group (model 1 - F(U) vs observed) by band, CRPS on the reported gusts,
and the implied median physical gust factor.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_phys_fit.py
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
from gust_measured_fit import feats, fit_gumbel, fit_logistic, gumbel_equivalent, standardise, to_raw   # noqa: E402
from tempest.gust import model as gm   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402

KT10, FLOOR = 10 * 0.514444, 14 * 0.514444


def fit_censored_at(X, G, c, cens, l2=1e-3):
    k = X.shape[1]
    Z, mu, sd = standardise(X)

    def nll(p):
        loc, beta = Z @ p[:k], np.exp(np.clip(Z @ p[k:], -6, 4))
        z = np.where(cens, (c - loc) / beta, (G - loc) / beta)
        ll = np.where(cens, -np.exp(-z), -np.log(beta) - z - np.exp(-z))
        return -np.mean(ll) + l2 * (np.sum(p[1:k] ** 2) + np.sum(p[k + 1:] ** 2))
    p0 = np.zeros(2 * k)
    p0[0], p0[k] = np.median(G), np.log(G.std() * np.sqrt(6) / np.pi)
    r = minimize(nll, p0, method="BFGS")
    return to_raw(r.x[:k], mu, sd), to_raw(r.x[k:], mu, sd)


def loglik(mu, beta, gust, U, rep):
    """per-report log-likelihood of what was reported, draws clipped at the wind (the clipped mass is a no-gust report)."""
    zg, zu = (gust - mu) / beta, (U - mu) / beta
    return np.where(rep, -np.log(beta) - zg - np.exp(-zg), -np.exp(-zu))


def main():
    surf = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))[["u10", "v10", "fg10"]].load()
    d = load(os.path.join(REPO, "data", "raw", "asos"), surf)
    wo, doy, hr, st = d.ws_obs.values, d.doy.values, d.hour.values, d.station.values
    ok = wo >= 2.0
    rep = d.reported.values & (d.gust_obs.values > wo)
    gust = np.where(rep, d.gust_obs.values, np.nan)
    U = np.maximum(wo + KT10, FLOOR)
    fit_m = (d.year.values <= 2020) & ok
    print(f"fit rows {int(fit_m.sum())}; reported gusts {int((fit_m & rep).sum())}; reported gust minus wind: median {np.nanmedian((gust - wo)[fit_m & rep]):.2f} m/s, "
          f"share below 5.14 m/s {np.mean((gust - wo)[fit_m & rep] < KT10):.2f}, share of reported gusts below 7.2 m/s {np.mean(gust[fit_m & rep] < FLOOR):.3f}")
    Xp, Xe = feats(wo, doy, hr, st, "add2")
    mix = {"excess": "add2", "p": fit_logistic(Xp[fit_m], rep[fit_m].astype(float))}
    mix["loc"], mix["lbeta"] = fit_gumbel(Xe[fit_m & rep], (gust - wo)[fit_m & rep])
    G_conv = np.fmax(np.nan_to_num(gust, nan=0.0), wo)
    cw = fit_censored_at(Xe[fit_m], G_conv[fit_m], wo[fit_m], ~rep[fit_m])
    cu = fit_censored_at(Xe[fit_m], np.where(rep, gust, U)[fit_m], U[fit_m], ~rep[fit_m])
    for name, (th, ph) in (("censored at ws", cw), ("reporting-aware", cu)):
        print(f"{name}: theta " + ", ".join(f"{x:.5f}" for x in th) + " | phi " + ", ".join(f"{x:.5f}" for x in ph))
    z = np.load(os.path.join(REPO, "models", "gust_model.npz"))
    shipped = dict(theta=z["wind_theta"], phi=z["wind_phi"])

    def params(name, m):
        if name == "shipped law":
            X = gm.design(wo[m], doy[m], hr[m], station=st[m])
            return X @ shipped["theta"], np.exp(np.clip(X @ shipped["phi"], -5, 5))
        if name == "add2 as Gumbel":
            return gumbel_equivalent(mix, wo[m], doy[m], hr[m], st[m])
        th, ph = cw if name == "censored at ws" else cu
        return Xe[m] @ th, np.exp(np.clip(Xe[m] @ ph, -6, 4))
    names_ = ("shipped law", "add2 as Gumbel", "censored at ws", "reporting-aware")
    rng = np.random.default_rng(0)
    for split, mask in (("validation 2021-23 (decision set)", (d.year.values >= 2021) & (d.year.values <= 2023)), ("test 2024-25 (development window)", (d.year.values >= 2024) & (d.year.values <= 2025))):
        m0 = mask & ok
        print(f"\n{split}: {int(m0.sum())} reports with ws >= 2 m/s")
        print("  band     n    | mean log-likelihood of the report: " + " / ".join(names_) + "\n                 | share with a gust group obs: model " + " / ".join(names_)
              + "\n                 | CRPS on reported gusts | median physical gust factor")
        ws_ = wo[m0]
        P = {nm: params(nm, m0) for nm in names_}
        for band, bm in [("all", np.ones(len(ws_), bool))] + [(f"{lo}-{hi}", (ws_ >= lo) & (ws_ < hi)) for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 16), (16, 40))]:
            if bm.sum() < 30:
                continue
            idx = np.flatnonzero(m0)[bm]
            r_, g_, u_, w_ = rep[idx], gust[idx], U[idx], wo[idx]
            ll = [np.mean(loglik(P[nm][0][bm], P[nm][1][bm], g_, u_, r_)) for nm in names_]
            sh = [np.mean(1 - np.exp(-np.exp(-(u_ - P[nm][0][bm]) / P[nm][1][bm]))) for nm in names_]
            crps, fac = [], []
            for nm in names_:
                mu, be = P[nm][0][bm], P[nm][1][bm]
                u = rng.random((len(mu), 199)).clip(1e-12, 1 - 1e-12)
                s = np.maximum(mu[:, None] - be[:, None] * np.log(-np.log(u)), w_[:, None])
                crps.append(crps_ensemble(s[r_][..., None], g_[r_][:, None])[:, 0].mean() if r_.sum() >= 10 else np.nan)
                fac.append(np.median(np.median(s, 1) / w_))
            print(f"  {band:6s} {int(bm.sum()):6d} | " + " / ".join(f"{x:7.3f}" for x in ll) + f"\n                 | {r_.mean():.3f}: " + " / ".join(f"{x:.3f}" for x in sh)
                  + "\n                 | " + " / ".join(f"{x:.3f}" for x in crps) + " | " + " / ".join(f"{x:.2f}" for x in fac))


if __name__ == "__main__":
    main()
