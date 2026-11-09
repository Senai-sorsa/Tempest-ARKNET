"""Daily forecast logger: saves the raw Open-Meteo ensemble members (WeatherNext 2 + ECMWF IFS ENS) at each
registered site. Past ensemble members are not served anywhere, so days not logged are lost for good; this archive
is what the near-term mode (TOOL_PLAN T3) is checked against.

    python -m tempest.ops.logger                  # fetch every active site x model; skip what is already stored
    python -m tempest.ops.logger --validate FILE  # check one stored file
    python -m tempest.ops.logger --loop 12        # run forever, one pass every 12 h (alternative to a scheduler)

Files: data/ops/raw/<site>/<model>/<YYYYMMDD>_<HH>z.json.gz, HH = fetch time rounded down to 12 h, so a rerun in
the same half-day is skipped. Each request appends one line to data/ops/logger.log.
A file is written only if it passes validation (fail closed); the response is stored unchanged.
"""
import argparse
import gzip
import json
import os
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODELS = {"ecmwf_ifs025": 51, "google_weathernext2_ensemble": 64}  # model -> members expected (control included)
LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]  # 975/950/900/800 hPa are not served (all null)
LEVEL_VARS = ["temperature", "relative_humidity", "wind_speed", "wind_direction", "geopotential_height"]
SURFACE = ["temperature_2m", "relative_humidity_2m", "surface_pressure", "wind_speed_10m", "wind_direction_10m",
           "wind_gusts_10m"]
HOURLY = SURFACE + [f"{v}_{l}hPa" for l in LEVELS for v in LEVEL_VARS]
# plausible ranges in the API's units (Celsius, %, m/s, degrees, m, hPa); longest prefix first
RANGES = [("temperature", -100, 60), ("relative_humidity", 0, 100.5), ("wind_speed", 0, 120),
          ("wind_direction", 0, 360.001), ("geopotential_height", -500, 25000), ("surface_pressure", 300, 1100),
          ("wind_gusts", 0, 150)]
OPTIONAL = {"google_weathernext2_ensemble": {"relative_humidity_2m", "wind_gusts_10m"}}  # served as all-null by this model
MAX_BAD_MEMBER_FRAC = 0.10  # more than this share of bad members rejects the file
ROOT = "data/ops"


def sites(path="configs/sites.toml"):
    with open(path, "rb") as f:
        return [s for s in tomllib.load(f)["site"] if s.get("active", True)]


def slot(now=None):
    now = now or datetime.now(timezone.utc)
    return f"{now:%Y%m%d}_{now.hour // 12 * 12:02d}z"


def request_url(site, model, days=16):
    q = dict(latitude=site["lat"], longitude=site["lon"], models=model, hourly=",".join(HOURLY),
             forecast_days=days, timezone="UTC", wind_speed_unit="ms")
    return URL + "?" + urllib.parse.urlencode(q, safe=",")


def fetch(url, tries=4, timeout=180):
    """Raw response bytes. Retries with backoff; honours Retry-After on HTTP 429 (never loops tightly)."""
    err = None
    for k in range(tries):
        wait = 15 * 2 ** k
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tempest-logger"}),
                                        timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 404):  # a bad request will not improve on retry
                raise
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 60))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(min(wait, 600))
    raise RuntimeError(f"fetch failed after {tries} tries: {err}")


def validate(doc, model):
    """-> (ok, message). Schema, member counts, ranges, missing values. Bad members are tolerated up to 10 %."""
    h = doc.get("hourly") if isinstance(doc, dict) else None
    if not h or "time" not in h:
        return False, "no hourly block"
    n_t = len(h["time"])
    if n_t < 24 * 10:
        return False, f"only {n_t} time steps"
    expect = MODELS.get(model)
    worst = 0
    for var in HOURLY:
        if var in OPTIONAL.get(model, ()):
            continue
        members = [k for k in h if k == var or (k.startswith(var + "_member") and k[len(var) + 7:].isdigit())]
        if expect and len(members) != expect:
            return False, f"{var}: {len(members)} members, expected {expect}"
        lo, hi = next(((a, b) for p, a, b in RANGES if var.startswith(p)), (-1e9, 1e9))
        bad = 0
        for m in members:
            col = h[m]
            if len(col) != n_t:
                return False, f"{m}: length {len(col)} != {n_t}"
            vals = [x for x in col[:72] if x is not None]  # the first 3 days must be present and in range
            if len(vals) < 72 or min(vals) < lo or max(vals) > hi:
                bad += 1
        worst = max(worst, bad)
        if members and bad / len(members) > MAX_BAD_MEMBER_FRAC:
            return False, f"{var}: {bad}/{len(members)} bad members"
    return True, f"{n_t} steps, worst variable has {worst} bad members"


def path_for(site, model, tag):
    return os.path.join(ROOT, "raw", site["name"], model, f"{tag}.json.gz")


def log(msg):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "logger.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc):%F %T}Z {msg}\n")


def run_once(site_list=None, models=None, tag=None):
    tag = tag or slot()
    ok_all = True
    for s in site_list or sites():
        for model in models or MODELS:
            out = path_for(s, model, tag)
            if os.path.exists(out):
                log(f"{s['name']} {model} {tag}: already stored, skipped")
                continue
            try:
                raw = fetch(request_url(s, model))
                good, msg = validate(json.loads(raw), model)
            except Exception as e:  # keep going: one failing source must not stop the others
                raw, good, msg = None, False, f"{type(e).__name__}: {e}"
            if good:
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with gzip.open(out + ".part", "wb") as f:
                    f.write(raw)
                os.replace(out + ".part", out)  # atomic: a half-written file never looks stored
            else:
                ok_all = False
            log(f"{s['name']} {model} {tag}: {'stored' if good else 'REJECTED'} ({msg})")
            time.sleep(2)  # be gentle with the free tier
    return ok_all


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", help="validate one stored .json.gz (the model is read from its folder name)")
    ap.add_argument("--loop", type=float, help="repeat forever, one pass every this many hours")
    a = ap.parse_args()
    if a.validate:
        with gzip.open(a.validate, "rt", encoding="utf-8") as f:
            ok, msg = validate(json.load(f), os.path.basename(os.path.dirname(a.validate)))
        print(msg)
        raise SystemExit(0 if ok else 1)
    while True:
        ok = run_once()
        if not a.loop:
            raise SystemExit(0 if ok else 1)
        time.sleep(a.loop * 3600)


if __name__ == "__main__":
    main()
