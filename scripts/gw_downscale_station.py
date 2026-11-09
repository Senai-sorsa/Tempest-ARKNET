"""More fixes for the 10 m wind at a station, tested with ERA5 as input and ASOS as truth, fit 2021-23, test 2024-25 (solar hours the tool serves):
 (a) ridge regression of the ASOS u and v on ERA5 u, v at 10 / 50 / 100 / 150 / 200 m, the T difference 100 m - 10 m and hour/month harmonics (a station-trained downscaling);
 (b) speed factor by wind-direction sector (16 sectors, from ERA5 10 m direction) x stability class: median ASOS speed / ERA5 speed in the fit years, applied to the ERA5 10 m wind (valley channelling and sheltering);
 (c) quantile mapping of the ERA5 10 m SPEED to the ASOS speed distribution (fixes bias and calm frequency, keeps order);
 (d) (b) followed by (c).
Reports test MAE of the u, v components, speed bias and speed correlation.   PYTHONPATH=. .venv/Scripts/python -W ignore scripts/gw_downscale_station.py
"""
import os
import sys

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import ground_wind_bench as gw   # noqa: E402
import gw_extrapolate_down as ex   # noqa: E402


def feats(u, v, T, hours, months):
    ang_h, ang_m = 2 * np.pi * hours / 24.0, 2 * np.pi * months / 12.0
    x = np.concatenate([u, v, (T[:, 4] - T[:, 0])[:, None], np.sin(ang_h)[:, None], np.cos(ang_h)[:, None], np.sin(ang_m)[:, None], np.cos(ang_m)[:, None]], 1)
    return x


def main():
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    t_all = z["time"].values
    for st in gw.STATIONS:
        Af, uf, vf, Tf = ex.load(z, st, [2021, 2022, 2023])
        At, ut, vt, Tt = ex.load(z, st, [2024, 2025])

        def hm(years):
            import datetime as dt
            asos = gw.load_asos(st, years)
            hs = [h for h in sorted(asos) if gw.valid_hour(st, h)]
            tt = {np.datetime64(x, "h"): k for k, x in enumerate(t_all)}
            hs = [h for h in hs if tt.get(np.datetime64(h.replace(tzinfo=None), "h")) is not None]
            ks = np.array([tt[np.datetime64(h.replace(tzinfo=None), "h")] for h in hs])
            o = np.argsort(ks)
            hs = [hs[i] for i in o]
            return np.array([h.hour for h in hs], float), np.array([h.month for h in hs], float)
        hf, mf = hm([2021, 2022, 2023])
        ht, mt = hm([2024, 2025])
        sp = lambda x: np.hypot(x[:, 0], x[:, 1])
        mae = lambda x: np.abs(x - At).mean()
        raw = np.stack([ut[:, 0], vt[:, 0]], 1)
        rawf = np.stack([uf[:, 0], vf[:, 0]], 1)
        print(f"\n{st}: test {len(At)} hours; ASOS mean speed {sp(At).mean():.2f}")
        row = lambda name, x: print(f"  {name:46} MAE {mae(x):.3f}  speed bias {sp(x).mean() - sp(At).mean():+.2f}  speed corr {np.corrcoef(sp(x), sp(At))[0, 1]:.3f}")
        row("raw ERA5 10 m", raw)
        # (a) ridge
        Xf, Xt = feats(uf, vf, Tf, hf, mf), feats(ut, vt, Tt, ht, mt)
        mu, sd = Xf.mean(0), Xf.std(0) + 1e-9
        Xf, Xt = (Xf - mu) / sd, (Xt - mu) / sd
        Xf1, Xt1 = np.c_[np.ones(len(Xf)), Xf], np.c_[np.ones(len(Xt)), Xt]
        W = np.linalg.solve(Xf1.T @ Xf1 + 10.0 * np.eye(Xf1.shape[1]), Xf1.T @ Af)
        row("(a) ridge on ERA5 u, v at 5 heights, dT, harmonics", Xt1 @ W)
        # (b) sector x stability speed factor
        def sector(u, v):
            d = (np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0
            return (np.floor((d + 11.25) / 22.5) % 16).astype(int)
        def stab(T):
            return (T[:, 4] - T[:, 0] > 0.3).astype(int)
        sf, stf = sector(uf[:, 0], vf[:, 0]), stab(Tf)
        fac = np.ones((16, 2))
        for s in range(16):
            for c in range(2):
                m = (sf == s) & (stf == c) & (np.hypot(uf[:, 0], vf[:, 0]) > 0.5)
                if m.sum() >= 40:
                    fac[s, c] = np.median(sp(Af)[m] / np.hypot(uf[m, 0], vf[m, 0]))
        st_t, s_t = stab(Tt), sector(ut[:, 0], vt[:, 0])
        b = raw * fac[s_t, st_t][:, None]
        row("(b) speed factor by direction sector x stability", b)
        # (c) quantile map of the speed
        q = np.linspace(0.005, 0.995, 199)
        src, dst = np.quantile(np.hypot(rawf[:, 0], rawf[:, 1]), q), np.quantile(sp(Af), q)
        def qmap(x):
            s = np.hypot(x[:, 0], x[:, 1])
            s2 = np.interp(s, src, dst)
            return x * (s2 / np.maximum(s, 1e-6))[:, None]
        row("(c) quantile map of the speed", qmap(raw))
        row("(d) sector factor, then quantile map", qmap(b))
        print("  factors by sector (stable | unstable), first 8:", " ".join(f"{fac[s, 1]:.2f}|{fac[s, 0]:.2f}" for s in range(8)))


if __name__ == "__main__":
    main()
