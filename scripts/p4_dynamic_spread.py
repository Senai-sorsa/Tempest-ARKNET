"""P4: ground-wind spread that follows the day's uncertainty. Past mode (ERA5 hour + learned residuals, ERA5 anchor on, the default) has 90 % coverage of the 10 m speed of only
0.78-0.86 at the airports; a fixed x1.2 widening helps there (M5c) but over-widens the USCRN basin, where the plain spread is already calibrated (GW-F). Here the factor depends on the
regime: local day / night x tercile of the ERA5 boundary-layer height of that hour (data/pilot/surface_hourly.zarr, blh), so deep mixed layers and shallow stable ones get their own width.
Fit (2021-23, TCS + MAF ASOS, random stored hours): factor per class from a grid by mean CRPS of the speed. Test 2024-25 at TCS / MAF (development window) and, with the SAME factors,
the USCRN basin station 2019-22 at local 10-18 h (1.5 m scaled to 10 m, as gw_uscrn_bench.py). Compared: factor 1 (plain), fixed 1.2, regime factor. Speed CRPS, MAE of the median,
90 % coverage. The ensemble is widened about its median: x' = med + f (x - med), clipped at 0.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p4_dynamic_spread.py [--n 200]
"""
import argparse
import os
import sys
from datetime import timedelta, timezone

import numpy as np
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
os.environ.setdefault("TEMPEST_ERA5_STORE", os.path.join(REPO, "data", "pilot", "profiles.zarr"))
import ground_wind_bench as gw   # noqa: E402
from uscrn_compare import read_uscrn   # noqa: E402
from tempest import region   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402

GRID = np.round(np.arange(0.8, 1.81, 0.1), 2)
OFF = {"TCS": -7, "MAF": -6, "BASIN": -7}
BASIN = (32.61, -106.74, None)
F10 = np.log(10 / 0.03) / np.log(1.5 / 0.03)


def ens(lat, lon, el, t, seed):
    atm, info = api.atmosphere_set(lat, lon, t.isoformat(), n=100, mode="past", seed=seed, elevation=el, era5_anchor=1.0)
    assert info["mode"] == "past", info.get("quality")
    return np.hypot(atm["u"][:, 0], atm["v"][:, 0])


def widen(x, f):
    m = np.median(x)
    return np.maximum(m + f * (x - m), 0.0)


def score(x, y):
    return crps_ensemble(x[None, :, None], np.array([[y]]))[0, 0], abs(np.median(x) - y), coverage90(x[None, :, None], np.array([[y]]), 0.9)[0, 0]


def collect(site, lat, lon, el, truth, years, n, rng, blh, pt, tt, local_hours=None):
    hs = [h for h in sorted(truth) if h.year in years and h.hour in gw.HOURS_OK and np.datetime64(h.replace(tzinfo=None), "h") in tt]
    if local_hours:
        hs = [h for h in hs if (h.hour + OFF[site]) % 24 in local_hours]
    rows = []
    for k in rng.choice(len(hs), min(len(hs), 3 * n), replace=False):
        if len(rows) >= n:
            break
        h = hs[k]
        try:
            x = ens(lat, lon, el, h, int(k))
        except AssertionError:
            raise
        except Exception:   # noqa: BLE001
            continue
        lh = (h.hour + OFF[site]) % 24
        rows.append((x, truth[h], 8 <= lh <= 17, float(blh[pt, tt[np.datetime64(h.replace(tzinfo=None), "h")]])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    s = xr.open_zarr(os.path.join(REPO, "data", "pilot", "surface_hourly.zarr"))
    tt = {np.datetime64(x, "h"): k for k, x in enumerate(s.time.values)}
    blh_all = s["blh"]
    sets = {}
    for st in ("TCS", "MAF"):
        lat, lon, el = gw.STATIONS[st]
        pt = int(region.load().point_index(lat, lon))
        blh = blh_all.isel(point=[pt]).values
        a_ = gw.load_asos(st, range(2021, 2026))
        sp = {h: float(np.hypot(*uv)) for h, uv in a_.items()}
        sets[(st, "fit")] = collect(st, lat, lon, el, sp, range(2021, 2024), a.n, rng, blh, 0, tt)
        sets[(st, "test")] = collect(st, lat, lon, el, sp, range(2024, 2026), a.n, rng, blh, 0, tt)
        print(f"{st}: fit {len(sets[(st, 'fit')])}, test {len(sets[(st, 'test')])} hours", flush=True)
    jr = {}
    for y in range(2019, 2023):
        jr.update(read_uscrn(y))
    ptb = int(region.load().point_index(BASIN[0], BASIN[1]))
    sets[("BASIN", "test")] = collect("BASIN", BASIN[0], BASIN[1], None, {h: v * F10 for h, v in jr.items()}, range(2019, 2023), a.n, rng, blh_all.isel(point=[ptb]).values, 0, tt, local_hours=range(10, 19))
    print(f"basin: test {len(sets[('BASIN', 'test')])} hours (2019-22, local 10-18 h)", flush=True)
    fit = sets[("TCS", "fit")] + sets[("MAF", "fit")]
    edges = np.quantile([r[3] for r in fit], [1 / 3, 2 / 3])
    cls = lambda r: (int(r[2]), int(np.searchsorted(edges, r[3])))
    fac = {}
    for c in sorted({cls(r) for r in fit}):
        rr = [r for r in fit if cls(r) == c]
        crps = [np.mean([score(widen(r[0], f), r[1])[0] for r in rr]) for f in GRID]
        fac[c] = float(GRID[int(np.argmin(crps))])
        print(f"class {'day' if c[0] else 'night'} blh tercile {c[1]} (edges {edges.round(0)} m): {len(rr)} fit hours, factor {fac[c]:.1f}")
    print("\nsite  set     variant          n    CRPS   MAE(median)  cov90")
    for key in (("TCS", "test"), ("MAF", "test"), ("BASIN", "test")):
        rows = sets[key]
        for name, ff in (("plain (x1.0)", lambda r: 1.0), ("fixed x1.2", lambda r: 1.2), ("regime factor", lambda r: fac.get(cls(r), 1.0))):
            sc = np.array([score(widen(r[0], ff(r)), r[1]) for r in rows])
            print(f"{key[0]:5s} {key[1]:5s}  {name:15s} {len(rows):4d}  {sc[:, 0].mean():.3f}   {sc[:, 1].mean():.3f}      {sc[:, 2].mean():.2f}")


if __name__ == "__main__":
    main()
