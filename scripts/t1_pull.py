"""23.T1: pull NCEI 1-s radiosonde C-BUFR months, keep only EPZ (WBAN 03020) and MAF (23023), parse each flight to a 50 m grid, drop the raw files.
Output: data/t1/<station>_<yyyymm>.npz  (z [m, geopotential, ASL], time [flight start, ns], u, v, T [K], p [Pa]; shape (flights, nz); NaN where missing)
Log: docs/results/logs/t1_provenance.log (source, files, counts).  Usage: python scripts/t1_pull.py 2024-01 2025-12   (months without an archive are skipped)
"""
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

import numpy as np
from eccodes import (codes_bufr_new_from_file, codes_get, codes_get_array, codes_release, codes_set)

BASE = "https://www.ncei.noaa.gov/data/us-radiosonde-bufr/archive/"
ST = {"03020": "EPZ", "23023": "MAF"}
Z = np.arange(1250.0, 30001.0, 50.0)
OUT, TMP, LOG = "data/t1", "data/t1_tmp", "docs/results/logs/t1_provenance.log"


def parse(path):
    f = open(path, "rb")
    h = codes_bufr_new_from_file(f)
    f.close()
    if h is None:
        return None
    try:
        codes_set(h, "unpack", 1)
        g = lambda k: np.array(codes_get_array(h, k), float)
        z, t, sp, wd = g("nonCoordinateGeopotentialHeight"), g("airTemperature"), g("windSpeed"), g("windDirection")
        p = g("pressure")[-len(z):]
        date, tm = codes_get(h, "typicalDate"), codes_get(h, "typicalTime")
        for a in (z, t, sp, wd, p):
            a[np.abs(a) > 1e20] = np.nan
        u, v = -sp * np.sin(np.radians(wd)), -sp * np.cos(np.radians(wd))
        zm = np.fmax.accumulate(np.where(np.isfinite(z), z, -1e9))        # ascent: height must not go down
        ok = np.isfinite(z) & (z >= zm - 1e-6)
        row = []
        for a in (u, v, t, p):
            m = ok & np.isfinite(a)
            row.append(np.interp(Z, z[m], a[m], left=np.nan, right=np.nan) if m.sum() > 100 else np.full(Z.size, np.nan))
        d8, t6 = f"{int(date):08d}", f"{int(tm):06d}"
        return np.datetime64(f"{d8[:4]}-{d8[4:6]}-{d8[6:]}T{t6[:2]}:00"), row
    finally:
        codes_release(h)


def month(ym):
    y, m = ym.split("-")
    if all(os.path.exists(f"{OUT}/{n}_{y}{m}.npz") for n in ST.values()):
        return f"{ym}: already parsed"
    for k in range(6):                                  # the server sometimes refuses; wait and retry
        try:
            idx = urllib.request.urlopen(BASE, timeout=120).read().decode()
            break
        except Exception:
            time.sleep(60)
    else:
        return f"{ym}: listing unreachable"
    mt = re.findall(rf'(us-radiosonde_CBUFR_d{y}{m}_c\d+\.tar\.gz)', idx)
    if not mt:
        return f"{ym}: no C-BUFR archive"
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    os.makedirs(OUT, exist_ok=True)
    cmd = f'curl -sL --retry 3 "{BASE}{mt[0]}" | tar -xz -C {TMP} --wildcards "03020_*" "23023_*"'
    subprocess.run(cmd, shell=True, check=False)
    msg = []
    for wb, name in ST.items():
        fl = sorted(x for x in os.listdir(TMP) if x.startswith(wb + "_"))
        rows, times = [], []
        for x in fl:
            try:
                r = parse(os.path.join(TMP, x))
            except Exception as e:
                msg.append(f"{x} parse error {type(e).__name__}")
                continue
            if r:
                times.append(r[0])
                rows.append(r[1])
        if rows:
            a = np.array(rows)
            np.savez_compressed(f"{OUT}/{name}_{y}{m}.npz", z=Z, time=np.array(times), u=a[:, 0], v=a[:, 1], T=a[:, 2], p=a[:, 3])
        msg.append(f"{name} {len(rows)} flights of {len(fl)} files")
    shutil.rmtree(TMP, ignore_errors=True)
    return f"{ym}: {mt[0]}; " + "; ".join(msg)


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    ys, ms = int(a[:4]), int(a[5:])
    ye, me = int(b[:4]), int(b[5:])
    while (ys, ms) <= (ye, me):
        line = month(f"{ys}-{ms:02d}")
        print(line, flush=True)
        with open(LOG, "a", encoding="utf-8") as lg:
            lg.write(line + "\n")
        ms += 1
        if ms > 12:
            ys, ms = ys + 1, 1
