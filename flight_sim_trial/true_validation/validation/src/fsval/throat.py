"""Estimate nozzle throat area and chamber pressure of each flight's motor from its .eng and the CDX1 exit diameter.

Isp = I/m_prop = c* CF / g0 fixes CF for an assumed c*; CF(eps, Pc/Pa) then fixes eps = Ae/At; Pc(t) = F/(At CF).
No throat or chamber-pressure data is in the files, so c* and gamma are assumptions (ranges below). Ideal nozzle, no loss factors.
shortcut: ideal CF at the burn-average thrust, attached flow; upgrade when real throat sizes are found."""
import json
import math
import sys

import numpy as np
from scipy.optimize import brentq

from . import RAS_VENDOR, ROOT, cdx1, eng
from .units import IN

PA = 101325.0
G0 = 9.80665


def area_ratio(M, g):
    return (2 / (g + 1) * (1 + (g - 1) / 2 * M * M)) ** ((g + 1) / (2 * (g - 1))) / M


def cf_ideal(eps, pc_over_pa, g):
    M = brentq(lambda m: area_ratio(m, g) - eps, 1 + 1e-9, 30)
    tau = (1 + (g - 1) / 2 * M * M) ** (-g / (g - 1))
    mom = math.sqrt(2 * g * g / (g - 1) * (2 / (g + 1)) ** ((g + 1) / (g - 1)) * (1 - tau ** ((g - 1) / g)))
    return mom + (tau - 1 / pc_over_pa) * eps


def estimate(times, thrusts, m_prop, ae, cstar, g):
    imp = np.trapezoid(thrusts, times)
    f_avg, isp = imp / (times[-1] - times[0]), imp / m_prop / G0
    cf_need = isp * G0 / cstar

    def resid(at):
        pc = f_avg / (at * cf_need)  # burn-average chamber pressure at the CF the Isp demands
        return cf_ideal(ae / at, pc / PA, g) - cf_need

    ats = ae / np.geomspace(1.5, 60, 200)
    r = [resid(a) for a in ats]
    for i in range(len(ats) - 1):
        if r[i] * r[i + 1] < 0:
            at = brentq(resid, ats[i], ats[i + 1])
            pc_t = thrusts / (at * cf_need)
            return {"throat_mm": 2000 * math.sqrt(at / math.pi), "eps": ae / at, "pc_avg_MPa": f_avg / (at * cf_need) / 1e6,
                    "pc_max_MPa": float(pc_t.max()) / 1e6, "isp_s": isp, "cf": cf_need}
    return None


def motor_estimates(d: cdx1.Design, m: eng.Motor) -> dict:
    rows = np.array([[float(x) for x in ln.split()[:2]] for ln in m.text.splitlines()[1:] if len(ln.split()) >= 2])
    ae = math.pi * (d.nozzle_in * IN / 2) ** 2
    res = {}
    for cs, g in ((1500, 1.22), (1450, 1.18), (1580, 1.25)):
        res[f"c*{cs}_g{g}"] = estimate(rows[:, 0], rows[:, 1], m.propellant_kg, ae, cs, g)
    return {"motor": d.engine, "exit_in": d.nozzle_in, "est": res}


def main() -> None:
    out = {}
    for f in sorted((RAS_VENDOR / "examples").glob("*.CDX1")):
        d = cdx1.read(f)
        if d.n_stages != 1 or d.truth_ft is None or d.nozzle_in <= 0:
            continue
        out[f.stem] = motor_estimates(d, eng.find(d.engine))
        res = out[f.stem]["est"]
        mid = res["c*1500_g1.22"]
        rng = [v["throat_mm"] for v in res.values() if v]
        print(f"{f.stem[:24]:24} {d.engine[:18]:18} exit {2 * d.nozzle_in * 12.7:5.1f}mm  " +
              (f"Isp {mid['isp_s']:5.1f}s throat {mid['throat_mm']:5.1f}mm (range {min(rng):.1f}-{max(rng):.1f}) eps {mid['eps']:5.2f} Pc avg/max {mid['pc_avg_MPa']:.2f}/{mid['pc_max_MPa']:.2f} MPa" if mid else "no solution"))
    (ROOT / "results" / "throat_estimates.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
