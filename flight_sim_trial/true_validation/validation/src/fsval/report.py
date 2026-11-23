"""Write REPORT.md and REPORT.html from results/ras_cases.json and results/scores.json."""
import html
import json

from . import ROOT, score

V = (("ras", "RASAero II 1.0.2.0"), ("fs_plain", "FS (RAS aero, sea-level table)"), ("fs", "FS + Reynolds correction*"), ("rpy", "RocketPy 1.13"))
CAVEATS = """\
- All four engines are fed **RASAero's own aero** (CA, CN, CP). The comparison tests flight dynamics, atmosphere, thrust and mass handling, not aerodynamic prediction. FS has no aero solver, so it cannot be tested on drag prediction alone.
- The 23 flights are RASAero's own validation set, with the RAS predictions published by its author. That favours RAS (possible post-flight input tuning; the headless engine reproduces each file's stated prediction within 0.5 %, so those are RAS's numbers).
- Truth is the apogee written in each file's comments: sensors differ (baro, accelerometer-integrated, GPS, optical); error bars of a few percent are plausible. Truth is assumed AGL.
- Inferred inputs (same for FS and RocketPy, not in the files): latitude 35 deg, rocket inertia (slender rod), motor flush with the base, FS dry mass = launch weight - motor total mass. RocketPy ignores site temperature and wind (stock ISA); FS uses site temperature and uniform wind; RAS uses its own.
- *The Reynolds correction's CxViscous is my own construction from RAS altitude scans at Mach 0.5, log-extrapolated above Reynolds(M0.5); it over-corrects very high flights (Qu8k, Proteus 6). Treat as a diagnostic, not as FS's validated mode.
- Designs were not chosen using truth, but this protocol was written after a first pass over all 23 flights; no flights were dropped. Small sample: Wilcoxon p-values are indicative only. Two-stage (AeroPac 104K) and `.alx1`-only files excluded.
"""


def build() -> None:
    rows = score.load()
    sc = json.loads((ROOT / "results" / "scores.json").read_text())
    off = [r for r in rows if abs(r["fs_plain_ft"] / r["ras_ft"] - 1) > 0.02]
    near = sum(abs(r["fs_plain_ft"] / r["ras_ft"] - 1) <= 0.01 for r in rows)
    far = (f"It departs from RAS by more than 2 % on {len(off)}: " + ", ".join(
        f"{r['case']} ({'FS' if abs(r['fs_plain_err']) < abs(r['ras_err']) else 'RAS'} closer)" for r in off) + ".")
    md = ["# FS vs RASAero II vs RocketPy vs measured apogees", "",
          "Branch JARVIS-TRUE-VALIDATION. Flight simulator code untouched; harness in `validation/`.", "", "## Verdict", "",
          "On these 23 flights **FS is not more accurate than RASAero II**: it is statistically indistinguishable from RocketPy and slightly behind RAS. "
          f"Given RAS's aero, FS lands within 1 % of RAS on {near} of {len(rows)} flights. {far}", "",
          "## Summary (signed apogee error vs measured, %)", "",
          "| set | n | " + " | ".join(f"{n} median / mean abs, bias, within 5%" for _, n in V) + " |", "|---|---|" + "---|" * len(V)]
    for s in sc:
        md.append(f"| {s['label']} | {s['n']} | " + " | ".join(
            f"{s[k]['median_abs']:.1f} / {s[k]['mean_abs']:.1f}, {s[k]['bias']:+.1f}, {s[k]['within5']}" for k, _ in V) + " |")
    md += ["", "Paired against RAS (|err| smaller = closer): " + "; ".join(
        f"{n}: closer on {s[f'{k}_vs_ras']['fs_closer']} of {s['n']}, Wilcoxon p={s[f'{k}_vs_ras']['wilcoxon_p']:.2f} ({s['label']})"
        for s in sc for k, n in V[1:]), "", "## Per flight (apogee ft AGL; error % vs truth)", "",
          "| flight | truth | wind mph | " + " | ".join(n for _, n in V) + " |", "|---|---|---|" + "---|" * len(V)]
    for r in sorted(rows, key=lambda r: r["truth_ft"]):
        md.append(f"| {r['case']} | {r['truth_ft']:.0f} | {r['wind_mph']:.0f} | " + " | ".join(
            f"{r[k + '_ft']:.0f} ({r[k + '_err']:+.1f}%)" for k, _ in V) + " |")
    md += ["", "## Caveats", "", CAVEATS, "## Reproduce", "",
           "`PYTHONPATH=src .venv/Scripts/python.exe -m fsval.run_ras_cases && -m fsval.rpy && -m fsval.score && -m fsval.report` from `validation/` "
           "(needs the RPA headless RAS under `~/Rocket-Profile-Analysis` and FS's own venv)."]
    text = "\n".join(md) + "\n"
    (ROOT / "REPORT.md").write_text(text)
    body = html.escape(text)
    (ROOT / "REPORT.html").write_text(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>FS validation</title>"
        "<style>:root{color-scheme:light dark}body{font:15px/1.5 system-ui;margin:1rem auto;max-width:70rem;padding:0 16px}"
        "pre{white-space:pre-wrap;overflow-x:auto}</style><pre>" + body + "</pre>")


if __name__ == "__main__":
    build()
