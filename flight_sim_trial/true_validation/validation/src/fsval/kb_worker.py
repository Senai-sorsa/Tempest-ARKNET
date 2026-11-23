"""Add-on, runs in the simulator's venv: fs_worker.py with SolidEngine.get_thrust patched at runtime to a Kalt-Badal
separated / unchoked nozzle (spec in tasks/nozzle_separation.md). FS's files are not edited.
argv: sim.toml out.json throat_m. The curve is inverted to chamber pressure at the engine's reference pressure.
shortcut: gamma fixed at the throat estimate's 1.22, no loss factor; upgrade with real motor data."""
import math
import runpy
import sys
from pathlib import Path

import numpy as np
from flight_sim.vehicle.engine import SolidEngine
from scipy.optimize import brentq

G = 1.22
K_REC = 0.08
NPR_CRIT = ((G + 1) / 2) ** (G / (G - 1))


def area_ratio(m):
    return (2 / (G + 1) * (1 + (G - 1) / 2 * m * m)) ** ((G + 1) / (2 * (G - 1))) / m


def cf_mom(p_ratio):
    return math.sqrt(2 * G * G / (G - 1) * (2 / (G + 1)) ** ((G + 1) / (G - 1)) * (1 - p_ratio ** ((G - 1) / G)))


def thrust(pc, pa, at, eps, tau):
    if pc <= pa:
        return 0.0
    if pc / pa < NPR_CRIT:
        return G * pa * 2 / (G - 1) * ((pc / pa) ** ((G - 1) / G) - 1) * at
    pe = tau * pc
    psep = min(0.667 * (pc / pa) ** -0.2 * pa, pc / NPR_CRIT)
    if pe >= psep:
        return pc * at * cf_mom(tau) + (pe - pa) * eps * at
    msep = math.sqrt(2 / (G - 1) * ((pc / psep) ** ((G - 1) / G) - 1))
    es = min(max(area_ratio(msep), 1.0), eps)
    cf = cf_mom(psep / pc) + (psep - pa) / pc * es - K_REC * (pa - psep) / pc * (eps - es)
    return max(pc * at * cf, 0.0)


throat = float(sys.argv[3])
At = math.pi / 4 * throat**2
cache = {}


def nozzle(engine):
    if id(engine) not in cache:
        eps = engine._exit_area_m2 / At
        me = brentq(lambda m: area_ratio(m) - eps, 1 + 1e-9, 20)
        tau = (1 + (G - 1) / 2 * me * me) ** (-G / (G - 1))
        p0 = engine._reference_pressure_pa
        pc = [brentq(lambda p: thrust(p, p0, At, eps, tau) - f, p0, 3e7) if f > 0 else p0 for f in engine.thrusts]
        cache[id(engine)] = eps, tau, np.array(pc)
    return cache[id(engine)]


def get_thrust(self, time, ambient_pressure):
    burn = time - self._ignition_s
    if not self.times[0] <= burn <= self.times[-1]:
        return 0.0
    eps, tau, pc = nozzle(self)
    return thrust(float(np.interp(burn, self.times, pc)), ambient_pressure, At, eps, tau)


SolidEngine.get_thrust = get_thrust
sys.argv = sys.argv[:3]
runpy.run_path(str(Path(__file__).with_name("fs_worker.py")), run_name="__main__")
