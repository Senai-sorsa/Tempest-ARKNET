"""Single-value atmosphere inputs for the simulator, in the layout of dynamics/tools/weather/Weather_to_JARVIS_inputs.py.

`inputs_from_values(...)` -> dict; `to_text`, `to_toml`, `to_json` format it. The wind is the 100 m wind (the one that file uses for UniformWind), as
speed and the azimuth it blows FROM, plus east / north components. Temperatures, pressures and speeds come with the common alternative units.
"""
import json
import math

import numpy as np


def inputs_from_values(lat, lon, elevation_m, t2m_k, sp_pa, rh_frac, u100, v100, extras=None, meta=None):
    speed = math.hypot(u100, v100)
    from_deg = math.degrees(math.atan2(-u100, -v100)) % 360.0
    d = dict(launch_latitude_deg=lat, launch_longitude_deg=lon, launch_elevation_m=float(elevation_m),
             launch_temperature_degC=float(t2m_k - 273.15), launch_temperature_degF=float((t2m_k - 273.15) * 9 / 5 + 32), launch_temperature_K=float(t2m_k),
             barometric_pressure_Pa=float(sp_pa), barometric_pressure_hPa=float(sp_pa / 100), barometric_pressure_psi=float(sp_pa / 6894.757),
             relative_humidity=float(min(max(rh_frac, 0.0), 1.0)),
             wind_east_mps=float(u100), wind_north_mps=float(v100), wind_speed_mps=float(speed), wind_speed_mph=float(speed * 2.23694), wind_from_azimuth_deg=float(from_deg))
    d["extras"] = {k: float(v) for k, v in (extras or {}).items()}
    d["meta"] = meta or {}
    return d


def to_text(d, label=""):
    rows = [("launch latitude", f"{d['launch_latitude_deg']:g} deg"), ("launch longitude", f"{d['launch_longitude_deg']:g} deg"),
            ("launch elevation", f"{d['launch_elevation_m']:.1f} m"),
            ("temperature", f"{d['launch_temperature_degC']:.1f} degC   ({d['launch_temperature_degF']:.1f} degF, {d['launch_temperature_K']:.1f} K)"),
            ("pressure", f"{d['barometric_pressure_Pa']:.0f} Pa   ({d['barometric_pressure_hPa']:.1f} hPa, {d['barometric_pressure_psi']:.3f} psi)"),
            ("relative humidity", f"{d['relative_humidity']:.3f}   (0 to 1)"),
            ("wind (100 m)", f"{d['wind_speed_mps']:.1f} m/s   ({d['wind_speed_mph']:.1f} mph) from {d['wind_from_azimuth_deg']:.0f} deg   [east {d['wind_east_mps']:+.1f}, north {d['wind_north_mps']:+.1f} m/s]")]
    rows += [(k, f"{v:.4g}") for k, v in d["extras"].items()]
    w = max(len(k) for k, _ in rows)
    head = f"{label}\n" if label else ""
    return head + "\n".join(f"  {k:<{w}}  {v}" for k, v in rows) + "\n"


def to_toml(d, source="", day="", hour=""):
    return f'''# Launch site weather {day} {hour}; {source}, from tempest_weather.

launch_latitude = "{d['launch_latitude_deg']:g} deg"
launch_elevation = "{d['launch_elevation_m']:.1f} m"

[atmosphere]
type = "flight_sim.environment.atmosphere.StandardAtmosphere1976"
launch_temperature = "{d['launch_temperature_degC']:.1f} degC"
barometric_pressure = "{d['barometric_pressure_Pa']:.0f} Pa"
relative_humidity = {d['relative_humidity']:.3f}

[gravity]
type = "flight_sim.environment.gravity.WGS84Gravity"

[wind]
type = "flight_sim.environment.wind.UniformWind"
speed = "{d['wind_speed_mps']:.1f} m/s"
from_azimuth = "{d['wind_from_azimuth_deg']:.0f} deg"
'''


def to_json(d):
    return json.dumps(d, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o))
