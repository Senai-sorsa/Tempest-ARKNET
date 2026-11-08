"""Result objects (spec I-2, 1.5): `Weather` prints as an aligned table with units and a trust line, gives attribute access in the chosen units and exports to RASAero / OpenRocket.

Internally every value is SI (temperature in degC, pressure in hPa, wind in m/s, lengths in m, density in kg/m3, shear in 1/s). Attributes return the DISPLAY units (`units="us"`: degF, inHg, mph, ft;
`"si"`: degC, hPa, m/s, m). `r.si("temperature")` always gives the internal value.
"""
from tempest_weather_v2 import names
from tempest_weather_v2.names import VARIABLES
from tempest_weather_v2.weather_calc import cardinal

__all__ = ["Weather", "DEFAULT_FIELDS", "ALL_FIELDS"]

DEFAULT_FIELDS = ("elevation", "temperature", "pressure", "wind_speed", "density_altitude")
ALL_FIELDS = ("elevation", "temperature", "pressure", "station_pressure", "mslp", "wind_speed", "wind_from_deg", "wind_10m", "wind_10m_from_deg", "wind_3km", "wind_3km_from_deg", "gust",
              "humidity", "dew_point", "density", "density_ratio", "density_altitude", "surface_roughness_m", "max_wind_shear", "max_wind_shear_alt", "upper_wind_max", "upper_wind_max_alt")


class Weather:
    def __init__(self, values, *, units="us", all_fields=False, label="", flags=(), provenance=None, trust="", declination=None, notes=()):
        self._v = dict(values)
        self.units, self.all_fields, self.label = units, bool(all_fields), label
        self.flags, self.provenance, self.trust, self.notes = list(flags), dict(provenance or {}), trust, list(notes)
        self.declination = declination

    # ---- access
    def si(self, name):
        return self._v[names.resolve_name(name)]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            key = names.resolve_name(name)
        except ValueError as e:
            raise AttributeError(str(e)) from None
        if key not in self._v:
            raise AttributeError(f"{key} is not in this result (ask for all=True)")
        return names.to_units(key, self._v[key], self.units)

    def fields(self):
        return [f for f in (ALL_FIELDS if self.all_fields else DEFAULT_FIELDS) if f in self._v]

    def to_dict(self, units=None, all_fields=True):
        u = units or self.units
        keys = [f for f in ALL_FIELDS if f in self._v] if all_fields else self.fields()
        return {k: names.to_units(k, self._v[k], u) for k in keys}

    def to_df(self):
        import pandas as pd   # optional dependency
        d = self.to_dict()
        return pd.DataFrame({"value": list(d.values()), "unit": [names.unit_label(k, self.units) for k in d]}, index=list(d))

    # ---- text
    def _row(self, k):
        text = names.format_value(k, self._v[k], self.units)
        if k.endswith("_from_deg"):
            deg = self._v[k]
            text = f"{deg:.0f}° (from {cardinal(deg)})"
            if self.all_fields and self.declination is not None:
                mag = (deg - self.declination) % 360.0
                text = f"{deg:.0f}° True ({mag:.1f}° Mag, from {cardinal(deg)})"
            return text, ""
        return text, names.unit_label(k, self.units)

    def __str__(self):
        rows = [(k, VARIABLES[k][0], *self._row(k)) for k in self.fields()]
        w0, w1, w2 = max(len(r[0]) for r in rows), max(len(r[1]) for r in rows), max(len(r[2]) for r in rows)
        head = f"{self.label}\n" if self.label else ""
        lines = [f"{k:<{w0}}  {d:<{w1}}  {v:>{w2}} {u}".rstrip() for k, d, v, u in rows]
        out = head + "\n".join(lines)
        for n in self.notes:
            out += f"\n  note: {n}"
        out += f"\n{self.trust}" if self.trust else ""
        if self.flags:
            out += f"\nflags: {', '.join(self.flags)}"
        return out

    __repr__ = __str__

    # ---- exports
    def to_ras(self):
        """RASAero II launch-site inputs in the order of its window: elevation (ft), temperature (degF), barometric pressure at SEA LEVEL (inHg altimeter setting), wind speed (mph, uniform).
        Always US units, whatever `units` is."""
        g = lambda k: names.to_units(k, self._v[k], "us")
        lines = ["RASAero II launch site", f"  Launch site elevation (ft):        {g('elevation'):.0f}", f"  Temperature (F):                   {g('temperature'):.1f}",
                 f"  Barometric pressure (inHg):        {g('pressure'):.2f}   (sea-level altimeter setting)", f"  Wind speed (mph):                  {g('wind_speed'):.1f}   (uniform, drift-equivalent)"]
        if "density_altitude" in self._v and self._v["density_altitude"] > 6000 * 0.3048:
            lines.append(f"  note: density altitude {g('density_altitude'):.0f} ft: reduced fin authority off the rail")
        return "\n".join(lines)

    def to_openrocket(self, wind_std_ms=None):
        """OpenRocket Launch Conditions tab: pad elevation, average wind speed and its standard deviation (turbulence), wind direction FROM, temperature and STATION pressure in mbar."""
        g = lambda k: names.to_units(k, self._v[k], "si")
        sd = wind_std_ms if wind_std_ms is not None else self._v.get("wind_10m_std")
        lines = ["OpenRocket launch conditions", f"  Launch altitude (m):               {g('elevation'):.1f}", f"  Average wind speed (m/s):          {g('wind_10m') if 'wind_10m' in self._v else g('wind_speed'):.1f}"]
        if sd is not None and (self._v.get('wind_10m') or self._v.get('wind_speed')):
            spd = self._v.get('wind_10m', self._v.get('wind_speed'))
            lines.append(f"  Wind standard deviation (m/s):     {sd:.2f}   (turbulence intensity {100 * sd / max(spd, 1e-6):.0f} %)")
        lines += [f"  Wind direction (deg, from):        {self._v.get('wind_10m_from_deg', self._v['wind_from_deg']):.0f}", f"  Temperature (C):                   {g('temperature'):.1f}",
                  f"  Station pressure (mbar):           {g('station_pressure'):.1f}"]
        return "\n".join(lines)
