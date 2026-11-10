"""Fresh one-time final-test window (user approval 2026-11-09, ASK_LATER 14): ERA5 for 2026 July-October over the pilot box from the Copernicus CDS, because the Earthmover
store (data/raw/era5_em80) ends on 2026-06-30. Two requests per month into data/raw/era5_2026h2 (its own new folder):
  pl1_ / pl2_ / pl3_<yyyymm>.grib   u, v, t, r, z on the 13 Earthmover levels + the 8 boundary-layer levels (21 in all, 7 per request: one 21-level month exceeds the CDS cost limit), hourly;
  sfc_<yyyymm>.grib  10u, 10v, 100u, 100v, 2t, 2d, sp, hourly.
The ledger (ledger.csv: key, request_id, status) is the state, so a rerun only polls and downloads. Needs %USERPROFILE%\\.ecmwfdatastoresrc (never commit it). Nothing here is scored:
the data are converted, profiled and scored ONCE at the very end (lock file data/FINAL_TEST_2026H2_DONE).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/fetch_final_window.py [--months 202607 202608 202609 202610]
"""
import argparse
import calendar
import csv
import os
import time

from ecmwf.datastores import Client

AREA = [34, -108, 31, -101]
LEVELS = ["1000", "975", "950", "925", "900", "875", "850", "825", "800", "775", "750", "700", "600", "500", "400", "300", "250", "200", "150", "100", "50"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "era5_2026h2")


def days(ym):
    return [f"{d:02d}" for d in range(1, calendar.monthrange(int(ym[:4]), int(ym[4:]))[1] + 1)]


GROUPS = {"pl1": LEVELS[:7], "pl2": LEVELS[7:14], "pl3": LEVELS[14:]}


def req(kind, ym):
    base = {"product_type": ["reanalysis"], "year": [ym[:4]], "month": [ym[4:]], "day": days(ym), "time": [f"{h:02d}:00" for h in range(24)], "area": AREA, "data_format": "grib"}
    if kind in GROUPS:
        return "reanalysis-era5-pressure-levels", dict(base, variable=["u_component_of_wind", "v_component_of_wind", "temperature", "relative_humidity", "geopotential"], pressure_level=GROUPS[kind])
    return "reanalysis-era5-single-levels", dict(base, variable=["10m_u_component_of_wind", "10m_v_component_of_wind", "100m_u_component_of_wind", "100m_v_component_of_wind",
                                                                 "2m_temperature", "2m_dewpoint_temperature", "surface_pressure"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*", default=["202607", "202608", "202609", "202610"])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lp = os.path.join(OUT, "ledger.csv")
    ledger = {}
    if os.path.exists(lp):
        with open(lp, newline="") as f:
            ledger = {r["key"]: r for r in csv.DictReader(f)}

    def save():
        with open(lp + ".tmp", "w", newline="") as f:
            w = csv.DictWriter(f, ["key", "request_id", "status"])
            w.writeheader()
            w.writerows(ledger.values())
        os.replace(lp + ".tmp", lp)
    client = Client(progress=False)
    client.check_authentication()
    keys = [f"{k}_{m}" for m in a.months for k in ("pl1", "pl2", "pl3", "sfc")]
    while True:
        pending = [k for k in keys if not os.path.exists(os.path.join(OUT, f"{k}.grib"))]
        if not pending:
            print("all downloaded", flush=True)
            return
        for k in pending:
            r = ledger.get(k)
            if r and r["request_id"]:
                remote = client.get_remote(r["request_id"])
                r["status"] = remote.status
                if r["status"] == "successful":
                    dst = os.path.join(OUT, f"{k}.grib")
                    remote.download(dst + ".part")
                    os.replace(dst + ".part", dst)
                    print(f"{k}: downloaded {os.path.getsize(dst) / 1e6:.0f} MB", flush=True)
                elif r["status"] in ("failed", "rejected"):
                    print(f"{k}: {r['status']}, resubmitting", flush=True)
                    r["request_id"] = ""
            if not r or not r["request_id"]:
                ds, body = req(*k.split("_"))
                rid = client.submit(ds, body).request_id
                ledger[k] = dict(key=k, request_id=rid, status="accepted")
                print(f"{k}: submitted {rid}", flush=True)
            save()
        time.sleep(60)


if __name__ == "__main__":
    main()
