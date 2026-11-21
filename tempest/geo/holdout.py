"""G0 lock (docs/plans/GLOBAL_PLAN.md 3.1): global loaders call check() so no script reads the locked holdout places
(configs/global_holdout.toml: 4 sites + 1 IGRA station per WMO region, within radius_deg) or valid times on or after
2026-07-01 before stage G6. Setting TEMPEST_FINAL_GLOBAL=1 (G6 only) turns the check off.

    from tempest.geo.holdout import check
    check(lat, lon, times)     # raises HoldoutError on any locked row; any argument may be None
"""
import os
import tomllib

import numpy as np

HOLDOUT = "configs/global_holdout.toml"
IGRA_LIST = "data/raw/igra_list/igra2-station-list.txt"
CUTOFF = np.datetime64("2026-07-01")


class HoldoutError(RuntimeError):
    pass


def places(path=HOLDOUT, igra_list=IGRA_LIST):
    """(lat, lon arrays of every locked place, radius_deg)."""
    h = tomllib.load(open(path, "rb"))
    pts = [(s["lat"], s["lon"]) for s in h["site"]]
    held = set(h["igra"])
    with open(igra_list) as f:   # same fixed-width columns as fetch_global.igra_stations
        for ln in f:
            if ln.split()[0] in held:
                pts.append((float(ln[12:20]), float(ln[21:30])))
                held.discard(ln.split()[0])
    if held:
        raise HoldoutError(f"held IGRA stations missing from {igra_list}: {sorted(held)}")
    lat, lon = np.array(pts).T
    return lat, lon, float(h["radius_deg"])


def locked_mask(lat, lon, path=HOLDOUT, igra_list=IGRA_LIST):
    """True where a point lies within radius_deg (great circle) of a locked place."""
    hl, ho, r = places(path, igra_list)
    a, b = np.radians(np.asarray(lat, float))[..., None], np.radians(np.asarray(lon, float))[..., None]
    c = np.sin(a) * np.sin(np.radians(hl)) + np.cos(a) * np.cos(np.radians(hl)) * np.cos(b - np.radians(ho))
    return (np.degrees(np.arccos(np.clip(c, -1, 1))) <= r).any(-1)


def check(lat=None, lon=None, times=None, what="rows"):
    if os.environ.get("TEMPEST_FINAL_GLOBAL") == "1":
        return
    if times is not None:
        t = np.asarray(times).astype("datetime64[s]")
        if t.size and (t >= CUTOFF).any():
            raise HoldoutError(f"{what}: {int((t >= CUTOFF).sum())} valid times on or after {CUTOFF} (global test window, G6 only)")
    if lat is not None and lon is not None:
        m = locked_mask(lat, lon)
        if m.any():
            raise HoldoutError(f"{what}: {int(m.sum())} points within the locked holdout radius (G6 only)")
