"""Site registry (spec 0.1, I-5): named launch sites with coordinates, pad elevation, time zone and magnetic declination.

    site = get_site("spaceport_america")                  # Site(name, lat, lon, elevation_m, tz, declination_deg, source)
    add_site("my_pad", 32.5, -105.5, elevation=None)       # looks the elevation up (see elevation.py) and stores it in the user file
    guess_tz(lat, lon)                                     # rough US zone for a bare point, flagged; pass tz= to be exact
Built-in sites live in data/sites.toml; user sites in <cache>/sites.toml (TEMPEST_CACHE overrides the folder).
"""
import difflib
import os
import re
from dataclasses import dataclass

from tempest_weather_v2 import _files, names, weather_calc

__all__ = ["Site", "load_sites", "get_site", "add_site", "guess_tz", "BUILTIN"]

BUILTIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sites.toml")


@dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    elevation_m: float = None
    tz: str = None
    declination_deg: float = None
    source: str = "built-in"
    aliases: tuple = ()

    def declination(self, year=2026.9):
        return self.declination_deg if self.declination_deg is not None else weather_calc.declination_deg(self.lat, self.lon, year)


def _parse_toml(text):
    try:
        import tomllib
        return tomllib.loads(text)
    except ModuleNotFoundError:                          # Python 3.10: a minimal reader for the flat [[site]] files written here
        sites, cur = [], None
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line == "[[site]]":
                cur = {}
                sites.append(cur)
            elif "=" in line and cur is not None:
                k, v = (x.strip() for x in line.split("=", 1))
                if v.startswith("["):
                    cur[k] = [x.strip().strip('"') for x in v.strip("[]").split(",") if x.strip()]
                elif v.startswith('"'):
                    cur[k] = v.strip('"')
                elif v.lower() in ("true", "false"):
                    cur[k] = v.lower() == "true"
                else:
                    cur[k] = float(v)
        return {"site": sites}


def _norm(name):
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


def _user_path():
    return os.path.join(_files.cache_dir(), "sites.toml")


def load_sites(user=True):
    """-> {normalised name: Site}; user sites override built-in ones of the same name."""
    out = {}
    for path, source in ((BUILTIN, "built-in"), (_user_path() if user else None, "user")):
        if not path or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for d in _parse_toml(f.read()).get("site", []):
                s = Site(_norm(d["name"]), float(d["lat"]), float(d["lon"]), d.get("elevation_m"), d.get("tz"), d.get("declination_deg"), source, tuple(d.get("aliases", ())))
                out[s.name] = s
    return out


def get_site(name):
    sites = load_sites()
    key = _norm(name)
    if key in sites:
        return sites[key]
    for s in sites.values():
        if key in {_norm(a) for a in s.aliases}:
            return s
    close = difflib.get_close_matches(key, list(sites), n=1, cutoff=0.5)
    raise KeyError(f"unknown site {name!r}" + (f" — did you mean {close[0]}?" if close else "") + f" (known sites: {', '.join(sorted(sites))}; or give lat, lon)")


def guess_tz(lat, lon):
    """Rough IANA zone for a point: the contiguous US by longitude bands (flagged as a guess by the caller), elsewhere a fixed-offset Etc zone with no daylight saving."""
    if 24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0:
        if lon < -114.0:
            return "America/Los_Angeles"
        if lon < -103.06:                                # mountain time reaches the New Mexico / Texas border
            return "America/Denver"
        if lon < -85.0:
            return "America/Chicago"
        return "America/New_York"
    off = -int(round(lon / 15.0))                       # Etc/GMT+5 means UTC-5
    return "UTC" if off == 0 else f"Etc/GMT{'+' if off > 0 else '-'}{abs(off)}"


def add_site(name, lat, lon, elevation=None, tz=None, declination_deg=None, lookup=None):
    """Store a site in the user file. `elevation` (m, or a string like '4600 ft'); None looks it up through `lookup(lat, lon)` (default: elevation.lookup). Returns the Site."""
    if elevation is None:
        if lookup is None:
            from tempest_weather_v2 import elevation as E
            lookup = lambda a, b: E.lookup(a, b).m
        elevation_m = float(lookup(lat, lon))
    else:
        elevation_m = names.parse_quantity(elevation, "length", "si") if isinstance(elevation, str) else float(elevation)
    tz = tz or guess_tz(lat, lon)
    s = Site(_norm(name), float(lat), float(lon), elevation_m, tz, declination_deg, "user")
    path = _user_path()
    with _files.file_lock(path):
        existing = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = f.read()
        block = (f'\n[[site]]\nname = "{s.name}"\nlat = {s.lat}\nlon = {s.lon}\nelevation_m = {s.elevation_m:.1f}\ntz = "{s.tz}"\n'
                 + (f"declination_deg = {declination_deg}\n" if declination_deg is not None else ""))
        _files.atomic_write(path, existing + block)
    return s
