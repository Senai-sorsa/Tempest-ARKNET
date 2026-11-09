"""Gust truth worldwide: hourly METAR/ASOS reports (wind, gust, direction, temperature) for ~200 airports spread over the globe.

    python -m tempest.ingest.fetch_asos_global [--out data/raw/asos_global] [--n 200] [--first 2016] [--last 2025]

Stations: every IEM *ASOS network (countries and US states), kept if the archive starts by 2015 and is still running,
minus everything within radius_deg of the locked holdouts (configs/global_holdout.toml sites + held IGRA stations);
then n picked by farthest-point sampling so they spread over climates instead of crowding into the US. The pick is
written once to <out>/stations.csv and reused. Downloads go year by year, newest first (a partial run already covers
every station), one CSV per station and year (<out>/<id>/<year>.csv), through tempest.ingest.fetch_asos.fetch_year
(rate-limit back-off), 8 s between requests. 2026 is never requested. A station-year that keeps failing is skipped and logged.
"""
import argparse
import csv
import json
import os
import time
import tomllib
import urllib.request

import numpy as np

from tempest.ingest.fetch_asos import fetch_year
from tempest.ingest.fetch_global import HOLDOUT, gc_deg, igra_stations

API = "https://mesonet.agron.iastate.edu/"


def get_json(path):
    with urllib.request.urlopen(urllib.request.Request(API + path, headers={"User-Agent": "tempest-asos"}), timeout=120) as r:
        return json.load(r)


def candidates():
    nets = [d["id"] for d in get_json("api/1/networks.json")["data"] if d["id"].endswith("ASOS")]
    out = []
    for n in nets:
        try:
            feats = get_json(f"geojson/network/{n}.geojson")["features"]
        except Exception as e:  # noqa: BLE001
            print(f"{n}: {type(e).__name__}", flush=True); continue
        for f in feats:
            pr = f["properties"]
            if pr.get("archive_end") is None and (pr.get("archive_begin") or "9999") <= "2015-01-01" and f.get("geometry"):
                lon, lat = f["geometry"]["coordinates"][:2]
                out.append((f["id"], n, float(lat), float(lon)))
        time.sleep(1)
    return out


def pick(cands, n):
    h = tomllib.load(open(HOLDOUT, "rb"))
    byid = {s[0]: s for s in igra_stations()}
    hold = [(s["lat"], s["lon"]) for s in h["site"]] + [(byid[i][1], byid[i][2]) for i in h["igra"]]
    lat, lon = np.array([c[2] for c in cands]), np.array([c[3] for c in cands])
    ok = np.ones(len(cands), bool)
    for a, b in hold:
        ok &= gc_deg(lat, lon, a, b) > h["radius_deg"]
    idx = np.flatnonzero(ok)
    chosen = [idx[np.argmin(np.abs(lat[idx]) + np.abs(lon[idx]))]]  # deterministic start, then farthest-point sampling
    d = gc_deg(lat[idx], lon[idx], lat[chosen[0]], lon[chosen[0]])
    while len(chosen) < min(n, len(idx)):
        k = idx[np.argmax(d)]
        chosen.append(k)
        d = np.minimum(d, gc_deg(lat[idx], lon[idx], lat[k], lon[k]))
    return [cands[k] for k in chosen]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/asos_global")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--first", type=int, default=2016)
    ap.add_argument("--last", type=int, default=2025)
    a = ap.parse_args()
    assert a.last <= 2025, "2026 is the locked test window"
    os.makedirs(a.out, exist_ok=True)
    sf = os.path.join(a.out, "stations.csv")
    if not os.path.exists(sf):
        st = pick(candidates(), a.n)
        with open(sf + ".part", "w", newline="") as f:
            csv.writer(f).writerows([("id", "network", "lat", "lon")] + st)
        os.replace(sf + ".part", sf)
    st = list(csv.DictReader(open(sf)))
    print(f"{len(st)} stations", flush=True)
    for y in range(a.last, a.first - 1, -1):
        for s in st:
            path = os.path.join(a.out, s["id"], f"{y}.csv")
            if os.path.exists(path):
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                text = fetch_year(s["id"], y)
            except RuntimeError as e:
                print(e, flush=True); continue
            with open(path + ".part", "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(path + ".part", path)
            print(f"{s['id']} {y}: {text.count(chr(10)) - 1:,} reports", flush=True)
            time.sleep(8)
    print("asos_global done", flush=True)


if __name__ == "__main__":
    main()
