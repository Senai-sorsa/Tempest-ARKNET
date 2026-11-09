"""Ground-wind data check: is the error at 10 m in the DATA (ERA5 itself, the balloon correction, the station truth) or in the tool? For TCS and MAF, every valid hour of 2024-25: raw ERA5 10 m wind (profile store, nearest grid point) against the ASOS report of that hour:
mean error of u and v (MAE, m/s), speed bias, correlation of speed, share of hours ASOS is calm; and the same for the ASOS report of the hour BEFORE (persistence) as a yardstick. Compare with the earlier numbers: past-mode median MAE 1.61, HRRR MAE 1.04, tool climate median error.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_data_check.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t_all = z["time"].values
    rows = []
    for st, (lat, lon, el) in gw.STATIONS.items():
        asos = gw.load_asos(st, [2024, 2025])
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        u10 = z["u10"].isel(point=i).values.astype(float)
        v10 = z["v10"].isel(point=i).values.astype(float)
        up = z["u"].isel(point=i, height=0).values.astype(float)
        vp = z["v"].isel(point=i, height=0).values.astype(float)
        idx = {np.datetime64(t.replace(tzinfo=None), "h"): k for k, t in enumerate(sorted(asos))}
        keys = sorted(asos)
        tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
        A, E, P, B = [], [], [], []
        for h in keys:
            if not gw.valid_hour(st, h):
                continue
            k = tt.get(np.datetime64(h.replace(tzinfo=None), "h"))
            hp = h.replace(hour=h.hour) - gw.timedelta(hours=1)
            if k is None or hp not in asos:
                continue
            A.append(asos[h])
            E.append((u10[k], v10[k]))
            P.append((up[k], vp[k]))
            B.append(asos[hp])
        A, E, P, B = (np.array(x) for x in (A, E, P, B))
        sp = lambda x: np.hypot(x[:, 0], x[:, 1])
        mae = lambda x: np.abs(x - A).mean(0)
        print(f"\n{st}: {len(A)} hours 2024-25, ASOS mean speed {sp(A).mean():.2f} m/s, calm reports {(sp(A) < 0.3).mean():.3f}")
        for name, x in (("ERA5 10 m field (u10, v10)", E), ("ERA5 profile store at 10 m", P), ("ASOS 1 h earlier (persistence)", B)):
            print(f"  {name:32} MAE u {mae(x)[0]:.2f} v {mae(x)[1]:.2f} (mean {mae(x).mean():.2f}); speed bias {sp(x).mean() - sp(A).mean():+.2f} m/s; speed correlation {np.corrcoef(sp(x), sp(A))[0, 1]:.2f}; vector corr u {np.corrcoef(x[:, 0], A[:, 0])[0, 1]:.2f} v {np.corrcoef(x[:, 1], A[:, 1])[0, 1]:.2f}")
        rows.append((st, mae(E).mean(), mae(P).mean(), mae(B).mean()))
    print("\nreference: tool past-mode median MAE 1.61, HRRR near-analysis MAE 1.04 (earlier runs, 240 cases)")


if __name__ == "__main__":
    main()
