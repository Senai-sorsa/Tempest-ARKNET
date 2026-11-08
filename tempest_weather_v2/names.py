"""Plain variable names, units and quantity parsing (spec I-3). numpy-free stdlib.

* `VARIABLES`: public name -> (description, SI unit, US unit, SI->US factor/offset). `units="us"` (default: degF, inHg, mph, ft) or `"si"` (degC, hPa, m/s, m).
* `parse_quantity("4600 ft", "length")` -> SI value; bare numbers use the unit system's default unit. Strings carry their own unit: "1.4 km", "14 mph", "82 F", "1013 hPa".
* `resolve_name(name)` accepts the legacy coded names (t2m_c, wind_speed@100) as aliases and raises ValueError with a difflib suggestion for typos.
"""
import difflib
import re

__all__ = ["VARIABLES", "ALIASES", "resolve_name", "parse_quantity", "to_units", "from_units", "unit_label", "format_value"]

# name: (description, kind, SI unit, US unit)
VARIABLES = {
    "elevation": ("launch site elevation", "length", "m", "ft"),
    "temperature": ("2 m air temperature", "temperature", "C", "F"),
    "pressure": ("sea-level altimeter setting (what METARs report)", "pressure", "hPa", "inHg"),
    "station_pressure": ("pressure at the pad", "pressure", "hPa", "inHg"),
    "mslp": ("mean sea-level pressure (reduced with the actual temperature)", "pressure", "hPa", "inHg"),
    "wind_speed": ("drift-equivalent uniform wind", "speed", "m/s", "mph"),
    "wind_from_deg": ("direction the uniform wind blows FROM", "angle", "deg", "deg"),
    "wind_10m": ("wind at 10 m (pad anemometer)", "speed", "m/s", "mph"),
    "wind_10m_from_deg": ("direction the 10 m wind blows FROM", "angle", "deg", "deg"),
    "gust": ("10 m wind gust", "speed", "m/s", "mph"),
    "humidity": ("relative humidity at 2 m", "percent", "%", "%"),
    "dew_point": ("dew point", "temperature", "C", "F"),
    "density": ("air density at the pad", "density", "kg/m3", "slug/ft3"),
    "density_ratio": ("air density over standard sea-level density", "ratio", "-", "-"),
    "density_altitude": ("altitude of the same density in the standard atmosphere", "length", "m", "ft"),
    "surface_roughness_m": ("surface roughness length z0", "length_m", "m", "m"),
    "max_wind_shear": ("largest vertical wind shear in the column", "shear", "1/s", "mph/1000ft"),
    "max_wind_shear_alt": ("height AGL of the largest shear", "length", "m", "ft"),
    "upper_wind_max": ("peak wind speed above 5 km (jet stream)", "speed", "m/s", "mph"),
    "upper_wind_max_alt": ("height AGL of the peak upper wind", "length", "m", "ft"),
    "wind_3km": ("0-3 km vector-mean wind", "speed", "m/s", "mph"),
    "wind_3km_from_deg": ("direction the 0-3 km mean wind blows FROM", "angle", "deg", "deg"),
}
ALIASES = {"t2m_c": "temperature", "t2m": "temperature", "sp": "station_pressure", "rh2m": "humidity", "ws": "wind_speed", "wind": "wind_speed", "wind_speed@10": "wind_10m",
           "wind_speed@100": "wind_10m", "gust_mps": "gust", "td": "dew_point", "rho": "density", "elev": "elevation", "altimeter": "pressure", "baro": "pressure"}

# conversion to SI from each unit: value_si = value * scale + offset
_TO_SI = {
    "length": {"m": (1.0, 0.0), "km": (1000.0, 0.0), "ft": (0.3048, 0.0), "mi": (1609.344, 0.0), "in": (0.0254, 0.0)},
    "speed": {"m/s": (1.0, 0.0), "mps": (1.0, 0.0), "mph": (0.44704, 0.0), "kt": (0.514444, 0.0), "kts": (0.514444, 0.0), "km/h": (1 / 3.6, 0.0), "kph": (1 / 3.6, 0.0), "ft/s": (0.3048, 0.0), "fps": (0.3048, 0.0)},
    "temperature": {"c": (1.0, 0.0), "degc": (1.0, 0.0), "k": (1.0, -273.15), "f": (5.0 / 9.0, -32.0 * 5.0 / 9.0), "degf": (5.0 / 9.0, -32.0 * 5.0 / 9.0)},   # to degC
    "pressure": {"hpa": (1.0, 0.0), "mb": (1.0, 0.0), "mbar": (1.0, 0.0), "pa": (0.01, 0.0), "kpa": (10.0, 0.0), "inhg": (33.8639, 0.0), "psi": (68.9476, 0.0)},              # to hPa
    "angle": {"deg": (1.0, 0.0), "": (1.0, 0.0)},
}
_UNIT_RE = re.compile(r"^\s*([-+]?\d*\.?\d+(?:e[-+]?\d+)?)\s*(?:°|deg)?\s*([a-zA-Z/%]*)\s*$")


def resolve_name(name):
    """Plain public name for `name` (aliases accepted); ValueError with a suggestion for anything else."""
    if name in VARIABLES:
        return name
    if name in ALIASES:
        return ALIASES[name]
    close = difflib.get_close_matches(name, list(VARIABLES) + list(ALIASES), n=1, cutoff=0.6)
    hint = f" — did you mean {ALIASES.get(close[0], close[0])}?" if close else ""
    raise ValueError(f"unknown variable {name!r}{hint} (run `tempest variables` for the list)")


def parse_quantity(x, kind, units="us"):
    """Number or string with a unit -> value in the base unit of `kind` (length m, speed m/s, temperature degC, pressure hPa, angle deg). A bare number uses the unit system's own unit."""
    if isinstance(x, (int, float)):
        default = {"length": ("ft", "m"), "speed": ("mph", "m/s"), "temperature": ("f", "c"), "pressure": ("inhg", "hpa"), "angle": ("deg", "deg")}[kind][0 if units == "us" else 1]
        val, unit = float(x), default
    else:
        m = _UNIT_RE.match(str(x))
        if not m:
            raise ValueError(f"cannot read the quantity {x!r}: write a number with a unit, e.g. '4600 ft', '14 mph', '82 F', '1013 hPa'")
        val, unit = float(m.group(1)), m.group(2).lower()
        if unit == "":
            return parse_quantity(val, kind, units)
    table = _TO_SI[kind]
    if unit not in table:
        raise ValueError(f"unit {unit!r} is not a {kind} unit (known: {', '.join(sorted(k for k in table if k))})")
    scale, offset = table[unit]
    return val * scale + offset


def to_units(name, value_si, units="us"):
    """Value in the internal SI unit (temperature in degC here, pressure hPa, speeds m/s, lengths m, density kg/m3, shear 1/s) -> the display unit system."""
    if units == "si":
        return value_si
    kind = VARIABLES[name][1]
    if kind == "length":
        return value_si / 0.3048
    if kind == "speed":
        return value_si / 0.44704
    if kind == "temperature":
        return value_si * 1.8 + 32.0
    if kind == "pressure":
        return value_si / 33.8639
    if kind == "density":
        return value_si / 515.378819
    if kind == "shear":
        return value_si * 304.8 / 0.44704                     # 1/s over 1000 ft = m/s per 304.8 m, in mph
    return value_si


def from_units(name, value, units="us"):
    """Inverse of `to_units`."""
    if units == "si":
        return value
    kind = VARIABLES[name][1]
    return {"length": lambda v: v * 0.3048, "speed": lambda v: v * 0.44704, "temperature": lambda v: (v - 32.0) / 1.8, "pressure": lambda v: v * 33.8639,
            "density": lambda v: v * 515.378819, "shear": lambda v: v * 0.44704 / (0.3048 * 1000.0)}.get(kind, lambda v: v)(value)


def unit_label(name, units="us"):
    u = VARIABLES[name][3 if units == "us" else 2]
    return {"C": "°C", "F": "°F"}.get(u, u)


def format_value(name, value_si, units="us"):
    v = to_units(name, value_si, units)
    digits = {"pressure": 2 if units == "us" else 1, "density": 5 if units == "us" else 3, "ratio": 3, "shear": 4 if units == "si" else 2}.get(VARIABLES[name][1], 1)
    if name.endswith("_deg"):
        digits = 0
    return f"{v:.{digits}f}"
