"""Launch-day observation ingestion (spec R2, IL-156): find the nearest weather stations, fetch their latest METAR, and turn the report into a properly weighted observation.

    near = nearest(32.94, -106.91)                              # [(id, distance_km, elevation_m), ...]
    t, m = latest_report("TCS", launch_time_utc)                # newest METAR at or before the launch time (IEM, keyless; through _net)
    Launch(...).observe_latest()                                # does all of it and conditions the atmosphere

Why weights: an observation is not the pad state. Its usefulness decays with its AGE (the ground-wind benchmark GW-1 on ASOS 2024-25: the regression of the wind anomaly at the launch hour on the anomaly
one hour earlier is 0.80 (u) / 0.88 (v), three hours earlier 0.63 / 0.66, a decay time of about 6 h), and with DISTANCE and ELEVATION difference between the station and the pad (no data yet: the defaults
below are ASSUMPTIONS, flagged in the trust line, to be fitted when pad-side wind logs exist). The weight is turned into an observation error for the Gaussian update: with prior spread s and gain r,
the observation sd is s * sqrt(1 / r - 1), so r = 1 pins the value (the old behaviour) and r = 0.5 moves the median half way.
"""
import csv
import io
import math
from datetime import datetime, timedelta, timezone

from tempest_weather_v2 import _net, metar as _metar

__all__ = ["STATIONS", "nearest", "latest_report", "persistence_gain", "representativeness_gain", "effective_gain", "observation_sigma", "TAU_H", "REP_KM", "REP_DZ_M"]

TAU_H, REP_KM, REP_DZ_M = 6.3, 150.0, 400.0        # age decay (fitted, GW-1), distance and elevation scales (assumed)
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


def persistence_gain(age_hours, tau=TAU_H):
    """Regression gain of the anomaly `age_hours` later on an observed anomaly: exp(-age / tau) (0.84 at 1 h, 0.62 at 3 h: close to the benchmark's 0.80-0.88 and 0.63-0.66)."""
    return math.exp(-max(float(age_hours), 0.0) / tau)


def representativeness_gain(distance_km, dz_m, rep_km=REP_KM, rep_dz=REP_DZ_M):
    """How much of the pad anomaly a station at `distance_km` and `dz_m` higher or lower sees (ASSUMED scales; 1 at the pad)."""
    return math.exp(-max(float(distance_km), 0.0) / rep_km) * math.exp(-abs(float(dz_m)) / rep_dz)


def effective_gain(age_hours=0.0, distance_km=0.0, dz_m=0.0):
    return max(persistence_gain(age_hours) * representativeness_gain(distance_km, dz_m), 0.02)


def observation_sigma(prior_sd, gain):
    """Observation error that makes the Gaussian update move the median by the fraction `gain` of the anomaly: sd = prior_sd * sqrt(1 / gain - 1); a gain of 1 gives a tiny error (exact pin)."""
    g = min(max(float(gain), 0.02), 1.0)
    return max(float(prior_sd) * math.sqrt(1.0 / g - 1.0), 1e-3 * max(float(prior_sd), 1e-6))
