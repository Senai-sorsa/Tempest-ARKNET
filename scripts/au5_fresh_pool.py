"""AU-5 step 0 (New_Plan 15.2): a station map with the shipped a, b tables and a FRESH leftover pool.

    python scripts/au5_fresh_pool.py [--map models/station_map_mix.npz] [--first-year 2021] [--last-year 2023]
                                     [--out models/station_map_mix_pool2123.npz]

The shipped map's leftover pool comes from 1991-2020 balloons; every corrected ERA5 row, test years too, carries one of
those profiles, so the 2024-25 ERA5 truth holds noise the generator has learnt. This keeps the map's lines (a, b) and
refills pool / n / cuts from the 2021-23 balloon pairs (never used by the map). Build the 2024-25 rows with this map
and with the shipped one (same seed, so the same rows and the same draws) to get the two truths.
"""
import argparse

import numpy as np
import xarray as xr

from tempest.calibrate import station


def demean(pool, n):
    """(G, 3, P, V, H) pool and (G, 3) counts -> the pool with each group x tercile's mean leftover profile removed: keeps the
    fresh noise, drops the drift of the newer balloons away from the map's line (AU-5 step 1)."""
    out = pool.copy()
    for g, j in np.ndindex(n.shape):
        out[g, j, :n[g, j]] -= out[g, j, :n[g, j]].mean(0)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", default="models/station_map_mix.npz")
    ap.add_argument("--profiles", default="data/pilot/profiles.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--first-year", type=int, default=2021)
    ap.add_argument("--last-year", type=int, default=2023)
    ap.add_argument("--out", default="models/station_map_mix_pool2123.npz")
    ap.add_argument("--demean", action="store_true", help="AU-5 step 1: remove each group x tercile's mean leftover (noise only, no drift)")
    a = ap.parse_args()
    old = station.load(a.map)
    assert list(old["stations"]) == list(station.STATIONS), "map station order differs from the region config"
    assert old["fit_years"][1] < a.first_year, "the fresh pool must come from years the map never used"
    pairs = station.station_pairs(xr.open_zarr(a.profiles), a.igra, a.first_year, a.last_year)
    era = np.concatenate([p[1] for p in pairs])
    obs = np.concatenate([p[2] for p in pairs])
    groups = np.concatenate([station.group_id(s, t.month, (t.hour == 12).astype(int)) for s, (t, *_) in enumerate(pairs)])
    new = station.fit(era, obs, groups, len(old["a"]), ab=(old["a"], old["b"]))
    assert np.array_equal(new["a"], old["a"]) and np.array_equal(new["b"], old["b"])
    out = dict(old, pool=demean(new["pool"], new["n"]) if a.demean else new["pool"], n=new["n"], cuts=new["cuts"], pool_years=np.array([a.first_year, a.last_year]))
    np.savez(a.out, **out)
    print(f"wrote {a.out}: fresh leftovers per group {new['n'].tolist()} (old {old['n'].tolist()})")


if __name__ == "__main__":
    main()
