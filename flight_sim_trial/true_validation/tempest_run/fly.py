"""Step B (simulator venv): fly the JARVIS-TRUE-VALIDATION frozen setup for each flight through (a) the branch's own standard air, (b) a plain standard atmosphere at the TRUE pad
elevation and latitude, and (c) Tempest-ARKNET atmospheres (climate, past = ERA5 corrected to balloons, past conditioned on measured surface values).

    cd flight_sim_trial/true_validation ; .venv/Scripts/python -W ignore -I tempest_run/fly.py [--n 100]
Everything but the atmosphere and wind is the branch's frozen setup (sea-level drag table, built-in Reynolds correction, power-on table, linear nozzle; rail as filed).
Apogee is feet above the pad, as in the branch's report; error is (simulated / true - 1) in percent.
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROOT, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, REPO)

from flight_sim.environment.atmosphere import StandardAtmosphere1976   # noqa: E402
from flight_sim.environment.wind import UniformWind                    # noqa: E402
from flight_sim.simulation import Simulation                           # noqa: E402
from flight_sim.units import scalar                                    # noqa: E402
from tempest_weather_v2.readers import Atmosphere                      # noqa: E402

FT = 0.3048
SITE = dict(lat=32.939377, elev_m=1401.0)
TRUTH = {"Prometheus": 12788.714, "Juno3": 10541.339, "HeartOfSteel": 30411.0}


def fly(flight, atmosphere=None, wind=None, true_site=True):
    d = os.path.join(ROOT, "validation", "results", "matrix", flight, "sea_re2_po1_w0_linear")
    cwd = os.getcwd()
    os.chdir(d)
    try:
        sim = Simulation.from_file("sim.toml")
        if true_site:
            sim.config.truth.launch_latitude = scalar(SITE["lat"], "deg")
            sim.config.truth.launch_elevation = scalar(SITE["elev_m"], "m")
        if atmosphere is not None:
            sim.config.truth.atmosphere = atmosphere
        if wind is not None:
            sim.config.truth.wind = wind
        f = sim.run()
        df = f.to_dataframe()
        alt = df["environment.altitude [m]"].to_numpy()
        return dict(apogee_ft=float((alt.max() - alt[0]) / FT), t_apogee=float(df["time [s]"].iloc[-1]), rho_pad=float(df["environment.atmosphere.air_density [kg/m**3]"].iloc[0]),
                    T_pad=float(df["environment.atmosphere.temperature [K]"].iloc[0]), max_wind=float(np.hypot(df["environment.wind_y [m/s]"], df["environment.wind_z [m/s]"]).max()))
    finally:
        os.chdir(cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    rows = []
    t0 = time.time()
    for fl, truth in TRUTH.items():
        base = fly(fl, true_site=False)                               # the branch's own run, untouched (latitude 35 deg, its elevation, its filed air)
        rows.append(dict(flight=fl, scenario="S0 branch as filed", k=-1, truth_ft=truth, **base))
        d = os.path.join(ROOT, "validation", "results", "matrix", fl, "sea_re2_po1_w0_linear")
        isa = StandardAtmosphere1976()
        isa.anchor(SITE["elev_m"])
        rows.append(dict(flight=fl, scenario="S1 plain standard atmosphere at the true pad, no wind", k=-1, truth_ft=truth, **fly(fl, isa, UniformWind())))
        for scen, label in (("ai", "S2 Tempest climate (date + hour)"), ("past", "S3 Tempest past (ERA5 + balloon correction)"), ("past_obs", "S4 Tempest past + measured surface values")):
            path = os.path.join(HERE, "inputs", f"{fl}__{scen}.npz")
            if not os.path.exists(path):
                print("missing", path)
                continue
            z = np.load(path)
            samples = {k: z[k] for k in z.files}
            samples["elevation_m"] = float(samples["elevation_m"])
            n = min(a.n, len(samples["u"]))
            for k in range(n):
                atm = Atmosphere(samples, k)
                rows.append(dict(flight=fl, scenario=label, k=k, truth_ft=truth, **fly(fl, atm, atm)))
            print(f"{fl} {label}: {n} flights done ({time.time() - t0:.0f} s)", flush=True)
    keys = list(rows[0])
    with open(os.path.join(HERE, "flights.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)
    print("done", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
