"""Fly every scored design in RocketPy, one flight per process, from the same CDX1, motor and RAS sea-level drag as FS's frozen setup, with RocketPy's own physics.
Same inputs as FS: fin can reference area, the file's site temperature, pressure and wind, FS's scaled standard air, linear nozzle.
RocketPy's own: its integrator, its constant 9.80665 gravity, and Barrowman stability from the nose and fins, which only steer it. Its drag follows Mach alone, so no Reynolds change.
Results go to results/rpy_helped.json, beside the plain fsval.rpy. Usage: python -m fsval.rpy_helped [case ...]"""
import csv
import json
import os
import sys
import warnings
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")  # before numpy loads: one flight, one core

import numpy as np
from rocketpy import Environment, Flight, GenericMotor, Rocket

from . import ROOT, cdx1, eng, matrix
from .fsrun import LATITUDE_DEG, inertia
from .units import FT, IN, INHG, LB, MPH

NOSES = {"Tangent Ogive": "tangent", "Von Karman Ogive": "vonKarman", "Conical": "conical", "Elliptical": "elliptical", "Parabolic": "parabolic"}  # shortcut: other shapes fly as von Karman, nose CN is 2 for all and only CP shifts; upgrade if a flight's stability is close
TOP_M = 80000  # RocketPy's standard atmosphere ends here


def air(env: Environment, site: dict) -> None:
    """FS's rule: standard air scaled to pass through the site's values, with the file's wind blowing from the north."""
    env.set_atmospheric_model(type="standard_atmosphere")
    z = np.linspace(0, TOP_M, 801)
    p, t = np.vectorize(env.pressure)(z), np.vectorize(env.temperature)(z)
    site_t = (site.get("Temperature", 59) + 459.67) / 1.8
    scale_t = site_t / env.temperature(env.elevation)
    scale_p = site["Pressure"] * INHG / 101325 if site.get("Pressure") else 1.0
    wind = -site.get("WindSpeed", 0) * MPH
    env.set_atmospheric_model(type="custom_atmosphere", pressure=np.column_stack((z, p * scale_p)).tolist(), temperature=np.column_stack((z, t * scale_t)).tolist(), wind_u=0.0, wind_v=[(0.0, wind), (float(TOP_M), wind)])


def surfaces(rocket: Rocket, path: Path, d: cdx1.Design) -> None:
    """Nose and fins, so a tilted or windy flight weathercocks as FS's table makes it."""
    rd = ET.fromstring(path.read_text(encoding="utf-8-sig", errors="replace")).find("RocketDesign")
    t = lambda e, k: float(e.findtext(k) or 0) * IN  # noqa: E731
    nose = rd.find("NoseCone")
    rocket.add_nose(length=t(nose, "Length"), kind=NOSES.get(nose.findtext("Shape"), "vonKarman"), position=d.length_m)
    tail = rd.find("BoatTail")
    aft = t(tail, "Length") if tail is not None else 0.0
    for fin in rd.iter("Fin"):  # Location runs forward from the rear of the part that holds the fin
        rocket.add_trapezoidal_fins(n=int(fin.findtext("Count")), root_chord=t(fin, "Chord"), tip_chord=t(fin, "TipChord"), span=t(fin, "Span"), position=aft + t(fin, "Location"), sweep_length=t(fin, "SweepDistance"))


def fly(case: str) -> dict:
    warnings.filterwarnings("ignore")
    path, run = matrix.cdx_path(case), matrix.src_dir(case) / "rpy"
    plain = cdx1.read(path)
    d = matrix.fincan_design(plain, case)
    m = eng.find(d.engine)
    run.mkdir(parents=True, exist_ok=True)
    (run / "motor.eng").write_text(m.text)
    rows = [r for r in csv.DictReader((run.parent / "ras_aero.csv").open()) if float(r["Alpha"]) == 0]
    off = [(float(r["Mach"]), float(r["CA Power-Off"])) for r in rows]
    on = [(float(r["Mach"]), float(r["CA Power-On"])) for r in rows]
    mlen, mrad = m.length_mm / 1000, m.diameter_mm / 2000
    wt = d.launch_wt_lb * LB
    dry = wt - m.total_kg
    ixx, iyy = inertia(dry, d.length_m, d.ref_diameter_m)
    cg_dry = (wt * d.cg_in * IN - m.total_kg * (d.length_m - mlen / 2)) / dry  # from the nose
    motor = GenericMotor.load_from_eng_file(
        str(run / "motor.eng"), nozzle_radius=max(d.nozzle_in * IN / 2, 1e-6), chamber_radius=mrad, chamber_height=mlen,  # RocketPy reads a zero radius as unset and picks a real nozzle
        chamber_position=mlen / 2, center_of_dry_mass_position=mlen / 2, reference_pressure=101325,
        dry_inertia=(0, 0, 0))  # casing inertia is inside the rocket's own, as in FS
    rocket = Rocket(radius=d.ref_diameter_m / 2, mass=dry, inertia=(iyy, iyy, ixx), power_off_drag=off, power_on_drag=on,
                    center_of_mass_without_motor=d.length_m - cg_dry, coordinate_system_orientation="tail_to_nose")  # origin at the base
    rocket.add_motor(motor, position=0)
    surfaces(rocket, path, d)
    assert abs(rocket.total_mass(0) / wt - 1) < 1e-3, (case, rocket.total_mass(0), wt)
    s = d.site
    env = Environment(latitude=LATITUDE_DEG, longitude=-100.0, elevation=s.get("Altitude", 0) * FT)
    air(env, s)
    fl = Flight(rocket=rocket, environment=env, rail_length=max(s.get("RodLength", 0) * FT, 0.1),
                inclination=90 - s.get("RodAngle", 0), heading=0, terminate_on_apogee=True, max_time=400)
    return {"case": case, "rpy_ft": (fl.apogee - env.elevation) / FT, "rpy_vmax_fps": fl.max_speed / FT, "rpy_t_ap": fl.apogee_time, "rpy_margin": float(rocket.static_margin(0))}


def attempt(case: str) -> dict:
    try:
        return fly(case)
    except Exception as e:  # noqa: BLE001
        return {"case": case, "rpy_error": repr(e)[-300:]}


def main(only: list[str]) -> None:
    dev, held = matrix.flights()
    cases = [r["case"] for r in dev + held if not only or r["case"] in only]
    out = {}
    with ProcessPoolExecutor(min(len(cases), matrix.WORKERS)) as pool:
        for f in as_completed([pool.submit(attempt, c) for c in cases], timeout=1800):
            o = out[f.result()["case"]] = f.result()
            print(o["case"], round(o["rpy_ft"]) if "rpy_ft" in o else "FAIL " + o["rpy_error"], flush=True)
    (ROOT / "results" / "rpy_helped.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
