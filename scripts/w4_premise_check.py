"""W4 premise check: is the tool's 10 m speed shape gap (W1: calm share 0.9 % vs ASOS 6 %, k 2.05 vs 2.23) made by the
generator, or is it already in its training source (ERA5)? A Weibull-space head trained on ERA5 can only fix the part the
generator adds. Same 168 cells as scripts/weibull_check.py (TCS, MAF; month x local hour 8-20), ERA5 = profile store
(data/pilot/profiles.zarr, nearest grid point, height 10 m, 2015-25), ASOS 2015-25, tool climate mode n = 600 (seed 5).
W9: this is also the speed-SHAPE check for any change of the tool's assets (k, calm share, p99, KS against stations and ERA5): pass --assets DIR.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/w4_premise_check.py [--assets DIR]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from weibull_check import HOURS, KT, ST, ks, weibull_mle   # noqa: E402
from tempest_weather_v2 import Launch   # noqa: E402


def local_cells(times_utc, values, tz):
    t = pd.DatetimeIndex(times_utc).tz_localize("UTC").tz_convert(tz)
    h = (t.hour + (t.minute >= 30)) % 24
    out = {}
    for m in range(1, 13):
        for hh in HOURS:
            sel = (t.month == m) & (h == hh)
            out[(m, hh)] = values[sel]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default=None, help="tool asset directory to check (default: the shipped assets)")
    assets = ap.parse_args().assets
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    rows = []
    for name, (lat, lon, el, tz) in ST.items():
        i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
        tt = z.time.values
        keep = (tt >= np.datetime64("2015-01-01")) & (tt < np.datetime64("2026-01-01"))
        u = z["u"].isel(point=i, height=0).values[keep].astype(float)
        v = z["v"].isel(point=i, height=0).values[keep].astype(float)
        ok = np.isfinite(u) & np.isfinite(v)
        era = local_cells(tt[keep][ok], np.hypot(u, v)[ok], tz)
        a = pd.concat([pd.read_csv(os.path.join(REPO, "data", "raw", "asos", name, f"{y}.csv"), usecols=["valid", "sknt"]) for y in range(2015, 2026)])
        a["s"] = pd.to_numeric(a["sknt"], errors="coerce") * KT
        a = a.dropna(subset=["s"])
        obs = local_cells(pd.to_datetime(a["valid"]).values, a["s"].values, tz)
        for m in range(1, 13):
            for h in HOURS:
                o, e = obs[(m, h)], era[(m, h)]
                if len(o) < 100 or len(e) < 50:
                    continue
                try:
                    s = Launch(lat, lon, f"2020-{m:02d}-15 {h:02d}:00", mode="ai", n=600, units="si", elevation=el, tz=tz, seed=5, assets=assets)._ensure_pool()["samples"]
                except Exception:   # noqa: BLE001
                    continue
                tool = np.hypot(s["u"][:, 0], s["v"][:, 0])
                rows.append((name, weibull_mle(o)[0], weibull_mle(e)[0], weibull_mle(tool)[0], (o < 0.5).mean(), (e < 0.5).mean(), (tool < 0.5).mean(),
                             np.percentile(o, 99), np.percentile(e, 99), np.percentile(tool, 99), ks(o, e), ks(o, tool), ks(e, tool), o.mean(), e.mean(), tool.mean()))
    r = np.array([x[1:] for x in rows], float)
    lab = ["ASOS", "ERA5", "tool"]
    print(f"{len(rows)} cells (TCS + MAF, month x local hour {HOURS[0]}-{HOURS[-1]}); 10 m speed")
    print("              " + "  ".join(f"{x:>6}" for x in lab))
    print("Weibull k     " + "  ".join(f"{np.median(r[:, j]):6.2f}" for j in range(3)))
    print("calm < 0.5    " + "  ".join(f"{r[:, 3 + j].mean():6.3f}" for j in range(3)))
    print("p99 (m/s)     " + "  ".join(f"{np.median(r[:, 6 + j]):6.1f}" for j in range(3)))
    print("mean (m/s)    " + "  ".join(f"{np.median(r[:, 12 + j]):6.2f}" for j in range(3)))
    print(f"KS distance (median / p90): ASOS-ERA5 {np.median(r[:, 9]):.3f} / {np.percentile(r[:, 9], 90):.3f}; ASOS-tool {np.median(r[:, 10]):.3f} / {np.percentile(r[:, 10], 90):.3f}; ERA5-tool {np.median(r[:, 11]):.3f} / {np.percentile(r[:, 11], 90):.3f}")
    print(f"mean |k_tool - k_ERA5| {np.abs(r[:, 2] - r[:, 1]).mean():.2f}; mean |k_ERA5 - k_ASOS| {np.abs(r[:, 1] - r[:, 0]).mean():.2f}")
    for st in ST:
        sel = np.array([x[0] == st for x in rows])
        print(f"  {st}: k ASOS/ERA5/tool {np.median(r[sel, 0]):.2f}/{np.median(r[sel, 1]):.2f}/{np.median(r[sel, 2]):.2f}; calm {r[sel, 3].mean():.3f}/{r[sel, 4].mean():.3f}/{r[sel, 5].mean():.3f}; "
              f"KS ERA5-tool {np.median(r[sel, 11]):.3f}")


if __name__ == "__main__":
    main()
