"""Hybrid rerun (step A, project venv): the PAST-mode wind of the Tempest atmospheres (same pool as inputs2/<flight>__past: seed 1, n = 100) plus Dryden turbulence and discrete gust fields from the Tempest engine,
saved so that the simulator step can fly them over a STANDARD atmosphere (air = 'standard').

    cd <repo> ; TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/gen_atmospheres3.py [--n 100]
Writes inputs3/<flight>__turb.npz : z (fine grid, m above the pad, up to 12 km), u_turb, v_turb, w_turb, gust_u, gust_v  (n, nz) float32 (east, north, up wind perturbations; frozen fields).
The pool wind of row k is paired with turbulence row k (independent draws; the turbulence strength depends on the engine batch's own profile, a limitation).
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_atmospheres as G   # noqa: E402
from tempest_weather_v2 import Launch, Window   # noqa: E402

OUT = os.path.join(HERE, "inputs3")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(G.REPO, "data", "pilot", "profiles.zarr")
    for fl, spec in G.FLIGHTS.items():
        when = spec["when"] if isinstance(spec["when"], str) else Window(earliest=spec["when"][0], latest=spec["when"][1])
        L = Launch(G.SITE["lat"], G.SITE["lon"], when, mode="past", units="si", elevation=G.SITE["elev_m"], tz=G.SITE["tz"], n=a.n, seed=1)
        eng = L.engine()
        u = np.random.default_rng(11).random((a.n, 10))
        b = eng.sample_sobol_batch(u, k_atmo=6)
        f = b["fine"]
        keep = f["z"] <= 12000.0
        np.savez(os.path.join(OUT, f"{fl}__turb.npz"), z=f["z"][keep].astype(np.float32), **{k: np.asarray(f[k])[:, keep].astype(np.float32) for k in ("u_turb", "v_turb", "w_turb", "gust_u", "gust_v")})
        z = f["z"]
        rms = lambda k, lo, hi: float(np.sqrt(np.mean(np.asarray(f[k])[:, (z >= lo) & (z < hi)] ** 2)))
        print(f"{fl}: turbulence rms u below 200 m {rms('u_turb', 0, 200):.2f}, 200-1000 m {rms('u_turb', 200, 1000):.2f} m/s; w below 200 m {rms('w_turb', 0, 200):.2f}; gust peak median {np.median(np.abs(f['gust_u']).max(1)):.1f} m/s", flush=True)


if __name__ == "__main__":
    main()
