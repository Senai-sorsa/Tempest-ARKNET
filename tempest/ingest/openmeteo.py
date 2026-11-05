"""Open-Meteo client with an on-disk cache (PHASE4_FORECAST.md 4.1): one function per API, retry with backoff, no tight loops.

    from tempest.ingest import openmeteo as om
    doc = om.ensemble(31.94, -102.19, models="ecmwf_ifs025", hourly=["temperature_2m"], forecast_days=3)
    doc = om.historical_forecast(31.94, -102.19, models="gfs_global", hourly=["temperature_500hPa"], start="2023-06-01", end="2023-06-02")

Responses are cached as JSON under `cache_dir` (default data/cache/openmeteo), keyed by the full request; `max_age_hours` decides when a cached
answer is stale (None = never expires, right for archives; live forecasts should pass a small number). A stale or missing entry triggers one request;
on failure the stale cached answer is returned with doc["_stale"] = True if one exists, otherwise the error is raised. Free tier: about 10,000 calls a day,
and requests with many variables or long spans count as several calls; this module does not spread them out, callers batch.
`fetcher` can be replaced in tests so no network is touched.
"""
import hashlib
import json
import os
import time
import urllib.parse

from tempest.ops import logger as _lg

BASES = dict(
    forecast="https://api.open-meteo.com/v1/forecast",
    ensemble="https://ensemble-api.open-meteo.com/v1/ensemble",
    historical_forecast="https://historical-forecast-api.open-meteo.com/v1/forecast",
    previous_runs="https://previous-runs-api.open-meteo.com/v1/forecast",
    single_runs="https://single-runs-api.open-meteo.com/v1/forecast",
    seasonal="https://seasonal-api.open-meteo.com/v1/seasonal",
    elevation="https://api.open-meteo.com/v1/elevation",
)
CACHE_DIR = "data/cache/openmeteo"
fetcher = _lg.fetch  # replaced by tests


def _url(api, params):
    q = {k: (",".join(v) if isinstance(v, (list, tuple)) else v) for k, v in params.items() if v is not None}
    return BASES[api] + "?" + urllib.parse.urlencode(q, safe=",")


def get(api, params, max_age_hours=None, cache_dir=None):
    url = _url(api, params)
    d = cache_dir or CACHE_DIR
    path = os.path.join(d, hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")
    cached = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if max_age_hours is None or (time.time() - os.path.getmtime(path)) < max_age_hours * 3600:
            return cached
    try:
        doc = json.loads(fetcher(url))
        if isinstance(doc, dict) and doc.get("error"):
            raise RuntimeError(f"Open-Meteo refused the request: {doc.get('reason')}")
    except Exception:
        if cached is not None:  # degrade to the last good answer, flagged
            cached["_stale"] = True
            return cached
        raise
    os.makedirs(d, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as f:
        json.dump(doc, f)
    os.replace(path + ".part", path)
    return doc


def _site(lat, lon, **kw):
    return dict(latitude=lat, longitude=lon, timezone="UTC", **kw)


def ensemble(lat, lon, models, hourly, forecast_days=16, max_age_hours=3, **kw):
    return get("ensemble", _site(lat, lon, models=models, hourly=hourly, forecast_days=forecast_days, wind_speed_unit="ms"), max_age_hours, **kw)


def historical_forecast(lat, lon, models, hourly, start, end, **kw):
    return get("historical_forecast", _site(lat, lon, models=models, hourly=hourly, start_date=start, end_date=end, wind_speed_unit="ms"), None, **kw)


def previous_runs(lat, lon, models, hourly, start, end, **kw):
    return get("previous_runs", _site(lat, lon, models=models, hourly=hourly, start_date=start, end_date=end, wind_speed_unit="ms"), None, **kw)


def seasonal(lat, lon, daily, models="ecmwf_ec46", forecast_days=46, max_age_hours=12, **kw):
    return get("seasonal", _site(lat, lon, models=models, daily=daily, forecast_days=forecast_days, wind_speed_unit="ms"), max_age_hours, **kw)


def elevation(lat, lon, **kw):
    doc = get("elevation", dict(latitude=lat, longitude=lon), None, **kw)
    return float(doc["elevation"][0])
