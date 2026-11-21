"""IL-175 (2026-11-10): what the tool ACTUALLY ships, one line per item per installed asset set (tempest_weather/assets*), read from the manifests and the bundled arrays, not from the logs.
Run after every export next to scripts/tool_audit.py (checklist B34: a KEEP verdict is not done until the tool serves it). Compare its output with the plan's KEEP lines.
    PYTHONPATH=. python scripts/shipped_check.py [--out docs/results/logs/shipped_check.log]"""
import argparse
import json
import os
from datetime import datetime

import numpy as np

from tempest_weather import api


def describe(path):
    m = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
    z = np.load(os.path.join(path, "model.npz"))
    keys = set(z.files)
    out = [("area", f"lat {m['area']['lat']} lon {m['area']['lon']}"), ("model", f"{m.get('model_source')} trained {m.get('trained_years')} calibration {m.get('calibration_fit')}"),
           ("solar hours", str(m.get("solar_hours", "[6, 21] (old manifest)")))]
    if "post/rank" in keys:
        r = z["post/rank"]
        out.append(("shuffle templates", f"{r.shape[0]} blocks of cell {int(z['post/cell'])}, empty month x 2-h bins {int((r.max(axis=(2, 3)) == 0).sum())} of {r.shape[0] * r.shape[1]}"))
    elif "post/tpl" in keys:
        out.append(("shuffle templates", "pooled (one set for the box)"))
    else:
        out.append(("shuffle templates", "NONE"))
    out += [("shear map", "yes" if "post/smap_grid" in keys else "NONE"), ("lapse map", "yes" if "post/lmap_xk" in keys else "NONE"), ("shear map aloft (AV35)", "yes" if "post/amap_grid" in keys else "NONE"),
            ("forecast mode (F)", ("yes" + (" + ridge" if m.get("modef_ridge_included") else "") + (f", source {m['modef_source']}" if m.get("modef_source") else "")) if m.get("modef_included") else "NONE"),
            ("past mode (P)", ("yes" + (" + station hybrid" if m.get("modep_sta_included") else "") + (" + surface pool" if m.get("modep_sfc_included") else "")) if m.get("modep_included") else "NONE"),
            ("w head", (f"yes ({m.get('head_source') or 'source not recorded: day-trained'})" + (" + range map" if m.get("wcalib_included") else "")) if m.get("head_included") else "NONE"),
            ("gust law", "yes" if m.get("gust_included") else "NONE"),
            ("time / distance correlation", ("time" if m.get("coherence_included") else "-") + " / " + ("distance" if m.get("coherence_dist_included") else "-")),
            ("created", m.get("created"))]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/logs/shipped_check.log")
    a = ap.parse_args()
    lines = [f"shipped check {datetime.now():%Y-%m-%d %H:%M}"]
    for name in sorted(api.regions()):
        lines.append(f"== {name}")
        lines += [f"  {k:30s} {v}" for k, v in describe(os.path.join(os.path.dirname(api.__file__), name))]
    print("\n".join(lines))
    with open(a.out, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    main()
