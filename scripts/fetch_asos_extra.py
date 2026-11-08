"""Fetch hourly ASOS winds and temperature for extra stations (IEM, keyless, small) into data/raw/asos/<ST>/<year>.csv, the same layout as the existing TCS and MAF files. Skips files that exist.

    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/fetch_asos_extra.py [--years 2015 2025] [--stations ONM LRU ELP ALM FST PEQ ABQ]
About 5 MB per station for eleven years; one request per station-year at 1 per second through tempest_weather_v2._net (timeouts, retries, rate limit, atomic write).
"""
import argparse
import csv
import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from tempest_weather_v2 import _files, _net   # noqa: E402

URL = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st}&data=sknt&data=gust&data=drct&data=tmpf&year1={y}&month1=1&day1=1&year2={y}&month2=12&day2=31"
       "&tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=empty&trace=empty&direct=no&report_type=3&report_type=4")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs=2, type=int, default=[2015, 2025])
    ap.add_argument("--stations", nargs="+", default=["ONM", "LRU", "ELP", "ALM", "FST", "PEQ", "ABQ"])
    a = ap.parse_args()
    for st in a.stations:
        for y in range(a.years[0], a.years[1] + 1):
            path = os.path.join(REPO, "data", "raw", "asos", st, f"{y}.csv")
            if os.path.exists(path):
                continue
            raw = _net.fetch(URL.format(st=st, y=y), service="iem", timeout=90, retries=2).decode("utf-8", "replace")
            rows = list(csv.DictReader(io.StringIO(raw)))
            if not rows or "valid" not in rows[0]:
                print(f"{st} {y}: no data ({raw[:80]!r})", flush=True)
                continue
            out = io.StringIO()
            w = csv.writer(out, lineterminator="\n")
            w.writerow(["station", "valid", "sknt", "gust", "drct", "tmpf"])
            for r in rows:
                w.writerow([r["station"], r["valid"], r.get("sknt", ""), r.get("gust", ""), r.get("drct", ""), r.get("tmpf", "")])
            _files.atomic_write(path, out.getvalue())
            print(f"{st} {y}: {len(rows)} reports", flush=True)


if __name__ == "__main__":
    main()
