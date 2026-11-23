"""Score the matrix by how far each flight can be trusted. Run after fsval.matrix and fsval.weather_run score.

A flight's tier comes only from how its apogee was measured and what motor it flew, as its file states, never from its error:
A: pressure or GPS truth with no recorded disagreement, certified motor. B: one recorded doubt (sensors over 5 % apart, or an
experimental motor). C: truth inferred from integrated acceleration or an optical track.
Combos are never picked on the flights they are scored on: the picked line is the best on every flight outside the slice.
shortcut: A holds mostly one-altimeter flights, which is the file's whole record of them; upgrade if raw altimeter logs turn up."""
import json
import re

import numpy as np

from . import RAS_VENDOR, ROOT, cdx1
from .matrix import FACTORS, combos, tag

FIXED = "surface_re2_po1_w0_linear_fc"  # the setup the weather run used, chosen before any tier existed
INFERRED = {"Qu8k": "accelerometer", "Proteus6": "accelerometer", "Full Metal Jacket1": "optical", "Full Metal Jacket2": "optical", "L500Roc": "optical"}
PAIR_DISAGREE = {"CancerDescending", "IonDrive"}  # 6400/5975 and 8302/7752 ft
CROSS_CHECKED = {"DontDebateThisN5800MinDia", "Kinsel_P4935_A-601_Rocket"}  # two sensors within 2 %: 56504/56641, GPS 42771/baro 42231
HIGH_FT = 20000
BOOT = 10000


def truth_class(case: str) -> str:
    if case in INFERRED:
        return INFERRED[case]
    return "pair disagrees" if case in PAIR_DISAGREE else "cross-checked" if case in CROSS_CHECKED else "one altimeter"


def motor_class(engine: str) -> str:
    maker = re.search(r"\((.+)\)", engine).group(1)
    return "experimental" if maker.endswith("EX") else "historic" if maker == "Hist" else "commercial"


def tier(case: str, engine: str) -> str:
    if case in INFERRED:
        return "C"
    return "B" if case in PAIR_DISAGREE or motor_class(engine) != "commercial" else "A"


def gap_ci(fs: np.ndarray, ras: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """Mean |FS error| less mean |RAS error|, with a bootstrap 95 % interval over flights; negative means FS is closer."""
    gap = abs(fs) - abs(ras)
    means = rng.choice(gap, (BOOT, gap.size)).mean(axis=1)
    return float(gap.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    base = {r["case"]: r for r in json.loads((ROOT / "results" / "ras_cases.json").read_text())}
    cases = sorted(base)
    engine = {c: cdx1.read(RAS_VENDOR / "examples" / f"{c}.CDX1").engine for c in cases}
    truth = np.array([base[c]["truth_ft"] for c in cases])
    ras = 100 * (np.array([base[c]["ras_ft"] for c in cases]) / truth - 1)
    physics = [c for c in combos() if not c["g"]]  # g is a diagnostic, not a candidate
    tags = [tag(c) for c in physics]
    index = {t: i for i, t in enumerate(tags)}
    err = np.full((len(tags), len(cases)), np.nan)
    for x in json.loads((ROOT / "results" / "matrix.json").read_text()):
        if x["tag"] in index:
            i = cases.index(x["case"])
            err[index[x["tag"]], i] = 100 * (x["ft"] / truth[i] - 1)
    assert not np.isnan(err).any()
    fixed = err[index[FIXED]]
    rng = np.random.default_rng(0)

    tiers = np.array([tier(c, engine[c]) for c in cases])
    slices = {
        **{f"tier {t}": tiers == t for t in "ABC"},
        "tiers A+B": tiers != "C",
        **{f"truth: {k}": np.array([truth_class(c) == k for c in cases]) for k in ("cross-checked", "one altimeter", "pair disagrees", "accelerometer", "optical")},
        **{f"motor: {k}": np.array([motor_class(engine[c]) == k for c in cases]) for k in ("commercial", "experimental", "historic")},
        f"apogee < {HIGH_FT} ft": truth < HIGH_FT,
        f"apogee >= {HIGH_FT} ft": truth >= HIGH_FT,
        "all": np.ones(len(cases), bool),
    }
    print(f"{'slice':26} {'n':>2}  {'RAS bias/mean/med':>19}  {'FS fixed bias/mean/med':>22}  {'FS-RAS mean [95%]':>23}  {'beat RAS':>8}  picked elsewhere")
    table = {}
    for name, s in slices.items():
        gap, lo, hi = gap_ci(fixed[s], ras[s], rng)
        beat = float((abs(err[:, s]).mean(axis=1) < abs(ras[s]).mean()).mean())
        picked = None if s.all() else int(np.argmin(abs(err[:, ~s]).mean(axis=1)))
        line = "" if picked is None else f"{abs(err[picked, s]).mean():5.2f} {tags[picked]}"
        print(f"{name:26} {s.sum():2}  {ras[s].mean():+6.2f} {abs(ras[s]).mean():5.2f} {np.median(abs(ras[s])):5.2f}  "
              f"{fixed[s].mean():+6.2f} {abs(fixed[s]).mean():5.2f} {np.median(abs(fixed[s])):5.2f}  {gap:+6.2f} [{lo:+6.2f},{hi:+6.2f}]  {100 * beat:6.0f} %  {line}")
        table[name] = {"cases": [c for c, x in zip(cases, s) if x], "gap": gap, "ci": [lo, hi], "beat": beat}

    print("\nmain effect on mean |err| by tier (pct pts, averaged over the other factors)")
    for f, levels in FACTORS.items():
        if f != "g":
            for lv in levels[1:]:
                row = []
                for t in "ABC":
                    s = tiers == t
                    on = np.array([abs(err[i, s]).mean() for i, c in enumerate(physics) if c[f] == lv])
                    off = np.array([abs(err[i, s]).mean() for i, c in enumerate(physics) if c[f] == levels[0]])
                    row.append(f"{t} {(on - off).mean():+5.2f}")
                print(f"  {f} {levels[0]} -> {lv}: " + "  ".join(row))

    scores = json.loads((ROOT / "results" / "weather" / "scores.json").read_text())
    print("\nthe 10 flights with known air, raw truth: bias / mean |err|")
    for t in ("A", "B", "C", "ABC"):
        names = [c for c in scores["raw|air_wind"] if tier(c, engine[c]) in t]
        cols = []
        for v in ("ras_filed", "filed", "air_wind"):
            e = np.array([scores[f"raw|{v}"][c] for c in names])
            cols.append(f"{v} {e.mean():+6.2f} {abs(e).mean():5.2f}")
        print(f"  tier {t:3} n {len(names):2}  " + "  ".join(cols))

    print("\nby flight, % error: RAS, FS fixed")
    for i in np.lexsort((truth, tiers)):
        print(f"  {tiers[i]} {cases[i][:26]:26} {truth_class(cases[i]):14} {motor_class(engine[cases[i]]):12} {truth[i]:7.0f} ft  {ras[i]:+6.1f} {fixed[i]:+6.1f}")
    (ROOT / "results" / "tiers.json").write_text(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
