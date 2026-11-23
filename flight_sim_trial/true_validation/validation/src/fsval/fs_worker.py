"""Runs in the simulator's own venv: fly one sim.toml, dump the flight as JSON. Reads FS, never edits it."""
import json
import sys

import numpy as np
from flight_sim.simulation import Simulation

flight = Simulation.from_file(sys.argv[1]).run()
d = flight.to_dataframe()
alt = d["environment.altitude [m]"].to_numpy()
t = d["time [s]"].to_numpy()
speed = d["aero.airspeed [m/s]"].to_numpy()
mach = d["aero.mach [-]"].to_numpy()
i = int(np.argmax(alt))
col = lambda name: d[next(c for c in d.columns if c.startswith(name + " ["))].to_numpy()
json.dump({
    "apogee_agl_m": float(alt[i] - alt[0]),
    "t_apogee_s": float(t[i]),
    "vmax_m_s": float(speed.max()),
    "mach_max": float(mach.max()),
    "series": {"t": t[::5].tolist(), "alt_agl": (alt[::5] - alt[0]).tolist(),
               "speed": speed[::5].tolist(), "mach": mach[::5].tolist(), "thrust": col("thrust")[::5].tolist(),
               "mass": col("mass.mass")[::5].tolist(), "force_x": col("aero.force_x")[::5].tolist(),
               "q": col("aero.dynamic_pressure")[::5].tolist(), "rho": col("environment.atmosphere.air_density")[::5].tolist(),
               "alpha_deg": np.degrees(col("aero.alpha"))[::5].tolist()},
}, open(sys.argv[2], "w"))
