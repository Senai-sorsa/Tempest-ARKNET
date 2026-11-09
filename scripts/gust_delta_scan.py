"""W8c part 3: the effective reporting threshold. gust_phys_fit.py censored the no-gust reports at U = max(ws + 5.14, 7.2) m/s (10 kt over the mean), but 84 % of
reported gusts are less than 5.14 m/s over the mean (the rule is peak-to-LULL, 10 kt): the threshold over the mean is lower. Scan delta in U = max(ws + delta, 7.2):
fit the censored Gumbel of the physical gust on 2000-2020 and keep the delta whose model share of gust groups (1 - F(U)) matches the observed share in every
wind band of the FIT years; then report validation 2021-23: share, CRPS on the reported gusts, and the implied median physical gust factor by band.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_delta_scan.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_check import load   # noqa: E402
from gust_measured_fit import feats   # noqa: E402
from gust_phys_fit import FLOOR, fit_censored_at   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402

BANDS = ((2, 5), (5, 8), (8, 12), (12, 16), (16, 40))


def main():
    surf = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))[["u10", "v10", "fg10"]].load()
    d = load(os.path.join(REPO, "data", "raw", "asos"), surf)
    wo, doy, hr, st = d.ws_obs.values, d.doy.values, d.hour.values, d.station.values
    ok = wo >= 2.0
    rep = d.reported.values & (d.gust_obs.values > wo)
    gust = d.gust_obs.values
    ex = (gust - wo)[rep & ok & (d.year.values <= 2020)]
    print("reported gust minus wind (m/s), fit years, quantiles 1/5/10/25/50 %:", np.round(np.quantile(ex, [.01, .05, .1, .25, .5]), 2))
    Xe = feats(wo, doy, hr, st, "add2")[1]
    fit_m = (d.year.values <= 2020) & ok
    val_m = (d.year.values >= 2021) & (d.year.values <= 2023) & ok
    rng = np.random.default_rng(0)
    print("delta | fit-years share of gust groups obs:model by band " + " ".join(f"{lo}-{hi}" for lo, hi in BANDS) + " | max abs error | validation CRPS reported / median factor by band")
    best = None
    for delta in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        U = np.maximum(wo + delta, FLOOR)
        th, ph = fit_censored_at(Xe[fit_m], np.where(rep, gust, U)[fit_m], U[fit_m], ~rep[fit_m])
        mu, be = Xe @ th, np.exp(np.clip(Xe @ ph, -6, 4))
        share = 1 - np.exp(-np.exp(-(U - mu) / be))
        txt, err = [], []
        for lo, hi in BANDS:
            b = fit_m & (wo >= lo) & (wo < hi)
            txt.append(f"{rep[b].mean():.2f}:{share[b].mean():.2f}")
            err.append(abs(rep[b].mean() - share[b].mean()))
        vt = []
        for lo, hi in BANDS:
            b = np.flatnonzero(val_m & (wo >= lo) & (wo < hi))
            u = rng.random((len(b), 199)).clip(1e-12, 1 - 1e-12)
            s = np.maximum(mu[b][:, None] - be[b][:, None] * np.log(-np.log(u)), wo[b][:, None])
            r = rep[b]
            c = crps_ensemble(s[r][..., None], gust[b][r][:, None])[:, 0].mean() if r.sum() >= 10 else np.nan
            vt.append(f"{c:.2f}/{np.median(np.median(s, 1) / wo[b]):.2f}")
        print(f"{delta:4.1f}  | " + " ".join(txt) + f" | {max(err):.3f} | " + " ".join(vt))
        if best is None or max(err) < best[0]:
            best = (max(err), delta, th, ph)
    print(f"\nchosen delta {best[1]} (smallest worst-band share error {best[0]:.3f})")
    print("  theta " + ", ".join(f"{x:.5f}" for x in best[2]))
    print("  phi   " + ", ".join(f"{x:.5f}" for x in best[3]))


if __name__ == "__main__":
    main()
