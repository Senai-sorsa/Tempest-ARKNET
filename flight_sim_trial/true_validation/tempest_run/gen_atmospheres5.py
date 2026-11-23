"""G6 (2026-11-10, project venv): turbulence-option apogee test. Same pool as the hybrid rerun (past mode, seed 1, n 100, the engine's own batch), four turbulence variants from the SAME uniforms:
dryden (as shipped), uw (Reynolds-stress coupling uw_corr 0.35), karman (von Karman spectrum), karman_uw (both). Writes inputs5/<flight>__turb_<variant>.npz (as inputs3). Copies of the
2026-11-08 scripts; earlier outputs are untouched.
    cd <repo> ; TEMPEST_ERA5_STORE='data/pilot/profiles.zarr;data/pilot/profiles80_night.zarr' .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/gen_atmospheres5.py"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_atmospheres as G   # noqa: E402
from tempest_weather_v2 import Launch, Window   # noqa: E402

OUT = os.path.join(HERE, "inputs5")
VARIANTS = {"dryden": {}, "uw": dict(uw_corr=0.35), "karman": dict(spectrum="karman"), "karman_uw": dict(spectrum="karman", uw_corr=0.35)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for fl, spec in G.FLIGHTS.items():
        when = spec["when"] if isinstance(spec["when"], str) else Window(earliest=spec["when"][0], latest=spec["when"][1])
        L = Launch(G.SITE["lat"], G.SITE["lon"], when, mode="past", units="si", elevation=G.SITE["elev_m"], tz=G.SITE["tz"], n=a.n, seed=1)
        assert L._ensure_pool()["modes"] == {"past": 1.0}, "past mode required (B24)"
        eng = L.engine()
        u = np.random.default_rng(11).random((a.n, 10))
        for var, kw in VARIANTS.items():
            f = eng.sample_sobol_batch(u, k_atmo=6, **kw)["fine"]
            keep = f["z"] <= 12000.0
            np.savez(os.path.join(OUT, f"{fl}__turb_{var}.npz"), z=f["z"][keep].astype(np.float32), **{k: np.asarray(f[k])[:, keep].astype(np.float32) for k in ("u_turb", "v_turb", "w_turb", "gust_u", "gust_v")})
            z = f["z"]
            low = (z < 200)
            print(f"{fl} {var}: rms u < 200 m {np.sqrt(np.mean(np.asarray(f['u_turb'])[:, low] ** 2)):.2f}, w < 200 m {np.sqrt(np.mean(np.asarray(f['w_turb'])[:, low] ** 2)):.2f}, "
                  f"corr(u', w') < 200 m {np.corrcoef(np.asarray(f['u_turb'])[:, low].ravel(), np.asarray(f['w_turb'])[:, low].ravel())[0, 1]:+.2f}", flush=True)


if __name__ == "__main__":
    main()
