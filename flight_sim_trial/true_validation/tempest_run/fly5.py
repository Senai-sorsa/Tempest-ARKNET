"""G6 (2026-11-10 copy of fly3.py; outputs inputs5 / flights5.csv): turbulence options. Was: Hybrid rerun (step B, simulator venv): fly the 3 testable flights with the branch's own air (S0), a plain standard atmosphere at the true pad (S1), the full Tempest past-mode atmosphere (B, as in rerun 2), and the HYBRIDS:
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
        z = np.load(os.path.join(HERE, "inputs2", f"{fl}__past.npz"))
        s = {k: z[k] for k in z.files}
        s["elevation_m"] = float(s["elevation_m"])
        T5 = {v: np.load(os.path.join(HERE, "inputs5", f"{fl}__turb_{v}.npz")) for v in ("dryden", "uw", "karman", "karman_uw")}
        for label, kw in (("H0 standard air + Tempest wind", dict(air="standard")), ("H1 + Dryden (shipped)", dict(air="standard", turb="dryden")), ("H1 + Dryden + u'w' coupling", dict(air="standard", turb="uw")),
                          ("H1 + von Karman", dict(air="standard", turb="karman")), ("H1 + von Karman + u'w'", dict(air="standard", turb="karman_uw"))):
            for k in range(min(n, len(s["u"]))):
                extra = {}
                if kw and kw.get("air"):
                    extra["air"] = kw["air"]
                if kw and kw.get("turb"):
                    t = T5[kw["turb"]]
                    e, no = t["u_turb"][k].astype(float), t["v_turb"][k].astype(float)
                    if kw.get("gust"):
                        e, no = e + t["gust_u"][k], no + t["gust_v"][k]
                    extra["perturbation"] = dict(z=t["z"], east=e, north=no, up=t["w_turb"][k])
                a = Atmosphere(s, k, **extra)
                rows.append(dict(flight=fl, scenario=label, k=k, truth_ft=truth, **F.fly(fl, a, a)))
            print(f"{fl} {label}: done ({time.time() - t0:.0f} s)", flush=True)
    with open(os.path.join(HERE, "flights5.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("done", f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
