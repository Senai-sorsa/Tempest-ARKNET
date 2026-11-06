"""Group C, C1 (IL-35): hourly coherence. Lag correlation of the standardised hourly anomalies of the 176 profile columns, per season, for lags 0..9 hours, from ERA5 at 8 grid points
(the two sites and six spread over the box).

Anomaly = (value - mean) / sd of the same point, month, hour of day over the fit years; the lag-tau correlation pairs hour t with hour t+tau of the same day sequence.
Fit years 2005-2022 (out-of-sample check: 2023-2025). Writes models/coherence_lagcorr.npz: rho (4 seasons, 10 lags, 176 columns), n pairs, fit years.
    PYTHONPATH=. python scripts/c1_fit_lagcorr.py"""
import numpy as np
import pandas as pd
import xarray as xr

from tempest.profiles.to_heights import PROFILE

PROFILES = "data/pilot/profiles80.zarr"
WANT = [(31.94, -102.19), (32.99, -106.97), (32.5, -104.5), (33.5, -103.0), (31.5, -105.0), (33.75, -101.5), (32.0, -107.5), (33.0, -102.0)]
LAGS = 13


def load(ds, pts, y0, y1):
    sub = ds.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31 23:00")).isel(point=pts)
    x = np.concatenate([sub[v].values for v in PROFILE], axis=2).astype(np.float32)      # (pt, T, 176)
    return pd.DatetimeIndex(sub.time.values), x


def anomalies(times, x, clim=None):
    key = times.month.to_numpy() * 24 + times.hour.to_numpy()
    if clim is None:
        mean, sd = np.zeros((len(x), 400, x.shape[2])), np.ones((len(x), 400, x.shape[2]))
        for k in np.unique(key):
            sel = key == k
            mean[:, k], sd[:, k] = x[:, sel].mean(1), x[:, sel].std(1) + 1e-6
        clim = (mean, sd)
    mean, sd = clim
    return (x - mean[:, key]) / sd[:, key], clim


def lag_corr(times, z):
    """z (pt, T, D) -> rho (4 seasons, LAGS, D), n pairs (4, LAGS)"""
    season = ((times.month.to_numpy() % 12) // 3)
    contiguous = np.r_[True, np.diff(times.asi8) == 3600 * 10 ** 9]
    rho, cnt = np.zeros((4, LAGS, z.shape[2])), np.zeros((4, LAGS))
    for tau in range(LAGS):
        a, b = z[:, : len(times) - tau], z[:, tau:]
        ok = np.ones(len(times) - tau, bool)
        if tau:
            ok = np.array([contiguous[i + 1:i + tau + 1].all() for i in range(len(times) - tau)]) if False else (times.asi8[tau:] - times.asi8[:-tau] == tau * 3600 * 10 ** 9)
        for s in range(4):
            m = ok & (season[: len(times) - tau] == s)
            am, bm = a[:, m], b[:, m]                                       # Pearson correlation inside the period: a trend or a shifted mean in the period must not count as correlation
            rho[s, tau] = ((am * bm).mean((0, 1)) - am.mean((0, 1)) * bm.mean((0, 1))) / (am.std((0, 1)) * bm.std((0, 1)) + 1e-9)
            cnt[s, tau] = m.sum() * len(z)
    return rho, cnt


def main():
    ds = xr.open_zarr(PROFILES)
    la, lo = ds.lat.values, ds.lon.values
    pts = sorted({int(np.argmin((la - a) ** 2 + (lo - b) ** 2)) for a, b in WANT})
    print("points", pts, flush=True)
    t, x = load(ds, pts, 2005, 2022)
    z, clim = anomalies(t, x)
    rho, cnt = lag_corr(t, z)
    print("fit pairs per season at lag 3:", cnt[:, 3].astype(int), flush=True)
    t2, x2 = load(ds, pts, 2023, 2025)
    z2, _ = anomalies(t2, x2, clim)                      # same climatology: an honest out-of-sample table
    rho2, cnt2 = lag_corr(t2, z2)
    d = np.abs(rho - rho2)
    nh = 44
    for v, name in enumerate(PROFILE):
        s = slice(v * nh, (v + 1) * nh)
        print(f"{name:>3}: mean rho lag 1/3/6/9 (fit) {rho[:, 1, s].mean():.3f}/{rho[:, 3, s].mean():.3f}/{rho[:, 6, s].mean():.3f}/{rho[:, 9, s].mean():.3f}   mean |fit - 2023-25| by lag 1/3/6/9: {d[:, 1, s].mean():.3f}/{d[:, 3, s].mean():.3f}/{d[:, 6, s].mean():.3f}/{d[:, 9, s].mean():.3f}   max {d[:, :, s].max():.3f}", flush=True)
    np.savez("models/coherence_lagcorr.npz", rho=rho.astype(np.float32), n_pairs=cnt, rho_2023_25=rho2.astype(np.float32), points=np.array(pts), fit_years="2005-2022")
    print("wrote models/coherence_lagcorr.npz")


if __name__ == "__main__":
    main()
