"""ERA5 pressure levels + surface anchors -> profiles on fixed heights above ground.

    python -m tempest.profiles.to_heights [--raw data/raw/era5_em] [--cds data/raw/era5_cds] [--out data/pilot/profiles.zarr]

If --cds holds monthly <yyyymm>.grib files from fetch_cds, their 8 boundary-layer levels (975-750 hPa) are added
to the 13 Earthmover levels (21 in all). Months without a file get NaN there, which interpolation skips.

Output dims (point, time, height): u, v, T (K), RH (%), plus surface t2m, sp, rh2m, u10, v10 and per-point
lat, lon (-180..180), z_sfc (m). Kept UTC hours: 12-23 and 00-04 (every pilot-box point's solar 06-21 h, plus
the 00Z/12Z radiosonde times); the exact solar window is applied when building the training set.
Processed one store time-chunk (364 days) at a time; finished blocks are recorded in done.txt, so reruns resume.
"""
import argparse
import os

import numpy as np
import pandas as pd

HEIGHTS = np.array([10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000]
                   + list(range(2500, 18001, 500)), dtype=np.float32)
assert len(HEIGHTS) == 44
UTC_HOURS = list(range(12, 24)) + list(range(0, 5))
G0, R_EARTH = 9.80665, 6371000.0
PROFILE = ["u", "v", "T", "RH"]
SURFACE = ["t2m", "sp", "rh2m", "u10", "v10"]
CDS_LEVELS = [975, 950, 900, 875, 825, 800, 775, 750]


def parse_hours(spec):
    """'12-23,0-4' -> [12..23, 0..4] (UTC hours, in that order); 'all' -> 0..23."""
    if spec == "all":
        return list(range(24))
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    assert out and len(set(out)) == len(out) and all(0 <= h < 24 for h in out), spec
    return out


assert parse_hours("12-23,0-4") == UTC_HOURS and parse_hours("5-11") == list(range(5, 12))


def geometric_height(z):
    """Geopotential (m2/s2) -> geometric height (m)."""
    zh = z / G0
    return R_EARTH * zh / (R_EARTH - zh)


def magnus_rh(t, td):
    """RH (%) from temperature and dewpoint (K)."""
    t, td = t - 273.15, td - 273.15
    return 100 * np.exp(17.625 * td / (243.04 + td) - 17.625 * t / (243.04 + t))


def liquid_rh(t, r):
    """ERA5 RH (%, IFS: over a water/ice mix below 0 C, all ice below -23 C) -> RH over liquid water, as balloons
    (IGRA) report it. Checked on 2023-25 soundings: removes the ERA5-vs-balloon bias above 5 km (-8..-16 % -> ~-1 %)."""
    es_l = 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))
    es_i = 611.21 * np.exp(22.587 * (t - 273.16) / (t + 0.7))
    a = np.clip((t - 250.16) / 23.0, 0, 1) ** 2
    return r * (a * es_l + (1 - a) * es_i) / es_l


def interp_columns(h, x, targets, log_below=None):
    """Interpolate every column (last axis = levels) of x at heights h onto `targets`.

    h may hold NaN (unusable level) and need not be sorted. Targets outside a column's valid range -> NaN.
    Targets below `log_below` are interpolated linearly in ln(height), the rest linearly in height.
    """
    h = np.where(np.isfinite(h) & np.isfinite(x), h, np.inf)
    order = np.argsort(h, axis=-1)
    h, x = np.take_along_axis(h, order, -1), np.take_along_axis(x, order, -1)
    n_valid = np.isfinite(h).sum(-1, keepdims=True)
    out = np.full(h.shape[:-1] + (len(targets),), np.nan, np.float32)
    for j, t in enumerate(targets):
        k = (h <= t).sum(-1, keepdims=True) - 1          # last level at or below t
        ok = (k >= 0) & (k + 1 < n_valid)
        k0, k1 = np.clip(k, 0, h.shape[-1] - 2), np.clip(k + 1, 1, h.shape[-1] - 1)
        h0, h1 = np.take_along_axis(h, k0, -1), np.take_along_axis(h, k1, -1)
        x0, x1 = np.take_along_axis(x, k0, -1), np.take_along_axis(x, k1, -1)
        with np.errstate(invalid="ignore", divide="ignore"):
            if log_below is not None and t < log_below:
                w = (np.log(t) - np.log(h0)) / (np.log(h1) - np.log(h0))
            else:
                w = (t - h0) / (h1 - h0)
        exact = (h0 == t) & (k >= 0)
        val = np.where(exact, x0, x0 + w * (x1 - x0))
        out[..., j] = np.where(ok | exact, val, np.nan)[..., 0]
    return out


def top_valid(x):
    """(..., 44) profile -> index of the highest finite height (-1 if none); heights above it are what fill_top fills."""
    ok = np.isfinite(x)
    return np.where(ok.any(-1), x.shape[-1] - 1 - np.argmax(ok[..., ::-1], -1), -1)


def fill_top(x):
    """(..., 44) profile -> copy whose NaN heights ABOVE the highest valid one take that value (u, v, RH constant, T
    isothermal). Mountain columns (ground > ~2.6 km) put the 18 km-AGL top above the 50 hPa level, so these heights
    were NaN and build_dataset dropped the whole row (Denver build: 934,359 of 4.0 M rows; Gemini review 2026-11-06).
    shortcut: isothermal T is ~1 K/km too cold in the lower stratosphere (<= ~3 K at 18 km AGL over 5 km ground);
    upgrade to a fitted stratospheric lapse rate if the global G4 upper-T bands show it."""
    x = np.array(x, dtype=np.float32, copy=True)
    top = top_valid(x)
    above = (np.arange(x.shape[-1]) > top[..., None]) & (top[..., None] >= 0)
    val = np.take_along_axis(x, np.clip(top, 0, None)[..., None], -1)
    return np.where(above, val, x)


assert np.allclose(fill_top(np.array([[1, 2, np.nan, np.nan], [1, np.nan, 3, 4], [np.nan] * 4])),  # top filled; interior gap and all-NaN left alone
                   [[1, 2, 2, 2], [1, np.nan, 3, 4], [np.nan] * 4], equal_nan=True)


def profiles_from_levels(z, u, v, t, r, z_sfc, u10, v10, u100, v100, t2m, d2m):
    """Arrays (..., L) on pressure levels and (...) surface fields -> dict of (..., 44) profiles.

    Pressure levels at or below the ground are dropped. Wind below 100 m comes from the 10/100 m anchors only.
    """
    agl = geometric_height(z) - geometric_height(z_sfc)[..., None]
    agl = np.where(agl > 0, agl, np.nan)
    agl_w = np.where(agl > 100, agl, np.nan)                 # pressure-level winds only above the 100 m anchor
    shape = agl.shape[:-1] + (1,)
    hw = np.concatenate([np.full(shape, 10.0), np.full(shape, 100.0), agl_w], -1)
    ht = np.concatenate([np.full(shape, 2.0), agl], -1)
    rh2m = np.clip(magnus_rh(t2m, d2m), 0, 100)
    return dict(
        u=interp_columns(hw, np.concatenate([u10[..., None], u100[..., None], u], -1), HEIGHTS, 100),
        v=interp_columns(hw, np.concatenate([v10[..., None], v100[..., None], v], -1), HEIGHTS, 100),
        T=interp_columns(ht, np.concatenate([t2m[..., None], t], -1), HEIGHTS),
        # ERA5 RH is over ice when cold; balloons use liquid water. Clipped: past 100 % barely moves air density
        RH=interp_columns(ht, np.concatenate([rh2m[..., None], np.clip(liquid_rh(t, r), 0, 100)], -1), HEIGHTS),
    ), rh2m


def open_raw(raw):
    import xarray as xr
    names = ["u", "v", "t", "r", "z", "u10", "v10", "u100", "v100", "t2m", "d2m", "sp"]
    return xr.merge([xr.open_zarr(os.path.join(raw, f"{n}.zarr")) for n in names], compat="override")


def cds_levels(cds, times, lat, lon):
    import xarray as xr
    """CDS fill for `times` on the (lat, lon) grid (lon 0-360) -> dict u, v, t, r, z of (lat, lon, time, 8) float32.
    NaN where a month's grib is missing."""
    times = pd.DatetimeIndex(times)
    out = {n: np.full((len(lat), len(lon), len(times), len(CDS_LEVELS)), np.nan, np.float32) for n in "uvtrz"}
    months = times.strftime("%Y%m")
    for ym in np.unique(months):
        path = os.path.join(cds, f"{ym}.grib")
        nc = os.path.join(cds, f"{ym}.nc")                       # same fill written by tempest.ingest.arco_fill (ARCO-ERA5), used when no grib exists
        if not os.path.exists(path) and not os.path.exists(nc):
            continue
        k = months == ym
        opener = dict(engine="cfgrib", backend_kwargs={"indexpath": ""}) if os.path.exists(path) else {}
        with xr.open_dataset(path if os.path.exists(path) else nc, **opener) as g:
            g = g.assign_coords(longitude=g.longitude % 360)
            g = g.sel(isobaricInhPa=CDS_LEVELS, latitude=lat, longitude=lon, time=times[k].values)  # exact; KeyError if off-grid
            for n in out:
                out[n][:, :, k] = g[n].transpose("latitude", "longitude", "time", "isobaricInhPa").values
    return out


def main():
    import dask.array as da
    import xarray as xr
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw/era5_em")
    ap.add_argument("--cds", default="data/raw/era5_cds")
    ap.add_argument("--out", default="data/pilot/profiles.zarr")
    ap.add_argument("--hours", default="12-23,0-4", help="UTC hours to keep, e.g. 5-11 (the night hours the default leaves out) or all")
    ap.add_argument("--last-year", type=int, help="leave out later years (e.g. 2025: no 2026 holdout data in the store)")
    a = ap.parse_args()
    hours = parse_hours(a.hours)

    ds = open_raw(a.raw)
    ds = ds.sel(valid_time=ds.valid_time.dt.hour.isin(hours) & (ds.valid_time.dt.year <= (a.last_year or 9999)))
    use_cds = os.path.isdir(a.cds) and any(f.endswith((".grib", ".nc")) for f in os.listdir(a.cds))
    if use_cds:
        have = {f[:6] for f in os.listdir(a.cds) if f.endswith((".grib", ".nc"))}
        need = set(pd.DatetimeIndex(ds.valid_time.values).strftime("%Y%m"))
        missing = sorted(m for m in need if m not in have and m >= "199101")  # CDS fill starts 1991; late 1990 is trimmed later
        print(f"CDS fill: {len(have)} months, {len(missing)} missing (those keep 13 levels)", flush=True)
    lat2, lon2 = np.meshgrid(ds.latitude.values, ds.longitude.values, indexing="ij")
    lat, lon = lat2.ravel(), ((lon2.ravel() + 180) % 360) - 180
    z_sfc = ds.z_sfc.values.ravel()
    n_pt, n_t = len(lat), ds.sizes["valid_time"]
    block = 364 * len(hours)                                 # one store time-chunk after the hour filter

    if not os.path.exists(a.out):
        p3, p2 = (29, block, 44), (29, block)
        template = xr.Dataset(
            {**{k: (("point", "time", "height"), da.zeros((n_pt, n_t, 44), np.float32, chunks=p3)) for k in PROFILE},
             **{k: (("point", "time"), da.zeros((n_pt, n_t), np.float32, chunks=p2)) for k in SURFACE}},
            coords=dict(point=np.arange(n_pt), time=ds.valid_time.values, height=HEIGHTS,
                        lat=("point", lat), lon=("point", lon), z_sfc=("point", geometric_height(z_sfc))),
        )
        template.to_zarr(a.out, compute=False, mode="w", zarr_format=3)
    done_path = os.path.join(a.out, "done.txt")
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()

    for i0 in range(0, n_t, block):
        if str(i0) in done:
            continue
        b = ds.isel(valid_time=slice(i0, i0 + block)).load()
        # -> (point, time, level) / (point, time)
        em = lambda n: b[n].transpose("latitude", "longitude", "valid_time", "pressure_level").values.reshape(n_pt, -1, b.sizes["pressure_level"])
        if use_cds:
            fill = cds_levels(a.cds, b.valid_time.values, b.latitude.values, b.longitude.values)
            lv = lambda n: np.concatenate([em(n), fill[n].reshape(n_pt, -1, len(CDS_LEVELS))], -1)
        else:
            lv = em
        sf = lambda n: b[n].transpose("latitude", "longitude", "valid_time").values.reshape(n_pt, -1)
        prof, rh2m = profiles_from_levels(lv("z"), lv("u"), lv("v"), lv("t"), lv("r"), np.broadcast_to(z_sfc[:, None], (n_pt, b.sizes["valid_time"])),
                                          sf("u10"), sf("v10"), sf("u100"), sf("v100"), sf("t2m"), sf("d2m"))
        out = xr.Dataset({**{k: (("point", "time", "height"), prof[k]) for k in PROFILE},
                          "t2m": (("point", "time"), sf("t2m")), "sp": (("point", "time"), sf("sp")),
                          "rh2m": (("point", "time"), rh2m.astype(np.float32)),
                          "u10": (("point", "time"), sf("u10")), "v10": (("point", "time"), sf("v10"))})
        out.to_zarr(a.out, region={"point": slice(None), "time": slice(i0, i0 + b.sizes["valid_time"]), "height": slice(None)})
        with open(done_path, "a") as f:
            f.write(f"{i0}\n")
        print(f"block {i0 // block + 1}/{-(-n_t // block)}: {str(b.valid_time.values[0])[:10]}", flush=True)


if __name__ == "__main__":
    main()
