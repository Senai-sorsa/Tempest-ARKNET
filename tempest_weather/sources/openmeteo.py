"""Open-Meteo forecast client (standard library only). One call returns the hourly pressure-level and surface fields tempest_weather.forecast needs at one point.

    doc = fetch(lat, lon, day="2026-11-08", model="ecmwf_ifs025")       # network; raises OSError / ValueError on failure
The tool takes `fetch` as a parameter so tests (and offline users) can pass a function that returns a canned response.
"""
import json
import urllib.parse
import urllib.request

from tempest_weather.forecast import LEVELS_SERVED

BASE = "https://api.open-meteo.com/v1/forecast"
SURFACE = ["temperature_2m", "dew_point_2m", "wind_speed_10m", "wind_direction_10m", "surface_pressure"]
PRESSURE = ["temperature", "relative_humidity", "wind_speed", "wind_direction", "geopotential_height"]


def hourly_variables():
    return SURFACE + [f"{v}_{p}hPa" for v in PRESSURE for p in LEVELS_SERVED]


def url(lat, lon, day, model="ecmwf_ifs025"):
    q = dict(latitude=f"{lat:.4f}", longitude=f"{lon:.4f}", hourly=",".join(hourly_variables()), start_date=day, end_date=day, models=model, wind_speed_unit="ms",
             timezone="GMT")
    return BASE + "?" + urllib.parse.urlencode(q)


def fetch(lat, lon, day, model="ecmwf_ifs025", timeout=30):
    with urllib.request.urlopen(url(lat, lon, day, model), timeout=timeout) as r:
        doc = json.loads(r.read().decode("utf-8"))
    if "hourly" not in doc:
        raise ValueError(f"Open-Meteo answered without hourly data: {str(doc)[:200]}")
    return doc
