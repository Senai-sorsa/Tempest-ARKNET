"""C3 (L12): HRRR 10 m wind at the pad as a near-analysis anchor for the ground wind.

HRRR comes from Open-Meteo (keyless, through `_net`): the historical-forecast archive for past times (model ncep_hrrr_conus; the stitched first hours of each run, i.e. a near-analysis) and the forecast API for times
up to about two days ahead. Test L1 (scripts/hrrr_vs_asos.py, 240 station cases 2024-25, TCS and MAF): HRRR 10 m wind CRPS 1.04 against 1.17 for the tool's past mode and 1.98 for its climate mode; the fitted combination
(shift the past-mode median to HRRR's value, spread x0.8) scored 0.76. CAVEAT (docs/AI_MISTAKES_CHECKLIST.md B16): the truth stations (ASOS TCS, MAF) are airport stations that HRRR very likely assimilates, so these scores are optimistic for a pad with no station nearby; an independent-station check is queued (plan L12b). Only the NEAR-ANALYSIS value was tested: at a forecast lead of many hours the skill is not measured (flagged by `Launch.observe_hrrr`).
"""
from datetime import datetime, timedelta, timezone

import numpy as np

from tempest_weather_v2 import _net

__all__ = ["fetch_wind", "HRRR_WEIGHT", "SPREAD_SCALE", "TAPER_TOP_M"]

HRRR_WEIGHT = 1.0          # fitted on 2021-23: 0.98 (u) / 1.00 (v)
SPREAD_SCALE = 0.8         # remaining past-mode spread scale, fitted 0.8
TAPER_TOP_M = 300.0        # the shift and the spread change fade to nothing at this height (only 10 m was tested)
ARCHIVE = "https://historical-forecast-api.open-meteo.com/v1/forecast"
LIVE = "https://api.open-meteo.com/v1/forecast"


def fetch_wind(lat, lon, when_utc, now=None, fetch=None):
    """-> (u, v, note): HRRR 10 m wind components (m/s, east/north) for the UTC hour containing `when_utc`. `fetch(url) -> parsed JSON` is injectable (tests)."""
    now = now or datetime.now(timezone.utc)
    hour = when_utc.replace(minute=0, second=0, microsecond=0)
    if hour > now + timedelta(days=2):
        raise LookupError("HRRR reaches about two days ahead; give a nearer launch time or use the climate / forecast modes")
    day = hour.strftime("%Y-%m-%d")
    base = ARCHIVE if hour < now - timedelta(days=2) else LIVE
    url = (f"{base}?latitude={lat:.4f}&longitude={lon:.4f}&start_date={day}&end_date={day}&hourly=wind_speed_10m,wind_direction_10m&models=ncep_hrrr_conus&wind_speed_unit=ms&timezone=UTC")
    d = (fetch or (lambda u: _net.fetch_json(u, service="open-meteo", retries=2, timeout=60)))(url)
    h = d["hourly"]
    key = hour.strftime("%Y-%m-%dT%H:00")
    if key not in h["time"]:
        raise LookupError(f"HRRR has no value for {key} UTC at this point")
    i = h["time"].index(key)
    sp, dr = h["wind_speed_10m"][i], h["wind_direction_10m"][i]
    if sp is None or dr is None:
        raise LookupError(f"HRRR value for {key} UTC is missing")
    u, v = -sp * np.sin(np.radians(dr)), -sp * np.cos(np.radians(dr))
    lead = "near-analysis (archive)" if base == ARCHIVE else "live HRRR run (forecast skill at long lead not measured)"
    return float(u), float(v), f"HRRR {key}Z, {lead}"
