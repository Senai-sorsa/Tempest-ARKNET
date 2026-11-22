"""Vertical wind (w) targets for the rows of a generator dataset (PHASED_PLAN 3.2).

    python -m tempest.generator.build_wdata --data data/train/pilot80_dpd.npz --out data/train/pilot80_w.npz
                                            [--profiles data/pilot/profiles80.zarr] [--w data/raw/era5_em/w.zarr]

build_dataset draws its rows with a seeded random mask; this script replays the SAME draw (same arguments as the
dataset build: rows 8,000,000, seed 0, years 1980-2026) so each dataset row can be matched to its grid point and time,
checks the match against the dataset's year and latitude, and for each row computes w (m/s, up positive) on the 44
heights above ground from ERA5's pressure velocity omega (Pa/s) on the 13 pressure levels:
    w = -omega / (rho g),   rho and the pressure at each height from profiles.thermo (the row's own T, RH, sp).
omega is interpolated linearly in pressure to the pressure of each height; levels at or below the ground are replaced
by omega = 0 at the surface (flat-ground assumption). Rows before the w record starts (1990-10-29) get NaN.
Output npz: w (N, 44) float32 aligned with the dataset rows (NaN = no w).
"""
import argparse
import os

import numpy as np
import pandas as pd
import xarray as xr

from tempest.generator.build_dataset import solar_hour
from tempest.generator.train import load_npz
from tempest.profiles import thermo
from tempest.profiles.to_heights import HEIGHTS

G0 = 9.80665


def omega_to_w(omega, level_pa, sp, p_target, rho):
    """omega (n, L) Pa/s at ascending pressure levels level_pa (L,), surface pressure sp (n,), target pressures p_target
    (n, H) and densities rho (n, H) -> w (n, H) m/s. Levels within 10 hPa of the ground or below are set to omega = 0 at
    the surface."""
    n, L = omega.shape
    lv = np.broadcast_to(level_pa[None, :].astype(np.float64), (n, L))
    under = lv >= (sp[:, None] - 1000.0)
    p_eff = np.where(under, sp[:, None], lv) + np.arange(L)[None, :] * 1e-3   # stay strictly ascending
    w_eff = np.where(under, 0.0, omega)
    p_all = np.concatenate([p_eff, (sp + 1.0)[:, None]], 1)                    # ground level, omega = 0
    w_all = np.concatenate([w_eff, np.zeros((n, 1))], 1)
    idx = np.clip((p_all[:, None, :] <= p_target[:, :, None]).sum(-1) - 1, 0, p_all.shape[1] - 2)
    p0, p1 = np.take_along_axis(p_all, idx, 1), np.take_along_axis(p_all, idx + 1, 1)
    w0, w1 = np.take_along_axis(w_all, idx, 1), np.take_along_axis(w_all, idx + 1, 1)
    om = w0 + (w1 - w0) * np.clip((p_target - p0) / np.maximum(p1 - p0, 1e-6), 0, 1)
    return -om / (rho * G0)


def row_times(cond, year=None):
    """IL-177: each dataset row's grid point time in UTC from its own features: the day of year (UTC date, sin / cos at 365.25 d; day 366 wraps to about 0.75 and is mapped back),
    the year (from `cond` or the `year` array for P2 datasets without a year feature) and the solar hour minus lon / 15 (rounded to the whole UTC hour). -> pandas DatetimeIndex (naive UTC)."""
    from tempest.generator.features import FEATURES
    c = {k: np.asarray(cond[:, FEATURES.index(k)], np.float64) for k in ("doy_sin", "doy_cos", "hour_sin", "hour_cos", "lon")}
    if year is not None:
        yr = np.asarray(year, np.float64)
    elif "year" in FEATURES:
        yr = np.asarray(cond[:, FEATURES.index("year")], np.float64)
    else:
        raise ValueError("row_times needs a `year` feature in cond or an explicit `year` array (P2 datasets)")
    d = (np.arctan2(c["doy_sin"], c["doy_cos"]) % (2 * np.pi)) * 365.25 / (2 * np.pi)
    d = np.where(d < 0.9, d + 365.25, d)
    doy = np.rint(d).astype(np.int64)
    sh = (np.arctan2(c["hour_sin"], c["hour_cos"]) % (2 * np.pi)) * 24.0 / (2 * np.pi)
    hu = np.rint((sh - c["lon"] / 15.0) % 24.0).astype(np.int64) % 24
    base = (np.rint(yr).astype(np.int64) - 1970).astype("datetime64[Y]").astype("datetime64[h]")
    return pd.DatetimeIndex(base + ((doy - 1) * 24 + hu).astype("timedelta64[h]"))


def from_cond(a):
    """IL-177 (2026-11-10): w for ANY dataset (the joined all-hours files have no row provenance and cannot be replayed): grid point from the row's lat / lon, UTC time from row_times,
    T / RH / sp / t2m / rh2m from the row's own target (what the store holds for that hour), omega from the store, the same omega -> w physics. Rows in time order, in blocks."""
    d = load_npz(a.data)                                                   # audit #8: activates the dataset's own inputs and humidity target (a dpd file read as RH biased w)
    from tempest.generator.features import FEATURES
    from tempest.generator.sample import to_physical
    from tempest.profiles.to_heights import PROFILE
    cond, target = d["cond"], d["target"]
    N = len(cond)
    lat_r = np.asarray(cond[:, FEATURES.index("lat")], np.float64)
    lon_r = np.asarray(cond[:, FEATURES.index("lon")], np.float64)
    elev_r = np.asarray(cond[:, FEATURES.index("elev_grid")], np.float64)
    tt = row_times(np.asarray(cond), year=np.asarray(d["year"]) if "year" in d else None)
    wz = xr.open_zarr(a.w, zarr_format=3)["w"]
    wt = pd.DatetimeIndex(wz.valid_time.values)
    levels = wz.pressure_level.values.astype(float) * 100.0
    order = np.argsort(levels)
    levels = levels[order]
    glat, glon = wz.latitude.values, np.where(wz.longitude.values > 180, wz.longitude.values - 360, wz.longitude.values)
    pi_ = np.abs(glat[None, :] - lat_r[:, None]).argmin(1)
    pj_ = np.abs(glon[None, :] - lon_r[:, None]).argmin(1)
    assert np.abs(glat[pi_] - lat_r).max() < 1e-3 and np.abs(glon[pj_] - lon_r).max() < 1e-3, "rows off the omega grid"
    tw = wt.get_indexer(tt)
    srt = np.argsort(tw, kind="stable")
    out = np.full((N, len(HEIGHTS)), np.nan, np.float32)
    NH = len(HEIGHTS)
    iT, iR = PROFILE.index("T") * NH, PROFILE.index("RH") * NH
    step = a.block_rows
    for b0 in range(0, N, step):
        rows = srt[b0:b0 + step]
        rows = rows[tw[rows] >= 0]
        if not len(rows):
            continue
        lo, hi = int(tw[rows].min()), int(tw[rows].max()) + 1
        om = wz.isel(valid_time=slice(lo, hi)).values[:, order][tw[rows] - lo, :, pi_[rows], pj_[rows]].astype(np.float64)
        x = to_physical(np.asarray(target[np.sort(rows)]))
        x = x[np.argsort(np.argsort(rows))]                                       # back to the order of `rows`
        T, RH = x[:, iT:iT + NH].astype(np.float64), x[:, iR:iR + NH].astype(np.float64)
        t2m, sp, rh2m = (x[:, 4 * NH + k].astype(np.float64) for k in range(3))
        ok = np.isfinite(T).all(1) & np.isfinite(RH).all(1) & np.isfinite(sp) & np.isfinite(om).all(1)
        if ok.any():
            th = thermo.column(HEIGHTS, T[ok], RH[ok], sp[ok], t_sfc=t2m[ok], rh_sfc=rh2m[ok], z_sfc=elev_r[rows][ok])
            out[rows[ok]] = omega_to_w(om[ok], levels, sp[ok], th["p"], th["rho"]).astype(np.float32)
        print(f"{b0 + len(rows):,}/{N:,} rows ({str(tt[rows[-1]])[:10]})", flush=True)
    np.savez(a.out, w=out)
    print(f"wrote {a.out}: {out.shape}, {np.isfinite(out).all(1).mean():.1%} rows with w (rows before the w record, 1990-10-29, have none)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/train/pilot80_dpd.npz")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--w", default="data/raw/era5_em/w.zarr")
    ap.add_argument("--out", default="data/train/pilot80_w.npz")
    ap.add_argument("--rows", type=int, default=8_000_000)
    ap.add_argument("--first-year", type=int, default=1980)
    ap.add_argument("--last-year", type=int, default=2026)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--from-cond", action="store_true", help="IL-177: build w for any dataset from its own rows (times from the features) instead of replaying the day file's draw")
    ap.add_argument("--block-rows", type=int, default=200_000, help="with --from-cond: rows per time-sorted block")
    a = ap.parse_args()
    if a.from_cond:
        return from_cond(a)
    d = load_npz(a.data)
    from tempest.generator.features import FEATURES
    cond = d["cond"]
    ds_sig = np.stack([np.asarray(cond[:, FEATURES.index(k)], np.float64) for k in ("lat", "doy_sin", "hour_sin")], 1)
    ds_year = np.asarray(d["year"])
    ds = xr.open_zarr(a.profiles)
    times = pd.DatetimeIndex(ds.time.values)
    lat, lon, elev = ds.lat.values, ds.lon.values, ds.z_sfc.values
    sh = solar_hour(times, lon)
    keep = (sh >= 6) & (sh <= 21) & ((times.year >= a.first_year) & (times.year <= a.last_year))[None, :]
    sel = keep & (np.random.default_rng(a.seed).random(keep.shape, dtype=np.float32) < min(1.0, a.rows / keep.sum()))
    n = int(sel.sum())
    wz = xr.open_zarr(a.w, zarr_format=3)["w"]
    wt = pd.DatetimeIndex(wz.valid_time.values)
    levels = wz.pressure_level.values.astype(float) * 100.0
    order = np.argsort(levels)
    levels = levels[order]
    glat, glon = wz.latitude.values, np.where(wz.longitude.values > 180, wz.longitude.values - 360, wz.longitude.values)
    pt_i = np.array([int(np.argmin(np.abs(glat - la))) for la in lat])
    pt_j = np.array([int(np.argmin(np.abs(glon - lo))) for lo in lon])
    block = ds["u"].data.chunks[1][0]
    out = np.full((n, len(HEIGHTS)), np.nan, np.float32)
    yrs, sig = np.empty(n, np.int16), np.empty((n, 3), np.float64)
    r = 0
    for i0 in range(0, len(times), block):
        p, t = np.nonzero(sel[:, i0:i0 + block])
        if len(p) == 0:
            continue
        tt = times[i0 + t]
        k = slice(r, r + len(p))
        yrs[k] = tt.year
        sig[k] = np.stack([lat[p], np.sin(2 * np.pi * tt.dayofyear.to_numpy() / 365.25), np.sin(2 * np.pi * sh[p, i0 + t] / 24.0)], 1)
        tw = wt.get_indexer(tt)
        have = tw >= 0
        if have.any():
            b = ds.isel(time=slice(i0, i0 + block))
            ti = t[have]
            T, RH = (b[v].values[p[have], ti] for v in ("T", "RH"))
            sp, t2m, rh2m = (b[v].values[p[have], ti].astype(np.float64) for v in ("sp", "t2m", "rh2m"))
            lo, hi = tw[have].min(), tw[have].max() + 1
            om = wz.isel(valid_time=slice(lo, hi)).values[:, order][tw[have] - lo, :, pt_i[p[have]], pt_j[p[have]]]  # (m, 13)
            ok = np.isfinite(T).all(1) & np.isfinite(RH).all(1) & np.isfinite(sp) & np.isfinite(om).all(1)
            res = np.full((int(have.sum()), len(HEIGHTS)), np.nan, np.float32)
            if ok.any():
                th = thermo.column(HEIGHTS, T[ok].astype(np.float64), RH[ok].astype(np.float64), sp[ok], t_sfc=t2m[ok], rh_sfc=rh2m[ok], z_sfc=elev[p[have]][ok])
                res[ok] = omega_to_w(om[ok].astype(np.float64), levels, sp[ok], th["p"], th["rho"]).astype(np.float32)
            blockw = out[k]
            blockw[have] = res
        r += len(p)
        print(f"{times[i0].date()}: {r:,}/{n:,} rows", flush=True)
    # align with the dataset: it dropped the few rows whose targets or inputs were not finite; walk both sequences
    match = lambda i, j: yrs[i] == ds_year[j] and np.all(np.abs(sig[i] - ds_sig[j]) < 2e-4)
    keep_rows, i, j = np.zeros(n, bool), 0, 0
    while i < n and j < len(ds_year):
        if match(i, j):
            keep_rows[i] = True
            j += 1
        i += 1
    if j != len(ds_year):
        raise SystemExit(f"could not align the replayed rows with the dataset (matched {j:,} of {len(ds_year):,})")
    print(f"{n - len(ds_year)} replayed rows were dropped by the dataset build", flush=True)
    out = out[keep_rows]
    np.savez(a.out, w=out)
    print(f"wrote {a.out}: {out.shape}, {np.isfinite(out).all(1).mean():.1%} rows with w")


if __name__ == "__main__":
    main()
