"""Launch-day observation ingestion (spec R2, IL-156): find the nearest weather stations, fetch their latest METAR, and turn the report into a properly weighted observation.

    near = nearest(32.94, -106.91)                              # [(id, distance_km, elevation_m), ...]
    t, m = latest_report("TCS", launch_time_utc)                # newest METAR at or before the launch time (IEM, keyless; through _net)
    Launch(...).observe_latest()                                # does all of it and conditions the atmosphere

Why weights: an observation is not the pad state. Weights are FITTED on ASOS station pairs (scripts/obs_loso.py, 9 stations in southern NM and west Texas, anomalies against the month x hour climatology,
fit 2015-2022): the gain of a neighbour's wind anomaly on the target's is 0.62 (day) / 0.48 (night) within 100 km, 0.46 / 0.31 at 100-200 km, 0.36 / 0.20 at 200-350 km and 0.32 / 0.18 beyond; it barely decays
with the age of the report across stations (0-3 h), slowly by day (scale 27 h) and faster at night (12 h, stable and decoupled). A report from the SAME location (a pad anemometer, distance under 5 km) is much more
informative: the benchmark GW-1 gives 0.80 (u) / 0.88 (v) one hour earlier and 0.63 / 0.66 three hours earlier (decay time 6.3 h). The gain is turned into an observation error for the Gaussian update: with prior spread s
and gain r the observation sd is s * sqrt(1 / r - 1), so r = 1 pins the value and r = 0.5 moves the median half way.
"""
import csv
import io
import math
from datetime import datetime, timedelta, timezone

from tempest_weather_v2 import _net, metar as _metar

__all__ = ["STATIONS", "nearest", "latest_report", "persistence_gain", "representativeness_gain", "effective_gain", "observation_sigma", "night_weight", "TAU_H", "REP_TABLE"]

TAU_H = 6.3                                         # own-station persistence decay time, hours (GW-1)
# cross-station gain at age 0 by distance (km) for day and night (obs_loso.py bin means), elevation scale (fitted, weakly identified) and age decay time (hours)
REP_TABLE = {"day": ((0.0, 0.66), (50.0, 0.62), (150.0, 0.46), (275.0, 0.36), (500.0, 0.32)), "night": ((0.0, 0.52), (50.0, 0.48), (150.0, 0.31), (275.0, 0.20), (500.0, 0.18))}
REP_DZ = {"day": 1317.0, "night": 919.0}
# age factor of a CROSS-station gain relative to age 0 (obs_loso.py, pairs under 100 km): flat for about 3 h, then falling; beyond 6 h an exponential tail with this decay time (hours)
AGE_TABLE = {"day": ((0, 1.0), (1, 1.0), (2, 1.0), (3, 0.97), (6, 0.81)), "night": ((0, 1.0), (1, 0.98), (2, 0.92), (3, 0.83), (6, 0.60))}
TAU_X = {"day": 27.0, "night": 12.0}
OWN_STATION_KM = 5.0
# id: (latitude, longitude, elevation m). APPROXIMATE; IEM's station metadata is the authority. TCS and MAF are the stations used in the benchmark.
STATIONS = {
    "TCS": (33.2369, -107.2672, 1479.0),     # Truth or Consequences Municipal
    "ONM": (34.0225, -106.9031, 1486.0),     # Socorro Municipal
    "LRU": (32.2894, -106.9222, 1357.0),     # Las Cruces International
    "ELP": (31.8072, -106.3778, 1206.0),     # El Paso International
    "ALM": (32.8399, -105.9908, 1304.0),     # Alamogordo-White Sands Regional
    "MAF": (31.9425, -102.2019, 872.0),      # Midland International
    "FST": (30.9157, -102.9163, 920.0),      # Fort Stockton-Pecos County
    "PEQ": (31.3792, -103.5106, 790.0),      # Pecos Municipal
    "ABQ": (35.0402, -106.6092, 1619.0),     # Albuquerque Sunport
}
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180.0
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def nearest(lat, lon, k=3, max_km=150.0, stations=None):
    """The k nearest stations within max_km: [(id, distance_km, elevation_m)] sorted by distance."""
    rows = sorted((haversine_km(lat, lon, la, lo), sid, el) for sid, (la, lo, el) in (stations or STATIONS).items())
    return [(sid, d, el) for d, sid, el in rows if d <= max_km][:k]


def latest_report(station, when_utc, hours=6, fetch=None):
    """-> (time_utc, Metar) of the newest report at or before `when_utc` within `hours`, or (None, None). `fetch(url) -> bytes` is injectable (tests); the default goes through _net with the iem rate limit."""
    end = when_utc + timedelta(minutes=1)
    start = when_utc - timedelta(hours=hours)
    q = (f"?station={station}&data=metar&year1={start.year}&month1={start.month}&day1={start.day}&hour1={start.hour}&minute1=0"
         f"&year2={end.year}&month2={end.month}&day2={end.day}&hour2={end.hour}&minute2={end.minute}&tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4")
    raw = (fetch or (lambda u: _net.fetch(u, service="iem")))(IEM_URL + q)
    best = None
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))):
        try:
            t = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            text = row["metar"]
        except (KeyError, ValueError):
            continue
        if t <= when_utc and (best is None or t > best[0]):
            try:
                best = (t, _metar.parse(text))
            except _metar.MetarError:
                continue
    return best if best else (None, None)


def night_weight(solar_hour):
    """0 in the day (solar 08-17 h), 1 at night (20-05 h), linear in the transitions: the stable, decoupled regime the cross-station gains are lower in."""
    h = float(solar_hour) % 24.0
    if 8.0 <= h < 17.0:
        return 0.0
    if h >= 20.0 or h < 5.0:
        return 1.0
    return (h - 17.0) / 3.0 if 17.0 <= h < 20.0 else (8.0 - h) / 3.0


def persistence_gain(age_hours, tau=TAU_H):
    """Regression gain of the anomaly `age_hours` later on an observed anomaly at the SAME place: exp(-age / tau) (0.85 at 1 h, 0.62 at 3 h; GW-1: 0.80-0.88 and 0.63-0.66)."""
    return math.exp(-max(float(age_hours), 0.0) / tau)


def _blend(table_day_night, night):
    return (1.0 - night) * table_day_night["day"] + night * table_day_night["night"]


def representativeness_gain(distance_km, dz_m=0.0, night=0.0):
    """Gain of a station `distance_km` away and `dz_m` higher or lower on the pad's wind anomaly at age 0 (fitted on station pairs; `night` in 0..1 blends the night table)."""
    d = max(float(distance_km), 0.0)

    def interp(tab):
        xs, ys = zip(*tab)
        return float(__import__("numpy").interp(d, xs, ys))
    g = _blend({k: interp(v) for k, v in REP_TABLE.items()}, night)
    return g * math.exp(-abs(float(dz_m)) / _blend(REP_DZ, night))


def cross_age_factor(age_hours, night=0.0):
    """How much of a cross-station gain is left when the report is `age_hours` old (table from the station pairs, exponential tail beyond 6 h)."""
    import numpy as np
    a = max(float(age_hours), 0.0)

    def one(regime):
        xs, ys = zip(*AGE_TABLE[regime])
        return float(np.interp(a, xs, ys)) if a <= 6.0 else ys[-1] * math.exp(-(a - 6.0) / TAU_X[regime])
    return (1.0 - night) * one("day") + night * one("night")


def effective_gain(age_hours=0.0, distance_km=0.0, dz_m=0.0, night=0.0):
    """Total gain of an observation: a report from the same place (under 5 km) decays with age like the benchmark's persistence; any other station is weighted by distance, height and (slowly) age."""
    if float(distance_km) < OWN_STATION_KM:
        return max(persistence_gain(age_hours), 0.02)
    return max(representativeness_gain(distance_km, dz_m, night) * cross_age_factor(age_hours, night), 0.02)


def observation_sigma(prior_sd, gain):
    """Observation error that makes the Gaussian update move the median by the fraction `gain` of the anomaly: sd = prior_sd * sqrt(1 / gain - 1); a gain of 1 gives a tiny error (exact pin)."""
    g = min(max(float(gain), 0.02), 1.0)
    return max(float(prior_sd) * math.sqrt(1.0 / g - 1.0), 1e-3 * max(float(prior_sd), 1e-6))
