"""Hybrid rerun (step B, simulator venv): fly the 3 testable flights with the branch's own air (S0), a plain standard atmosphere at the true pad (S1), the full Tempest past-mode atmosphere (B, as in rerun 2), and the HYBRIDS:
 H0 = standard air + Tempest past-mode wind;  H1 = H0 + Dryden turbulence (frozen field);  H2 = H1 + the 1-cos discrete gust.

    cd flight_sim_trial/true_validation ; .venv/Scripts/python -W ignore -I tempest_run/fly3.py [--n 100]
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
        z = np.load(os.path.join(HERE, "inputs2", f"{fl}__past.npz"))
        s = {k: z[k] for k in z.files}
        s["elevation_m"] = float(s["elevation_m"])
        t = np.load(os.path.join(HERE, "inputs3", f"{fl}__turb.npz"))
        for label, kw in (("B Tempest past (full atmosphere)", None), ("H0 standard air + Tempest wind", dict(air="standard")), ("H1 H0 + turbulence", dict(air="standard", turb=True)),
                          ("H2 H1 + discrete gust", dict(air="standard", turb=True, gust=True))):
            for k in range(min(n, len(s["u"]))):
                extra = {}
                if kw and kw.get("air"):
                    extra["air"] = kw["air"]
                if kw and kw.get("turb"):
                    e, no = t["u_turb"][k].astype(float), t["v_turb"][k].astype(float)
                    if kw.get("gust"):
                        e, no = e + t["gust_u"][k], no + t["gust_v"][k]
                    extra["perturbation"] = dict(z=t["z"], east=e, north=no, up=t["w_turb"][k])
                a = Atmosphere(s, k, **extra)
                rows.append(dict(flight=fl, scenario=label, k=k, truth_ft=truth, **F.fly(fl, a, a)))
            print(f"{fl} {label}: done ({time.time() - t0:.0f} s)", flush=True)
    with open(os.path.join(HERE, "flights3.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("done", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
