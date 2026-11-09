"""Audit of the lapse-map decision: is the lapse-rate distribution of the ERA5-based training target (which the lapse map was fitted to match) heavier or lighter than that of real balloons? Same stations (EPZ, MAF),
same layers and times as il103_balloon_shear.py: lapse rate -dT/dz (K per km) between neighbouring model heights, quantiles by band, balloon against ERA5 profile store (2015-25, 00 and 12 UTC).
If balloons have clearly heavier lapse tails than ERA5, matching ERA5's lapse tail (what the lapse map does) moves AWAY from reality and the map's claimed gain is only against the ERA5 reference.
"""
import os

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
Q = [0.5, 0.9, 0.99, 0.999]


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    ht = z["height"].values.astype(float)
    mid, dz = ht[1:], np.diff(ht) / 1000.0
    for sid, name in (("USM00072364", "EPZ"), ("USM00072265", "MAF")):
        d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
        sel = np.array([np.argmin(np.abs(d["heights"] - h)) for h in ht])
        yrs = d["time"].astype("datetime64[Y]").astype(int) + 1970
        tsel = (yrs >= 2015) & (yrs <= 2025)
        tb = d["time"][tsel].astype("datetime64[ns]")
        Tb = d["T"][tsel][:, sel].astype(float)
        bad = d["T"][tsel][:, sel] == -32768
        Tb[bad] = np.nan
        Tb = Tb * 0.1
        i = int(np.argmin((z.lat.values - d["lat"][0]) ** 2 + (z.lon.values - d["lon"][0]) ** 2))
        common = np.intersect1d(tb, z["time"].values)
        ib = np.searchsorted(tb, common)
        Te = z["T"].isel(point=i).sel(time=common).values.astype(float)
        lb = -np.diff(Tb[ib], axis=1) / dz
        le = -np.diff(Te, axis=1) / dz
        print(f"\n{name}: {len(common)} common soundings. lapse rate K/km, balloon / ERA5 (ratio) at p50, p90, p99, p99.9; share of layers above 9.8 K/km")
        for b, lo, hi in BANDS:
            m = (mid > lo) & (mid <= hi)
            ok = np.isfinite(lb[:, m])
            a, e = lb[:, m][ok], le[:, m][ok]
            qa, qe = np.quantile(a, Q), np.quantile(e, Q)
            print(f"  {b:9} " + "  ".join(f"{x:6.1f}/{y:6.1f} ({x / y if abs(y) > 0.2 else float('nan'):4.2f})" for x, y in zip(qa, qe)) + f"   >9.8: {np.mean(a > 9.8):.3f} / {np.mean(e > 9.8):.3f}")


if __name__ == "__main__":
    main()
