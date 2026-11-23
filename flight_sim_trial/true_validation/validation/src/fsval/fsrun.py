"""Build and fly an FS sim for a RASAero design, through the simulator's own venv."""
import json
import math
import os
import subprocess
import threading
from pathlib import Path

from . import FS_PYTHON
from .cdx1 import Design
from .eng import Motor
from .units import FT, IN, INHG, LB, MPH

_local = threading.local()
LATITUDE_DEG = 35.0  # inferred: sites are not in the files; g varies 0.02 % over +-10 deg


def inertia(mass: float, length: float, diameter: float) -> tuple[float, float]:
    """Slender-body estimate (roll, pitch/yaw) about the CG; inferred, bracket +-30 %."""
    return 0.5 * mass * (diameter / 2) ** 2, mass * length**2 / 12


def build(d: Design, m: Motor, run: Path, reynolds: bool = True, ras_wind: bool = True, gravity_m_s2: float | None = None, physics: str = "", air_profile: bool = False, wind_profile: bool = False, **over) -> Path:
    run.mkdir(parents=True, exist_ok=True)
    (run / "motor.eng").write_text(m.text)
    wt = d.launch_wt_lb * LB
    dry = wt - m.total_kg
    if dry <= 0:
        raise ValueError(f"launch weight {wt:.1f} kg is below the motor's {m.total_kg:.1f} kg")
    mlen = m.length_mm / 1000
    fwd = d.length_m - mlen  # motor flush with the base: inferred, RASAero never needs a motor position
    motor_cg = fwd + mlen / 2
    cg_dry = (wt * d.cg_in * IN - m.total_kg * motor_cg) / dry
    ixx, iyy = inertia(dry, d.length_m, d.ref_diameter_m)
    area = math.pi * d.ref_diameter_m**2 / 4
    s = d.site
    wind = s.get("WindSpeed", 0.0) * MPH if ras_wind else 0.0
    atm = f'launch_temperature = "{s.get("Temperature", 59):g} degF"\n'
    if s.get("Pressure"):
        atm += f'barometric_pressure = "{s["Pressure"]:g} inHg"\n'
    atm_toml = 'type = "profile_air.ProfileAtmosphere"\nfilepath = "profile.json"\n' if air_profile else f'type = "flight_sim.environment.atmosphere.StandardAtmosphere1976"\n{atm}'
    wind_toml = 'type = "profile_air.ProfileWind"\nfilepath = "profile.json"' if wind_profile else f'type = "flight_sim.environment.wind.UniformWind"\nspeed = "{wind:.4f} m/s"\nfrom_azimuth = "0 deg"'
    gravity = f'type = "flight_sim.environment.gravity.ConstantGravity"\nmagnitude_m_s2 = {gravity_m_s2}' if gravity_m_s2 else 'type = "flight_sim.environment.gravity.WGS84Gravity"'
    reyn = reynolds_block(d, area) if reynolds else ""
    (run / "sim.toml").write_text(f'''name = "{d.name}"
stop_event = "apogee"
max_time = "400 s"

[properties.aero_table]
type = "flight_sim.utilities.data_loader.aero_table_from_csv"
filepath = "aero.csv"
reference_area = "{area:.9f} m**2"
reference_length = "{d.ref_diameter_m:.6f} m"
reference_point = {{ value = [0.0, 0.0, 0.0], units = "m" }}
frame = "missile"
extrapolation = "clamp"

[properties.dry_mass_properties]
mass = "{dry:.4f} kg"
cg_location = {{ value = [{-cg_dry:.5f}, 0.0, 0.0], units = "m" }}
inertia = {{ diag = [{ixx:.5f}, {iyy:.4f}, {iyy:.4f}], units = "kg*m**2" }}

[properties.engine]
type = "flight_sim.vehicle.engine.SolidEngine.from_eng"
motor_file_path = "motor.eng"
forward_end_location = {{ value = [{-fwd:.5f}, 0.0, 0.0], units = "m" }}
nozzle_exit_area = "{math.pi * (d.nozzle_in * IN / 2) ** 2:.6f} m**2"
reference_pressure = "101325 Pa"
{reyn}{physics}
[config.truth]
launch_latitude = "{LATITUDE_DEG} deg"
launch_elevation = "{s.get("Altitude", 0) * FT:.2f} m"

[config.truth.atmosphere]
{atm_toml}
[config.truth.gravity]
{gravity}

[config.truth.wind]
{wind_toml}

[config.truth.launch_rail]
length = "{s.get("RodLength", 0) * FT:.3f} m"
friction_coefficient = 0.0
elevation = "{90 - s.get("RodAngle", 0):g} deg"
azimuth = "0 deg"

[[events]]
ref = "flight_sim.events.APOGEE"
''')
    return run / "sim.toml"


def reynolds_block(d: Design, area_m2: float) -> str:
    """The sim.toml block for FS's built-in correction, on the area the aero table flies."""
    s = d.skin
    fins = "".join(f'\n[[properties.reynolds_correction.fins]]\nwetted_area = "{a:.6f} m**2"\nmean_chord = "{c:.5f} m"\nthickness = "{t:.5f} m"\n' for a, c, t in s.fins)
    return f'''
[properties.reynolds_correction]
type = "flight_sim.vehicle.reynolds_correction.ReynoldsCorrection"
reference_area = "{area_m2:.9f} m**2"
body_length = "{d.length_m:.5f} m"
body_diameter = "{s.diameter_m:.5f} m"
body_wetted_area = "{s.body_wetted_m2:.6f} m**2"
roughness = "{s.roughness_m:.9f} m"
all_turbulent = {str(s.all_turbulent).lower()}
{fins}'''


def base_drag(model: str, throat_mm: float, base_mm: float, gamma: float) -> str:
    """The sim.toml block that selects FS's PowerOnBaseDrag."""
    return f'''
[config.physics]
type = "flight_sim.phases.PowerOnBaseDrag"
model = "{model}"
throat_diameter = "{throat_mm:.3f} mm"
base_diameter = "{base_mm:.3f} mm"
exhaust_gamma = {gamma}
'''


def _server() -> subprocess.Popen:
    """This thread's long-lived FS process, started on first use and again if it died."""
    p = getattr(_local, "server", None)
    if p is None or p.poll() is not None:
        p = _local.server = subprocess.Popen([str(FS_PYTHON), "-I", str(Path(__file__).with_name("flight_server.py"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                             env={"PYTHONPATH": str(FS_PYTHON.parents[2] / "src"), "SYSTEMROOT": os.environ["SYSTEMROOT"], "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    return p


def _run(script: str, args: list[str], cwd: Path) -> None:
    p = _server()
    timer = threading.Timer(600, p.kill)  # a hung flight ends in the empty reply below
    timer.start()
    try:
        p.stdin.write(json.dumps({"script": script, "argv": [script, *args], "cwd": str(cwd)}) + "\n")
        p.stdin.flush()
        reply = p.stdout.readline()
    finally:
        timer.cancel()
    if not reply:
        raise RuntimeError(f"flight server died on {cwd}")
    if json.loads(reply)["error"]:
        raise RuntimeError(json.loads(reply)["error"][-1500:])


def fly(sim: Path, throat_m: float | None = None, surface: Path | None = None, profile: bool = False) -> dict:
    out = sim.parent / "fs.json"
    if surface:
        worker = ("profile_worker.py" if profile else "surface_worker.py", sim, out, surface, *([throat_m] if throat_m else []))
    else:
        worker = ("kb_worker.py", sim, out, throat_m) if throat_m else ("fs_worker.py", sim, out)
    _run(str(Path(__file__).with_name(worker[0])), [*map(str, worker[1:])], sim.parent)
    return json.loads(out.read_text())
