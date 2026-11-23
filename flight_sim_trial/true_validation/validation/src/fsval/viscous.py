"""CxViscous for FS's ReynoldsCorrection, measured from RASAero itself.

RAS skin friction depends on Reynolds number, so at a low fixed Mach (no wave drag) a scan over altitude
traces CA against Reynolds number. FS wants the viscous Cx as a function of the Mach that would give the same
Reynolds number in sea-level air; only differences of it are used, so the constant (inviscid) part never matters.
"""
import csv
import math
from pathlib import Path

import numpy as np

import os
SCAN_MACH = float(os.environ.get("FSVAL_SCAN_MACH", 0.5))
SCAN_ALTS_FT = (0, 10000, 20000, 30000, 40000, 60000, 80000)  # 100000 ft turns laminar: CA rises again


def _rho_a_over_mu(h_m: float) -> float:
    t = 288.15 - 0.0065 * h_m if h_m < 11000 else 216.65
    p = 101325 * (t / 288.15) ** 5.2559 if h_m < 11000 else 22632 * math.exp(-9.80665 * (h_m - 11000) / (287.05 * t))
    mu = 1.458e-6 * t**1.5 / (t + 110.4)
    return p / (287.05 * t) * math.sqrt(1.4 * 287.05 * t) / mu


def cx_viscous(ras, key: str, nozzle_in: float, workdir: Path, machs: np.ndarray) -> np.ndarray:
    """Positive viscous-drag value at each sea-level-equivalent Mach in `machs` (differences are what count)."""
    workdir.mkdir(parents=True, exist_ok=True)
    ms, ca = [], []
    for h in SCAN_ALTS_FT:
        out = ras.aero(key, nozzle_in, (workdir / f"scan_{h}.csv").resolve(), altitude_ft=h, mach_max=max(1.0, SCAN_MACH + 0.5))
        row = next(r for r in csv.DictReader(out.open()) if float(r["Alpha"]) == 0 and abs(float(r["Mach"]) - SCAN_MACH) < 1e-6)
        ms.append(SCAN_MACH * _rho_a_over_mu(h * 0.3048) / _rho_a_over_mu(0.0))
        ca.append(float(row["CA Power-Off"]))
    order = np.argsort(ms)
    ms, ca = np.array(ms)[order], np.array(ca)[order]
    ca = np.minimum.accumulate(ca) - 1e-9 * np.arange(len(ca))  # strictly falling with Reynolds number, as FS requires
    top = ms[-1]
    slope = np.polyfit(np.log(ms[-3:]), ca[-3:], 1)[0]  # CA per ln(m) over the three highest-Re rows
    out = np.interp(np.log(machs), np.log(ms), ca)
    above = machs > top
    out[above] = ca[-1] + slope * np.log(machs[above] / top)  # shortcut: scan stops at Re(M0.5, sea level); log-linear beyond
    return out
