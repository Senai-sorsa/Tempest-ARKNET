"""New_Plan 28.11 item 12 step 1: build the WD1 / UR5 table (tempest_weather/ur5.py) on a set of tool assets.
Points: 1-degree grid 31.5-33.5 N x 107.5-101.5 W (21 points; holds the 12 b29 / b40 cells). Per point x month x UTC hour: the tool's climate-mode 10 m speed
(atmosphere_set on the 15th of the month in 2013, n members, seed) mapped to the ERA5 speed of the nearest profiles80 store point (1991-2005, same month and hour);
regime correlations from the real 3-hour ERA5 windows starting at that hour (1991-2005); s_u, s_v = one number each on a 0.01 grid so that the mean 5-95 %
coverage of the mapped hour members against the 1991-2005 ERA5 u / v over all cells is nearest 0.90 (b40 pick_scale). Fit years only (<= 2005), never 2006+.
    PYTHONPATH="." .venv/Scripts/python -W ignore scripts/build_ur5.py OUT.npz [--assets DIR] [--n 1024] [--seed 0] [--pts 21]
"""
import argparse
import time

import numpy as np
import pandas as pd
import xarray as xr

from tempest_weather import api, ur5

LATS, LONS = (31.5, 32.5, 33.5), tuple(np.arange(-107.5, -101.0, 1.0))
FIT = ("1991", "2005")
GRID = np.round(np.arange(0.70, 1.2001, 0.01), 2)


def windows(w, t, month, hour):
    gap = np.diff(t.values).astype("timedelta64[h]").astype(int)
    ok = np.flatnonzero((gap[:-1] == 1) & (gap[1:] == 1) & (t.month[:-2] == month) & (t.hour[:-2] == hour))
    return np.stack([w[ok], w[ok + 1], w[ok + 2]], 1)


def cov90(m, y):
    lo, hi = np.percentile(m, 5), np.percentile(m, 95)
    return float(np.mean((y >= lo) & (y <= hi)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"), ap.add_argument("--assets"), ap.add_argument("--n", type=int, default=1024), ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pts", type=int, default=0, help="first k points only (smoke test)")
    a = ap.parse_args()
    pl = [(la, lo) for la in LATS for lo in LONS][: a.pts or None]
    ds = xr.open_zarr("data/pilot/profiles80.zarr")
    sla, slo = ds.lat.values, ds.lon.values
    sp = [int(np.argmin((sla - la) ** 2 + (slo - lo) ** 2)) for la, lo in pl]
    sub = ds[["u10", "v10"]].isel(point=sp).sel(time=slice(*FIT)).load()
    t = pd.DatetimeIndex(sub.time.values)
    assert t.year.max() <= 2005
    U, V = sub.u10.values.astype(float), sub.v10.values.astype(float)
    W = np.hypot(U, V)
    P, Q = len(pl), len(ur5.QS)
    xt, xe = np.zeros((P, 12, 24, Q), np.float32), np.zeros((P, 12, 24, Q), np.float32)
    ok, rho = np.zeros((P, 12, 24), bool), np.zeros((P, 12, 24, 3), np.float32)
    cells = []
    t0 = time.time()
    for pi, (la, lo) in enumerate(pl):
        for m in range(1, 13):
            for h in range(24):
                sel = (t.month == m) & (t.hour == h)
                tpl = windows(W[pi], t, m, h)
                if sel.sum() < 100 or len(tpl) < 100:
                    continue
                try:
                    atm, _ = api.atmosphere_set(la, lo, f"2013-{m:02d}-15T{h:02d}:00:00+00:00", n=a.n, seed=a.seed, mode="ai", assets=a.assets)
                except ValueError:
                    continue
                u, v = atm["u"][:, 0].astype(float), atm["v"][:, 0].astype(float)
                xt[pi, m - 1, h], xe[pi, m - 1, h] = ur5.fit_map(np.hypot(u, v), W[pi][sel])
                rho[pi, m - 1, h] = ur5.regime_rho(tpl)
                ok[pi, m - 1, h] = True
                mu, mv = ur5.apply_map(u, v, xt[pi, m - 1, h], xe[pi, m - 1, h])
                cells.append((mu, mv, U[pi][sel], V[pi][sel]))
        print(f"point {pi + 1}/{P} ({la}, {lo}): {int(ok[pi].sum())} cells, {time.time() - t0:.0f} s", flush=True)
    s = []
    for c in (0, 1):
        cv = [np.mean([cov90(ur5.scale(x[c], g), x[2 + c]) for x in cells]) for g in GRID]
        s.append(float(GRID[int(np.argmin(np.abs(np.array(cv) - 0.90)))]))
    print(f"s_u {s[0]:.2f}, s_v {s[1]:.2f} (b40: 1.07 / 0.89 seed 0, 1.05 / 0.91 seed 1); {int(ok.sum())} cells")
    np.savez(a.out, lat=np.array([p[0] for p in pl]), lon=np.array([p[1] for p in pl]), xt=xt, xe=xe, ok=ok, rho=rho, s=np.array(s), n=a.n, seed=a.seed,
             assets=str(a.assets))


if __name__ == "__main__":
    main()
