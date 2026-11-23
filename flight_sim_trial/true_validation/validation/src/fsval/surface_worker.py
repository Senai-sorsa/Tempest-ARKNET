"""Add-on, runs in the simulator's venv: FS's ReynoldsCorrection hook returns RAS's own change in Cx with Mach and altitude.
FS's files are not edited. argv: sim.toml out.json surface.json [throat_m]; the sim must have a reynolds_correction.
The surface is keyed on density*a/mu, as FS's own correction is, so a hot or cold day shifts it the same way.
shortcut: the hook cannot see the motor state, so the power-off change is used in the burn too; upgrade if the two differ in trace."""
import json
import math
import runpy
import sys
from pathlib import Path

from flight_sim.environment.atmosphere import StandardAtmosphere1976, dynamic_viscosity
from flight_sim.vehicle.reynolds_correction import ReynoldsCorrection

HERE = Path(__file__).parent
Surface = runpy.run_path(str(HERE / "surface_lookup.py"))["Surface"]


def group(air):
    return air.air_density * air.speed_of_sound / dynamic_viscosity(air.temperature)


data = json.loads(Path(sys.argv[3]).read_text())
atmosphere = StandardAtmosphere1976()
sea = group(atmosphere.conditions(0.0))
# Altitude rises as the Reynolds ratio falls, so both lists turn around for the rising axis
keys = [math.log(group(atmosphere.conditions(h * 0.3048)) / sea) for h in reversed(data["altitudes_ft"])]
surface = Surface(keys, data["machs"], data["dcx"][::-1])


def correction(self, mach, air):
    if air.air_density <= 0.0 or mach <= 0.0:
        return 0.0
    return surface(math.log(group(air) / sea), mach)


ReynoldsCorrection.__call__ = correction
worker, sys.argv = ("kb_worker.py", [sys.argv[0], sys.argv[1], sys.argv[2], sys.argv[4]]) if len(sys.argv) > 4 else ("fs_worker.py", sys.argv[:3])
runpy.run_path(str(HERE / worker), run_name="__main__")
