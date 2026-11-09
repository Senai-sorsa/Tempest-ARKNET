"""W8d: the PHYSICAL gust from ASOS one-minute data (IEM asos1min: 2-minute mean wind `sknt` and the 5-second peak `gust_sknt` of every minute; no reporting threshold).
METAR writes a gust group only for about 10 kt peak-to-lull variation and never below 14 kt, so every gust law fitted on hourly METARs (the model-wind law in the assets and the
measured-wind law of W8c) learned G = wind for most light-wind hours. Here, for each routine hourly report (time key = report rounded to the hour, as scripts/gust_check.py),
the physical gust is the highest 5-second peak in the 10 minutes up to the report minute (:53 -> 10 minutes ending :53), the mean wind is the 2-minute mean at that minute.
Output: (1) by band of the measured wind: median and p90 of the physical gust factor, share of hours with a METAR gust group, the METAR-convention factor; (2) both laws refitted on the
physical gust (Gumbel of G, location / log-scale linear in the add2 features; measured wind for the observe() law, ERA5 10 m wind for the model law), fitted 2016-2020, scored on
2021-23 (CRPS against the physical gust, 90 % coverage, median factor) against the shipped laws; coefficients printed for the runtime.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_1min.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_check import load   # noqa: E402
from gust_measured_fit import feats, fit_gumbel   # noqa: E402
from tempest.gust import model as gm   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402

KT = 0.514444


def physical_hourly(path):
    d = pd.read_csv(path, usecols=["valid(UTC)", "sknt", "gust_sknt"], na_values=["M", ""])
    d["t"] = pd.to_datetime(d["valid(UTC)"])
    d = d.dropna(subset=["t"]).set_index("t").sort_index()
    d = d[~d.index.duplicated()]
    peak = d["gust_sknt"].rolling("10min").max()                        # highest 5-second peak in the 10 minutes ending at each minute
    rep = d.index[d.index.minute == 53]                                 # routine report minute
    out = pd.DataFrame({"ws1": d.loc[rep, "sknt"].values * KT, "gphys": peak.loc[rep].values * KT}, index=(rep + pd.Timedelta(minutes=7)))
    return out.dropna()


def main():
    rows = []
    for st in ("TCS", "MAF"):
        for f in sorted(glob.glob(os.path.join(REPO, "data", "raw", "asos1min", f"{st}_*.csv"))):
            h = physical_hourly(f)
            h["station_name"] = st
            rows.append(h)
    ph = pd.concat(rows)
    ph.index.name = "time"
    print(f"one-minute data: {len(ph)} routine hours with a 2-min wind and a 10-minute peak ({', '.join(sorted({os.path.basename(f)[:3] + os.path.basename(f)[4:8] for f in glob.glob(os.path.join(REPO, 'data', 'raw', 'asos1min', '*.csv'))}))})")
    surf = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))[["u10", "v10", "fg10"]].load()
    d = load(os.path.join(REPO, "data", "raw", "asos"), surf)
    d["station_name"] = np.where(d.station == 1, "TCS", "MAF")
    m = d.merge(ph.reset_index(), on=["station_name", "time"], how="inner")
    m = m[(m.ws1 >= 2.0) & (m.gphys >= m.ws1) & (np.abs(m.ws1 - m.ws_obs) < 1.5)]      # the 2-min wind of the one-minute file and the METAR wind must be the same report
    print(f"joined with the hourly METAR rows and ERA5: {len(m)} hours (2016-2023), measured wind >= 2 m/s")
    wo, g, doy, hr, st, era = m.ws_obs.values, m.gphys.values, m.doy.values, m.hour.values, m.station.values, m.ws.values
    yr = m.year.values
    print("\n(1) by measured wind: median / p90 of the PHYSICAL gust factor | share with a METAR gust group | median / p90 of the METAR-convention factor (G = max(reported, wind))")
    for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 16), (16, 40)):
        b = (wo >= lo) & (wo < hi)
        if b.sum() < 30:
            continue
        fp, fc = g[b] / wo[b], m.G.values[b] / wo[b]
        print(f"  {lo:2d}-{hi:<2d} m/s n {int(b.sum()):6d}: {np.median(fp):.2f} / {np.quantile(fp, .9):.2f} | {m.reported.values[b].mean():.2f} | {np.median(fc):.2f} / {np.quantile(fc, .9):.2f}")
    fit, val = yr <= 2020, (yr >= 2021) & (yr <= 2023)
    Xm = feats(wo, doy, hr, st, "add2")[1]
    Xe = feats(era, doy, hr, st, "add2")[1]
    lm = fit_gumbel(Xm[fit], g[fit])
    le = fit_gumbel(Xe[fit], g[fit])
    print("\nphysical-gust law on the MEASURED wind (features 1, min(ws,20), min(ws,20)^2/10, season, UTC hour, station):\n  theta " + ", ".join(f"{x:.5f}" for x in lm[0]) + "\n  phi   " + ", ".join(f"{x:.5f}" for x in lm[1]))
    print("physical-gust law on the ERA5 (model) wind, same features:\n  theta " + ", ".join(f"{x:.5f}" for x in le[0]) + "\n  phi   " + ", ".join(f"{x:.5f}" for x in le[1]))
    z = np.load(os.path.join(REPO, "models", "gust_model.npz"))
    shipped = dict(theta=z["wind_theta"], phi=z["wind_phi"])
    rng = np.random.default_rng(0)
    U = rng.random((int(val.sum()), 199)).clip(1e-12, 1 - 1e-12)
    L = -np.log(-np.log(U))
    wv, gv = wo[val], g[val]

    def draws(mu, beta, wind):
        return np.maximum(mu[:, None] + beta[:, None] * L, wind[:, None])
    mu_m, be_m = api._gust_params_measured(wv, doy[val], hr[val], st[val])
    Xs = gm.design(era[val], doy[val], hr[val], station=st[val])
    cand = {
        "shipped measured-wind law (W8c, METAR convention), measured wind": draws(mu_m, be_m, wv),
        "physical law, measured wind (new)": draws(Xm[val] @ lm[0], np.exp(np.clip(Xm[val] @ lm[1], -6, 4)), wv),
        "shipped model-wind law, ERA5 wind": np.maximum(gm.sample(shipped, Xs, 199, rng), wv[:, None]),
        "physical law, ERA5 wind (new)": draws(Xe[val] @ le[0], np.exp(np.clip(Xe[val] @ le[1], -6, 4)), wv),
    }
    print(f"\n(2) validation 2021-23 ({int(val.sum())} hours), truth = PHYSICAL gust: CRPS / cov90 / median factor (obs) by band of the measured wind")
    for name, x in cand.items():
        txt = []
        for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 40), (2, 40)):
            b = (wv >= lo) & (wv < hi)
            if b.sum() < 30:
                continue
            c = crps_ensemble(x[b][..., None], gv[b][:, None])[:, 0].mean()
            cv = coverage90(x[b][..., None], gv[b][:, None], 0.9)[:, 0].mean()
            txt.append(f"{lo}-{hi}: {c:.2f}/{cv:.2f}/{np.median(np.median(x[b], 1) / wv[b]):.2f} ({np.median(gv[b] / wv[b]):.2f})")
        print(f"  {name:62s} " + "  ".join(txt))


if __name__ == "__main__":
    main()
