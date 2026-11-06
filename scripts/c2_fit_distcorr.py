"""Group C, C2 (IL-36): downrange coherence. Correlation of the standardised anomalies of the 176 profile columns between two grid points as a function of their distance (km), per season, from ERA5
at 45 points of the box (5 latitude rows x 9 longitudes, 3-hourly 2005-2022; out-of-sample 2023-2025). Distance bins: 0 (same point), then the pair separations of the 0.25 degree grid up to 60 km
(about 24 / 28 / 37 / 48 / 55 / 59 km). Anomaly = (value - mean) / sd of the same point, month, hour of day over the fit years.
    PYTHONPATH=. python scripts/c2_fit_distcorr.py     -> models/coherence_distcorr.npz"""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.profiles.to_heights import PROFILE

PROFILES = "data/pilot/profiles80.zarr"
ROWS, COLS = range(4, 9), range(6, 15)
KM_LAT, STEP = 111.0, 0.25


def load(ds, pts, y0, y1):
    sub = ds.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31 21:00")).isel(point=pts)
    keep = np.flatnonzero(pd.DatetimeIndex(sub.time.values).hour % 3 == 0)
    sub = sub.isel(time=keep)
    x = np.concatenate([sub[v].values for v in PROFILE], axis=2).astype(np.float32)
    return pd.DatetimeIndex(sub.time.values), x


def anomalies(times, x, clim=None):
    key = times.month.to_numpy() * 24 + times.hour.to_numpy()
    if clim is None:
        mean, sd = np.zeros((len(x), 400, x.shape[2]), np.float32), np.ones((len(x), 400, x.shape[2]), np.float32)
        for k in np.unique(key):
            sel = key == k
            mean[:, k], sd[:, k] = x[:, sel].mean(1), x[:, sel].std(1) + 1e-6
        clim = (mean, sd)
    return (x - clim[0][:, key]) / clim[1][:, key], clim


def pair_corr(times, z, lat, lon, bins):
    season = ((times.month.to_numpy() % 12) // 3)
    P = len(lat)
    dist = np.hypot((lat[:, None] - lat[None]) * KM_LAT, (lon[:, None] - lon[None]) * KM_LAT * np.cos(np.radians(lat.mean())))
    rho = np.zeros((4, len(bins), z.shape[2]))
    for s in range(4):
        m = season == s
        zs = z[:, m]
        zc = (zs - zs.mean(1, keepdims=True)) / (zs.std(1, keepdims=True) + 1e-9)
        for bi, d in enumerate(bins):
            sel = np.argwhere(np.triu(np.abs(dist - d) < 2.0, 1)) if d > 0 else np.stack([np.arange(P), np.arange(P)], 1)
            if len(sel) == 0:
                rho[s, bi] = np.nan
                continue
            rho[s, bi] = np.mean([ (zc[i] * zc[j]).mean(0) for i, j in sel], axis=0)
    return rho, dist


def main():
    ds = xr.open_zarr(PROFILES)
    n_lon = 29
    pts = [r * n_lon + c for r in ROWS for c in COLS]
    lat, lon = ds.lat.values[pts], ds.lon.values[pts]
    d = np.hypot((lat[:, None] - lat[None]) * KM_LAT, (lon[:, None] - lon[None]) * KM_LAT * np.cos(np.radians(lat.mean())))
    cand = np.unique(np.round(d[np.triu_indices(len(pts), 1)]))
    bins = [0.0] + sorted({float(round(x)) for x in cand if 0 < x <= 62 and any(abs(x - y) < 1 for y in cand)})
    # merge near-equal separations: keep the distinct pair separations of the grid
    bins = [0.0, 24.0, 28.0, 34.0, 37.0, 48.0, 55.0, 59.0]
    print("points", len(pts), "bins (km)", bins, flush=True)
    t, x = load(ds, pts, 2005, 2022)
    z, clim = anomalies(t, x)
    rho, _ = pair_corr(t, z, lat, lon, bins)
    t2, x2 = load(ds, pts, 2023, 2025)
    z2, _ = anomalies(t2, x2, clim)
    rho2, _ = pair_corr(t2, z2, lat, lon, bins)
    nh = 44
    for v, name in enumerate(PROFILE):
        s = slice(v * nh, (v + 1) * nh)
        print(f"{name:>3}: rho at ~24 / 37 / 48 / 59 km (fit) {np.nanmean(rho[:, 1, s]):.3f}/{np.nanmean(rho[:, 4, s]):.3f}/{np.nanmean(rho[:, 5, s]):.3f}/{np.nanmean(rho[:, 7, s]):.3f}   mean |fit - 2023-25| {np.nanmean(np.abs(rho - rho2)[:, :, s]):.3f}  max {np.nanmax(np.abs(rho - rho2)[:, :, s]):.3f}", flush=True)
    keep = [i for i in range(len(bins)) if not np.isnan(rho[:, i]).any()]               # a separation that does not occur between the grid points has no pairs: drop it
    bins, rho, rho2 = [bins[i] for i in keep], rho[:, keep], rho2[:, keep]
    np.savez("models/coherence_distcorr.npz", rho=rho.astype(np.float32), km=np.array(bins), rho_2023_25=rho2.astype(np.float32), fit_years="2005-2022")
    print("wrote models/coherence_distcorr.npz")


if __name__ == "__main__":
    main()
