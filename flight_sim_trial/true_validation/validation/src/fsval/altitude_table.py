"""Add-on: replace FS's sea-level drag table with RAS's table at a mid-ascent altitude (no FS change).
Drag rises with altitude in RAS (lower Reynolds number), so a table taken at about half the apogee stands in for it.
shortcut: one altitude per flight, not a Mach-altitude surface; upgrade to the Reynolds correction once it has a real CxViscous."""
import json

from . import RAS_VENDOR, ROOT, aero, cdx1, eng, fsrun
from .ras import Ras
from .units import FT


def main() -> None:
    ras = Ras()
    res = json.loads((ROOT / "results" / "ras_cases.json").read_text())
    for r in res:
        if "fs_plain_ft" not in r:
            continue
        f = RAS_VENDOR / "examples" / f"{r['case']}.CDX1"
        d = cdx1.read(f)
        run = ROOT / "results" / "ras_cases" / r["case"].replace(" ", "_")
        ras.load(f, r["case"])
        mid = d.site.get("Altitude", 0) + 0.5 * r["ras_ft"]
        tbl = ras.aero(r["case"], d.nozzle_in, run / "ras_aero_mid.csv", altitude_ft=mid)
        aero.to_fs_table(tbl, run / "aero_mid.csv", d.ref_diameter_m)
        sim = fsrun.build(d, eng.find(d.engine), run / "fs_mid", reynolds=False)
        (run / "fs_mid" / "aero.csv").write_bytes((run / "aero_mid.csv").read_bytes())
        r["fs_mid_ft"] = fsrun.fly(sim)["apogee_agl_m"] / FT
        e = lambda k: 100 * (r[k] - r["truth_ft"]) / r["truth_ft"]
        print(f"{r['case'][:26]:26} truth {r['truth_ft']:7.0f} RAS {e('ras_ft'):+5.1f}% plain {e('fs_plain_ft'):+5.1f}% mid {e('fs_mid_ft'):+5.1f}%")
    (ROOT / "results" / "ras_cases.json").write_text(json.dumps(res, indent=1))
    ras.close()


if __name__ == "__main__":
    main()
