"""Download hourly airport weather reports (ASOS/METAR) with wind and gusts from the Iowa Environmental Mesonet.

    python -m tempest.ingest.fetch_asos [--out data/raw/asos] [--first 2000] [--last 2025]

One CSV per station and year in <out>/<station>/<year>.csv (UTC). Truth for the gust module (Phase 3.1):
MAF = Midland International (the Midland site), TCS = Truth or Consequences (closest ASOS to Spaceport America, ~30 km).
The service rate-limits; this waits between requests and retries. Existing files are skipped. Gusts are only reported
when the peak beats the lull by 10 kt or more, so an empty `gust` means "no reportable gust", not "unknown".
"""
import argparse
import os
import time
import urllib.parse
import urllib.request

STATIONS = ["MAF", "TCS"]
URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def fetch_year(station, year, tries=6):
    q = [("station", station), ("data", "sknt"), ("data", "gust"), ("data", "drct"), ("data", "tmpf"), ("year1", year), ("month1", 1),
         ("day1", 1), ("year2", year + 1), ("month2", 1), ("day2", 1), ("tz", "Etc/UTC"), ("format", "onlycomma"),
         ("latlon", "no"), ("missing", "empty"), ("trace", "empty"), ("direct", "no"), ("report_type", 3), ("report_type", 4)]
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "tempest-asos"}), timeout=300) as r:
                text = r.read().decode("utf-8", errors="replace")
            if text.startswith("station,valid"):
                return text
        except Exception as e:  # noqa: BLE001 - network hiccups of any kind are retried
            print(f"{station} {year}: {type(e).__name__}", flush=True)
        time.sleep(30 * (k + 1))  # "Too many requests": back off
    raise RuntimeError(f"{station} {year}: gave up")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/asos")
    ap.add_argument("--first", type=int, default=2000)
    ap.add_argument("--last", type=int, default=2025)
    a = ap.parse_args()
    for st in STATIONS:
        os.makedirs(os.path.join(a.out, st), exist_ok=True)
        for y in range(a.first, a.last + 1):
            path = os.path.join(a.out, st, f"{y}.csv")
            if os.path.exists(path):
                continue
            text = fetch_year(st, y)
            with open(path + ".part", "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(path + ".part", path)
            print(f"{st} {y}: {text.count(chr(10)) - 1:,} reports", flush=True)
            time.sleep(8)


if __name__ == "__main__":
    main()
