"""A-3 follow-up: at which post-processing stage does the tool lose the co-extremes of strong 10 m wind and strong 10 m - 1 km shear? (ERA5 has them together 0.22-0.51 of the
time at q95 in 3 of 4 cases, the pools 0.02-0.17; scripts/a3_coextremes.py.) Same cases and statistic; the tool's post-processing stack is switched stage by stage by removing keys
from the loaded assets' post dict (in memory only): full (shuffle + shear map + lapse map), no lapse map, no shear map and no lapse map, no shuffle at all (raw calibrated network).
    PYTHONPATH=. .venv/Scripts/python -W ignore scripts/a3_stage_audit.py
"""
import copy
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
from a3_coextremes import CASES, coext   # noqa: E402
from tempest_weather import api   # noqa: E402


def main():
    A = api._assets()
    full = A["post"]
    variants = {"full stack": full, "no lapse map": {k: v for k, v in full.items() if k != "lmap"},
                "shuffle only": {k: v for k, v in full.items() if k not in ("lmap", "smap")},
                "no shuffle (network + range map)": {k: v for k, v in full.items() if k not in ("lmap", "smap", "rank", "tpl")}}
    print("case                 " + "  ".join(f"{k:>32s}" for k in variants))
    for mo, hh, lat, lon in CASES:
        row = []
        for name, post in variants.items():
            A["post"] = post
            try:
                atm, _ = api.atmosphere_set(lat, lon, f"2025-{mo:02d}-15T{hh:02d}:00:00+00:00", n=4000, seed=mo)
            finally:
                A["post"] = full
            row.append(coext(atm["u"], atm["v"]))
        print(f"  month {mo:2d} {hh:2d}Z {lat:.1f},{lon:.1f}  " + "  ".join(f"{x:32.2f}" for x in row))


if __name__ == "__main__":
    main()
