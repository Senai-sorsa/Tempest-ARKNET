"""Download the ERA5 boundary-layer fill (8 pressure levels the Earthmover store lacks) from the Copernicus CDS.

    python -m tempest.ingest.fetch_cds [--out data/raw/era5_cds] [--first 1991] [--last 2025] [--in-flight 20]

Needs a free CDS account and %USERPROFILE%\\.ecmwfdatastoresrc holding `url:` and `key:` (never commit it).
One request per month -> <out>/<yyyymm>.grib. The ledger <out>/ledger.csv (yyyymm, request_id, status) is the
state: rerunning after a crash only polls and downloads, it never pays for a request twice.
"""
import argparse
import calendar
import csv
import os
import time

from ecmwf.datastores import Client

DATASET = "reanalysis-era5-pressure-levels"
AREA = [34, -108, 31, -101]  # N, W, S, E


def request(yyyymm):
    return {
        "product_type": ["reanalysis"],
        "variable": ["u_component_of_wind", "v_component_of_wind", "temperature", "relative_humidity", "geopotential"],
        "pressure_level": ["975", "950", "900", "875", "825", "800", "775", "750"],
        "year": [yyyymm[:4]], "month": [yyyymm[4:]],
        "day": [f"{d:02d}" for d in range(1, calendar.monthrange(int(yyyymm[:4]), int(yyyymm[4:]))[1] + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": AREA,
        "data_format": "grib",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/era5_cds")
    ap.add_argument("--first", type=int, default=1991)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--in-flight", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ledger_path = os.path.join(a.out, "ledger.csv")
    ledger = {}
    if os.path.exists(ledger_path):
        with open(ledger_path, newline="") as f:
            ledger = {r["yyyymm"]: r for r in csv.DictReader(f)}

    def save():
        with open(ledger_path + ".tmp", "w", newline="") as f:
            w = csv.DictWriter(f, ["yyyymm", "request_id", "status"])
            w.writeheader()
            w.writerows(ledger.values())
        for attempt in range(10):  # Windows: antivirus/indexer can lock the just-written file for a moment
            try:
                return os.replace(ledger_path + ".tmp", ledger_path)
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(1)

    client = Client(progress=False)
    client.check_authentication()
    months = [f"{y}{m:02d}" for y in range(a.first, a.last + 1) for m in range(1, 13)]
    while True:
        pending = [k for k in months if not os.path.exists(os.path.join(a.out, f"{k}.grib"))]
        if not pending:
            print("all months downloaded", flush=True)
            return
        for k in pending:
            r = ledger.get(k)
            if r and r["request_id"]:
                remote = client.get_remote(r["request_id"])
                r["status"] = remote.status
                if r["status"] == "successful":
                    dst = os.path.join(a.out, f"{k}.grib")
                    remote.download(dst + ".part")
                    os.replace(dst + ".part", dst)
                    print(f"{k}: downloaded", flush=True)
                elif r["status"] in ("failed", "rejected"):
                    print(f"{k}: {r['status']}, resubmitting", flush=True)
                    r["request_id"] = ""
            in_flight = sum(1 for x in ledger.values() if x["request_id"] and x["status"] in ("accepted", "running"))
            if (not r or not r["request_id"]) and in_flight < a.in_flight:
                rid = client.submit(DATASET, request(k)).request_id
                ledger[k] = dict(yyyymm=k, request_id=rid, status="accepted")
                print(f"{k}: submitted {rid}", flush=True)
            save()
        time.sleep(60)


if __name__ == "__main__":
    main()
