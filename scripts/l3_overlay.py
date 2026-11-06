"""Loop-3 input overlay (docs/logs/LOOP3.md L3-5/6/7): base cond + 12 new place/time columns, written as an
overlay npz (train._load merges it with the base file; target and year are not copied).

    python scripts/l3_overlay.py data/train/pilot80_dpd.npz data/train/pilot80_dpd_l3x.npz

New columns (variants switch groups off with ignore_inputs):
  terrain (L3-5): tpi (elevation minus the mean of the 0.25-degree neighbours), slope_ns, slope_ew (m per grid step),
                  rough (std of the 3x3 block)  - from elev_grid of the dataset's own grid points
  clocks  (L3-6): cosz (cosine of the solar zenith angle), daylen (hours of daylight)
  clim    (L3-7): per grid point x month mean of t2m, rh2m, T/RH at 3 km and u/v at 5 km above ground, years <= 2020 only
                  (the calibration 2021-23 and test 2024-25 years never enter)
"""
import os
import sys
import tempfile
import zipfile

import numpy as np

from tempest.generator.train import _load_one   # memory maps: the 6 GB target is read in row chunks, never whole

CLIM = ["t2m", "rh2m", "T_d3000", "RH_d3000", "u_d5000", "v_d5000"]


def _cols(tn, k):
    """Target columns whose sum is the absolute value of k: itself for surface extras, else its variable's steps up to it."""
    if "_d" not in k:
        return [tn.index(k)]
    var = k.split("_")[0] + "_"
    blk = [i for i, t in enumerate(tn) if t.startswith(var) and ("_d" in t or "_sfc" in t)]
    return [i for i in blk if i <= tn.index(k)]


def terrain(lat, lon, elev):
    pts = {(round(a, 3), round(o, 3)): e for a, o, e in zip(lat, lon, elev)}
    out = {}
    for (a, o), e in pts.items():
        nb = [pts.get((round(a + i * .25, 3), round(o + j * .25, 3))) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        ring = [x for k, x in enumerate(nb) if x is not None and k != 4]
        blk = [x for x in nb if x is not None]
        def d(p, m):  # centred difference where both sides exist, else one-sided, else 0
            if p is not None and m is not None:
                return (p - m) / 2
            return (p - e) if p is not None else (e - m) if m is not None else 0.0
        out[a, o] = (e - np.mean(ring) if ring else 0.0, d(nb[7], nb[1]), d(nb[5], nb[3]), float(np.std(blk)))
    return out


def clocks(lat, doy, hour):
    dec = np.radians(23.44) * np.sin(2 * np.pi * (doy - 81) / 365.25)
    phi = np.radians(lat)
    cosz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(np.radians((hour - 12) * 15))
    daylen = 2 / 15 * np.degrees(np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1)))
    return cosz, daylen


def main(src, dst):
    z = _load_one(src)
    cond, names = z["cond"], [str(n) for n in z["cond_names"]]
    tn = [str(n) for n in z["target_names"]]
    col = {k: cond[:, names.index(k)].astype(np.float64) for k in ("lat", "lon", "elev_grid", "doy_sin", "doy_cos", "hour_sin", "hour_cos")}
    doy = np.mod(np.arctan2(col["doy_sin"], col["doy_cos"]) / (2 * np.pi) * 365.25, 365.25)
    hour = np.mod(np.arctan2(col["hour_sin"], col["hour_cos"]) / (2 * np.pi) * 24, 24)
    month = np.minimum((doy / 365.25 * 12).astype(int), 11)
    la, lo = col["lat"].round(3), col["lon"].round(3)
    keys, first, pid = np.unique(np.stack([la, lo], 1), axis=0, return_index=True, return_inverse=True)
    pid = pid.ravel()
    elev = col["elev_grid"][first]
    tt = terrain(keys[:, 0], keys[:, 1], elev)
    ter = np.array([tt[round(a, 3), round(o, 3)] for a, o in keys])[pid]
    cosz, daylen = clocks(col["lat"], doy, hour)
    tgt, yr = z["target"], np.asarray(z["year"])
    fit = yr <= 2020
    g = pid * 12 + month
    ng = len(keys) * 12
    # profile targets are height-to-height steps (profiles.diff): the level value is the sum of its variable's steps up to it,
    # and a mean of a sum is the sum of the means, so each clim column sums the group means of those step columns
    tj = sorted({i for k in CLIM for i in _cols(tn, k)})
    s, n = np.zeros((ng, len(tj))), np.bincount(g[fit], minlength=ng)
    assert (n > 0).all(), "a point x month has no rows <= 2020"
    for a in range(0, len(cond), 500_000):
        b = min(a + 500_000, len(cond))
        f = fit[a:b]
        v = np.asarray(tgt[a:b])[:, tj][f].astype(np.float64)
        for j in range(len(tj)):
            s[:, j] += np.bincount(g[a:b][f], v[:, j], minlength=ng)
    m = s / n[:, None]
    cl = np.column_stack([m[:, [tj.index(i) for i in _cols(tn, k)]].sum(1) for k in CLIM])[g]
    extra = np.column_stack([ter, cosz, daylen, cl]).astype(np.float32)
    new = ["tpi", "slope_ns", "slope_ew", "rough", "cosz", "daylen"] + ["clim_" + k for k in CLIM]
    assert np.isfinite(extra).all()
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as td:   # stored zip written from a disk memmap
        mm = np.lib.format.open_memmap(os.path.join(td, "cond.npy"), "w+", np.float32, (len(cond), len(names) + len(new)))
        for a in range(0, len(cond), 1_000_000):
            mm[a:a + 1_000_000] = np.concatenate([np.asarray(cond[a:a + 1_000_000]), extra[a:a + 1_000_000]], 1)
        mm.flush(); del mm
        np.save(os.path.join(td, "base_npz.npy"), np.array(src))
        np.save(os.path.join(td, "cond_names.npy"), np.array(names + new))
        with zipfile.ZipFile(dst + ".part", "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for k in ("base_npz", "cond", "cond_names"):
                zf.write(os.path.join(td, k + ".npy"), k + ".npy")
    os.replace(dst + ".part", dst)
    print(f"{dst}: {len(cond)} rows, {len(keys)} points, +{new}")
    print("cosz range", cosz.min().round(3), cosz.max().round(3), "daylen", daylen.min().round(2), daylen.max().round(2),
          "tpi sd", ter[:, 0].std().round(1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
