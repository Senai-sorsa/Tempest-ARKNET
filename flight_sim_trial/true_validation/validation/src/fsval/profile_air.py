"""Runs in the simulator's venv: FS atmosphere and wind models that read a joined profile from fsval.weather.
FS's files are not edited; a sim.toml names these through its usual `type`. Altitude is geometric above sea level.
Conditions hold at the profile's ends; its top is about 48 km, above every flight here."""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from flight_sim.environment.atmosphere import _AIR_GAS_CONSTANT, _HEAT_CAPACITY_RATIO, AtmosphereConditions, AtmosphereModel
from flight_sim.environment.wind import WindModel
from flight_sim.utilities.dcm import world_direction


@dataclass
class ProfileAtmosphere(AtmosphereModel):
    filepath: Path
    _p: dict = field(init=False, repr=False)

    def __post_init__(self) -> None:
        p = json.loads(Path(self.filepath).read_text())
        self._p = {"z": p["z_m"], "lnp": np.log(p["pressure_pa"]).tolist(), "t": p["temperature_k"], "tv": p["virtual_temperature_k"]}

    def conditions(self, altitude_m: float) -> AtmosphereConditions:
        p = self._p
        pressure = math.exp(float(np.interp(altitude_m, p["z"], p["lnp"])))
        tv = float(np.interp(altitude_m, p["z"], p["tv"]))
        return AtmosphereConditions(float(np.interp(altitude_m, p["z"], p["t"])), pressure, pressure / (_AIR_GAS_CONSTANT * tv),
                                    math.sqrt(_HEAT_CAPACITY_RATIO * _AIR_GAS_CONSTANT * tv))


@dataclass
class ProfileWind(WindModel):
    filepath: Path
    _p: dict = field(init=False, repr=False)

    def __post_init__(self) -> None:
        p = json.loads(Path(self.filepath).read_text())
        self._p = {"z": p["z_m"], "east": p["east_m_s"], "north": p["north_m_s"], "e": world_direction(0.0, math.pi / 2), "n": world_direction(0.0, 0.0)}

    def velocity(self, altitude_m: float) -> np.ndarray:
        p = self._p
        return float(np.interp(altitude_m, p["z"], p["east"])) * p["e"] + float(np.interp(altitude_m, p["z"], p["north"])) * p["n"]
