"""IL-163: is the balloon shear ratio to ERA5 stable over the years, or does the sonde/processing change (about 2022-23) inflate it? EPZ and MAF, same layers and times as il103_balloon_shear.py, by year group.

    .venv/Scripts/python -W ignore scripts/il163_balloon_era.py
"""
import os

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUPS = [("2005-09", 2005, 2009), ("2010-14", 2010, 2014), ("2015-19", 2015, 2019), ("2020-22", 2020, 2022), ("2023-25", 2023, 2025)]
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000)]


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    ht = z["height"].values.astype(float)
    mid = ht[1:]
    dz = np.diff(ht) / 1000.0
    for sid, name in (("USM00072364", "EPZ"), ("USM00072265", "MAF")):
        d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
        sel = np.array([np.argmin(np.abs(d["heights"] - h)) for h in ht])
        yrs = d["time"].astype("datetime64[Y]").astype(int) + 1970
        i = int(np.argmin((z.lat.values - d["lat"][0]) ** 2 + (z.lon.values - d["lon"][0]) ** 2))
        print(f"\n{name}: ratio of balloon to ERA5 vector shear (p50 / p99), same times")
        print(f"  {'years':8} " + "  ".join(f"{b:>16}" for b, _, _ in BANDS) + "   n soundings")
        for g, y0, y1 in GROUPS:
            tsel = (yrs >= y0) & (yrs <= y1)
            tb = d["time"][tsel].astype("datetime64[ns]")
            common = np.intersect1d(tb, z["time"].values)
            if len(common) < 100:
                continue
            ib = np.searchsorted(tb, common)
            uraw, vraw = d["u"][tsel][:, sel][ib], d["v"][tsel][:, sel][ib]
            bad = (uraw == -32768) | (vraw == -32768)
            ub, vb = np.where(bad, np.nan, uraw * 0.1), np.where(bad, np.nan, vraw * 0.1)
            ue = z["u"].isel(point=i).sel(time=common).values.astype(float)
            ve = z["v"].isel(point=i).sel(time=common).values.astype(float)
            sb = np.hypot(np.diff(ub, axis=1), np.diff(vb, axis=1)) / dz
            se = np.hypot(np.diff(ue, axis=1), np.diff(ve, axis=1)) / dz
            cells = []
            for _, lo, hi in BANDS:
                m = (mid > lo) & (mid <= hi)
                ok = np.isfinite(sb[:, m])
                a, b = sb[:, m][ok], se[:, m][ok]
                cells.append(f"{np.quantile(a, 0.5) / np.quantile(b, 0.5):5.2f} / {np.quantile(a, 0.99) / np.quantile(b, 0.99):5.2f}")
            print(f"  {g:8} " + "  ".join(f"{c:>16}" for c in cells) + f"   {len(common)}")


if __name__ == "__main__":
    main()
