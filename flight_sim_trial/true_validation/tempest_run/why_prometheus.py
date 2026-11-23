"""Why does Prometheus react so strongly? Take the past-mode atmospheres and change only the wind in one height band, flight by flight.
    cd flight_sim_trial/true_validation ; .venv/Scripts/python -W ignore -I tempest_run/why_prometheus.py [--flight Prometheus] [--n 30]
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fly as F   # noqa: E402
from tempest_weather_v2.readers import Atmosphere   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--flight", default="Prometheus")
ap.add_argument("--n", type=int, default=30)
a = ap.parse_args()
z = np.load(os.path.join(HERE, "inputs", f"{a.flight}__past.npz"))
base = {k: z[k] for k in z.files}
base["elevation_m"] = float(base["elevation_m"])
h = base["height_agl"]
truth = F.TRUTH[a.flight]


def variant(low=1.0, high=1.0, split=200.0):
    s = dict(base)
    f = np.where(h <= split, low, high)[None, :]
    s["u"], s["v"] = base["u"] * f, base["v"] * f
    return s


def run(label, s):
    ap_ft = [F.fly(a.flight, (at := Atmosphere(s, k)), at)["apogee_ft"] for k in range(min(a.n, len(s["u"])))]
    m = float(np.median(ap_ft))
    print(f"{label:62} {m:8.0f} ft  ({100 * (m / truth - 1):+5.1f} %)", flush=True)
    return m


print(f"{a.flight}, truth {truth:.0f} ft, past-mode atmospheres, median of {a.n}")
ref = run("as generated (past mode)", variant())
run("wind below 200 m x 0 (calm near the ground), above unchanged", variant(low=0.0))
run("wind below 200 m x 0.3, above unchanged", variant(low=0.3))
run("wind below 200 m x 2, above unchanged", variant(low=2.0))
run("wind above 200 m x 0, below unchanged", variant(high=0.0))
run("no wind at all", variant(low=0.0, high=0.0))
