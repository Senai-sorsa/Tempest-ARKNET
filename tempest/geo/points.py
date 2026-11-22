"""G3/G4 point sets drawn from the global store's own 7,483 points (the only places with data).

    from tempest.geo import points as gp
    idx = gp.select(pts, box=(15, 75, -170, -50))             # G3 North America box (lat0, lat1, lon0, lon1)
    idx = gp.thin(pts, idx, nside=32)                          # at most one point per equal-area cell of HEALPix nside 32
    held = gp.igra_holdout(pts, idx, frac=0.3, seed=0)         # 30 % of the IGRA sites in idx, for the unseen-station gate

shortcut: equal-area cells (sin-latitude bands x longitude bins) of HEALPix nside's pixel area stand in for real
HEALPix pixels (healpy is not installed); same density, different cell shapes. Upgrade if healpy becomes a dependency.
"""
import numpy as np


def select(pts, box=None):
    """Indices of store points inside box = (lat0, lat1, lon0, lon1), lon in -180..180 (lon0 > lon1 crosses 180)."""
    lat, lon = np.asarray(pts["lat"]), (np.asarray(pts["lon"]) + 180) % 360 - 180
    if box is None:
        return np.arange(len(lat))
    la0, la1, lo0, lo1 = box
    inlon = (lon >= lo0) & (lon <= lo1) if lo0 <= lo1 else (lon >= lo0) | (lon <= lo1)
    return np.flatnonzero((lat >= la0) & (lat <= la1) & inlon)


def cell(lat, lon, nside):
    """Equal-area cell id with 12 * nside^2 cells on the sphere (HEALPix pixel area)."""
    nb = 2 * nside                                                          # sin-latitude bands
    z = np.sin(np.deg2rad(np.asarray(lat, float)))
    b = np.minimum(((z + 1) / 2 * nb).astype(int), nb - 1)
    per = 12 * nside * nside // nb                                          # cells per band: equal area
    j = np.minimum(((np.asarray(lon, float) % 360) / 360 * per).astype(int), per - 1)
    return b * per + j


def is_igra(ids):
    """True at IGRA stations: fetch_global ids are '' for lattice and 'T' for terrain points."""
    ids = np.asarray(ids)
    return (ids != "") & (ids != "T")


def thin(pts, idx, nside=32, keep_igra=True):
    """Keep at most one non-IGRA point per cell (the first in store order); IGRA sites are all kept when keep_igra."""
    idx = np.asarray(idx)
    igra = is_igra(np.asarray(pts["igra"])[idx])
    c = cell(np.asarray(pts["lat"])[idx], np.asarray(pts["lon"])[idx], nside)
    first = np.zeros(len(idx), bool)
    _, u = np.unique(np.where(igra, -1, c), return_index=True)
    first[u] = True
    return idx[(igra & keep_igra) | (~igra & first)]


def igra_holdout(pts, idx, frac=0.3, seed=0):
    """Random share frac of the IGRA sites among idx (store indices), fixed by seed."""
    idx = np.asarray(idx)
    sites = idx[is_igra(np.asarray(pts["igra"])[idx])]
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(sites, int(round(frac * len(sites))), replace=False)) if len(sites) else sites
