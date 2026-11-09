"""Fix idea 'extrapolate down': estimate the 10 m wind from ERA5's wind HIGHER up (50 / 100 / 200 m), where the reanalysis is smoother and less affected by the surface scheme, with a logarithmic profile and a fitted roughness
length z0, and compare with the raw ERA5 10 m wind against ASOS at TCS and MAF. z0 is fitted on 2021-23 and scored on 2024-25 (daytime solar hours the tool serves). Speed from the extrapolation, direction from ERA5's 10 m wind.
Also a simple stability-aware variant: z0 chosen separately for stable (T at 100 m above T at 10 m by more than 0.3 K) and unstable/neutral hours.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_extrapolate_down.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402

Z0 = [0.003, 0.01, 0.03, 0.1, 0.3, 1.0]
REF = {"50 m": 1, "100 m": 2, "200 m": 4}          # indices in the store's height axis 10, 50, 100, 150, 200


def load(z, st, years):
    lat, lon, el = gw.STATIONS[st]
    i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
    asos = gw.load_asos(st, years)
    t_all = z["time"].values
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
    ks, A = [], []
    for h in sorted(asos):
        if not gw.valid_hour(st, h):
            continue
        k = tt.get(np.datetime64(h.replace(tzinfo=None), "h"))
        if k is not None:
            ks.append(k)
            A.append(asos[h])
    ks = np.array(ks)
    o = np.argsort(ks)
    ks, A = ks[o], np.array(A)[o]
    sl = slice(ks.min(), ks.max() + 1)
    u = z["u"].isel(point=i, height=slice(0, 5), time=sl).values.astype(float)[ks - ks.min()]
    v = z["v"].isel(point=i, height=slice(0, 5), time=sl).values.astype(float)[ks - ks.min()]
    T = z["T"].isel(point=i, height=slice(0, 5), time=sl).values.astype(float)[ks - ks.min()]
    return A, u, v, T


def estimate(u, v, T, ref, z0, stable_z0=None):
    sp = np.hypot(u, v)
    zr = [10.0, 50.0, 100.0, 150.0, 200.0][ref]
    z0v = np.full(len(sp), z0)
    if stable_z0 is not None:
        z0v = np.where(T[:, ref] - T[:, 0] > 0.3, stable_z0, z0)
    f = np.log(10.0 / z0v) / np.log(zr / z0v)
    s10 = sp[:, ref] * f
    d = np.hypot(u[:, 0], v[:, 0])
    dirx = np.where(d > 1e-6, u[:, 0] / np.maximum(d, 1e-6), 1.0)
    diry = np.where(d > 1e-6, v[:, 0] / np.maximum(d, 1e-6), 0.0)
    return np.stack([s10 * dirx, s10 * diry], 1)


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    for st in gw.STATIONS:
        Af, uf, vf, Tf = load(z, st, [2021, 2022, 2023])
        At, ut, vt, Tt = load(z, st, [2024, 2025])
        mae = lambda x, A: np.abs(x - A).mean()
        sp = lambda x: np.hypot(x[:, 0], x[:, 1])
        raw = np.stack([ut[:, 0], vt[:, 0]], 1)
        print(f"\n{st}: fit {len(Af)} hours 2021-23, test {len(At)} hours 2024-25 (ASOS mean speed {sp(At).mean():.2f} m/s)")
        print(f"  raw ERA5 10 m wind                       test MAE {mae(raw, At):.3f}  speed bias {sp(raw).mean() - sp(At).mean():+.2f}")
        for name, ref in REF.items():
            fit = [(mae(estimate(uf, vf, Tf, ref, z0), Af), z0) for z0 in Z0]
            best = min(fit)[1]
            m = estimate(ut, vt, Tt, ref, best)
            # stability-aware: separate z0 for stable hours
            fit2 = [(mae(estimate(uf, vf, Tf, ref, best, s), Af), s) for s in Z0]
            bs = min(fit2)[1]
            m2 = estimate(ut, vt, Tt, ref, best, bs)
            print(f"  log-law from {name:6} z0 {best:<6g} test MAE {mae(m, At):.3f} speed bias {sp(m).mean() - sp(At).mean():+.2f} | stability-aware (stable z0 {bs:g}) MAE {mae(m2, At):.3f} bias {sp(m2).mean() - sp(At).mean():+.2f}")


if __name__ == "__main__":
    main()
