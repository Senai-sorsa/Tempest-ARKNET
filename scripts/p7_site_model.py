"""P7 / IL-168: can a site's ground-wind correction be predicted from static descriptors, without its own record? P1, P2 and P4 showed that the remaining 10 m gap is a property of the SITE.
Sites (inside the NM/TX box, local 10-18 h where the USCRN 1.5 m -> 10 m log-law scaling holds, 2019-2022 because the Las Cruces USCRN wind is bad from mid-2023): ASOS TCS, LRU, ELP, ALM,
MAF, PEQ; USCRN Las Cruces 20 N (basin) and Monahans 6 ENE. Per site, 120 random stored hours: past-mode 10 m speed ensemble (ERA5 anchor on) against the observed speed.
Site factors: scale = sum(observed) / sum(tool median); spread = the widening about the median (after scaling) with the lowest CRPS (grid 0.8-1.8).
Descriptors (USGS 3DEP through tempest_weather_v2.elevation, cached): TPI at 2 km and 5 km (site height minus the mean of 8 points on the ring), and the site height minus the ERA5 cell height.
Leave-one-site-out: each factor predicted from ONE descriptor by a straight line through the other 7 sites; CRPS at the left-out site with (a) no correction, (b) the predicted factors,
(c) the site's own best factors (oracle, = what a pad record gives); and the strongest simple baseline, the MEAN factors of the other sites (one regional pair). Speed CRPS / MAE of the median / cov90.
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p7_site_model.py [--n 120]
"""
import argparse
import math
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
from gw_uscrn_bench import read_station   # noqa: E402
from uscrn_compare import read_uscrn   # noqa: E402
from tempest.scoring.score import coverage90, crps_ensemble   # noqa: E402
from tempest_weather import api   # noqa: E402
from tempest_weather_v2 import elevation as E, obs as O   # noqa: E402

GRID = np.round(np.arange(0.8, 1.81, 0.1), 2)
F10 = np.log(10 / 0.03) / np.log(1.5 / 0.03)
YEARS = range(2019, 2023)


def sites():
    out = {}
    for st in ("TCS", "LRU", "ELP", "ALM", "MAF", "PEQ"):
        lat, lon, el = O.STATIONS[st]
        a = gw.load_asos(st, YEARS)
        out[st] = (lat, lon, el, -7 if lon < -104 else -6, {h: float(np.hypot(*uv)) for h, uv in a.items()})
    jr = {}
    for y in YEARS:
        jr.update(read_uscrn(y))
    out["LC20N"] = (32.61, -106.74, None, -7, {h: v * F10 for h, v in jr.items()})
    mo = {}
    for y in YEARS:
        mo.update(read_station(os.path.join(REPO, "data", "raw", "uscrn_monahans", f"CRNS_MONAHANS_{y}.txt")))
    out["MONAHANS"] = (31.62, -102.81, None, -6, {h: v * F10 for h, v in mo.items()})
    return out


def ring(lat, lon, r_km):
    pts = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        pts.append((lat + r_km / 111.0 * math.cos(a), lon + r_km / (111.0 * math.cos(math.radians(lat))) * math.sin(a)))
    return pts


def elev(lat, lon):
    return float(E.lookup(lat, lon).m)


def widen(x, f):
    m = np.median(x)
    return np.maximum(m + f * (x - m), 0.0)


def site_score(rows, scale, spread):
    sc = []
    for x, y in rows:
        xx = widen(x * scale, spread)
        sc.append((crps_ensemble(xx[None, :, None], np.array([[y]]))[0, 0], abs(np.median(xx) - y), coverage90(xx[None, :, None], np.array([[y]]), 0.9)[0, 0]))
    return np.mean(sc, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    zlat, zlon, zsfc = z.lat.values, z.lon.values, z.z_sfc.values
    have = {np.datetime64(t, "h") for t in z.time.values}
    data, desc = {}, {}
    for name, (lat, lon, el, off, truth) in sites().items():
        hs = [h for h in truth if h.hour in gw.HOURS_OK and 10 <= (h.hour + off) % 24 <= 18 and np.datetime64(h.replace(tzinfo=None), "h") in have]
        rows = []
        for k in rng.permutation(len(hs)):
            if len(rows) >= a.n:
                break
            h = hs[k]
            try:
                atm, info = api.atmosphere_set(lat, lon, h.isoformat(), n=100, mode="past", seed=int(k), elevation=el, era5_anchor=1.0)
            except Exception:   # noqa: BLE001
                continue
            assert info["mode"] == "past", info.get("quality")
            rows.append((np.hypot(atm["u"][:, 0], atm["v"][:, 0]), truth[h]))
        data[name] = rows
        e0 = elev(lat, lon)
        i = int(np.argmin((zlat - lat) ** 2 + (zlon - lon) ** 2))
        zc = float(zsfc[i]) / 9.80665 if float(zsfc[i]) > 20000 else float(zsfc[i])
        desc[name] = dict(tpi2=e0 - np.mean([elev(*p) for p in ring(lat, lon, 2.0)]), tpi5=e0 - np.mean([elev(*p) for p in ring(lat, lon, 5.0)]), dz_cell=e0 - zc)
        print(f"{name:9s} {len(rows)} hours; descriptors " + ", ".join(f"{k} {v:+.0f} m" for k, v in desc[name].items()), flush=True)
    fac = {}
    for name, rows in data.items():
        scale = sum(y for _, y in rows) / sum(np.median(x) for x, _ in rows)
        spread = float(GRID[int(np.argmin([site_score(rows, scale, f)[0] for f in GRID]))])
        fac[name] = (scale, spread)
        print(f"{name:9s} site factors: scale {scale:.2f}, spread {spread:.1f}")
    names = sorted(data)
    print("\nleave-one-site-out, CRPS / MAE / cov90 at the left-out site")
    print("site       none                 const(mean of others)   " + "  ".join(f"pred({d})            " for d in ("tpi2", "tpi5", "dz_cell")) + "  oracle")
    tot = {k: [] for k in ("none", "const", "tpi2", "tpi5", "dz_cell", "oracle")}
    for k in names:
        others = [n for n in names if n != k]
        line = [site_score(data[k], 1.0, 1.0)]
        tot["none"].append(line[0][0])
        cst = site_score(data[k], float(np.mean([fac[n][0] for n in others])), float(np.mean([fac[n][1] for n in others])))   # A6: the strongest simple baseline, one regional factor pair
        line.append(cst)
        tot["const"].append(cst[0])
        for d in ("tpi2", "tpi5", "dz_cell"):
            xs = np.array([desc[n][d] for n in others])
            pr = []
            for j in (0, 1):
                ys = np.array([fac[n][j] for n in others])
                b = np.polyfit(xs, ys, 1)
                pr.append(float(np.clip(np.polyval(b, desc[k][d]), 0.5, 2.0)))
            sc = site_score(data[k], pr[0], pr[1])
            line.append(sc)
            tot[d].append(sc[0])
        line.append(site_score(data[k], *fac[k]))
        tot["oracle"].append(line[-1][0])
        print(f"{k:9s} " + "  ".join(f"{s[0]:.3f}/{s[1]:.3f}/{s[2]:.2f}" for s in line))
    print("\nmean CRPS over sites: " + ", ".join(f"{k} {np.mean(v):.3f}" for k, v in tot.items()))


if __name__ == "__main__":
    main()
