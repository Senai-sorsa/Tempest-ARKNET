"""M5: analog-ensemble benchmark for the ground wind. For every test hour, the K most similar past ERA5 states (standardised u, v at 10 and 100 m, T(100 m) - T(10 m), hour of day, month of year) in the
library years give an ensemble from the ASOS wind (u, v) they were followed by. Compared with raw ERA5 10 m (one value), with the hour x month climatology of the station, and with a ridge regression of the ASOS wind
on the same features. Library 2015-2023, test 2024-25, TCS and MAF, daytime hours the store keeps (as gw_extrapolate_down.py).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_analog.py"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
from gw_extrapolate_down import load   # noqa: E402
from tempest.scoring.score import crps_ensemble   # noqa: E402


def feats(u, v, T, times):
    t = np.asarray(times, "datetime64[h]")
    hod = (t.astype("datetime64[h]").astype(np.int64) % 24).astype(float)
    mon = (t.astype("datetime64[M]").astype(np.int64) % 12).astype(float)
    return np.column_stack([u[:, 0], v[:, 0], u[:, 2], v[:, 2], T[:, 2] - T[:, 0], np.cos(2 * np.pi * hod / 24), np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * mon / 12), np.sin(2 * np.pi * mon / 12)])


def hours_of(z, st, years):
    """Same selection as load(): the UTC hours (datetime64[h]) of the kept ASOS hours, in order."""
    lat, lon, el = gw.STATIONS[st]
    asos = gw.load_asos(st, years)
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(z["time"].values)}
    out = []
    for h in sorted(asos):
        if not gw.valid_hour(st, h):
            continue
        k = tt.get(np.datetime64(h.replace(tzinfo=None), "h"))
        if k is not None:
            out.append((k, np.datetime64(h.replace(tzinfo=None), "h")))
    out.sort()
    return np.array([t for _, t in out])


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    K = 40
    W = np.array([1.0, 1.0, 1.0, 1.0, 0.6, 1.2, 1.2, 0.8, 0.8])          # feature weights after standardisation (time of day and season matter, as the wind has a diurnal cycle)
    for st in gw.STATIONS:
        yrs_lib, yrs_test = list(range(2015, 2024)), [2024, 2025]
        Al, ul, vl, Tl = load(z, st, yrs_lib)
        At, ut, vt, Tt = load(z, st, yrs_test)
        tl, tt_ = hours_of(z, st, yrs_lib), hours_of(z, st, yrs_test)
        Xl, Xt = feats(ul, vl, Tl, tl), feats(ut, vt, Tt, tt_)
        mu, sd = Xl.mean(0), Xl.std(0) + 1e-9
        Zl, Zt = (Xl - mu) / sd * W, (Xt - mu) / sd * W
        d2 = (Zt ** 2).sum(1)[:, None] + (Zl ** 2).sum(1)[None, :] - 2 * Zt @ Zl.T
        nn = np.argpartition(d2, K, axis=1)[:, :K]                       # (Nt, K) analogs
        ens = Al[nn]                                                     # (Nt, K, 2)
        sp = lambda a: np.hypot(a[..., 0], a[..., 1])
        spd_obs = sp(At)
        a_sp = sp(ens)                                                   # (Nt, K) analog speeds
        # ridge on the same features (+ quadratic terms of speeds)
        def design(X):
            return np.column_stack([np.ones(len(X)), X, X[:, :4] ** 2])
        Dl, Dt = design(Xl), design(Xt)
        beta = np.linalg.solve(Dl.T @ Dl + 3.0 * np.eye(Dl.shape[1]), Dl.T @ Al)
        rid = Dt @ beta
        # climatology: ASOS speeds of the same month and hour of day in the library
        key = lambda t: ((t.astype("datetime64[M]").astype(np.int64) % 12) * 24 + t.astype("datetime64[h]").astype(np.int64) % 24)
        kl, kt = key(tl), key(tt_)
        clim = [sp(Al[kl == k]) if (kl == k).sum() >= 20 else sp(Al) for k in kt]
        m = min(len(c) for c in clim)
        clim_e = np.stack([np.random.default_rng(i).choice(c, 200) for i, c in enumerate(clim)])
        raw = np.hypot(ut[:, 0], vt[:, 0])
        cr = lambda e: float(crps_ensemble(e[:, :, None], spd_obs[:, None])[:, 0].mean())
        cov = lambda e: float(np.mean((spd_obs >= np.quantile(e, 0.05, axis=1)) & (spd_obs <= np.quantile(e, 0.95, axis=1))))
        print(f"\n{st}: library {len(Al)} hours 2015-23, test {len(At)} hours 2024-25 (ASOS mean speed {spd_obs.mean():.2f} m/s), K = {K}")
        print(f"  raw ERA5 10 m (one value):    speed MAE {np.abs(raw - spd_obs).mean():.3f}  bias {raw.mean() - spd_obs.mean():+.2f}")
        print(f"  ridge on the features:        speed MAE {np.abs(sp(rid) - spd_obs).mean():.3f}  vector MAE {np.abs(rid - At).mean():.3f}")
        print(f"  analog median speed:          speed MAE {np.abs(np.median(a_sp, 1) - spd_obs).mean():.3f}  analog-mean vector MAE {np.abs(ens.mean(1) - At).mean():.3f}")
        print(f"  CRPS of speed: climatology {cr(clim_e):.3f}   analog ensemble {cr(a_sp):.3f}   (90 % interval coverage: clim {cov(clim_e):.2f}, analog {cov(a_sp):.2f})")
        hi = spd_obs >= 8.0
        print(f"  strong wind (>= 8 m/s, n {int(hi.sum())}): analog median {np.median(a_sp, 1)[hi].mean():.2f} vs obs {spd_obs[hi].mean():.2f}; raw ERA5 {raw[hi].mean():.2f}; ridge {sp(rid)[hi].mean():.2f}")


if __name__ == "__main__":
    main()
