"""GW-E (1): does the 2 km NREL WTK wind (WRF, no station assimilation) beat ERA5 at the airports and say anything about the pad? For TCS and MAF in every WTK year on disk: hourly WTK 10 m wind (speed + direction -> u, v) against the ASOS report of the hour:
MAE of u, v, speed bias, correlation; the same for ERA5 10 m (profile store) over the same hours (WTK years 2010-2012 are inside the ERA5 store 1990-2025).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/wtk_vs_asos.py
"""
import glob
import os
import sys
from datetime import datetime, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(z["time"].values)}
    for st in ("TCS", "MAF"):
        files = sorted(glob.glob(os.path.join(REPO, "data", "raw", "wtk", f"{st}_*.npz")))
        if not files:
            continue
        lat, lon, el = gw.STATIONS[st]
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        A, W, E = [], [], []
        for f in files:
            y = int(f[-8:-4])
            d = np.load(f)
            asos = gw.load_asos(st, [y])
            times = [datetime.strptime(str(t)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) for t in d["time"]]
            sp, dr = d["windspeed_10m"], d["winddirection_10m"]
            for k, h in enumerate(times):
                if h not in asos or not gw.valid_hour(st, h):
                    continue
                kk = tt.get(np.datetime64(h.replace(tzinfo=None), "h"))
                if kk is None:
                    continue
                A.append(asos[h])
                W.append((-sp[k] * np.sin(np.radians(dr[k])), -sp[k] * np.cos(np.radians(dr[k]))))
                E.append((kk,))
        ks = np.array([e[0] for e in E])
        o = np.argsort(ks)
        A, W, ks = np.array(A)[o], np.array(W)[o], ks[o]
        sl = slice(ks.min(), ks.max() + 1)
        u = z["u10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        v = z["v10"].isel(point=i, time=sl).values.astype(float)[ks - ks.min()]
        Er = np.stack([u, v], 1)
        sp_ = lambda x: np.hypot(x[:, 0], x[:, 1])
        print(f"\n{st}: {len(A)} hours in {', '.join(os.path.basename(f)[4:8] for f in files)}; ASOS mean speed {sp_(A).mean():.2f} m/s")
        for name, x in (("WTK 2 km 10 m", W), ("ERA5 10 m", Er)):
            print(f"  {name:14} MAE {np.abs(x - A).mean():.3f}  speed bias {sp_(x).mean() - sp_(A).mean():+.2f}  speed corr {np.corrcoef(sp_(x), sp_(A))[0, 1]:.3f}  vector corr u {np.corrcoef(x[:, 0], A[:, 0])[0, 1]:.2f} v {np.corrcoef(x[:, 1], A[:, 1])[0, 1]:.2f}")


if __name__ == "__main__":
    main()
