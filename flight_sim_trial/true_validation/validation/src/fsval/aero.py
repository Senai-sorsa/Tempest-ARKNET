"""RASAero aero-plot CSV -> flight_sim aero table (+ the CxViscous column FS's Reynolds correction reads)."""
import csv
from pathlib import Path

import numpy as np

from .units import IN


def to_fs_table(ras_csv: Path, out: Path, ref_diameter_m: float, viscous=None) -> None:
    """Axisymmetric missile-frame table about the nose tip: Cx=-CA, Cz=-CN, xCP=-CP/d (calibers aft of the nose).

    `viscous(machs)`, if given, fills the CxViscous column of the alpha-0 rows.
    """
    rows = list(csv.DictReader(ras_csv.open()))
    alphas = sorted({float(r["Alpha"]) for r in rows})
    by = {(float(r["Mach"]), float(r["Alpha"])): r for r in rows}
    machs = sorted({m for m, _ in by})
    vis = dict(zip([0.0, *machs], viscous(np.array([0.0, *machs]).clip(min=machs[0])))) if viscous else None
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Mach", "Alpha", "Phi", "Cx", "Cy", "Cz", "CMx", "xCP", "CxPowerOn", "CxViscous"])
        for m in [0.0, *machs]:
            for a in alphas:
                r = by[(max(m, machs[0]), a)]
                # CP at alpha 0 is the limit as alpha -> 0, which RASAero prints in the 0-4 deg column
                cp = float(r["CP (0 to 4 deg)"] if a == 0 else r["CP"])
                for phi in (0, 360):
                    w.writerow([f"{m:.2f}", f"{a:g}", phi, f"{-float(r['CA Power-Off']):.6f}", 0,
                                f"{-float(r['CN']):.6f}", 0, f"{-cp * IN / ref_diameter_m:.5f}",
                                f"{-float(r['CA Power-On']):.6f}", f"{vis[m] if a == 0 and vis else ''}"])
