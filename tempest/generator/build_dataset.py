"""Build the generator's training file from the profile store.

    python -m tempest.generator.build_dataset [--profiles data/pilot/profiles.zarr] [--out data/train/pilot.npz]
                                              [--rows 8000000] [--first-year 1991] [--last-year 2025]
                                              [--station-map models/station_map.npz]

Rows: random (point, hour) pairs in the solar 06-21 h window, so neighbouring hours and points are not all kept.
target = per variable u, v, T, RH: to_diff over the 44 heights (surface value + 43 differences), then surface
t2m, sp, rh2m. 10 m wind is not repeated: it is already the first profile value.
With --station-map (from tempest.calibrate.station) profiles are corrected toward weather-balloon
statistics first (phase 6 S4); without it the targets are plain ERA5.
"""
import argparse
import os

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station
from tempest.generator import features as feat
from tempest.generator.features import FEATURES, features
from tempest.generator.sample import dpd_from_rh
from tempest.ingest import indices
from tempest.profiles.diff import from_diff, to_diff
from tempest.profiles.to_heights import HEIGHTS, PROFILE

SURFACE = ["t2m", "sp", "rh2m"]


def solar_hour(times, lon):
    """(T,) UTC times, (P,) lon -> (P, T) local solar hour."""
    h = pd.DatetimeIndex(times).hour.to_numpy()
    return (h[None, :] + lon[:, None] / 15.0) % 24


def target_names():
    return [f"{v}_{'sfc' if i == 0 else 'd'}{int(h)}" for v in PROFILE for i, h in enumerate(HEIGHTS)] + SURFACE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="data/pilot/profiles.zarr")
    ap.add_argument("--indices", default="data/raw/indices")
    ap.add_argument("--out", default="data/train/pilot.npz")
    ap.add_argument("--rows", type=int, default=8_000_000, help="about 6 GB at the default; keep it under half the RAM")
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--station-map", help="correction tables from tempest.calibrate.station; omit for plain ERA5")
    ap.add_argument("--features", choices=["base", "p2"], default="base", help="p2: global-temperature input (gmst) instead of "
                    "year, plus ONI hinges and a 3-month lagged ONI (Phase 2 items 2.2, 2.3); base = the original 13 columns")
    ap.add_argument("--rh-target", choices=["rh", "dpd"], default="rh", help="dpd: learn humidity as ln(T - Td + 1 K) so that "
                    "RH <= 100 %% by construction (Phase 2 item 2.1); rh = relative humidity as before")
    ap.add_argument("--station-blend", action="store_true", help="F-20: draw the correcting station by inverse-distance weights and the launch class by a cosine ramp over 05-17 h solar "
                    "(no Voronoi seam, no 11:00 switch); default off = the hard nearest-station / 11:00 rule")
    ap.add_argument("--sidecar", action="store_true", help="F-35: also store row provenance (grid point, UTC time, correction group, correction version) in the npz")
    a = ap.parse_args()
    if a.features == "p2":
        feat.set_active(feat.P2_FEATURES)
    qm = station.load(a.station_map) if a.station_map else None
    crng = np.random.default_rng(a.seed + 1)

    ds = xr.open_zarr(a.profiles)
    done = os.path.join(a.profiles, "done.txt")
    n_blocks = len(open(done).read().split()) if os.path.exists(done) else 0
    tchunks = ds["u"].data.chunks[1]  # (point, time, height)
    block = tchunks[0]
    if n_blocks < len(tchunks):
        raise SystemExit(f"profile store incomplete ({n_blocks}/{len(tchunks)} blocks); run to_heights first")

    times = pd.DatetimeIndex(ds.time.values)
    lat, lon, elev = ds.lat.values, ds.lon.values, ds.z_sfc.values
    sh = solar_hour(times, lon)
    keep = (sh >= 6) & (sh <= 21) & ((times.year >= a.first_year) & (times.year <= a.last_year))[None, :]
    rng = np.random.default_rng(a.seed)
    sel = keep & (rng.random(keep.shape, dtype=np.float32) < min(1.0, a.rows / keep.sum()))
    n = int(sel.sum())
    print(f"{keep.sum():,} eligible rows, keeping {n:,}", flush=True)

    tbl = indices.load(a.indices)
    gm = indices.gmst_table(a.indices) if a.features == "p2" else None
    cond = np.empty((n, len(FEATURES)), np.float32)
    target = np.empty((n, 4 * len(HEIGHTS) + len(SURFACE)), np.float32)
    year = np.empty(n, np.int16)
    prov = dict(point=np.empty(n, np.int32), time=np.empty(n, "datetime64[h]"), group=np.full(n, -1, np.int16))
    r = 0
    for i0 in range(0, len(times), block):
        s = sel[:, i0:i0 + block]
        p, t = np.nonzero(s)
        if len(p) == 0:
            continue
        b = ds.isel(time=slice(i0, i0 + block)).load()
        tt = times[i0 + t]
        diffs = np.stack([to_diff(b[v].values[p, t]) for v in PROFILE], 1)  # (n, variable, height)
        gid = None
        if qm is not None:
            diffs, gid = station.correct(qm, diffs, lat[p], lon[p], tt.month.to_numpy(), sh[p, i0 + t], crng, blend=a.station_blend, return_group=True)
        sfc = [b[v].values[p, t][:, None] for v in SURFACE]
        if a.rh_target == "dpd":  # humidity coordinate ln(T - Td + 1): on the levels (after the station correction), then back to steps
            lev = from_diff(diffs)
            i_t, i_rh = PROFILE.index("T"), PROFILE.index("RH")
            lev[:, i_rh] = dpd_from_rh(lev[:, i_t].astype(np.float64), lev[:, i_rh].astype(np.float64))
            diffs = to_diff(lev)
            sfc[SURFACE.index("rh2m")] = dpd_from_rh(sfc[SURFACE.index("t2m")].astype(np.float64), sfc[SURFACE.index("rh2m")].astype(np.float64))
        prof = np.concatenate([diffs.reshape(len(p), -1)] + sfc, axis=1)
        oni, qbo30, qbo50, wwv = indices.at(tbl, tt).T
        k = slice(r, r + len(p))
        cond[k] = features(lat[p], lon[p], elev[p], elev[p], tt.dayofyear.to_numpy(), sh[p, i0 + t],
                           tt.year.to_numpy(), oni, wwv, qbo30, qbo50,
                           **indices.feature_extras(FEATURES, tbl, gm, tt))
        target[k], year[k] = prof, tt.year.to_numpy()
        prov["point"][k], prov["time"][k] = p, tt.to_numpy().astype("datetime64[h]")
        if gid is not None:
            prov["group"][k] = gid
        r += len(p)
        print(f"{tt[0].date()}: {r:,}/{n:,} rows", flush=True)

    ok = np.isfinite(target).all(1) & np.isfinite(cond).all(1)
    print(f"dropping {(~ok).sum():,} rows with missing values (profile top above 50 hPa, or index gaps)", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    extra = {}
    if a.sidecar:
        extra = dict(row_point=prov["point"][ok], row_time=prov["time"][ok], row_group=prov["group"][ok],
                     correction=np.array(f"station-map {os.path.basename(a.station_map or 'none')}, blend={a.station_blend}"))
    np.savez(a.out, cond=cond[ok], target=target[ok], year=year[ok],
             cond_names=np.array(FEATURES), target_names=np.array(target_names()), rh_target=np.array(a.rh_target), **extra)
    print(f"wrote {a.out}: {ok.sum():,} rows, {target.shape[1]} targets", flush=True)


if __name__ == "__main__":
    main()
