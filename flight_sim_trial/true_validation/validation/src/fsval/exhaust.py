"""Nozzle and exhaust estimates PowerOnBaseDrag needs, for every flight. Flies nothing. Writes results/exhaust_estimates.json.
Throat: the Isp-based estimate of fsval.throat where it solved; otherwise thrust = Pc At CF at an assumed peak Pc, with Pc following thrust.
Exit: the CDX1's where given; otherwise a typical expansion ratio. No published throat or exit was found for any of these motors.
shortcut: one throat per motor, so a multi-hole nozzle such as the K550W's is treated as a single jet; upgrade with measured nozzles."""
import json
import math

import numpy as np

from . import RAS_VENDOR, ROOT, cdx1, eng
from .throat import PA, cf_ideal
from .units import IN

GAMMA = 1.22  # PowerOnBaseDrag's default, and about 1.2 in the worked solid-motor examples found
PSI = 6894.757
PEAK_PC_PSI = (500.0, 1000.0, 1250.0)  # middle and top: forum figures for Pro75-class motors; bottom: near the Isp-based estimates
EPS_TYPICAL = 5.6  # geometric middle of the 4.2 and 7.55 found for hobby-sized nozzles
THROAT_KEY = "c*1500_g1.22"


def from_pressure(f_avg: float, f_max: float, peak_pc: float, exit_area: float, g: float) -> dict | None:
    """Throat and exit for this thrust at a peak Pc; None if the given exit is too small to expand the flow."""
    pc = peak_pc * f_avg / f_max
    if exit_area:
        at = f_avg / (pc * 1.4)
        for _ in range(30):
            if exit_area / at < 1.05:
                return None
            at = f_avg / (pc * cf_ideal(exit_area / at, pc / PA, g))
    else:
        at = f_avg / (pc * cf_ideal(EPS_TYPICAL, pc / PA, g))
        exit_area = at * EPS_TYPICAL
    return {"throat_mm": 2000 * math.sqrt(at / math.pi), "exit_mm": 2000 * math.sqrt(exit_area / math.pi),
            "eps": exit_area / at, "pc_avg_MPa": pc / 1e6}


def entry(d: cdx1.Design, m: eng.Motor, fitted: dict) -> dict:
    """One flight's estimates; fitted is its throat.motor_estimates, if any."""
    rows = np.array([[float(x) for x in ln.split()[:2]] for ln in m.text.splitlines()[1:] if len(ln.split()) >= 2])
    f_avg = np.trapezoid(rows[:, 1], rows[:, 0]) / (rows[-1, 0] - rows[0, 0])
    exit_area = math.pi * (d.nozzle_in * IN / 2) ** 2
    byp = [from_pressure(f_avg, rows[:, 1].max(), p * PSI, exit_area, GAMMA) for p in PEAK_PC_PSI]
    solved = [b["throat_mm"] for b in byp if b]
    fit = fitted.get("est", {}).get(THROAT_KEY)
    e = {"throat_mm": fit["throat_mm"], "exit_mm": 25.4 * d.nozzle_in, "eps": fit["eps"], "pc_avg_MPa": fit["pc_avg_MPa"]} if fit else byp[1]
    return {**e, "gamma": GAMMA, "base_mm": d.base_m * 1000, "motor": d.engine,
            "throat_source": "isp fit" if fit else "assumed peak Pc", "exit_source": "CDX1" if d.nozzle_in else "typical eps",
            "throat_range_mm": [min(solved), max(solved)]}


def main() -> None:
    fitted = json.loads((ROOT / "results" / "throat_estimates.json").read_text())
    out = {}
    for r in json.loads((ROOT / "results" / "ras_cases.json").read_text()):
        if "fs_plain_ft" not in r:
            continue
        d = cdx1.read(RAS_VENDOR / "examples" / f"{r['case']}.CDX1")
        out[r["case"]] = e = entry(d, eng.find(d.engine), fitted.get(r["case"], {}))
        solved = e["throat_range_mm"]
        if e["exit_mm"] >= d.base_m * 1000:
            print("  EXIT WIDER THAN BASE:", r["case"])
        print(f"{r['case'][:24]:24} {d.engine[:18]:18} throat {e['throat_mm']:6.1f} ({min(solved):.1f}-{max(solved):.1f}) exit {e['exit_mm']:6.1f} eps {e['eps']:5.2f} Pc {e['pc_avg_MPa']:.1f} MPa base {d.base_m * 1000:6.1f}  {out[r['case']]['throat_source']}, {out[r['case']]['exit_source']}")
    (ROOT / "results" / "exhaust_estimates.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
