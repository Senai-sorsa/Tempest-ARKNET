"""Global ERA5 point store for stage G4 (docs/GLOBAL_PLAN.md, docs/DATA_NEEDS.md): ~6,000 points, one hour per day.

    python -m tempest.ingest.fetch_global [--out data/raw/era5_global] [--test]

Reads the Earthmover *spatial* group (one global field per chunk). The temporal group is chunked 1 year x 3x3 deg, so
for points scattered over the globe it would move ~10x more bytes (every tile's full hourly record); here each step costs
one global field per variable, whatever the number of points.
Points: every IGRA station reporting in 2020 or later (nearest 0.25 deg grid point) + a Fibonacci (equal-area) lattice
up to 6,000, minus everything within radius_deg of configs/global_holdout.toml (the 4 sites + 1 IGRA station per WMO
region). Steps: one per day 1991-2025, UTC hour = day index mod 24 (cycles through the diurnal cycle; each longitude
sees every local hour). 2026 is never read. Values are stored as int16 with a per-variable scale/offset (in the file).
One file per month (<out>/YYYY-MM.npz, .part then rename), so a rerun resumes. Months 2011-2025 come first, then
2001-2010, then 1991-2000, so a partial store is already usable if DATA_NEEDS D1/D6 say fewer years suffice.
"""
import argparse
import os
import time
import tomllib

import dask
import numpy as np
import xarray as xr

from tempest.ingest.fetch_earthmover import open_store

PRESSURE = ["u", "v", "t", "r", "z"]
SINGLE = ["u10", "v10", "u100", "v100", "t2m", "d2m", "sp"]
# int16 coding: value = q * scale + offset; quantisation error <= scale / 2 (0.005 m/s, 0.005 K, 0.005 %RH, ~0.5 m in z)
CODE = {"u": (0.01, 0), "v": (0.01, 0), "t": (0.01, 200), "r": (0.01, 0), "z": (10.0, 0),
        "u10": (0.01, 0), "v10": (0.01, 0), "u100": (0.01, 0), "v100": (0.01, 0),
        "t2m": (0.01, 200), "d2m": (0.01, 200), "sp": (2.0, 80000)}
N_POINTS, DAY0 = 6000, np.datetime64("1991-01-01")
IGRA_LIST = "data/raw/igra_list/igra2-station-list.txt"
HOLDOUT = "configs/global_holdout.toml"


def wmo_region(sid):
    """WMO region (1-7) from the WMO block of an IGRA id like USM00072469, None for non-WMO ids."""
    if sid[2] != "M":
        return None
    b = int(sid[6:8])
    return 1 if 60 <= b <= 69 else 2 if 20 <= b <= 59 else 3 if 80 <= b <= 88 else 4 if 70 <= b <= 79 \
        else 5 if b >= 90 else 6 if b <= 19 else 7  # 89 = Antarctica


def igra_stations(path=IGRA_LIST):
    """(id, lat, lon, first year, last year) of IGRA stations with valid coordinates."""
    out = []
    with open(path) as f:
        for ln in f:
            p = ln.split()
            if not ln[12:20].strip() or not ln[21:30].strip():
                continue
            lat, lon = float(ln[12:20]), float(ln[21:30])
            if abs(lat) <= 90 and abs(lon) <= 180:
                out.append((p[0], lat, lon, int(p[-3]), int(p[-2])))
    return out


def pick_igra_holdouts(stations, seed):
    """One long-record (<= 2000 to >= 2020) WMO station per WMO region, by a fixed seed."""
    rng, picks = np.random.default_rng(seed), []
    for r in range(1, 8):
        c = sorted(s[0] for s in stations if wmo_region(s[0]) == r and s[3] <= 2000 and s[4] >= 2020)
        if c:
            picks.append(c[rng.integers(len(c))])
    return picks


def gc_deg(lat1, lon1, lat2, lon2):
    """Great-circle distance in degrees."""
    a = np.radians
    c = np.sin(a(lat1)) * np.sin(a(lat2)) + np.cos(a(lat1)) * np.cos(a(lat2)) * np.cos(a(lon1 - lon2))
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def to_grid(lat, lon):
    """Nearest ERA5 0.25 deg grid indices (latitude runs 90 -> -90, longitude 0 -> 359.75)."""
    return np.round((90 - np.asarray(lat)) / 0.25).astype(int), np.round(np.mod(lon, 360) / 0.25).astype(int) % 1440


def points():
    """dict of point arrays: lat, lon, ilat, ilon, igra id ('' for lattice points); holdouts removed."""
    h = tomllib.load(open(HOLDOUT, "rb"))
    st = igra_stations()
    held = h.get("igra") or pick_igra_holdouts(st, h["seed"])
    byid = {s[0]: s for s in st}
    hold = [(s["lat"], s["lon"]) for s in h["site"]] + [(byid[i][1], byid[i][2]) for i in held]
    act = [s for s in st if s[4] >= 2020]
    il, jl = to_grid([s[1] for s in act], [s[2] for s in act])
    seen, ids, ii, jj = set(), [], [], []
    for s, i, j in zip(act, il, jl):
        if (i, j) not in seen:
            seen.add((i, j)); ids.append(s[0]); ii.append(i); jj.append(j)
    k = np.arange(N_POINTS - len(ids)) + 0.5  # Fibonacci sphere for the rest
    flat, flon = np.degrees(np.arcsin(1 - 2 * k / len(k))), np.mod(k * 180 * (3 - np.sqrt(5)), 360)
    for i, j in zip(*to_grid(flat, flon)):
        if (i, j) not in seen:
            seen.add((i, j)); ids.append(""); ii.append(i); jj.append(j)
    ii, jj = np.array(ii), np.array(jj)
    lat, lon = 90 - ii * 0.25, np.where(jj * 0.25 > 180, jj * 0.25 - 360, jj * 0.25)
    ok = np.ones(len(ii), bool)
    for hl, ho in hold:
        ok &= gc_deg(lat, lon, hl, ho) > h["radius_deg"]
    return {"lat": lat[ok], "lon": lon[ok], "ilat": ii[ok], "ilon": jj[ok], "igra": np.array(ids)[ok], "held_igra": np.array(held)}


def month_order():
    yrs = list(range(2011, 2026)) + list(range(2001, 2011)) + list(range(1991, 2001))
    return [f"{y}-{m:02d}" for y in yrs for m in range(1, 13)]


def steps(month):
    """Valid times of a month: one per day, UTC hour = (days since 1991-01-01) mod 24."""
    d0 = np.datetime64(month, "D")
    days = np.arange(d0, np.datetime64(month, "M") + 1)
    return days.astype("datetime64[h]") + ((days - DAY0).astype(int) % 24).astype("timedelta64[h]")


def encode(name, x):
    s, o = CODE[name]
    q = np.round((np.asarray(x, np.float64) - o) / s)
    bad = ~np.isfinite(q) | (np.abs(q) > 32767)
    if bad.any():  # never clip silently: a value outside the int16 range would be stored wrong
        raise ValueError(f"{name}: {bad.sum()} values non-finite or outside the int16 range (scale {s}, offset {o})")
    return q.astype(np.int16)


def fetch_month(groups, pts, month):
    out = {}
    il, jl = xr.DataArray(pts["ilat"], dims="point"), xr.DataArray(pts["ilon"], dims="point")
    t = steps(month)
    for ds, names in groups:
        idx = np.searchsorted(ds.valid_time.values, t)
        assert (ds.valid_time.values[idx] == t).all(), f"{month}: missing time steps in the store"
        sub = ds[names].isel(valid_time=idx).isel(latitude=il, longitude=jl).compute()
        for v in names:
            out[v] = encode(v, sub[v].values)  # (time, [level,] point)
        if "pressure_level" in sub.dims:
            out["pressure_level"] = sub.pressure_level.values
    out["valid_time"] = t
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/era5_global")
    ap.add_argument("--workers", type=int, default=16, help="download threads")
    ap.add_argument("--test", action="store_true", help="fetch 2 days of one month into <out>/test and check the decoding")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pf = os.path.join(a.out, "points.npz")
    if not os.path.exists(pf):
        np.savez(pf, **points(), code=np.array([f"{k} {s} {o}" for k, (s, o) in CODE.items()]))
    pts = dict(np.load(pf))
    print(f"{len(pts['lat'])} points ({(pts['igra'] != '').sum()} at IGRA stations), IGRA holdouts {list(pts['held_igra'])}", flush=True)
    store = open_store()
    groups = [(xr.open_zarr(store, group="pressure/spatial", zarr_format=3, chunks={}), PRESSURE),
              (xr.open_zarr(store, group="single/spatial", zarr_format=3, chunks={}), SINGLE)]
    with dask.config.set(scheduler="threads", num_workers=a.workers):
        if a.test:
            global steps
            full = steps
            steps = lambda m: full(m)[:2]  # noqa: E731
            r = fetch_month(groups, pts, "2025-12")
            ds = groups[0][0]
            ref = ds["t"].isel(valid_time=int(np.searchsorted(ds.valid_time.values, r["valid_time"][0])), pressure_level=0,
                               latitude=int(pts["ilat"][0]), longitude=int(pts["ilon"][0])).values
            got = r["t"][0, 0, 0] * CODE["t"][0] + CODE["t"][1]
            assert abs(got - ref) <= CODE["t"][0] / 2 + 1e-6, (got, ref)
            print("test ok:", {k: v.shape for k, v in r.items()}, f"t[0,0,0] {got:.2f} vs store {float(ref):.2f}")
            return
        for m in month_order():
            dst = os.path.join(a.out, f"{m}.npz")
            if os.path.exists(dst):
                continue
            t0 = time.time()
            r = fetch_month(groups, pts, m)
            with open(dst + ".part", "wb") as f:
                np.savez_compressed(f, **r)
            os.replace(dst + ".part", dst)
            print(f"{m}: {len(r['valid_time'])} steps in {time.time() - t0:.0f}s, {os.path.getsize(dst) / 1e6:.0f} MB", flush=True)


if __name__ == "__main__":
    main()
