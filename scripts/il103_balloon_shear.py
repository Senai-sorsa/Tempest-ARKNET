"""L18 / IL-103 first step: how wide is REAL balloon shear compared with the ERA5 profiles the model is trained on (and, in this repo, the corrected truth)? Same station, same launch times, same layers.

    .venv/Scripts/python -W ignore scripts/il103_balloon_shear.py

Stations EPZ (72364) and MAF (72265): IGRA soundings at 00 and 12 UTC, interpolated to the model heights above ground (data/igra_heights, int16 x 0.1 m/s), against the ERA5 profile store at the nearest grid point
at the same times. Vector shear per layer between neighbouring model heights (m/s per km), quantiles by band. Years 2015-2025 (the store has the 12-04 UTC hours, so 00 and 12 UTC exist).
"""
import os

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
Q = [0.5, 0.9, 0.99, 0.999]


def shear(u, v, h):
    dz = np.diff(h) / 1000.0
    return np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / dz


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    ht = z["height"].values.astype(float)
    for sid, name in (("USM00072364", "EPZ"), ("USM00072265", "MAF")):
        d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
        sel = np.array([np.argmin(np.abs(d["heights"] - h)) for h in ht])
        ok_h = np.abs(d["heights"][sel] - ht) < 1.0
        yrs = d["time"].astype("datetime64[Y]").astype(int) + 1970
        tsel = (yrs >= 2015) & (yrs <= 2025)
        tb = d["time"][tsel].astype("datetime64[ns]")
        ub, vb = d["u"][tsel][:, sel].astype(float), d["v"][tsel][:, sel].astype(float)
        bad = (d["u"][tsel][:, sel] == -32768) | (d["v"][tsel][:, sel] == -32768)
        ub[bad] = np.nan
        vb[bad] = np.nan
        ub, vb = ub * 0.1, vb * 0.1
        i = int(np.argmin((z.lat.values - d["lat"][0]) ** 2 + (z.lon.values - d["lon"][0]) ** 2))
        common = np.intersect1d(tb, z["time"].values)
        ib = np.searchsorted(tb, common)
        ue = z["u"].isel(point=i).sel(time=common).values.astype(float)
        ve = z["v"].isel(point=i).sel(time=common).values.astype(float)
        print(f"\n{name}: {len(common)} common sounding times, nearest ERA5 point {z.lat.values[i]:.2f},{z.lon.values[i]:.2f}")
        sb, se = shear(ub[ib], vb[ib], ht), shear(ue, ve, ht)
        valid = np.isfinite(sb) & np.isfinite(se)
        mid = ht[1:]
        print(f"  {'band':9} {'n':>7}  " + "   ".join(f"p{int(q * 1000) / 10:g} bal/ERA5 (ratio)" for q in Q))
        for b, lo, hi in BANDS:
            m = (mid > lo) & (mid <= hi)
            v1 = sb[:, m][valid[:, m]]
            v2 = se[:, m][valid[:, m]]
            qb, qe = np.quantile(v1, Q), np.quantile(v2, Q)
            print(f"  {b:9} {len(v1):7d}  " + "   ".join(f"{x:5.1f}/{y:5.1f} ({x / y:4.2f})" for x, y in zip(qb, qe)))


if __name__ == "__main__":
    main()
