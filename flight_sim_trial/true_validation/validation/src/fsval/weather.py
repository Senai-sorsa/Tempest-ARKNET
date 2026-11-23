"""Launch-day air for a place and UTC hour: site.toml, Monte Carlo statistics and an upper-air profile.

    python -m fsval.weather "jean" 2007-07-14 18 [--out DIR]

Built on dynamics/tools/weather/Weather_to_JARVIS_inputs.py, which reads Open-Meteo at the surface only, so one
temperature and one wind stand in for the whole flight. Added here: the ERA5 reanalysis on 37 pressure levels from
Google's public ARCO store (no key, hourly, 0.25 deg, up to 1 hPa, about 48 km), joined to the Open-Meteo surface
values, and IGRA radiosondes as the measured check on it. Non-interactive, and every time is UTC.

ERA5 smooths the weather, so the spreads run a little low, most for wind.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import statistics
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numcodecs
import numpy as np

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_LAG_DAYS = 7  # the archive trails real time by about 5 days
FORECAST_DAYS = 15  # the forecast reaches 16 days ahead
CLIMATE_YEARS = 10  # past years behind the statistics
WINDOW_DAYS = 7  # days either side of the date, each year
HOUR_SPAN = 1  # hours either side of the launch hour
HOURLY = (
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_100m",  # UniformWind has one wind for every altitude: the 100 m one is closest to the flight
    "wind_direction_100m",
)
SEA_LEVEL_PA = 101325.0
CACHE_DIR = Path.home() / ".cache" / "weather_to_jarvis"  # finished past years never change, so they are kept
ERA5_URL = "https://storage.googleapis.com/gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
ERA5_START = datetime(1900, 1, 1)  # the store's hour zero
ERA5_FIELDS = ("geopotential", "temperature", "specific_humidity", "u_component_of_wind", "v_component_of_wind")
IGRA_URL = "https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por"
G0 = 9.80665
EARTH_RADIUS_M = 6371229.0  # the sphere ERA5's geopotential height is defined on

# latitude [deg], longitude [deg], elevation [m]; anything else is typed in as "lat, lon" or "lat, lon, elevation_m"
SITES = {
    "spaceport america": (32.99, -106.97, 4595 * 0.3048),
    "black rock": (40.85, -119.12, 3750 * 0.3048),  # the playa; files give 3750 to 3933 ft
    "jean": (35.77, -115.33, 2750 * 0.3048),  # Jean dry lake, as LDRS-26's files give it
}

# (name, TOML unit) of each sampled input, in the order of a sample tuple
VARIABLES = (
    ("launch_temperature", "degC"),
    ("barometric_pressure", "Pa"),
    ("relative_humidity", "0 to 1"),
    ("wind_east", "m/s"),
    ("wind_north", "m/s"),
)

Sample = tuple[float, float, float, float, float]


def standard_pressure(altitude_m: float) -> float:
    """Pressure of the 1976 standard atmosphere in Pa below 11 km."""
    return SEA_LEVEL_PA * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588


def fetch(
    url: str, lat: float, lon: float, elevation_m: float | None, start: date, end: date, cache: bool = False
) -> tuple[float, list[tuple[datetime, Sample]]]:
    """Hourly weather at a place from Open-Meteo, in UTC.

    Returns:
        tuple: The elevation the weather applies to in m, and (UTC time, sample) per hour with no gaps.
            With ``cache`` the response is kept on disk and reused: only for finished past years.
            Pressure is the site pressure reduced to sea level along the standard atmosphere, as the sim
            wants it; wind is east and north components of the wind's velocity.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(HOURLY),
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    if elevation_m is not None:
        params["elevation"] = f"{elevation_m:.1f}"
    query = f"{url}?{urlencode(params)}"
    cached = CACHE_DIR / f"{hashlib.sha1(query.encode()).hexdigest()}.json"
    if cache and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
    else:
        try:
            with urlopen(query, timeout=60) as response:
                data = json.load(response)
        except HTTPError as error:
            raise SystemExit(f"Open-Meteo refused {start} to {end}: {error.read().decode(errors='replace')}") from error
        except (URLError, TimeoutError) as error:
            raise SystemExit(f"Could not reach Open-Meteo ({error}). Check the internet connection.") from error
        if cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")

    grid_elevation_m = float(data["elevation"])
    hourly = data["hourly"]
    rows = []
    for index, stamp in enumerate(hourly["time"]):
        values = [hourly[name][index] for name in HOURLY]
        if any(value is None for value in values):
            continue
        temperature_c, humidity_percent, surface_hpa, speed, from_deg = values
        rows.append(
            (
                datetime.fromisoformat(stamp),
                (
                    temperature_c,
                    surface_hpa * 100.0 * SEA_LEVEL_PA / standard_pressure(grid_elevation_m),
                    humidity_percent / 100.0,
                    -speed * math.sin(math.radians(from_deg)),  # the wind blows away from where it comes from
                    -speed * math.cos(math.radians(from_deg)),
                ),
            )
        )
    return grid_elevation_m, rows


def climate_samples(
    lat: float, lon: float, elevation_m: float | None, day: date, hour: int
) -> tuple[float, list[Sample]]:
    """Samples of the same place and hour around the date, in each of the last CLIMATE_YEARS years."""
    samples: list[Sample] = []
    grid_elevation_m = elevation_m
    for year in range(date.today().year - CLIMATE_YEARS, date.today().year):
        try:
            centre = day.replace(year=year)
        except ValueError:  # 29 February
            centre = day.replace(year=year, day=28)
        print(f"Reading {year}...", flush=True)
        grid_elevation_m, rows = fetch(
            ARCHIVE_URL, lat, lon, elevation_m, centre - timedelta(WINDOW_DAYS), centre + timedelta(WINDOW_DAYS), cache=True
        )
        samples += [sample for stamp, sample in rows if abs(stamp.hour - hour) <= HOUR_SPAN]
    if len(samples) < 2:
        raise SystemExit("Open-Meteo returned too little history to take statistics from.")
    return grid_elevation_m, samples


def day_sample(
    lat: float, lon: float, elevation_m: float | None, day: date, hour: int, samples: list[Sample]
) -> tuple[Sample, str]:
    """The inputs for one day and hour, and where they came from."""
    today = date.today()
    if day <= today + timedelta(FORECAST_DAYS):
        url, source = (ARCHIVE_URL, "archive") if day <= today - timedelta(ARCHIVE_LAG_DAYS) else (FORECAST_URL, "forecast")
        _, rows = fetch(url, lat, lon, elevation_m, day, day)
        for stamp, sample in rows:
            if stamp.hour == hour:
                return sample, source
        raise SystemExit(f"Open-Meteo has no data for {day} at {hour}:00.")
    return tuple(statistics.fmean(column) for column in zip(*samples)), f"average of the last {CLIMATE_YEARS} years"  # type: ignore[return-value]


def correlation(first: list[float], second: list[float]) -> float:
    """Pearson correlation, 0 when either input never changes."""
    try:
        return statistics.correlation(first, second)
    except statistics.StatisticsError:
        return 0.0


def site_toml(lat: float, elevation_m: float, sample: Sample, source: str, day: date, hour: int) -> str:
    """The sim's site.toml text for one sample."""
    temperature_c, pressure_pa, humidity, east, north = sample
    speed = math.hypot(east, north)
    from_deg = math.degrees(math.atan2(-east, -north)) % 360.0
    return f'''# Launch site weather for {day} at {hour}:00 UTC; {source}, from Open-Meteo.

launch_latitude = "{lat:g} deg"
launch_elevation = "{elevation_m:.1f} m"

[atmosphere]
type = "flight_sim.environment.atmosphere.StandardAtmosphere1976"
launch_temperature = "{temperature_c:.1f} degC"
barometric_pressure = "{pressure_pa:.0f} Pa"
relative_humidity = {min(max(humidity, 0.0), 1.0):.3f}

[gravity]
type = "flight_sim.environment.gravity.WGS84Gravity"

[wind]
type = "flight_sim.environment.wind.UniformWind"
speed = "{speed:.1f} m/s"
from_azimuth = "{from_deg:.0f} deg"
'''


def monte_carlo_toml(samples: list[Sample], day: date, hour: int) -> str:
    """Mean, standard deviation and correlation of the samples as TOML."""
    columns = [list(column) for column in zip(*samples)]
    lines = [
        f"# Statistics of the site inputs around {day:%m-%d} at {hour}:00 UTC, last {CLIMATE_YEARS} years,",
        f"# +-{WINDOW_DAYS} days and +-{HOUR_SPAN} h. Wind is the 100 m wind as east and north components.",
        "# The correlation keeps the link between variables, such as pressure and temperature.",
        "",
        f"samples = {len(samples)}",
    ]
    for (name, unit), column in zip(VARIABLES, columns):
        lines += ["", f"[{name}]  # {unit}", f"mean = {statistics.fmean(column):.6g}", f"std = {statistics.stdev(column):.6g}"]
    lines += ["", "[correlation]"]
    for first in range(len(VARIABLES)):
        for second in range(first + 1, len(VARIABLES)):
            pair = f"{VARIABLES[first][0]}__{VARIABLES[second][0]}"
            lines.append(f"{pair} = {correlation(columns[first], columns[second]):.3f}")
    return "\n".join(lines) + "\n"


def geometric_m(geopotential_height_m):
    """Geometric height of a geopotential height."""
    return EARTH_RADIUS_M * geopotential_height_m / (EARTH_RADIUS_M - geopotential_height_m)


def isa_altitude_m(pressure_pa):
    """Height a standard-atmosphere altimeter gives for a pressure; shortcut: isothermal above 11 km, so it is good to 20 km, the baro flights stop below that."""
    pressure = np.asarray(pressure_pa, float)
    tropopause_pa = standard_pressure(11000.0)
    low = (1.0 - (pressure / SEA_LEVEL_PA) ** (1.0 / 5.25588)) / 2.25577e-5
    return np.where(pressure > tropopause_pa, low, 11000.0 + 6341.6 * np.log(tropopause_pa / pressure))


def _read(url: str) -> bytes:
    with urlopen(url, timeout=300) as response:
        return response.read()


def _era5_axis(name: str) -> np.ndarray:
    meta = json.loads(_read(f"{ERA5_URL}/{name}/.zarray"))
    return np.frombuffer(numcodecs.Blosc().decode(_read(f"{ERA5_URL}/{name}/0")), meta["dtype"])


def era5_levels(lat: float, lon: float, when: datetime) -> dict:
    """ERA5 on its pressure levels at a point, bilinear between the four grid points, cached on disk.

    One store chunk holds one hour of the whole globe, about 85 MB per field, so a point costs five of them.
    """
    cached = CACHE_DIR / f"era5_{lat:g}_{lon:g}_{when:%Y%m%d%H}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    index = int((when - ERA5_START).total_seconds() // 3600)
    latitudes, longitudes = _era5_axis("latitude"), _era5_axis("longitude")
    row = float(np.interp(-lat, -latitudes, np.arange(latitudes.size)))  # the store runs from the north pole down
    col = float(np.interp(lon % 360.0, longitudes, np.arange(longitudes.size)))
    r0, c0 = int(row), int(col)
    weights = np.array([[1.0 - row + r0], [row - r0]]) @ np.array([[1.0 - col + c0, col - c0]])
    out = {"level_hpa": _era5_axis("level").astype(float).tolist()}
    for name in ERA5_FIELDS:
        raw = numcodecs.Blosc().decode(_read(f"{ERA5_URL}/{name}/{index}.0.0.0"))
        cells = np.frombuffer(raw, "<f4").reshape(len(out["level_hpa"]), latitudes.size, longitudes.size)
        out[name] = (cells[:, r0:r0 + 2, c0:c0 + 2] * weights).sum(axis=(1, 2)).tolist()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(out), encoding="utf-8")
    return out


def surface_point(lat: float, lon: float, elevation_m: float, when: datetime) -> dict:
    """Open-Meteo's values at the site for one past hour: 2 m temperature and humidity, 100 m wind, site pressure."""
    grid_elevation_m, rows = fetch(ARCHIVE_URL, lat, lon, elevation_m, when.date(), when.date(), cache=True)
    temperature_c, pressure_msl, humidity, east, north = next(sample for stamp, sample in rows if stamp == when)
    return {
        "temperature_k": temperature_c + 273.15,
        "pressure_pa": pressure_msl * standard_pressure(grid_elevation_m) / SEA_LEVEL_PA,
        "relative_humidity": humidity,
        "east_m_s": east,
        "north_m_s": north,
    }


def join_profile(levels: dict, surface: dict, site_m: float) -> dict:
    """One rising profile from the site up: the surface point, then the ERA5 levels above it.

    ERA5's levels below its smooth ground are extrapolated, so the surface point replaces them.
    Water vapour goes through the virtual temperature, which sets density and speed of sound.
    """
    z = geometric_m(np.array(levels["geopotential"]) / G0)
    keep = np.argsort(z)
    keep = keep[z[keep] > site_m + 100.0]
    tc = surface["temperature_k"] - 273.15
    vapour_pa = surface["relative_humidity"] * 610.78 * math.exp(17.27 * tc / (tc + 237.3))  # Tetens, as FS's atmosphere
    q = 0.622 * vapour_pa / (surface["pressure_pa"] - 0.378 * vapour_pa)
    column = lambda name: np.array(levels[name])[keep].tolist()
    t = [surface["temperature_k"], *column("temperature")]
    humidity = np.array([q, *column("specific_humidity")])
    return {
        "z_m": [site_m, *z[keep].tolist()],
        "pressure_pa": [surface["pressure_pa"], *(np.array(levels["level_hpa"])[keep] * 100.0).tolist()],
        "temperature_k": t,
        "virtual_temperature_k": (np.array(t) * (1.0 + 0.608 * humidity)).tolist(),
        "east_m_s": [surface["east_m_s"], *column("u_component_of_wind")],
        "north_m_s": [surface["north_m_s"], *column("v_component_of_wind")],
    }


def air_profile(lat: float, lon: float, elevation_m: float, when: datetime) -> dict:
    """The joined profile for a place and hour."""
    return join_profile(era5_levels(lat, lon, when), surface_point(lat, lon, elevation_m, when), elevation_m)


def igra_soundings(station: str, days: set[date]) -> dict[datetime, list[dict]]:
    """Measured radiosonde levels of an IGRA 2 station on some days, by launch hour; the station file is cached."""
    cached = CACHE_DIR / f"{station}-data.txt.zip"
    if not cached.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(_read(f"{IGRA_URL}/{station}-data.txt.zip"))
    found: dict[datetime, list[dict]] = {}
    with zipfile.ZipFile(cached) as archive, io.TextIOWrapper(archive.open(archive.namelist()[0]), "ascii") as lines:
        levels = None
        for line in lines:
            if line.startswith("#"):
                year, month, day, hour = int(line[13:17]), int(line[18:20]), int(line[21:23]), int(line[24:26])
                levels = None
                if date(year, month, day) in days and hour != 99:
                    levels = found.setdefault(datetime(year, month, day, hour), [])
            elif levels is not None:
                level = _igra_level(line)
                if level:
                    levels.append(level)
    return found


def _igra_level(line: str) -> dict | None:
    """One IGRA 2 data line as SI values; None without pressure, height and temperature together."""
    pressure, height, temperature = int(line[9:15]), int(line[16:21]), int(line[22:27])
    if min(pressure, height, temperature) < -8000:
        return None
    return {"pressure_pa": float(pressure), "height_m": float(height), "temperature_k": temperature / 10.0 + 273.15}


def main() -> int:
    """Fetch and write; returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", help=f"one of {', '.join(SITES)}, or 'lat,lon,elevation_m'")
    parser.add_argument("date", type=date.fromisoformat)
    parser.add_argument("hour", type=int, help="UTC")
    parser.add_argument("--out", type=Path, default=Path.home() / "Downloads")
    args = parser.parse_args()
    lat, lon, elevation_m = SITES[args.site] if args.site in SITES else tuple(float(part) for part in args.site.split(","))
    args.out.mkdir(parents=True, exist_ok=True)

    _, samples = climate_samples(lat, lon, elevation_m, args.date, args.hour)
    sample, source = day_sample(lat, lon, elevation_m, args.date, args.hour, samples)
    (args.out / f"site_{args.date}.toml").write_text(site_toml(lat, elevation_m, sample, source, args.date, args.hour), encoding="utf-8")
    (args.out / f"site_{args.date}_monte_carlo.toml").write_text(monte_carlo_toml(samples, args.date, args.hour), encoding="utf-8")
    if source == "archive":
        when = datetime.combine(args.date, datetime.min.time()) + timedelta(hours=args.hour)
        (args.out / f"profile_{args.date}_{args.hour:02d}.json").write_text(json.dumps(air_profile(lat, lon, elevation_m, when)), encoding="utf-8")
    print(f"Wrote site files for {args.date} ({source}) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
