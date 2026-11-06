"""Download the plain IGRA2 sounding files (data-por, not the 2x larger derived files) for every IGRA station in the global store.

    python -m tempest.ingest.fetch_igra_data [--out data/raw/igra2_data] [--points data/raw/era5_global/points.npz]

Stations = the IGRA ids in points.npz, which already excludes the locked holdout stations and everything within
radius_deg of the holdout sites (configs/global_holdout.toml); the held ids are re-checked here. Files are whole records
(up to ~80 MB zipped for long ones); they are converted to our 44 heights later and then deleted (docs/data/DATA_NEEDS.md).
Resumable: finished files are skipped; a failed station is retried 3 times, then listed at the end (exit 1 if any).
"""
import argparse
import os
import time

import numpy as np

from tempest.ingest.fetch_igra import download

BASE = "https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/igra2_data")
    ap.add_argument("--points", default="data/raw/era5_global/points.npz")
    a = ap.parse_args()
    p = np.load(a.points)
    ids = sorted(set(p["igra"]) - {"", "T"})
    assert not set(ids) & set(p["held_igra"]), "holdout station in the list"
    print(f"{len(ids)} stations", flush=True)
    failed = []
    for sid in ids:
        dst = os.path.join(a.out, f"{sid}-data.txt.zip")
        for k in range(3):
            try:
                download(BASE + f"{sid}-data.txt.zip", dst)
                break
            except Exception as e:  # noqa: BLE001 - network errors and 404s alike
                print(f"{sid}: {type(e).__name__} {e}", flush=True)
                time.sleep(20 * (k + 1))
        else:
            failed.append(sid)
    print(f"done, {len(failed)} failed: {failed}", flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
