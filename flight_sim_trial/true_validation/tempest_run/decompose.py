"""Which part of the Tempest effect is air (temperature, pressure, density) and which is wind? For the 'past' scenario (ERA5 + balloon correction), fly
 (air only)  = Tempest air profile, no wind;   (wind only) = standard atmosphere at the true pad with the Tempest wind profile;   (both) = the S3 flights.
    cd flight_sim_trial/true_validation ; .venv/Scripts/python -W ignore -I tempest_run/decompose.py [--n 40]
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fly as F   # noqa: E402  (puts flight_sim and the repo on the path)
from flight_sim.environment.atmosphere import StandardAtmosphere1976   # noqa: E402
from flight_sim.environment.wind import UniformWind                    # noqa: E402
from tempest_weather_v2.readers import Atmosphere                      # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
n = ap.parse_args().n
print(f"{'flight':13} {'truth':>7} | {'ISA, no wind':>16} | {'Tempest air only':>18} | {'ISA + Tempest wind':>20} | {'Tempest air + wind':>20}")
for fl, truth in F.TRUTH.items():
    z = np.load(os.path.join(HERE, "inputs", f"{fl}__past.npz"))
    s = {k: z[k] for k in z.files}
    s["elevation_m"] = float(s["elevation_m"])
    isa = StandardAtmosphere1976()
    isa.anchor(F.SITE["elev_m"])
    base = F.fly(fl, isa, UniformWind())["apogee_ft"]
    air, wind, both = [], [], []
    for k in range(min(n, len(s["u"]))):
        a = Atmosphere(s, k)
        air.append(F.fly(fl, a, UniformWind())["apogee_ft"])
        i2 = StandardAtmosphere1976()
        i2.anchor(F.SITE["elev_m"])
        wind.append(F.fly(fl, i2, a)["apogee_ft"])
        both.append(F.fly(fl, a, a)["apogee_ft"])
    e = lambda v: f"{np.median(v):7.0f} ({100 * (np.median(v) / truth - 1):+5.1f}%)"
    print(f"{fl:13} {truth:7.0f} | {base:7.0f} ({100 * (base / truth - 1):+5.1f}%) | {e(air):>18} | {e(wind):>20} | {e(both):>20}", flush=True)
