"""Same atmospheres, real simulator: v2 readers (tempest_weather_v2.readers.Atmosphere) vs the original readers. Part of the deletable trial folder."""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import experiment as ex   # noqa: E402
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402
from tempest_weather_v2.readers import Atmosphere   # noqa: E402

N = 20
atm, info = api.atmosphere_set(ex.LAT, ex.LON, "2025-06-24T20:00:00+00:00", n=N, mode="ai", seed=1, elevation=ex.PAD_M)
s = {k: atm[k] for k in ("u", "v", "T", "RH", "p", "t2m", "sp", "rh2m")}
s["w"] = atm["w"]
s["height_agl"] = np.asarray(_core.HEIGHTS, np.float32)
s["height_asl"] = (ex.PAD_M + np.asarray(_core.HEIGHTS)).astype(np.float32)
d_ap, d_dr, t_old, t_new = [], [], 0.0, 0.0
for k in range(N):
    t0 = time.perf_counter(); mo = ex.metrics(ex.fly(TempestAtmosphere(s, k), TempestWind(s, k))); t_old += time.perf_counter() - t0
    v2 = Atmosphere(s, k)
    t0 = time.perf_counter(); mn = ex.metrics(ex.fly(v2, v2)); t_new += time.perf_counter() - t0
    d_ap.append(mn["apogee_asl_m"] - mo["apogee_asl_m"]); d_dr.append(mn["drift_m"] - mo["drift_m"])
print(f"{N} flights: v2 - old  apogee max |diff| {np.abs(d_ap).max():.3f} m, drift max |diff| {np.abs(d_dr).max():.3f} m;  wall {t_old:.1f} s (old) vs {t_new:.1f} s (v2)")
