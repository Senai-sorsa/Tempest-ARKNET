"""Fly Sol Invictus through the atmospheres of data/kit/flight_inputs.npz (truth balloon, real Earth-GRAM, tool), launched AT each balloon station
(launch elevation and latitude set to the station, heights above sea level = station elevation + the 44 model heights). Dry, no vertical wind, no pad node
(the same for every source). One row per flight -> results/gram_flights_<shard>.csv.

    cd flight_sim_trial/src ; .venv/Scripts/python -W ignore -I ../gram_flights.py --shard 0 --nshard 4
"""
import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src", "src"))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from flight_sim.simulation import Simulation                 # noqa: E402
from flight_sim.units import scalar                          # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402

import experiment as E                                       # noqa: E402  metrics() and the example's sim.toml

INP = os.path.join(os.path.dirname(HERE), "data", "kit", "flight_inputs.npz")


def fly(lat, elev, samples, k):
    sim = Simulation.from_file(E.SIM)
    tr = sim.config.truth
    tr.launch_elevation, tr.launch_latitude = scalar(elev, "m"), scalar(lat, "deg")
    atm = TempestAtmosphere(samples, k, pad_node=False)
    atm.anchor(elev)
    tr.atmosphere, tr.wind = atm, TempestWind(samples, k, include_vertical=False, pad_node=False)
    return E.metrics(sim.run())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshard", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="first N cases of the shard, 3 members (smoke)")
    ap.add_argument("--m", type=int, default=30, help="members flown per source (the first m)")
    a = ap.parse_args()
    d = np.load(INP)
    idx = np.arange(len(d["case"]))[a.shard::a.nshard]
    if a.limit:
        idx = idx[:a.limit]
    rows, t0 = [], time.time()
    for n, i in enumerate(idx):
        lat, elev = float(d["lat"][i]), float(d["elevation_m"][i])
        for s in d["sources"]:
            u = d[f"{s}__u"][i]
            m = min(u.shape[0], 3 if a.limit else a.m)
            samples = {q: d[f"{s}__{q}"][i].astype(float) for q in ("u", "v", "T", "p")}
            samples |= dict(RH=np.zeros_like(u, float), height_agl=d["height_agl"], height_asl=elev + d["height_agl"])
            for k in range(m):
                rows.append(dict(case=str(d["case"][i]), station=str(d["station"][i]), source=str(s), k=k, **fly(lat, elev, samples, k)))
        print(f"shard {a.shard}: case {n + 1}/{len(idx)} done ({time.time() - t0:.0f} s)", flush=True)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(HERE, "results", f"gram_flights_{a.shard}{'_smoke' if a.limit else ''}.csv"), index=False)


if __name__ == "__main__":
    main()
