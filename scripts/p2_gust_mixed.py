"""P2: is the gust a measurement of the wind a few hundred metres up? In mixed (daytime) air a gust is faster air brought down from aloft, so the gust should carry information about the
300-750 m wind beyond what the 10 m sustained wind says. Midland (MAF) has the ASOS station and the IGRA balloon site at the same airport. Truth: balloon mean wind speed over the model
heights 300, 500, 750 m (data/igra_heights). Predictors at the launch hour: 10 m sustained wind (METAR) and the PHYSICAL gust (highest 5-second peak in the 10 minutes before the report,
ASOS one-minute data, scripts/gust_1min.py). 00Z = 18 h local (mixed afternoon air), 12Z = 06 h local (stable morning). Linear least squares fitted 2016-2020, tested 2021-2023:
(a) speed aloft ~ 1 + ws10, (b) ~ 1 + ws10 + (gust - ws10). MAE and R2 on the test years; the gain of (b) over (a) says whether a gust observation is worth assimilating.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p2_gust_mixed.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from gust_1min import physical_hourly   # noqa: E402
from tempest_weather import _core   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)
AL = [300.0, 500.0, 750.0]


def main():
    d = np.load(os.path.join(REPO, "data", "igra_heights", "USM00072265.npz"))
    sel = [int(np.argmin(np.abs(d["heights"] - h))) for h in AL]
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    u, v = d["u"][:, sel].astype(float), d["v"][:, sel].astype(float)
    bad = (u == -32768) | (v == -32768)
    sp = np.where(bad, np.nan, np.hypot(u * 0.1, v * 0.1)).mean(1)
    bal = pd.Series(sp, index=t).dropna()
    bal = bal[(bal.index.year >= 2016) & (bal.index.year <= 2023)]
    ph = pd.concat([physical_hourly(f) for f in sorted(glob.glob(os.path.join(REPO, "data", "raw", "asos1min", "MAF_*.csv")))])
    ph = ph[~ph.index.duplicated()]
    j = pd.DataFrame({"aloft": bal}).join(ph, how="inner").dropna()
    j = j[(j.ws1 >= 1.0) & (j.gphys >= j.ws1)]
    print(f"MAF: {len(j)} soundings with a one-minute record at the launch hour (2016-2023)")
    for hour, label in ((0, "00Z (18 h local, mixed)"), (12, "12Z (06 h local, stable)")):
        k = j[j.index.hour == hour]
        fit, test = k[k.index.year <= 2020], k[k.index.year >= 2021]
        y_f, y_t = fit.aloft.values, test.aloft.values
        out = {}
        for name, cols in (("ws10", ["ws1"]), ("ws10 + gust excess", ["ws1", "ex"])):
            for df in (fit, test):
                df.loc[:, "ex"] = df.gphys - df.ws1
            Xf = np.column_stack([np.ones(len(fit))] + [fit[c].values for c in cols])
            Xt = np.column_stack([np.ones(len(test))] + [test[c].values for c in cols])
            b = np.linalg.lstsq(Xf, y_f, rcond=None)[0]
            p = Xt @ b
            out[name] = (np.mean(np.abs(p - y_t)), 1 - np.mean((p - y_t) ** 2) / np.var(y_t), b)
        g = 100 * (1 - out["ws10 + gust excess"][0] / out["ws10"][0])
        print(f"\n{label}: fit {len(fit)}, test {len(test)} soundings; mean speed aloft {y_t.mean():.2f} m/s")
        for name, (mae, r2, b) in out.items():
            print(f"  {name:20s} MAE {mae:.3f} m/s  R2 {r2:.3f}  coefficients {np.round(b, 3)}")
        print(f"  gain of the gust: MAE {g:+.1f} %")


if __name__ == "__main__":
    main()
