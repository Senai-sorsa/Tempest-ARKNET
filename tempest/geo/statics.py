"""G0 static fields for any point (docs/plans/GLOBAL_PLAN.md G0), from the ERA5 invariants of tempest.ingest.fetch_statics.

    from tempest.geo.statics import statics
    s = statics(lat, lon)   # dict of arrays: oro_m, lsm, sdor, slor, anor, isor, coast_km (+ over land, - over sea), tpi_m

Nearest 0.25 deg grid point. coast_km and tpi_m are derived once from the whole field and cached next to the
invariants (derived.npz); coast_km is great-circle distance to the nearest land cell with a water neighbour
(lsm 0.5; large lakes count as water); tpi_m = orography minus the mean of its 8 neighbours (0.25 deg). Rebuild with --rebuild.
shortcut: no Koppen class yet (needs a precipitation climatology the global store does not hold); add at G4 if a run asks for it.
"""
import argparse
import os

import numpy as np

INV = "data/raw/era5_static/era5_invariants.npz"
DERIVED = "data/raw/era5_static/derived.npz"
R_KM = 6371.0
_cache = {}


def _xyz(lat, lon):
    a, b = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(a) * np.cos(b), np.cos(a) * np.sin(b), np.sin(a)], -1)


def derive(inv=INV, out=DERIVED):
    from scipy.spatial import cKDTree
    d = np.load(inv)
    oro = d["z_sfc"] / 9.80665
    land = d["lsm"] >= 0.5
    lat2, lon2 = np.meshgrid(d["lat"], d["lon"], indexing="ij")
    pl = np.pad(land, ((1, 1), (0, 0)), mode="edge")       # no wrap across the poles; longitude wraps
    nb = [np.roll(pl, j, 1)[1 + i: 1 + i + land.shape[0]] for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j]
    coast = land & ~np.logical_and.reduce(nb)              # land cells with a sea neighbour
    tree = cKDTree(_xyz(lat2[coast], lon2[coast]))
    chord, _ = tree.query(_xyz(lat2.ravel(), lon2.ravel()), workers=-1)
    km = (2 * R_KM * np.arcsin(np.clip(chord / 2, 0, 1))).reshape(land.shape)
    pad = np.pad(oro, ((1, 1), (0, 0)), mode="edge")
    s = sum(np.roll(pad, j, 1)[1 + i: 1 + i + oro.shape[0]] for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j)
    np.savez(out, coast_km=np.where(land, km, -km).astype(np.float32), tpi_m=(oro - s / 8).astype(np.float32))


def _fields():
    if not _cache:
        if not os.path.exists(DERIVED):
            derive()
        d, e = np.load(INV), np.load(DERIVED)
        _cache.update(oro_m=d["z_sfc"] / 9.80665, **{k: d[k] for k in ("lsm", "sdor", "slor", "anor", "isor")}, **dict(e))
    return _cache


def statics(lat, lon):
    i = np.round((90 - np.asarray(lat, float)) / 0.25).astype(int)            # same grid as fetch_global.to_grid
    j = np.round(np.mod(np.asarray(lon, float), 360) / 0.25).astype(int) % 1440
    return {k: v[i, j] for k, v in _fields().items()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    if a.rebuild or not os.path.exists(DERIVED):
        derive()
    print({k: np.round(v, 2) for k, v in statics([39.74, 0.0, 27.99], [-104.99, -30.0, 86.93]).items()})  # Denver, mid-Atlantic, Everest
