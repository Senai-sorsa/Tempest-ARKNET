"""L12b answered with an independent station: HRRR (Open-Meteo archive, 10 m wind) against ERA5 (10 m) as predictors of the hourly mean wind speed measured at the USCRN station Las Cruces 20 N (1.5 m, not an airport, wind not assimilated by HRRR),
2020-2023 (the station wind flag is bad in 2024-25), hours in the stored ERA5 set. Because the sensor is at 1.5 m the comparison removes the unknown height factor: each predictor is multiplied by its own best-fit single scale factor (least squares through the origin) before the error is computed,
and the correlation of hourly speeds is reported (scale-free). The same is done at TCS (ASOS, assimilated) for contrast, so the 'assimilation advantage' of HRRR can be read off.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/hrrr_vs_uscrn.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
import uscrn_compare as uc   # noqa: E402
from tempest_weather_v2 import _net   # noqa: E402


def hrrr_speed(lat, lon, years):
    out = {}
    for y in years:
        url = (f"https://historical-forecast-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&start_date={y}-01-01&end_date={y}-12-31&hourly=wind_speed_10m&models=ncep_hrrr_conus&wind_speed_unit=ms&timezone=UTC")
        h = _net.fetch_json(url, service="open-meteo", retries=2, timeout=90)["hourly"]
        for t, s in zip(h["time"], h["wind_speed_10m"]):
            if s is not None:
                out[datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)] = float(s)
    return out


def score(name, truth, preds):
    print(f"{name}: {len(truth)} hours, truth mean {truth.mean():.2f} m/s")
    for k, x in preds.items():
        s = float((x * truth).sum() / (x * x).sum())
        print(f"  {k:12} correlation {np.corrcoef(x, truth)[0, 1]:.3f}   RMSE after the best single scale (x{s:.2f}) {np.sqrt(np.mean((s * x - truth) ** 2)):.3f}   MAE {np.abs(s * x - truth).mean():.3f}")


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t_all = z["time"].values
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
    years = [2020, 2021, 2022, 2023]          # the USCRN wind flag is bad for 2024-25 (sensor problem), so the comparison uses 2020-23
    jr = {}
    for y in years:
        jr.update(uc.read_uscrn(y))
    sites = [("USCRN Las Cruces 20 N (independent, 1.5 m)", 32.61, -106.74, jr)]
    asos = gw.load_asos("TCS", years)
    sites.append(("ASOS Truth or Consequences (assimilated by HRRR, 10 m)", 33.2369, -107.2672, {h: float(np.hypot(*v)) for h, v in asos.items()}))
    for name, lat, lon, ref in sites:
        hr = hrrr_speed(lat, lon, years)
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        hs = [h for h in sorted(ref) if h in hr and tt.get(np.datetime64(h.replace(tzinfo=None), "h")) is not None and (h.hour >= 14 or h.hour <= 4)]
        ks = np.array([tt[np.datetime64(h.replace(tzinfo=None), "h")] for h in hs])
        o = np.argsort(ks)
        hs, ks = [hs[j] for j in o], ks[o]
        sl = slice(ks.min(), ks.max() + 1)
        u = z["u10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        v = z["v10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        truth = np.array([ref[h] for h in hs])
        prev = np.array([ref.get(h - timedelta(hours=1), np.nan) for h in hs])
        m = np.isfinite(prev)
        score(name, truth[m], {"HRRR 10 m": np.array([hr[h] for h in hs])[m], "ERA5 10 m": np.hypot(u, v)[m], "persistence": prev[m]})
        print()


if __name__ == "__main__":
    main()
