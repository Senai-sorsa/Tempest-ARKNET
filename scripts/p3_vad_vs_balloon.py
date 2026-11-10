"""P3 step 1: NEXRAD VAD wind profiles (Level III NVW, "VAD Algorithm Output" tab pages, decoded with MetPy) against the balloons. The El Paso radar (EPZ, Santa Teresa NM,
about 1250 m) stands next to the EPZ radiosonde site. For random days of 2021-2023 the NVW volume nearest 23:30 UTC (the 00Z balloon is in the air then) is fetched from the public
Unidata Level III archive on AWS (unidata-nexrad-level3, about 9 KB per file, into data/raw/nexrad_nvw) and its U, V at each altitude (100 ft above sea level) are put on the model
heights above the balloon site. Truth: the 00Z EPZ balloon at the same heights (data/igra_heights). Reference: ERA5 at the nearest grid point at 00 UTC (data/pilot/profiles.zarr).
Per height band: vector wind error (mean |difference|, m/s) of the radar and of ERA5 against the balloon, bias of the speed, and the share of days with a radar value (clear air leaves gaps).
If the radar is closer to the balloon than ERA5, it is worth feeding to the conditioning (which gained 15-17 % aloft from 500-2000 m data).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/p3_vad_vs_balloon.py [--n 120]
"""
import argparse
import os
import re
import sys
import urllib.request

import numpy as np
import pandas as pd
import xarray as xr

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather import _core   # noqa: E402

BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
OUT = os.path.join(REPO, "data", "raw", "nexrad_nvw")
SITE_M = 1252.0                                   # EPZ radiosonde site / radar ground, m above sea level
H = np.asarray(_core.HEIGHTS, float)
BANDS = [("0.5-1 km", 500, 1000), ("1-2 km", 1000, 2000), ("2-5 km", 2000, 5000), ("5-10 km", 5000, 10000)]


def fetch(day, radar="EPZ"):
    pre = f"{radar}_NVW_{day:%Y_%m_%d}_23"
    with urllib.request.urlopen(BUCKET + f"?list-type=2&prefix={pre}", timeout=60) as r:
        keys = re.findall(r"<Key>([^<]+)</Key>", r.read().decode())
    if not keys:
        return None
    best = min(keys, key=lambda k: abs(int(k[-8:-6]) * 60 + int(k[-5:-3]) - 30))
    path = os.path.join(OUT, best)
    if not os.path.exists(path):
        urllib.request.urlretrieve(BUCKET + best, path)
    return path


def parse(path, site_m=SITE_M):
    from metpy.io import Level3File
    f = Level3File(path)
    alt, u, v = [], [], []
    for page in f.tab_pages or []:
        for line in page.splitlines():
            p = line.split()
            if len(p) >= 3 and re.fullmatch(r"\d{3}", p[0]):
                try:
                    alt.append(float(p[0]) * 30.48 - site_m)
                    u.append(float(p[1]))
                    v.append(float(p[2]))
                except ValueError:
                    continue
    if len(alt) < 3:
        return None
    o = np.argsort(alt)
    a, uu, vv = np.array(alt)[o], np.array(u)[o], np.array(v)[o]
    ok = (H >= a[0]) & (H <= a[-1])
    return np.where(ok, np.interp(H, a, uu), np.nan), np.where(ok, np.interp(H, a, vv), np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(0)
    d = np.load(os.path.join(REPO, "data", "igra_heights", "USM00072364.npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    t = pd.DatetimeIndex(d["time"].astype("datetime64[ns]"))
    keep = np.flatnonzero((t.year >= 2021) & (t.year <= 2023) & (t.hour == 0))
    z = xr.open_zarr(os.path.join(REPO, "data", "pilot", "profiles.zarr"))
    pt = int(np.argmin((z.lat.values - 31.8728) ** 2 + (z.lon.values + 106.6981) ** 2))
    rows = []
    for k in rng.permutation(keep):
        if len(rows) >= a.n:
            break
        ub, vb = d["u"][k][sel].astype(float), d["v"][k][sel].astype(float)
        bad = (ub == -32768) | (vb == -32768)
        ub, vb = np.where(bad, np.nan, ub * 0.1), np.where(bad, np.nan, vb * 0.1)
        day = t[k] - pd.Timedelta(days=1)                  # the 00Z balloon flies in the 23 UTC hour of the day before
        try:
            p = fetch(day)
            r = parse(p) if p else None
        except Exception:   # noqa: BLE001  (a missing or unreadable volume: skip the day)
            r = None
        if r is None:
            continue
        try:
            e = z.isel(point=pt).sel(time=t[k].to_datetime64())
            ue, ve = e["u"].values.astype(float), e["v"].values.astype(float)
        except KeyError:
            continue
        rows.append((ub, vb, r[0], r[1], ue, ve))
    n = len(rows)
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) / 1e6
    print(f"{n} days 2021-2023 with an EPZ balloon (00Z) and a radar VAD volume near 23:30 UTC; files {size:.1f} MB in data/raw/nexrad_nvw")
    U = {k: np.array([r[i] for r in rows]) for i, k in enumerate(("ub", "vb", "ur", "vr", "ue", "ve"))}
    print("band       radar |error| / ERA5 |error| (m/s, vector)   speed bias radar / ERA5   share of days with a radar value")
    for name, lo, hi in BANDS:
        m = (H >= lo) & (H < hi)
        er = np.hypot(U["ur"][:, m] - U["ub"][:, m], U["vr"][:, m] - U["vb"][:, m])
        ee = np.hypot(U["ue"][:, m] - U["ub"][:, m], U["ve"][:, m] - U["vb"][:, m])
        both = np.isfinite(er) & np.isfinite(ee)
        sb = np.hypot(U["ub"][:, m], U["vb"][:, m])
        br = (np.hypot(U["ur"][:, m], U["vr"][:, m]) - sb)[both].mean()
        be = (np.hypot(U["ue"][:, m], U["ve"][:, m]) - sb)[both].mean()
        print(f"  {name:9s}  {er[both].mean():5.2f} / {ee[both].mean():5.2f}                              {br:+5.2f} / {be:+5.2f}            {np.isfinite(U['ur'][:, m]).mean():.2f}")


if __name__ == "__main__":
    main()
