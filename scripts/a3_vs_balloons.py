"""A-3, final check against the REAL truth: co-extremes of the 10 m wind and the 10 m - 1 km vector shear (both above their q95; statistic P / 0.05) in balloons (Santa Teresa EPZ,
Midland MAF, 00Z, 1991-2023, data/igra_heights) against the tool's pools at the same place, month and hour (generator pool and the observation engine's Gaussian-copula pool, n = 4000),
with a bootstrap interval for the balloons. (ERA5 at the balloon times overstates the co-extremes in most months, so it is not used as the truth.)
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/a3_vs_balloons.py
"""
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from a3_coextremes import coext   # noqa: E402
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight import TempestFlightSimEngine   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)


def main():
    rng = np.random.default_rng(0)
    print("station month  balloons (95 % interval)    generator pool   engine pool")
    for sid, lat, lon, el in (("USM00072364", 31.8728, -106.6981, 1252.0), ("USM00072265", 31.9475, -102.1894, 874.0)):
        d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
        sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
        t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
        for mo in (3, 4, 7, 12):
            k = np.flatnonzero((t.month == mo) & (t.hour == 0) & (t.year >= 1991) & (t.year <= 2023))
            u, v = d["u"][k][:, sel].astype(float), d["v"][k][:, sel].astype(float)
            ok = ~((u == -32768) | (v == -32768)).any(1)
            u, v = u[ok] * 0.1, v[ok] * 0.1
            b = coext(u, v)
            bs = [coext(u[j], v[j]) for j in (rng.integers(0, len(u), len(u)) for _ in range(300))]
            when = f"2025-{mo:02d}-15T00:00:00+00:00"
            atm, _ = api.atmosphere_set(lat, lon, when, n=4000, seed=mo, elevation=el)
            e = TempestFlightSimEngine(lat, lon, when, n_pool=1024, seed=mo, elevation=el).sample_sobol(np.random.default_rng(mo).random((4000, 12)))
            print(f"  {sid[-5:]}  {mo:2d}     {b:.2f} [{np.percentile(bs, 2.5):.2f}, {np.percentile(bs, 97.5):.2f}] (n {len(u)})      {coext(atm['u'], atm['v']):.2f}             {coext(e['u'], e['v']):.2f}")


if __name__ == "__main__":
    main()
