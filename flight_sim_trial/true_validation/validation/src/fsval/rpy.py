"""Fly the same RASAero designs in RocketPy, from the same CDX1, motor and RAS drag, with RocketPy's own physics.
Plain on purpose, as anyone would set it up: no site temperature or pressure, no wind, no fin can reference, no nose or fins. rpy_helped is the version given FS's inputs."""
import csv
import json
import math
import sys
import time
import warnings
from pathlib import Path

from rocketpy import Environment, Flight, GenericMotor, Rocket

from . import ROOT, cdx1, eng, matrix
from .fsrun import LATITUDE_DEG, inertia
from .units import FT, IN, LB


def fly(d: cdx1.Design, m: eng.Motor, ras_csv: Path, run: Path) -> dict:
    run.mkdir(parents=True, exist_ok=True)
    (run / "motor.eng").write_text(m.text)
    rows = [r for r in csv.DictReader(ras_csv.open()) if float(r["Alpha"]) == 0]
    off = [(float(r["Mach"]), float(r["CA Power-Off"])) for r in rows]
    on = [(float(r["Mach"]), float(r["CA Power-On"])) for r in rows]
    mlen, mrad = m.length_mm / 1000, m.diameter_mm / 2000
    dry = d.launch_wt_lb * LB - m.total_kg
    ixx, iyy = inertia(dry, d.length_m, d.ref_diameter_m)
    cg_dry = (d.launch_wt_lb * LB * d.cg_in * IN - m.total_kg * (d.length_m - mlen / 2)) / dry  # from the nose
    motor = GenericMotor.load_from_eng_file(
        str(run / "motor.eng"), nozzle_radius=d.nozzle_in * IN / 2, chamber_radius=mrad, chamber_height=mlen,
        chamber_position=mlen / 2, center_of_dry_mass_position=mlen / 2, reference_pressure=101325,
        dry_inertia=(0, 0, 0))  # casing inertia is inside the rocket's own, as in FS
    rocket = Rocket(radius=d.ref_diameter_m / 2, mass=dry, inertia=(iyy, iyy, ixx), power_off_drag=off, power_on_drag=on,
                    center_of_mass_without_motor=d.length_m - cg_dry)  # tail_to_nose, origin at the base
    rocket.add_motor(motor, position=0)
    s = d.site
    env = Environment(latitude=LATITUDE_DEG, longitude=-100.0, elevation=s.get("Altitude", 0) * FT)
    env.set_atmospheric_model("standard_atmosphere")
    fl = Flight(rocket=rocket, environment=env, rail_length=max(s.get("RodLength", 0) * FT, 0.1),
                inclination=90 - s.get("RodAngle", 0), heading=0, terminate_on_apogee=True, max_time=400)
    return {"rpy_ft": (fl.apogee - env.elevation) / FT, "rpy_vmax_fps": fl.max_speed / FT, "rpy_t_ap": fl.apogee_time}


def one(case: str) -> dict:
    d = cdx1.read(matrix.cdx_path(case))
    run = matrix.src_dir(case)
    t = time.perf_counter()
    r = fly(d, eng.find(d.engine), run / "ras_aero.csv", run / "rpy_plain")
    return {**r, "rpy_s": time.perf_counter() - t}


def main(only: list[str]) -> None:
    warnings.filterwarnings("ignore")
    for path in (ROOT / "results" / "ras_cases.json", ROOT / "results" / "extra" / "scores.json"):
        res = json.loads(path.read_text())
        for r in res:
            if "@" in r["case"] or (only and r["case"] not in only) or ("fs_plain_ft" not in r and "built_ft" not in r):
                continue
            for k in ("rpy_ft", "rpy_vmax_fps", "rpy_t_ap", "rpy_margin", "rpy_error", "rpy_s"):
                r.pop(k, None)
            try:
                r.update(one(r["case"]))
                print(r["case"], round(r["rpy_ft"]), "ras", round(r["ras_ft"]), "truth", round(r["truth_ft"]), f"{r['rpy_s']:.1f} s", flush=True)
            except Exception as e:  # noqa: BLE001
                r["rpy_error"] = repr(e)[-300:]
                print(r["case"], "FAIL", repr(e)[-200:], flush=True)
        path.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
