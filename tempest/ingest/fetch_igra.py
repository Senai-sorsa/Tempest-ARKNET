"""Download IGRA v2.2 derived radiosonde files (the truth data).

    python -m tempest.ingest.fetch_igra [--out data/raw/igra] [IDS ...]
"""
import argparse
import os
import urllib.request

BASE = "https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/derived-por/"
STATIONS = ["USM00072364", "USM00072265"]  # Santa Teresa NM, Midland TX


def download(url, dst, refresh=False):
    """Fetch url to dst via a .part file, so an interrupted download never looks finished."""
    if os.path.exists(dst) and not refresh:
        print(f"{dst}: exists, skipping", flush=True)
        return dst
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "tempest-arknet"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst + ".part", "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(dst + ".part", dst)
    print(f"{dst}: {os.path.getsize(dst) / 1e6:.1f} MB", flush=True)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/raw/igra")
    ap.add_argument("ids", nargs="*", default=STATIONS)
    a = ap.parse_args()
    for sid in a.ids:
        download(f"{BASE}{sid}-drvd.txt.zip", os.path.join(a.out, f"{sid}-drvd.txt.zip"))


if __name__ == "__main__":
    main()
