"""Second pass over the global G4 points: vertical wind and the convective / boundary-layer / gust fields.

    python -m tempest.ingest.fetch_global_extra [--out data/raw/era5_global_extra] [--test]

Same points (data/raw/era5_global/points.npz, holdouts already removed), same steps (one per day, UTC hour cycling) and
the same month order as tempest.ingest.fetch_global, which it reuses unchanged. Fields: w (13 levels, Pa/s), fg10 (10 m
gust), blh, cape, tcc, tp. ~18 global fields per step instead of 72, so ~1/4 of the main pass's time. int16 like the main
store, but values outside the int16 range are clipped and counted in the file (cape / tp extremes), not raised: a rare
clipped storm value must not stall the whole pass. 2026 is never read.
"""
import argparse
import os
import time

import dask
import numpy as np
import xarray as xr

from tempest.ingest import fetch_global as G
from tempest.ingest.fetch_earthmover import open_store

PRESSURE, SINGLE = ["w"], ["fg10", "blh", "cape", "tcc", "tp"]
CODE = {"w": (0.001, 0), "fg10": (0.01, 0), "blh": (1.0, 0), "cape": (1.0, 0), "tcc": (1e-4, 0), "tp": (1e-5, 0)}


def encode(name, x):
    s, o = CODE[name]
    q = np.round((np.asarray(x, np.float64) - o) / s)
    if not np.isfinite(q).all():
        raise ValueError(f"{name}: non-finite values")
    return np.clip(q, -32767, 32767).astype(np.int16), int((np.abs(q) > 32767).sum())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/era5_global_extra")
    ap.add_argument("--points", default="data/raw/era5_global/points.npz")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--test", action="store_true", help="2 days of 2025-12, checked against the store")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pts = dict(np.load(a.points))
    store = open_store()
    groups = [(xr.open_zarr(store, group="pressure/spatial", zarr_format=3, chunks={}), PRESSURE),
              (xr.open_zarr(store, group="single/spatial", zarr_format=3, chunks={}), SINGLE)]
    il, jl = xr.DataArray(pts["ilat"], dims="point"), xr.DataArray(pts["ilon"], dims="point")

    def fetch(month, n=None):
        t = G.steps(month)[:n]
        assert t.max() < np.datetime64("2026-01-01"), "2026 is never read"
        out, clipped = {"valid_time": t}, {}
        for ds, names in groups:
            idx = np.searchsorted(ds.valid_time.values, t)
            assert (ds.valid_time.values[idx] == t).all(), f"{month}: missing time steps"
            sub = ds[names].isel(valid_time=idx).isel(latitude=il, longitude=jl).compute()
            for v in names:
                out[v], clipped[v] = encode(v, sub[v].values)
            if "pressure_level" in sub.dims:
                out["pressure_level"] = sub.pressure_level.values
        out["clipped"] = np.array([f"{k} {c}" for k, c in clipped.items()])
        out["code"] = np.array([f"{k} {s} {o}" for k, (s, o) in CODE.items()])
        return out

    with dask.config.set(scheduler="threads", num_workers=a.workers):
        if a.test:
            r = fetch("2025-12", 2)
            ds = groups[1][0]
            ref = ds["blh"].isel(valid_time=int(np.searchsorted(ds.valid_time.values, r["valid_time"][0])),
                                 latitude=int(pts["ilat"][0]), longitude=int(pts["ilon"][0])).values
            got = r["blh"][0, 0] * CODE["blh"][0]
            assert abs(got - ref) <= CODE["blh"][0] / 2 + 1e-3, (got, ref)
            print("test ok:", {k: v.shape for k, v in r.items()}, f"blh {got:.0f} vs {float(ref):.1f}", list(r["clipped"]))
            return
        for m in G.month_order():
            dst = os.path.join(a.out, f"{m}.npz")
            if os.path.exists(dst):
                continue
            t0 = time.time()
            r = fetch(m)
            with open(dst + ".part", "wb") as f:
                np.savez_compressed(f, **r)
            os.replace(dst + ".part", dst)
            print(f"{m}: {time.time() - t0:.0f}s, {os.path.getsize(dst) / 1e6:.0f} MB, clipped {list(r['clipped'])}", flush=True)


if __name__ == "__main__":
    main()
