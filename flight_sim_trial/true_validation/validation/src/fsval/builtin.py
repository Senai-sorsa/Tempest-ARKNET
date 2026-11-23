"""Fly FS's built-in Reynolds correction on the fixed setup and score it against RAS's own surface and the measured apogees.
Only those flights are flown: the rest of the matrix stays as it is. Usage: python -m fsval.builtin [case ...]"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from . import RAS_VENDOR, ROOT, cdx1, matrix

SETUP = {"table": "sea", "re": 2, "po": 1, "wind": 0, "nozzle": "linear", "g": 0, "fincan": 1}
SURFACE = {**SETUP, "table": "surface", "re": 1}


def main(only: list[str]) -> None:
    res = [r for r in json.loads((ROOT / "results" / "ras_cases.json").read_text()) if "fs_plain_ft" in r and (not only or r["case"] in only)]
    est = json.loads((ROOT / "results" / "throat_estimates.json").read_text())
    exhaust = json.loads((ROOT / "results" / "exhaust_estimates.json").read_text())
    jobs = []
    for r in res:
        d = cdx1.read(RAS_VENDOR / "examples" / f"{r['case']}.CDX1")
        e = est.get(r["case"], {}).get("est", {}).get(matrix.THROAT_KEY)
        throat = e["throat_mm"] / 1000 if e else None
        has_fincan = matrix.fincan_design(d, r["case"]).ref_diameter_m > d.ref_diameter_m
        for c in (SETUP, SURFACE):
            jobs.append((r, matrix.effective(c, bool(r["wind_mph"]), d.nozzle_in, throat, has_fincan), throat, exhaust[r["case"]]))
    with ThreadPoolExecutor(matrix.WORKERS) as pool:
        out = list(pool.map(matrix.fly_one, jobs))
    rows = []
    print(f"{'flight':28} {'truth ft':>9} {'RAS %':>7} {'surface %':>9} {'built-in %':>10} {'built-in - surface %':>21}")
    for r, new, old in zip(res, out[::2], out[1::2]):
        t = r["truth_ft"]
        row = (100 * (r["ras_ft"] / t - 1), 100 * (old["ft"] / t - 1), 100 * (new["ft"] / t - 1), 100 * (new["ft"] / old["ft"] - 1))
        rows.append(row)
        print(f"{r['case'][:28]:28} {t:9.0f} {row[0]:+7.2f} {row[1]:+9.2f} {row[2]:+10.2f} {row[3]:+21.2f}")
    a, high = abs(np.array(rows)), np.array([r["truth_ft"] >= 20000 for r in res])
    for name, s in (("all", np.ones(len(res), bool)), ("high", high)):
        print(f"{name:5} n {s.sum():2}  mean |err| RAS {a[s, 0].mean():.2f} surface {a[s, 1].mean():.2f} built-in {a[s, 2].mean():.2f}; median {np.median(a[s, 0]):.2f} {np.median(a[s, 1]):.2f} {np.median(a[s, 2]):.2f}; built-in vs surface mean {a[s, 3].mean():.2f} max {a[s, 3].max():.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
