"""Fetch NREL WIND Toolkit (WTK CONUS v1.0.0, 2 km WRF, hourly, 2007-2013; public AWS Open Data, no key) time series at a few points: wind speed at 10 / 40 / 80 / 100 / 200 m, wind direction at 10 m (more variables cost about 70 MB and 2 min per variable, site and year).
Only the HDF5 chunks that hold the points are read (HTTP range requests through scripts/rangefile.py). Output: data/raw/wtk/<site>_<year>.npz (arrays in physical units, the time index as text) + a line in data/download_ledger.txt.

    .venv/Scripts/python -I scripts/fetch_wtk_points.py --years 2012 2011 2010 [--sites TCS MAF SAF]

WTK is a model (WRF run from ERA-Interim, no surface-station assimilation), so it is an INDEPENDENT high-resolution reference for the 10-200 m wind, not a measurement.
"""
import argparse
import os
import sys
import time

import h5py
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from rangefile import RangeFile   # noqa: E402

SITES = {"TCS": (33.2369, -107.2672), "MAF": (31.9425, -102.2019), "SAF": (32.9394, -106.9120)}      # SAF = the Spaceport America launch site used in the validation
VARS = ["windspeed_10m", "windspeed_40m", "windspeed_80m", "windspeed_100m", "windspeed_200m", "winddirection_10m"]
URL = "https://nrel-pds-wtk.s3.amazonaws.com/conus/v1.0.0/wtk_conus_{y}.h5"


def nearest_index(coords_ds, lat, lon, guess_rows=None):
    """Brute force over the coordinate table in slabs (2.5 M x 2 float32 = 20 MB)."""
    best, bi = 1e9, -1
    n = coords_ds.shape[0]
    step = 249998
    for a in range(0, n, step):
        c = coords_ds[a:a + step]
        d = (c[:, 0] - lat) ** 2 + ((c[:, 1] - lon) * np.cos(np.radians(lat))) ** 2
        k = int(np.argmin(d))
        if d[k] < best:
            best, bi = float(d[k]), a + k
    return bi, float(np.sqrt(best)) * 111.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2012])
    ap.add_argument("--sites", nargs="+", default=list(SITES))
    a = ap.parse_args()
    out = os.path.join(REPO, "data", "raw", "wtk")
    os.makedirs(out, exist_ok=True)
    total = 0
    for y in a.years:
        t0 = time.time()
        rf = RangeFile(URL.format(y=y), block=512 * 1024)
        h = h5py.File(rf, "r")
        idx = {}
        for s in a.sites:
            idx[s], dkm = nearest_index(h["coordinates"], *SITES[s])
            print(f"{y} {s}: grid index {idx[s]}, {dkm:.1f} km from the site", flush=True)
        times = [t.decode() for t in h["time_index"][:]]
        for s in a.sites:
            path = os.path.join(out, f"{s}_{y}.npz")
            if os.path.exists(path):
                continue
            arr = {}
            for v in VARS:
                print(f"    {s} {y} {v} ({time.time() - t0:.0f} s, {rf.fetched / 1e6:.0f} MB)", flush=True)
                d = h[v]
                sf = float(d.attrs.get("scale_factor", 1.0))
                arr[v] = d[:, idx[s]].astype(np.float64) / sf
            np.savez(path, time=np.array(times), index=idx[s], **arr)
            print(f"  {path} ({time.time() - t0:.0f} s, {rf.fetched / 1e6:.0f} MB fetched so far)", flush=True)
        total += rf.fetched
        with open(os.path.join(REPO, "data", "download_ledger.txt"), "a", encoding="utf-8") as f:
            f.write(f"2026-11-09 | NREL WTK CONUS {y} points {','.join(a.sites)} (range requests) | {rf.fetched / 1e9:.2f} GB\n")
        h.close()
    print(f"done, {total / 1e9:.2f} GB fetched in this run")


if __name__ == "__main__":
    main()
