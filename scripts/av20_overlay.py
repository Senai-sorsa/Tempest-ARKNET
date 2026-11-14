"""New_Plan 13 AV20: L3-7 climatology inputs extended to the upper air, as an overlay on top of an l3x overlay
(scripts/l3_overlay.py). The l3x clim columns stop at T 3 km / wind 5 km; AV20 adds what the stratosphere needs:

  clim_T_d9000 / d12000 / d15000 / d18000     mean T at those heights above ground
  clim_sdT_d3000 / d12000 / d15000            sd of T there (between-year + within-month spread)
  clim_tropo                                  lapse-rate tropopause height (m above ground) of the mean T profile:
                                              lowest height >= 5 km where the mean lapse rate over the next 2 km is < 2 K/km
  clim_u_d12000, clim_sdu_d12000              mean and sd of u at 12 km

All per grid point x month from rows of years <= 2020 only (the calibration 2021-23 and test 2024-25 years never enter),
same grouping as l3_overlay. The output overlay points at the ORIGINAL base file (target, year) and replaces cond with
l3x cond + these 10 columns, so nothing else changes. Opt-in: only configs that read this file see the columns.

    python scripts/av20_overlay.py data/train/pilot80_dpd_l3x.npz data/train/pilot80_dpd_av20.npz
"""
import os
import sys
import tempfile
import zipfile

import numpy as np

from tempest.generator.train import _load, _load_one

T_MEAN = [9000, 12000, 15000, 18000]
T_SD = [3000, 12000, 15000]
NEW = [f"clim_T_d{h}" for h in T_MEAN] + [f"clim_sdT_d{h}" for h in T_SD] + ["clim_tropo", "clim_u_d12000", "clim_sdu_d12000"]


def height(name):
    s = name.split("_")[1]
    return float(s[3:]) if s.startswith("sfc") else float(s[1:])


def tropopause(tm, hz):
    """tm (G, L) mean T profiles (K or C), hz (L,) heights -> (G,) lowest height >= 5 km with mean lapse < 2 K/km over the next 2 km."""
    out = np.full(len(tm), hz[-1])
    for k in np.where(hz >= 5000)[0]:
        j = np.searchsorted(hz, hz[k] + 2000)
        if j >= len(hz):
            break
        lapse = -(tm[:, j] - tm[:, k]) / ((hz[j] - hz[k]) / 1000)
        hit = (lapse < 2.0) & (out == hz[-1])
        out[hit] = hz[k]
    return out


def main(l3x, dst):
    ov = _load_one(l3x)
    base = str(np.asarray(ov["base_npz"]))
    z = _load(l3x)
    cond, names = z["cond"], [str(n) for n in z["cond_names"]]
    tn = [str(n) for n in z["target_names"]]
    col = {k: np.asarray(cond[:, names.index(k)], np.float64) for k in ("lat", "lon", "doy_sin", "doy_cos")}
    doy = np.mod(np.arctan2(col["doy_sin"], col["doy_cos"]) / (2 * np.pi) * 365.25, 365.25)
    month = np.minimum((doy / 365.25 * 12).astype(int), 11)
    keys, pid = np.unique(np.stack([col["lat"].round(3), col["lon"].round(3)], 1), axis=0, return_inverse=True)
    g = pid.ravel() * 12 + month
    ng = len(keys) * 12
    yr = np.asarray(z["year"])
    fit = yr <= 2020
    n = np.bincount(g[fit], minlength=ng).astype(np.float64)
    assert (n > 1).all(), "a point x month has < 2 rows <= 2020"
    # profile targets are height-to-height steps: the level value is the cumulative sum of the variable's block
    tb = [i for i, t in enumerate(tn) if t.startswith("T_") and ("_d" in t or "_sfc" in t)]
    ub = [i for i, t in enumerate(tn) if t.startswith("u_") and ("_d" in t or "_sfc" in t)]
    hz = np.array([height(tn[i]) for i in tb])
    assert (np.diff(hz) > 0).all()
    ku = [tn[i] for i in ub].index("u_d12000")
    s, s2 = np.zeros((ng, len(tb) + 1)), np.zeros((ng, len(tb) + 1))
    tgt = z["target"]
    for a in range(0, len(cond), 500_000):
        b = min(a + 500_000, len(cond))
        f = fit[a:b]
        blk = np.asarray(tgt[a:b])[f]
        v = np.column_stack([np.cumsum(blk[:, tb].astype(np.float64), 1), np.cumsum(blk[:, ub].astype(np.float64), 1)[:, ku]])
        gg = g[a:b][f]
        for j in range(v.shape[1]):
            s[:, j] += np.bincount(gg, v[:, j], minlength=ng)
            s2[:, j] += np.bincount(gg, v[:, j] ** 2, minlength=ng)
    m = s / n[:, None]
    sd = np.sqrt(np.maximum(s2 / n[:, None] - m ** 2, 0) * n[:, None] / (n[:, None] - 1))
    ix = {h: int(np.where(hz == h)[0][0]) for h in set(T_MEAN + T_SD)}
    tab = np.column_stack([m[:, ix[h]] for h in T_MEAN] + [sd[:, ix[h]] for h in T_SD]
                          + [tropopause(m[:, :len(tb)], hz), m[:, -1], sd[:, -1]])
    extra = tab[g].astype(np.float32)
    assert np.isfinite(extra).all()
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(dst))) as td:   # stored zip written from a disk memmap
        mm = np.lib.format.open_memmap(os.path.join(td, "cond.npy"), "w+", np.float32, (len(cond), len(names) + len(NEW)))
        for a in range(0, len(cond), 1_000_000):
            mm[a:a + 1_000_000] = np.concatenate([np.asarray(cond[a:a + 1_000_000]), extra[a:a + 1_000_000]], 1)
        mm.flush(); del mm
        np.save(os.path.join(td, "base_npz.npy"), np.array(base))
        np.save(os.path.join(td, "cond_names.npy"), np.array(names + NEW))
        with zipfile.ZipFile(dst + ".part", "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for k in ("base_npz", "cond", "cond_names"):
                zf.write(os.path.join(td, k + ".npy"), k + ".npy")
    os.replace(dst + ".part", dst)
    print(f"{dst}: {len(cond)} rows, {len(keys)} points, base {base}, +{NEW}")
    for k, name in enumerate(NEW):
        print(f"  {name:<16} min {tab[:, k].min():9.2f}  median {np.median(tab[:, k]):9.2f}  max {tab[:, k].max():9.2f}")


def _selfcheck():
    hz = np.arange(0, 20001, 500.0)
    t = np.where(hz < 11000, 15 - 6.5 * hz / 1000, 15 - 6.5 * 11)[None]      # standard atmosphere: tropopause at 11 km
    assert 10000 <= tropopause(t, hz)[0] <= 11000                                  # 2 km mean lapse crosses 2 K/km just below 11 km
    assert tropopause(np.array([15 - 6.5 * hz / 1000]), hz)[0] == hz[-1]       # no tropopause -> top height
    assert height("T_sfc10") == 10 and height("T_d12000") == 12000


_selfcheck()
if __name__ == "__main__":
    main(*sys.argv[1:3])
