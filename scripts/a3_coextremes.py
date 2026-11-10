"""Gemini A-3 against the truth: are co-extremes (10 m wind AND the 10 m - 1 km vector shear both above their 95th percentile) as frequent in the tool's pools as in reality?
Truth: the ERA5 profile store (data/pilot/profiles80.zarr) at the nearest point, every day of 1991-2023 in the same month at the same UTC hour (a climate sample, the same question the
climate pool answers). Pools: the generator pool (api.atmosphere_set, its joint order comes from the Schaake shuffle) and the observation engine's Gaussian-copula pool (free, no
observations), n = 4000 each. Statistic: P(both above q95) / 0.05 (1 = always together, 0.05 = independent); bootstrap interval for the truth.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/a3_coextremes.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight import TempestFlightSimEngine   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)
J1 = list(H).index(1000.0)
CASES = [(3, 20, 32.94, -106.91), (7, 20, 32.94, -106.91), (12, 19, 31.94, -102.19), (4, 22, 31.94, -102.19)]


def coext(u, v, q=0.95):
    w = np.hypot(u[:, 0], v[:, 0])
    sh = np.hypot(u[:, J1] - u[:, 0], v[:, J1] - v[:, 0])
    return float(((w > np.quantile(w, q)) & (sh > np.quantile(sh, q))).mean() / (1 - q))


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles80.zarr"))
    rng = np.random.default_rng(0)
    print("month hour place          truth (ERA5, 95 % interval)       generator pool   engine Gaussian-copula pool")
    for mo, hh, lat, lon in CASES:
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        t = z.time.to_index()
        sel = (t.month == mo) & (t.hour == hh) & (t.year >= 1991) & (t.year <= 2023)
        b = z.isel(point=i, time=np.flatnonzero(sel))
        u, v = b["u"].values.astype(float), b["v"].values.astype(float)
        tr = coext(u, v)
        bs = [coext(u[k], v[k]) for k in (rng.integers(0, len(u), len(u)) for _ in range(300))]
        when = f"2025-{mo:02d}-15T{hh:02d}:00:00+00:00"
        atm, _ = api.atmosphere_set(lat, lon, when, n=4000, seed=mo)
        eng = TempestFlightSimEngine(lat, lon, when, n_pool=1024, seed=mo)
        e = eng.sample_sobol(np.random.default_rng(mo).random((4000, 12)))
        print(f"  {mo:2d}   {hh:2d}  {lat:.2f},{lon:.2f}   {tr:.2f} [{np.percentile(bs, 2.5):.2f}, {np.percentile(bs, 97.5):.2f}] (n {len(u)})       {coext(atm['u'], atm['v']):.2f}             {coext(e['u'], e['v']):.2f}")


if __name__ == "__main__":
    main()
