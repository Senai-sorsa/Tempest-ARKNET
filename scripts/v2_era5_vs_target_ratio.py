"""V2b: is the training target (ERA5 corrected to balloons and stations) flatter in 10 -> 200 m wind than raw ERA5? Median speed ratio at 50 / 100 / 200 m to 10 m by 10 m speed class: raw ERA5 profile store, pooled over 60 random grid points, daytime stored hours of 2024-25
(solar 8-17 h), against the same statistic of the 2024-25 rows of data/train/pilot80_dpd.npz (the target the p2f model was trained on).
"""
import numpy as np
import xarray as xr

from tempest.generator.sample import to_physical
from tempest.generator.train import load_npz
from tempest.profiles.to_heights import HEIGHTS, PROFILE

CL = [(0, 3), (3, 6), (6, 10), (10, 40)]
IZ = [1, 2, 4]


def cells(sp, name):
    s10 = sp[:, 0]
    out = []
    for lo, hi in CL:
        m = (s10 >= lo) & (s10 < hi) & (s10 > 0.3)
        out.append(" ".join(f"{np.median(sp[m, i] / s10[m]):5.2f}" for i in IZ) + f" (n{m.sum()})")
    print(f"  {name:30} " + " | ".join(out))


def main():
    z = xr.open_zarr("data/pilot/profiles.zarr")
    rng = np.random.default_rng(1)
    pts = np.sort(rng.choice(z.sizes["point"], 60, replace=False))
    t = z["time"].values
    yr = t.astype("datetime64[Y]").astype(int) + 1970
    hr = (t.astype("datetime64[h]") - t.astype("datetime64[D]")).astype(int)
    ti = np.flatnonzero((yr >= 2024) & (yr <= 2025) & ((hr >= 16) & (hr <= 23)))           # 16-23 UTC = about 9-17 local solar in the box
    sub = z.isel(point=pts, time=ti, height=slice(0, 5))
    u, v = sub["u"].values, sub["v"].values
    sp = np.hypot(u, v).reshape(-1, 5)
    cells(sp, "raw ERA5 store (60 points)")
    d = load_npz("data/train/pilot80_dpd.npz")
    idx = np.flatnonzero(d["year"] >= 2024)
    tgt = to_physical(np.asarray(d["target"][idx]))
    n = len(HEIGHTS)
    iu, iv = PROFILE.index("u") * n, PROFILE.index("v") * n
    cells(np.hypot(tgt[:, iu:iu + 5], tgt[:, iv:iv + 5]), "training target (pilot80_dpd)")


if __name__ == "__main__":
    main()
