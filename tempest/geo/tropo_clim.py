"""G2 climatological tropopause input (GLOBAL_PLAN G2, D stage 2): per store point and calendar month, the median
tropopause height (m above sea level, WMO 2 K/km rule on the 13 store levels) over the training years only.

    python -m tempest.geo.tropo_clim fit --out models/global/tropo_clim.npz [--last-year 2023]
    python -m tempest.geo.tropo_clim overlay --data data/train/X.npz --table models/global/tropo_clim.npz --out data/train/X_ztrop.npz

overlay writes a train.load_npz overlay file (base_npz + a wider cond with the extra column `ztrop_clim`): the
base dataset is not copied. The query side uses lookup() with the same table.
"""
import argparse
import os

import numpy as np

LAPSE_MAX = 2.0     # K/km, as tempest.calibrate.tropo
BIN_M, TOP_M = 100.0, 20000.0


def tropopause_rows(T, z, z_min=5000.0, z_max=20000.0):
    """(N, L) temperature (K) and geometric height (m), heights rising along L -> (N,) lowest level whose lapse rate
    to every level within 2 km above stays <= 2 K/km; coldest level in [z_min, z_max] when none qualifies.
    Vectorised twin of tempest.calibrate.tropo.tropopause (the per-row loop there is too slow for the global store)."""
    T, z = np.asarray(T, float), np.asarray(z, float)
    N, L = T.shape
    out = np.full(N, np.nan)
    for i in range(L - 1):
        dz = (z[:, i + 1:] - z[:, i:i + 1]) / 1000.0
        lap = (T[:, i:i + 1] - T[:, i + 1:]) / np.where(dz > 0, dz, np.nan)
        first = lap[:, 0] <= LAPSE_MAX
        inwin = (dz > 0) & (dz <= 2.0)
        ok = first & np.where(inwin, lap <= LAPSE_MAX, True).all(1) & inwin.any(1)
        ok &= (z[:, i] >= z_min) & (z[:, i] <= z_max) & np.isnan(out)
        out[ok] = z[ok, i]
    miss = np.isnan(out)
    if miss.any():
        Tm = np.where((z >= z_min) & (z <= z_max) & np.isfinite(T), T, np.inf)
        k = np.argmin(Tm, 1)
        has = np.isfinite(Tm.min(1))
        out[miss & has] = z[miss & has, k[miss & has]]
    return out


def fit(first=1991, last=2023, store=None):
    from tempest.geo import global_store as gs
    from tempest.profiles.to_heights import geometric_height
    if last > 2023:
        raise ValueError("the tropopause climatology uses training years only (<= 2023)")
    pts = gs.points(store or gs.STORE)
    nb = int(TOP_M / BIN_M)
    hist = np.zeros((len(pts["lat"]), 12, nb), np.int32)
    for name in gs.months(first, last, store or gs.STORE):
        m = gs.month(name, store or gs.STORE)
        T = np.moveaxis(m["t"], 1, -1).reshape(-1, m["t"].shape[1])                  # (days * P, 13)
        z = geometric_height(np.moveaxis(m["z"], 1, -1).reshape(T.shape))
        h = tropopause_rows(T, z).reshape(m["t"].shape[0], -1)
        mo = int(name[5:7]) - 1
        for d in range(h.shape[0]):
            ok = np.isfinite(h[d])
            np.add.at(hist[:, mo], (np.flatnonzero(ok), np.minimum((h[d, ok] / BIN_M).astype(int), nb - 1)), 1)
        print(f"{name}: median {np.nanmedian(h):.0f} m", flush=True)
    c = np.cumsum(hist, -1)
    med = (np.argmax(c >= (c[..., -1:] + 1) // 2, -1) + 0.5) * BIN_M
    med = np.where(c[..., -1] > 0, med, np.nan).astype(np.float32)
    return dict(lat=pts["lat"], lon=pts["lon"], ztrop=med, first=first, last=last)


_trees = {}


def _nearest(tab, lat, lon):
    """Index of the nearest table point (great circle) for each query point; the KD tree is cached per table."""
    from scipy.spatial import cKDTree
    from tempest.scoring.spatial import xyz
    key = (id(tab["lat"]), len(tab["lat"]), float(tab["lat"][0]), float(tab["lon"][-1]))
    if key not in _trees:
        _trees.clear()
        _trees[key] = cKDTree(xyz(np.asarray(tab["lat"], float), np.asarray(tab["lon"], float)))
    return _trees[key].query(xyz(np.asarray(lat, float), np.asarray(lon, float)))[1]


def lookup(tab, lat, lon, month):
    """Nearest table point (great circle) and calendar month 1..12 -> tropopause height (m)."""
    return np.asarray(tab["ztrop"])[_nearest(tab, lat, lon), np.asarray(month, int) - 1]


def month_of(cond, names):
    doy = np.arctan2(cond[:, names.index("doy_sin")], cond[:, names.index("doy_cos")]) % (2 * np.pi) / (2 * np.pi) * 365.25
    return np.minimum((doy / (365.25 / 12)).astype(int), 11) + 1


def overlay(data, table, out, name="ztrop_clim", chunk=1_000_000):
    from tempest.generator.train import _load
    d = _load(data)
    names = [str(x) for x in d["cond_names"]]
    if name in names:
        raise ValueError(f"{data} already has {name}")
    tab = dict(np.load(table))
    cond = np.empty((len(d["year"]), len(names) + 1), np.float32)
    for i in range(0, len(cond), chunk):
        c = np.asarray(d["cond"][i:i + chunk])
        cond[i:i + len(c), :-1] = c
        cond[i:i + len(c), -1] = lookup(tab, c[:, names.index("lat")], c[:, names.index("lon")], month_of(c, names))
    with open(out, "wb") as fh:
        np.savez(fh, base_npz=np.array(os.path.abspath(data)), cond=cond, cond_names=np.array(names + [name]))
    print(f"wrote {out}: {len(cond):,} rows, + {name} (median {np.nanmedian(cond[:, -1]):.0f} m)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fit")
    f.add_argument("--out", required=True)
    f.add_argument("--first-year", type=int, default=1991)
    f.add_argument("--last-year", type=int, default=2023)
    o = sp.add_parser("overlay")
    o.add_argument("--data", required=True)
    o.add_argument("--table", required=True)
    o.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "fit":
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        t = fit(a.first_year, a.last_year)
        with open(a.out, "wb") as fh:
            np.savez(fh, **t)
        print(f"wrote {a.out}")
    else:
        overlay(a.data, a.table, a.out)


if __name__ == "__main__":
    main()
