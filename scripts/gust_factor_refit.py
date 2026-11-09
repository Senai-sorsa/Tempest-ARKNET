"""W8b: refit the gust law as a gust FACTOR. Baseline = the shipped law (Gumbel of G = max(gust, wind), location linear in wind, wind^2/10, season, hour, station; models fitted 2000-2020). Candidate = Gumbel of f = G / max(ws, 1.5) whose
location and log-scale are linear in min(ws, 15), season, hour and station (no wind^2 term), fitted 2000-2020 on the same rows; G = max(ws, 1.5) f. Input wind = ERA5 10 m wind (as in gust_check.py). Scored on validation 2021-23 and test 2024-25 in
bands of the ERA5 wind: CRPS, 90 % coverage, median gust factor, p90 gust factor against the observed ones.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_factor_refit.py"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_check import load   # noqa: E402
from tempest.gust import model as gm   # noqa: E402


def fit_factor(X, f, l2=1e-3):
    """Gumbel fit of a gust factor by maximum likelihood on the MEAN negative log-likelihood with standardised slopes (gm.fit stopped at the intercept-only start on this scale: first runs were degenerate)."""
    from scipy.optimize import minimize
    k = X.shape[1]
    mu_x, sd_x = X.mean(0), X.std(0)
    sd_x[0], mu_x[0] = 1.0, 0.0
    Z = (X - mu_x) / np.where(sd_x > 0, sd_x, 1.0)

    def nll(p):
        mu, beta = Z @ p[:k], np.exp(np.clip(Z @ p[k:], -6, 4))
        z = (f - mu) / beta
        return np.mean(np.log(beta) + z + np.exp(-z)) + l2 * (np.sum(p[1:k] ** 2) + np.sum(p[k + 1:] ** 2))
    sd = f.std() * np.sqrt(6) / np.pi
    p0 = np.zeros(2 * k)
    p0[0], p0[k] = f.mean() - 0.5772 * sd, np.log(sd)
    r = minimize(nll, p0, method="BFGS")
    th, ph = r.x[:k], r.x[k:]
    scale = np.where(sd_x > 0, sd_x, 1.0)
    # back to raw-feature coefficients
    th_raw, ph_raw = th / scale, ph / scale
    th_raw[0], ph_raw[0] = th[0] - (th[1:] * mu_x[1:] / scale[1:]).sum(), ph[0] - (ph[1:] * mu_x[1:] / scale[1:]).sum()
    return dict(theta=th_raw, phi=ph_raw)

from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402

surf = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))[["u10", "v10", "fg10"]].load()
d = load(os.path.join(REPO, "data", "raw", "asos"), surf)
fit_m = d.year <= 2020
w = np.maximum(d.ws.values, 1.5)
f = (d.G.values / w)
a_, h_ = 2 * np.pi * d.doy.values / 365.25, 2 * np.pi * d.hour.values / 24.0
Xf = np.stack([np.ones(len(d)), np.minimum(d.ws.values, 15.0), np.sin(a_), np.cos(a_), np.sin(h_), np.cos(h_), d.station.values.astype(float)], 1)
Xb = gm.design(d.ws, d.doy, d.hour, station=d.station)
base = gm.fit(Xb[fit_m], d.G[fit_m].values)
cand = fit_factor(Xf[fit_m], f[fit_m])
print("fit rows", int(fit_m.sum()), " candidate theta", np.round(cand["theta"], 3), " phi", np.round(cand["phi"], 3))
rng = np.random.default_rng(0)
bands = [(0, 4), (4, 8), (8, 12), (12, 16), (16, 40)]
for split, mask in (("validation 2021-23", (d.year >= 2021) & (d.year <= 2023)), ("test 2024-25", (d.year >= 2024) & (d.year <= 2025))):
    y = d.G.values[mask]
    ws = d.ws.values[mask]
    sb = gm.sample(base, Xb[mask], 199, rng)
    sc = gm.sample(cand, Xf[mask], 199, rng) * w[mask][:, None]
    print(f"\n{split} ({int(mask.sum())} reports); wind = ERA5 10 m wind")
    print("  band      n      CRPS base  CRPS cand | cov90 base cand | median factor obs / base / cand | p90 factor obs / base / cand")
    rows = [("all", np.ones(len(y), bool))] + [(f"{lo}-{hi}", (ws >= lo) & (ws < hi)) for lo, hi in bands]
    for name, m in rows:
        if m.sum() < 30:
            continue
        cb = crps_ensemble(sb[m][..., None], y[m][:, None])[:, 0].mean()
        cc = crps_ensemble(sc[m][..., None], y[m][:, None])[:, 0].mean()
        vb, vc = coverage90(sb[m][..., None], y[m][:, None], 0.9)[:, 0].mean(), coverage90(sc[m][..., None], y[m][:, None], 0.9)[:, 0].mean()
        fo, fb, fc = y[m] / np.maximum(ws[m], 1.5), np.median(sb[m], 1) / np.maximum(ws[m], 1.5), np.median(sc[m], 1) / np.maximum(ws[m], 1.5)
        q = lambda s_: np.quantile(s_ / np.maximum(ws[m][:, None], 1.5), 0.9, axis=1).mean()
        print(f"  {name:7s} {int(m.sum()):7d}   {cb:8.3f}  {cc:8.3f} |  {vb:.2f}  {vc:.2f} |  {np.median(fo):.2f} / {np.median(fb):.2f} / {np.median(fc):.2f} | {np.quantile(fo, .9):.2f} / {q(sb[m]):.2f} / {q(sc[m]):.2f}")


# ---- (B) the same factor law with the OBSERVED sustained wind as input (what a pad anemometer / observe() gives); fitted 2000-2020 on reports with sustained wind >= 2 m/s
wo = d.ws_obs.values
ok = wo >= 2.0
fo_ = d.G.values / wo
Xo = np.stack([np.ones(len(d)), np.minimum(wo, 15.0), np.sin(a_), np.cos(a_), np.sin(h_), np.cos(h_), d.station.values.astype(float)], 1)
obsm = fit_factor(Xo[fit_m & ok], fo_[fit_m & ok])
print("\nobserved-wind factor law: theta", np.round(obsm["theta"], 3), "phi", np.round(obsm["phi"], 3))
for split, mask in (("validation 2021-23", (d.year >= 2021) & (d.year <= 2023)), ("test 2024-25", (d.year >= 2024) & (d.year <= 2025))):
    m0 = mask & ok
    y = d.G.values[m0]
    ws = wo[m0]
    sf = gm.sample(obsm, Xo[m0], 199, rng) * ws[:, None]
    sl = gm.sample(base, gm.design(ws, d.doy.values[m0], d.hour.values[m0], station=d.station.values[m0]), 199, rng)       # the shipped law fed the OBSERVED wind
    print(f"\n{split}: input = OBSERVED sustained wind ({int(m0.sum())} reports with wind >= 2 m/s)")
    print("  band      n      CRPS shipped law | factor law | cov90 shipped factor | median factor obs / shipped / factor | p90 obs / shipped / factor")
    for name, m in [("all", np.ones(len(y), bool))] + [(f"{lo}-{hi}", (ws >= lo) & (ws < hi)) for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 16), (16, 40))]:
        if m.sum() < 30:
            continue
        cl = crps_ensemble(sl[m][..., None], y[m][:, None])[:, 0].mean()
        cf = crps_ensemble(sf[m][..., None], y[m][:, None])[:, 0].mean()
        vl, vf = coverage90(sl[m][..., None], y[m][:, None], 0.9)[:, 0].mean(), coverage90(sf[m][..., None], y[m][:, None], 0.9)[:, 0].mean()
        fo, fl, ff = y[m] / ws[m], np.median(sl[m], 1) / ws[m], np.median(sf[m], 1) / ws[m]
        q = lambda s_: np.quantile(s_ / ws[m][:, None], 0.9, axis=1).mean()
        print(f"  {name:7s} {int(m.sum()):7d}   {cl:8.3f}  {cf:8.3f} |  {vl:.2f}  {vf:.2f} |  {np.median(fo):.2f} / {np.median(fl):.2f} / {np.median(ff):.2f} | {np.quantile(fo, .9):.2f} / {q(sl[m]):.2f} / {q(sf[m]):.2f}")
