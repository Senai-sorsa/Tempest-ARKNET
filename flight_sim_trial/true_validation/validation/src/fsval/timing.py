"""Time per flight, one at a time on an idle machine, for the same 38 flights: RAS, FS (its frozen setup) and RocketPy helped. Plain RocketPy times itself in fsval.rpy.
FS refreezes its own matrix run, so the apogee is also a check that it reproduces. Writes results/timing.json. Usage: python -m fsval.timing"""
import json
import time
import warnings

import numpy as np

from . import RAS_VENDOR, ROOT, final_score, fsrun, matrix, rpy_helped
from .ras import Ras
from .units import FT


def main() -> None:
    warnings.filterwarnings("ignore")
    dev, held = matrix.flights()
    jobs, maps = matrix.plan(dev + held)
    real = {a: t for a, b, t in maps if b == matrix.tag(final_score.FROZEN)}
    ras = Ras()
    ras.call(op="motors", files=[str(RAS_VENDOR / "rasp.eng"), str(ROOT / "results" / "extra" / "designs" / "rocketpy.eng")])
    out = {}
    for r in dev + held:
        c = r["case"]
        ras.load(matrix.cdx_path(c), c)
        t = time.perf_counter()
        ras.fly(c)
        o = {"ras_s": time.perf_counter() - t}
        fs = ROOT / "results" / "matrix" / c.replace(" ", "_") / real[c] / "fs.json"
        old = json.loads(fs.read_text())["apogee_agl_m"]
        fs.unlink()
        t = time.perf_counter()
        ft = matrix.fly_one(jobs[(c, real[c])])["ft"]
        o["fs_s"] = time.perf_counter() - t
        assert abs(ft * FT / old - 1) < 1e-9, (c, ft * FT, old)
        t = time.perf_counter()
        rpy_helped.fly(c)
        o["rpy_helped_s"] = time.perf_counter() - t
        out[c] = o
        print(c, {k: round(v, 2) for k, v in o.items()}, flush=True)
    ras.close()
    t = time.perf_counter()
    fsrun._local.server.kill()
    fsrun._local.server.wait()
    c = dev[0]["case"]
    fs = ROOT / "results" / "matrix" / c.replace(" ", "_") / real[c] / "fs.json"
    fs.unlink()
    t = time.perf_counter()
    matrix.fly_one(jobs[(c, real[c])])
    cold = time.perf_counter() - t
    for k in ("ras_s", "fs_s", "rpy_helped_s"):
        v = np.array([o[k] for o in out.values()])
        print(f"{k:14} total {v.sum():8.1f} s  median {np.median(v):7.3f}  max {v.max():7.2f}")
    print("FS with a fresh process, one flight", round(cold, 2), "s", flush=True)
    (ROOT / "results" / "timing.json").write_text(json.dumps({"flights": out, "fs_cold_s": cold}, indent=1))


if __name__ == "__main__":
    main()
