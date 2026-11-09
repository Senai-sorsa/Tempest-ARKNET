"""M6 test: measure-correlate-predict (wind-energy practice) with a short on-site campaign. The 'site' is the USCRN station Las Cruces 20 N (1.5 m speed, a basin site like the pad), the long-term reference is ERA5 10 m at the nearest point.
A campaign of 1 / 2 / 3 / 6 months starting in each calendar month of 2021 or 2022 calibrates: (a) one scale factor (ratio of means), (b) least-squares scale through the origin, (c) hour-of-day scale factors (24), (d) Weibull-quantile mapping of the reference speed onto the campaign's speed distribution.
Each is applied to the REST of the same year (outside the campaign months) and scored against the station: mean absolute error (m/s), bias, and the error of the 90th-percentile speed. Reported: mean over the 12 campaign start months, and the best / worst start month.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/mcp_test.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import uscrn_compare as uc   # noqa: E402


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t_all = z["time"].values
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
    i = int(np.argmin((z.lat.values - 32.61) ** 2 + (z.lon.values + 106.74) ** 2))
    for year in (2021, 2022):
        jr = uc.read_uscrn(year)
        hs = [h for h in sorted(jr) if tt.get(np.datetime64(h.replace(tzinfo=None), "h")) is not None]
        ks = np.array([tt[np.datetime64(h.replace(tzinfo=None), "h")] for h in hs])
        sl = slice(ks.min(), ks.max() + 1)
        u = z["u10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        v = z["v10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        ref, site = np.hypot(u, v), np.array([jr[h] for h in hs])
        mon = np.array([h.month for h in hs])
        hr = np.array([h.hour for h in hs])
        for length in (1, 2, 3, 6):
            rows = {k: [] for k in ("no correction (ERA5 10 m)", "(a) ratio of means", "(b) least-squares scale", "(c) hour-of-day scales", "(d) quantile (Weibull-type) mapping")}
            for start in range(1, 13):
                camp = np.isin(mon, [((start - 1 + j) % 12) + 1 for j in range(length)])
                test = ~camp
                if camp.sum() < 300 or test.sum() < 1000:
                    continue
                r, s = ref[camp], site[camp]
                preds = {"no correction (ERA5 10 m)": ref[test], "(a) ratio of means": ref[test] * s.mean() / r.mean(), "(b) least-squares scale": ref[test] * (r * s).sum() / (r * r).sum()}
                f = np.array([s[hr[camp] == h].mean() / r[hr[camp] == h].mean() if (hr[camp] == h).sum() > 20 else s.mean() / r.mean() for h in range(24)])
                preds["(c) hour-of-day scales"] = ref[test] * f[hr[test]]
                q = np.linspace(0.01, 0.99, 99)
                preds["(d) quantile (Weibull-type) mapping"] = np.interp(ref[test], np.quantile(r, q), np.quantile(s, q))
                for k, p in preds.items():
                    rows[k].append((np.abs(p - site[test]).mean(), (p - site[test]).mean(), np.percentile(p, 90) - np.percentile(site[test], 90)))
            print(f"\n{year}, campaign length {length} month(s), mean over the start months (MAE m/s | bias | p90 error), worst start month MAE:")
            for k, v in rows.items():
                a = np.array(v)
                print(f"  {k:40} MAE {a[:, 0].mean():.3f} | bias {a[:, 1].mean():+.3f} | p90 error {a[:, 2].mean():+.3f} | worst MAE {a[:, 0].max():.3f} (best {a[:, 0].min():.3f})")


if __name__ == "__main__":
    main()
