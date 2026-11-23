"""First pass: for every single-stage RASAero example with a measured apogee, fly RAS and FS."""
import json
import sys
from pathlib import Path

from . import RAS_VENDOR, ROOT
from functools import partial

from . import aero, cdx1, eng, fsrun, viscous
from .ras import Ras
from .units import FT


def main(only: list[str]) -> None:
    ras = Ras()
    results = []
    for f in sorted((RAS_VENDOR / "examples").glob("*.CDX1")):
        if only and f.stem not in only:
            continue
        d = cdx1.read(f)
        if d.n_stages != 1 or d.truth_ft is None:
            print("skip", f.stem, d.n_stages, d.truth_ft)
            continue
        run = ROOT / "results" / "ras_cases" / f.stem.replace(" ", "_")
        try:
            ras.load(f, f.stem)
            row = ras.fly(f.stem)
            tbl = ras.aero(f.stem, d.nozzle_in, run / "ras_aero.csv")
        except Exception as e:  # noqa: BLE001
            print("RAS fail", f.stem, str(e)[:120]); continue
        res = {"case": f.stem, "truth_ft": d.truth_ft, "truth_note": d.truth_note, "ras_ft": row["max_alt_ft"],
               "ras_vmax_fps": row["max_vel_fps"], "ras_t_ap": row["t_apogee_s"], "wind_mph": d.site.get("WindSpeed", 0)}
        try:
            m = eng.find(d.engine)
            vis = partial(viscous.cx_viscous, ras, f.stem, d.nozzle_in, run / "scan")
            aero.to_fs_table(tbl, run / "aero_plain.csv", d.ref_diameter_m)
            aero.to_fs_table(tbl, run / "aero_re.csv", d.ref_diameter_m, vis)
            for tag, rey in (("fs", True), ("fs_plain", False)):
                sim = fsrun.build(d, m, run / tag, reynolds=rey)
                (run / tag / "aero.csv").write_bytes((run / ("aero_re.csv" if rey else "aero_plain.csv")).read_bytes())
                o = fsrun.fly(sim)
                res[f"{tag}_ft"] = o["apogee_agl_m"] / FT
                res[f"{tag}_vmax_fps"] = o["vmax_m_s"] / FT
                res[f"{tag}_t_ap"] = o["t_apogee_s"]
        except Exception as e:  # noqa: BLE001
            res["fs_error"] = str(e)[-300:]
        results.append(res)
        print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in res.items() if k != "truth_note"}))
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "ras_cases.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
