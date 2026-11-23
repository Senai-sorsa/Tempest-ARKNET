"""Score apogee predictions against measured truth; also check the headless RAS against each file's own stated prediction."""
import json
import re
import sys
from statistics import median

import numpy as np
from scipy import stats

from . import RAS_VENDOR, ROOT, cdx1

VARIANTS = ("ras", "fs_plain", "fs", "rpy")  # fs = with the Reynolds correction derived from RAS scans


def load() -> list[dict]:
    rows = json.loads((ROOT / "results" / "ras_cases.json").read_text())
    for r in rows:
        d = cdx1.read(RAS_VENDOR / "examples" / f"{r['case']}.CDX1")
        m = re.search(r"RASAero II Prediction\s*=\s*([\d,]+)\s*ft", d.comments)
        r["file_ras_ft"] = float(m.group(1).replace(",", "")) if m else None
        for v in VARIANTS:
            if f"{v}_ft" in r:
                r[f"{v}_err"] = 100 * (r[f"{v}_ft"] - r["truth_ft"]) / r["truth_ft"]
    return [r for r in rows if "fs_ft" in r and "rpy_ft" in r]


def summarize(rows: list[dict], label: str) -> dict:
    out = {"label": label, "n": len(rows)}
    for v in VARIANTS:
        e = np.array([r[f"{v}_err"] for r in rows])
        out[v] = {"median_abs": float(np.median(abs(e))), "mean_abs": float(abs(e).mean()), "bias": float(e.mean()),
                  "within5": int((abs(e) <= 5).sum()), "within10": int((abs(e) <= 10).sum())}
    for v in ("fs_plain", "fs", "rpy"):
        a = np.array([abs(r[f"{v}_err"]) for r in rows]); b = np.array([abs(r["ras_err"]) for r in rows])
        out[f"{v}_vs_ras"] = {"fs_closer": int((a < b).sum()), "ras_closer": int((a > b).sum()),
                              "wilcoxon_p": float(stats.wilcoxon(a, b).pvalue) if len(a) > 5 and (a != b).any() else None,
                              "mean_diff_abs_pct_points": float((a - b).mean())}
    return out


def main() -> None:
    rows = load()
    bad = [(r["case"], r["ras_ft"], r["file_ras_ft"]) for r in rows if r["file_ras_ft"] and abs(r["ras_ft"] / r["file_ras_ft"] - 1) > 0.005]
    print("host vs file-stated RAS prediction off by >0.5%:", bad)
    sets = {"all": rows, "no_wind": [r for r in rows if r["wind_mph"] == 0]}
    res = [summarize(s, k) for k, s in sets.items()]
    (ROOT / "results" / "scores.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
