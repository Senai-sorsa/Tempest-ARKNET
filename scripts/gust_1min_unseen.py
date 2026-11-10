"""W8d check on an UNSEEN station: the physical measured-wind gust law (api._gust_params_measured, fitted on ASOS one-minute data of TCS and MAF 2016-2020) scored at El Paso (ELP,
never used in the fit), 2021-2023, from its own one-minute file: the 2-minute mean wind at the routine report minute and the highest 5-second peak in the 10 minutes before it.
The law's station flag is 1 for the TCS side and 0 for MAF; ELP is scored with both and the better one reported. Compared with the old METAR-convention law (GUST_PHYSICAL = False)
and with a constant gust factor 1.4 (the strongest simple baseline). CRPS, 90 % coverage, median factor by wind band.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gust_1min_unseen.py
"""
import glob
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_1min import physical_hourly   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402


def main():
    import pandas as pd
    files = [f for f in sorted(glob.glob(os.path.join(REPO, "data", "raw", "asos1min", "ELP_*.csv"))) if os.path.getsize(f) > 1000 and 2021 <= int(f[-8:-4]) <= 2023]
    h = pd.concat([physical_hourly(f) for f in files])
    h = h[(h.ws1 >= 2.0) & (h.gphys >= h.ws1)]
    t = pd.DatetimeIndex(h.index)
    ws, g = h.ws1.values, h.gphys.values
    doy, hr = t.dayofyear.values, (t.hour + t.minute / 60).values
    print(f"ELP 2021-23: {len(h)} routine hours with wind >= 2 m/s (station never used in the fit)")
    rng = np.random.default_rng(0)
    L = -np.log(-np.log(rng.random((len(ws), 199)).clip(1e-12, 1 - 1e-12)))
    cands = {}
    for flag in (0.0, 1.0):
        mu, be = np.empty(len(ws)), np.empty(len(ws))
        for d in np.unique(doy):
            for hh in np.unique(np.round(hr[doy == d])):
                m = (doy == d) & (np.round(hr) == hh)
                mu[m], be[m] = api._gust_params_measured(ws[m], int(d), float(hh), flag)
        cands[f"physical law, station flag {flag:.0f}"] = np.maximum(mu[:, None] + be[:, None] * L, ws[:, None])
    old = api.GUST_PHYSICAL
    api.GUST_PHYSICAL = False
    try:
        mu, be = np.empty(len(ws)), np.empty(len(ws))
        for d in np.unique(doy):
            for hh in np.unique(np.round(hr[doy == d])):
                m = (doy == d) & (np.round(hr) == hh)
                mu[m], be[m] = api._gust_params_measured(ws[m], int(d), float(hh), 1.0)
        cands["METAR-convention law (old)"] = np.maximum(mu[:, None] + be[:, None] * L, ws[:, None])
    finally:
        api.GUST_PHYSICAL = old
    cands["constant factor 1.4"] = np.repeat((1.4 * ws)[:, None], 199, 1)
    print("candidate                               CRPS by band 2-5 / 5-8 / 8-12 / 12+ / all     cov90 all   median factor all (obs)")
    for name, x in cands.items():
        txt = []
        for lo, hi in ((2, 5), (5, 8), (8, 12), (12, 40), (2, 40)):
            b = (ws >= lo) & (ws < hi)
            txt.append(f"{crps_ensemble(x[b][..., None], g[b][:, None])[:, 0].mean():.2f}" if b.sum() >= 30 else "  - ")
        cv = coverage90(x[..., None], g[:, None], 0.9)[:, 0].mean()
        print(f"  {name:38s} {' / '.join(txt)}     {cv:.2f}        {np.median(np.median(x, 1) / ws):.2f} ({np.median(g / ws):.2f})")


if __name__ == "__main__":
    main()
