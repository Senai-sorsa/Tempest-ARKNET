"""Phase 4 logger (PHASE4_FORECAST.md 4.3): daily archive of the ECMWF 46-day ensemble (EC46) at the registered sites.

    python -m tempest.ops.logger_p4                 # one pass: fetch what is not stored for today (UTC date)
    python -m tempest.ops.logger_p4 --loop 24       # repeat forever, one pass every 24 h
    python -m tempest.ops.logger_p4 --validate FILE

The Seasonal API serves 51 members x 46 days of DAILY SURFACE variables only (no pressure levels) and keeps past runs only from
2025-09, so this archive is what weeks 3-6 can be checked against later. Files: data/ops/raw/<site>/ecmwf_ec46/<YYYYMMDD>.json.gz, same
fail-closed rules as tempest.ops.logger (validated, atomic writes, one log line per request in data/ops/logger.log).
"""
import argparse
import gzip
import json
import os
import time
import urllib.parse
from datetime import datetime, timezone

from tempest.ops import logger as L

URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
MODEL = "ecmwf_ec46"
DAILY = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", "wind_speed_10m_mean", "wind_gusts_10m_max",
         "relative_humidity_2m_mean", "surface_pressure_mean", "precipitation_sum"]
MEMBERS, DAYS = 51, 40  # at least this many days must be present (the feed offers 46)


def request_url(site):
    q = dict(latitude=site["lat"], longitude=site["lon"], models=MODEL, daily=",".join(DAILY), forecast_days=46, timezone="UTC", wind_speed_unit="ms")
    return URL + "?" + urllib.parse.urlencode(q, safe=",")


def validate(doc):
    d = doc.get("daily") if isinstance(doc, dict) else None
    if not d or "time" not in d:
        return False, "no daily block"
    n = len(d["time"])
    if n < DAYS:
        return False, f"only {n} days"
    for var in DAILY:
        keys = [k for k in d if k == var or (k.startswith(var + "_member") and k[len(var) + 7:].isdigit())]
        if len(keys) != MEMBERS:
            return False, f"{var}: {len(keys)} members, expected {MEMBERS}"
        bad = sum(1 for k in keys if sum(x is not None for x in d[k][:DAYS - 5]) < DAYS - 8)
        if bad / len(keys) > L.MAX_BAD_MEMBER_FRAC:
            return False, f"{var}: {bad}/{len(keys)} members mostly empty"
    return True, f"{n} days, {MEMBERS} members, {len(DAILY)} variables"


def run_once(site_list=None, tag=None):
    tag = tag or f"{datetime.now(timezone.utc):%Y%m%d}"
    ok_all = True
    for s in site_list or L.sites():
        out = os.path.join(L.ROOT, "raw", s["name"], MODEL, f"{tag}.json.gz")
        if os.path.exists(out):
            L.log(f"{s['name']} {MODEL} {tag}: already stored, skipped")
            continue
        try:
            raw = L.fetch(request_url(s))
            good, msg = validate(json.loads(raw))
        except Exception as e:  # keep going: one failing site must not stop the other
            raw, good, msg = None, False, f"{type(e).__name__}: {e}"
        if good:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with gzip.open(out + ".part", "wb") as f:
                f.write(raw)
            os.replace(out + ".part", out)
        else:
            ok_all = False
        L.log(f"{s['name']} {MODEL} {tag}: {'stored' if good else 'REJECTED'} ({msg})")
        time.sleep(2)
    return ok_all


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate")
    ap.add_argument("--loop", type=float)
    a = ap.parse_args()
    if a.validate:
        with gzip.open(a.validate, "rt", encoding="utf-8") as f:
            ok, msg = validate(json.load(f))
        print(msg)
        raise SystemExit(0 if ok else 1)
    while True:
        ok = run_once()
        if not a.loop:
            raise SystemExit(0 if ok else 1)
        time.sleep(a.loop * 3600)


if __name__ == "__main__":
    main()
