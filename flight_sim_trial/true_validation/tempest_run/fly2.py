"""Rerun 2026-11-08 (step B, simulator venv): fly the 3 testable flights through S0 (branch air), S1 (standard air at the true pad) and every inputs2 scenario.

    cd flight_sim_trial/true_validation ; .venv/Scripts/python -W ignore -I tempest_run/fly2.py [--n 100]
"""
import argparse
import csv
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fly as F   # noqa: E402
from flight_sim.environment.atmosphere import StandardAtmosphere1976   # noqa: E402
from flight_sim.environment.wind import UniformWind                    # noqa: E402
from tempest_weather_v2.readers import Atmosphere                      # noqa: E402

SCEN = [("ai", "A climate"), ("past", "B past (ERA5+balloons)"), ("past_pin", "C past + ASOS pinned"), ("past_w", "D past + ASOS weighted"), ("ai_w", "E climate + ASOS weighted"),
        ("past_hrrr", "F past + HRRR ground anchor"), ("past_s12", "G past, wind spread x1.2")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    n = ap.parse_args().n
    rows, t0 = [], time.time()
    for fl, truth in F.TRUTH.items():
        rows.append(dict(flight=fl, scenario="S0 branch as filed", k=-1, truth_ft=truth, **F.fly(fl, true_site=False)))
        isa = StandardAtmosphere1976()
        isa.anchor(F.SITE["elev_m"])
        rows.append(dict(flight=fl, scenario="S1 standard air, true pad, no wind", k=-1, truth_ft=truth, **F.fly(fl, isa, UniformWind())))
        for key, label in SCEN:
            path = os.path.join(HERE, "inputs2", f"{fl}__{key}.npz")
            if not os.path.exists(path):
                print("missing", path, flush=True)
                continue
            z = np.load(path)
            s = {k: z[k] for k in z.files}
            s["elevation_m"] = float(s["elevation_m"])
            for k in range(min(n, len(s["u"]))):
                a = Atmosphere(s, k)
                rows.append(dict(flight=fl, scenario=label, k=k, truth_ft=truth, **F.fly(fl, a, a)))
            print(f"{fl} {label}: done ({time.time() - t0:.0f} s)", flush=True)
    with open(os.path.join(HERE, "flights2.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("done", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
