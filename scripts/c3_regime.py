"""Group C, C3: regime check for the coherence tables. Are the hourly lag correlation (C1) and the distance correlation (C2) different on calm, middle and windy days?
Regime = tercile of the 0-3 km wind shear |V(3 km) - V(10 m)| of the grid point at that time (terciles of the fit years, all seasons). Correlations are recomputed inside each regime
(a pair counts for the regime of its first element) and compared with the all-days table: mean and worst |difference| per variable at lag 3 / 6 / 12 h and at ~24 / 48 / 59 km.
Decision rule (AUTOPILOT group C): all within 0.05 -> keep one table; otherwise fit per regime.
    PYTHONPATH=. python scripts/c3_regime.py"""
import numpy as np
import pandas as pd
import xarray as xr

from scripts import c1_fit_lagcorr as C1
from scripts import c2_fit_distcorr as C2
from tempest.profiles.to_heights import HEIGHTS, PROFILE

nh = len(HEIGHTS)
I3 = int(np.argmin(np.abs(HEIGHTS - 3000)))


def regimes(x, edges=None):
    u, v = x[:, :, :nh], x[:, :, nh:2 * nh]
    sh = np.hypot(u[:, :, I3] - u[:, :, 0], v[:, :, I3] - v[:, :, 0])
    if edges is None:
        edges = np.quantile(sh, [1 / 3, 2 / 3])
    return np.digitize(sh, edges), edges


def lag_by_regime(times, z, reg):
    season = (times.month.to_numpy() % 12) // 3
    rho = np.zeros((3, 4, C1.LAGS, z.shape[2]))
    for tau in range(C1.LAGS):
        ok = np.ones(len(times) - tau, bool) if tau == 0 else (times.asi8[tau:] - times.asi8[:-tau] == tau * 3600 * 10 ** 9)
        for s in range(4):
            for r in range(3):
                m = (ok & (season[: len(times) - tau] == s))[None, :] & (reg[:, : len(times) - tau] == r)          # (pt, T-tau)
                a, b = z[:, : len(times) - tau][m], z[:, tau:][m]                                                  # (N, D)
                if len(a) > 50:
                    rho[r, s, tau] = ((a * b).mean(0) - a.mean(0) * b.mean(0)) / (a.std(0) * b.std(0) + 1e-9)
    return rho


def dist_by_regime(times, z, reg, lat, lon, bins):
    season = (times.month.to_numpy() % 12) // 3
    P = len(lat)
    dist = np.hypot((lat[:, None] - lat[None]) * C2.KM_LAT, (lon[:, None] - lon[None]) * C2.KM_LAT * np.cos(np.radians(lat.mean())))
    rho = np.full((3, 4, len(bins), z.shape[2]), np.nan)
    for s in range(4):
        for r in range(3):
            for bi, d in enumerate(bins):
                pairs = np.argwhere(np.triu(np.abs(dist - d) < 2.0, 1))
                if d == 0 or len(pairs) == 0:
                    continue
                acc, cnt = 0.0, 0
                for i, j in pairs:
                    m = (season == s) & (reg[i] == r) & (reg[j] == r)
                    if m.sum() > 50:
                        a, b = z[i][m], z[j][m]
                        acc = acc + ((a * b).mean(0) - a.mean(0) * b.mean(0)) / (a.std(0) * b.std(0) + 1e-9)
                        cnt += 1
                if cnt:
                    rho[r, s, bi] = acc / cnt
    return rho


def main():
    ds = xr.open_zarr(C1.PROFILES)
    la, lo = ds.lat.values, ds.lon.values
    # --- C1: hourly lag, 8 points
    pts = sorted({int(np.argmin((la - a) ** 2 + (lo - b) ** 2)) for a, b in C1.WANT})
    t, x = C1.load(ds, pts, 2005, 2022)
    z, _ = C1.anomalies(t, x)
    reg, edges = regimes(x)
    base = np.load("models/coherence_lagcorr.npz")["rho"]
    EDGES = edges
    rl = lag_by_regime(t, z, reg)
    print("C1 hourly lag correlation by regime (calm / middle / windy), mean over seasons and the 44 heights, and mean|difference| to the all-days table")
    out = {}
    for v, name in enumerate(PROFILE):
        sl = slice(v * nh, (v + 1) * nh)
        for tau in (3, 6, 12):
            vals = [np.nanmean(rl[r, :, tau, sl]) for r in range(3)]
            dif = [np.nanmean(np.abs(rl[r, :, tau, sl] - base[:, tau, sl])) for r in range(3)]
            out[(name, tau)] = max(dif)
            print(f"  {name:>3} lag {tau:>2} h: {vals[0]:.3f} / {vals[1]:.3f} / {vals[2]:.3f}   |diff| {dif[0]:.3f} / {dif[1]:.3f} / {dif[2]:.3f}", flush=True)
    del x, z
    # --- C2: distance, 45 points
    n_lon = 29
    p2 = [r * n_lon + c for r in C2.ROWS for c in C2.COLS]
    lat, lon = ds.lat.values[p2], ds.lon.values[p2]
    t, x = C2.load(ds, p2, 2005, 2022)
    z, _ = C2.anomalies(t, x)
    reg, _ = regimes(x)
    bz = np.load("models/coherence_distcorr.npz")
    bins = list(bz["km"])
    rd = dist_by_regime(t, z, reg, lat, lon, bins)
    print("C2 distance correlation by regime (calm / middle / windy) and mean|difference| to the all-days table")
    for v, name in enumerate(PROFILE):
        sl = slice(v * nh, (v + 1) * nh)
        for bi in (1, 4, 6):
            vals = [np.nanmean(rd[r, :, bi, sl]) for r in range(3)]
            dif = [np.nanmean(np.abs(rd[r, :, bi, sl] - bz["rho"][:, bi, sl])) for r in range(3)]
            out[(name, bins[bi])] = max(dif)
            print(f"  {name:>3} {bins[bi]:>4.0f} km: {vals[0]:.3f} / {vals[1]:.3f} / {vals[2]:.3f}   |diff| {dif[0]:.3f} / {dif[1]:.3f} / {dif[2]:.3f}", flush=True)
    worst = max(out.values())
    print(f"\nlargest mean |regime table - all-days table| over all variables and lags / distances: {worst:.3f}  ->  {'ONE table is enough (all within 0.05)' if worst <= 0.05 else 'FIT PER REGIME'}")
    np.savez("models/coherence_regimes.npz", lag=rl.astype(np.float32), dist=rd.astype(np.float32), km=np.array(bins), worst=worst, shear_edges=np.asarray(EDGES))


if __name__ == "__main__":
    main()
