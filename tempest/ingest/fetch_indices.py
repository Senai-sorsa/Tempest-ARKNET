"""Download the climate driver indices (ONI, QBO u30/u50, warm water volume). Always refreshed: they update monthly.

    python -m tempest.ingest.fetch_indices [--out data/raw/indices]
"""
import argparse
import os

from tempest.ingest.fetch_igra import download

URLS = {
    "oni.txt": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "qbo_u30.txt": "https://www.cpc.ncep.noaa.gov/data/indices/qbo.u30.index",
    "qbo_u50.txt": "https://www.cpc.ncep.noaa.gov/data/indices/qbo.u50.index",
    "wwv.txt": "https://www.pmel.noaa.gov/tao/wwv/data/wwv.dat",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/raw/indices")
    a = ap.parse_args()
    for name, url in URLS.items():
        download(url, os.path.join(a.out, name), refresh=True)


if __name__ == "__main__":
    main()
