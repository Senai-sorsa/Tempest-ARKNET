"""How much does the tool's own elevation lookup (1493 m at the pad; the sim's pad is 1400.6 m) change the flights? 40 samples, same seed, elevation pinned vs the tool default.
    cd flight_sim_trial/src ; .venv/Scripts/python -I ../elev_sensitivity.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import experiment as ex   # noqa: E402  (also puts flight_sim and tempest_weather on the path)
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402

N = 40
res = {}
for label, elev in (("pinned to the pad (1400.6 m)", ex.PAD_M), ("tool's own lookup", None)):
    atm, info = api.atmosphere_set(ex.LAT, ex.LON, "2025-06-24T20:00:00+00:00", n=N, mode="ai", seed=1, elevation=elev)
    site = info["elevation_m"]
    s = {k: atm[k] for k in ("u", "v", "T", "RH", "p", "t2m", "sp", "rh2m")}
    s["w"] = atm["w"]
    s["height_agl"] = np.asarray(_core.HEIGHTS, np.float32)
    s["height_asl"] = (site + np.asarray(_core.HEIGHTS)).astype(np.float32)
    rows = []
    for k in range(N):
        sim_at = TempestAtmosphere(s, k)
        sim_w = TempestWind(s, k)
        rows.append(ex.metrics(ex.fly(sim_at, sim_w)))
    res[label] = rows
    print(f"{label}: tool site {site:.1f} m  sp median {np.median(atm['sp']) / 1000:.2f} kPa  apogee AGL {np.mean([r['apogee_agl_m'] for r in rows]):.0f} m  rho_pad {np.mean([r['rho_pad'] for r in rows]):.3f}  drift {np.mean([r['drift_m'] for r in rows]):.0f} m")
