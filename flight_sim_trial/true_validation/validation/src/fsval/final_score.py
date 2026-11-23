"""Final scores: RASAero II, RocketPy and FS against measured apogee, from matrix.json, matrix_heldout.json and rpy_ft. Flies nothing.
The setup was frozen before this matrix (FROZEN). Selection reads the development flights only; held-out flights have been seen before, so they are reported, not used.
g on is a diagnostic, so it is out of the ranking. Usage: python -m fsval.final_score"""
import json

import numpy as np

from . import ROOT
from .matrix import FACTORS, flights, tag

FROZEN = {"table": "sea", "re": 2, "po": 1, "wind": 0, "nozzle": "linear", "g": 0, "fincan": 1}
BOOT = 20000
HIGH_FT = 20000


def errors(ft: dict, truth: dict) -> np.ndarray:
    return np.array([100 * (ft[c] / truth[c] - 1) for c in truth])


def stats(e: np.ndarray) -> dict:
    return {"mean_abs": float(abs(e).mean()), "median_abs": float(np.median(abs(e))), "bias": float(e.mean())}


def paired_ci(a: np.ndarray, b: np.ndarray, seed: int = 1) -> list[float]:
    """95 % bootstrap interval on mean |a| - mean |b|, over flights."""
    d = abs(a) - abs(b)
    picks = np.random.default_rng(seed).integers(0, len(d), (BOOT, len(d)))
    return [float(x) for x in np.percentile(d[picks].mean(axis=1), [2.5, 97.5])]


def leave_one_out(abs_err: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """abs_err is setups by flights. Each flight is scored on the setup that did best on all the others, so picking a setup cannot flatter it."""
    total = abs_err.sum(axis=1)
    picks = [int(np.argmin(total - abs_err[:, j])) for j in range(abs_err.shape[1])]
    return abs_err[picks, range(abs_err.shape[1])], picks


def main() -> None:
    dev, held = flights()
    helped = json.loads((ROOT / "results" / "rpy_helped.json").read_text())
    cells = {}
    for name in ("matrix.json", "matrix_heldout.json"):
        for row in json.loads((ROOT / "results" / name).read_text()):
            cells.setdefault(row["tag"], {})[row["case"]] = row["ft"]
    out = {"frozen": tag(FROZEN), "sets": {}}
    high = [r for r in dev if r["truth_ft"] >= HIGH_FT]
    for label, rows in (("dev 23", dev), (f"dev >= {HIGH_FT} ft", high), ("held-out 15", held), ("all 38", dev + held)):
        truth = {r["case"]: r["truth_ft"] for r in rows}
        e = {"RAS": errors({r["case"]: r["ras_ft"] for r in rows}, truth), "RocketPy plain": errors({r["case"]: r["rpy_ft"] for r in rows}, truth),
             "RocketPy helped": errors({r["case"]: helped[r["case"]]["rpy_ft"] for r in rows}, truth), "FS frozen": errors(cells[tag(FROZEN)], truth), "FS no Reynolds": errors(cells[tag({**FROZEN, "re": 0})], truth)}
        s = out["sets"][label] = {k: stats(v) for k, v in e.items()}
        fs = e["FS frozen"]
        s["FS closer than RAS"], s["FS closer than RocketPy"] = int((abs(fs) < abs(e["RAS"])).sum()), int((abs(fs) < abs(e["RocketPy plain"])).sum())
        s["FS - RAS CI"], s["FS - RocketPy CI"] = paired_ci(fs, e["RAS"]), paired_ci(fs, e["RocketPy plain"])
        print(f"\n{label} (n {len(rows)})")
        for k, v in e.items():
            print(f"  {k:16} mean {abs(v).mean():6.2f}  median {np.median(abs(v)):6.2f}  bias {v.mean():+6.2f}")
        print(f"  FS closer: {s['FS closer than RAS']} vs RAS, {s['FS closer than RocketPy']} vs plain RocketPy; mean |err| FS-RAS CI {s['FS - RAS CI'][0]:+.2f} {s['FS - RAS CI'][1]:+.2f}, FS-RocketPy CI {s['FS - RocketPy CI'][0]:+.2f} {s['FS - RocketPy CI'][1]:+.2f}")
    truth_d, truth_h = ({r["case"]: r["truth_ft"] for r in rows} for rows in (dev, held))
    mean = lambda t, truth: float(abs(errors(cells[t], truth)).mean())  # noqa: E731
    print("\none factor changed from the frozen setup (mean |err| %, dev then held-out)")
    print(f"  {'frozen':24} {mean(tag(FROZEN), truth_d):6.2f} {mean(tag(FROZEN), truth_h):6.2f}")
    out["one_change"] = {}
    for f, levels in FACTORS.items():
        for v in levels:
            if v != FROZEN[f]:
                t = tag({**FROZEN, f: v})
                out["one_change"][f"{f}={v}"] = [mean(t, truth_d), mean(t, truth_h)]
                print(f"  {f + '=' + str(v):24} {mean(t, truth_d):6.2f} {mean(t, truth_h):6.2f}")
    ranked = sorted((t for t in cells if "_gras" not in t and not t.startswith("surface_re0")), key=lambda t: mean(t, truth_d))  # a surface run ignores re
    out["best_on_dev"] = [[t, mean(t, truth_d), mean(t, truth_h)] for t in ranked[:5]]
    print("\nbest on dev, g off (dev, then held-out, which played no part)")
    for t, a, b in out["best_on_dev"]:
        print(f"  {t:36} {a:6.2f} {b:6.2f}")
    abs_err = abs(np.array([errors(cells[t], truth_d) for t in ranked]))
    loo, picks = leave_one_out(abs_err)
    frozen = abs_err[ranked.index(tag(FROZEN))]
    out["leave_one_out"] = {"picked": float(loo.mean()), "frozen": float(frozen.mean()), "setups": sorted({ranked[i] for i in picks}), "ci": paired_ci(loo, frozen)}
    print(f"\nleave-one-flight-out on dev: picking the best setup {loo.mean():.2f}, frozen {frozen.mean():.2f}, CI {out['leave_one_out']['ci'][0]:+.2f} {out['leave_one_out']['ci'][1]:+.2f}; picked {out['leave_one_out']['setups']}")
    (ROOT / "results" / "final_scores.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
