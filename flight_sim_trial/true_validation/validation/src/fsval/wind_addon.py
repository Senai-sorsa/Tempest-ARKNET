"""Add-on: stated site wind -> height-dependent wind. FS here only has UniformWind, so each flight gets the
altitude-averaged speed of a power-law profile (stated speed taken at 10 m, exponent 1/7, neutral air over open ground)
over the first-pass apogee. Gusts, 3D wind and updrafts have no truth in the files and are not modelled."""
import json
import sys
from pathlib import Path

from . import RAS_VENDOR, ROOT, cdx1, eng, fsrun
from .units import FT, MPH

ALPHA = 1 / 7


def effective_speed(v10: float, top_m: float) -> float:
    """Mean of v10*(h/10)^a over 0..top_m (below 10 m the profile is held at v10)."""
    if top_m <= 10:
        return v10
    return v10 * (10 + 10 ** -ALPHA * (top_m ** (1 + ALPHA) - 10 ** (1 + ALPHA)) / (1 + ALPHA)) / top_m


def main() -> None:
    res = json.loads((ROOT / "results" / "ras_cases.json").read_text())
    for r in res:
        if not r["wind_mph"]:
            continue
        d = cdx1.read(RAS_VENDOR / "examples" / f"{r['case']}.CDX1")
        run = ROOT / "results" / "ras_cases" / r["case"].replace(" ", "_")
        v = effective_speed(d.site["WindSpeed"] * MPH, r["fs_plain_ft"] * FT)
        d.site["WindSpeed"] = v / MPH
        sim = fsrun.build(d, eng.find(d.engine), run / "fs_wind", reynolds=False)
        (run / "fs_wind" / "aero.csv").write_bytes((run / "aero_plain.csv").read_bytes())
        r["fs_wind_ft"] = fsrun.fly(sim)["apogee_agl_m"] / FT
        print(r["case"], "stated", r["wind_mph"], "mph eff", round(d.site["WindSpeed"], 1), "FS plain", round(r["fs_plain_ft"]),
              "FS wind", round(r["fs_wind_ft"]), "truth", round(r["truth_ft"]), "RAS", round(r["ras_ft"]))
    (ROOT / "results" / "ras_cases.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
