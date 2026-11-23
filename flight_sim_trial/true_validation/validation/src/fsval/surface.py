"""Add-on: RAS's drag at every altitude a flight reaches, as the change in Cx from its sea-level table.
Replaces the one-altitude table and the Reynolds scaling. Writes results/ras_cases/<case>/surface.json. Calls RAS aero only, flies nothing."""
import csv
import json
from pathlib import Path

from . import RAS_VENDOR, ROOT, cdx1
from .ras import Ras

ALTS_FT = (0, 2500, 5000, 10000, 15000, 20000, 30000, 40000, 50000, 60000, 80000, 100000, 120000, 150000, 200000)
MARGIN = 1.15  # past the RAS apogee, as FS may fly higher


def altitudes(top_ft: float) -> list[int]:
    """The grid up to and including the first level above top_ft."""
    above = [h for h in ALTS_FT if h >= top_ft]
    if not above:
        raise ValueError(f"{top_ft:.0f} ft is above the altitude grid")
    return [h for h in ALTS_FT if h <= above[0]]


def zero_alpha_cx(path: Path) -> dict[float, float]:
    return {float(r["Mach"]): -float(r["CA Power-Off"]) for r in csv.DictReader(path.open()) if float(r["Alpha"]) == 0}


def changes(base: dict[float, float], tables: list[dict[float, float]]) -> tuple[list[float], list[list[float]]]:
    """Mach axis and the change in Cx from base, one row per table."""
    machs = sorted(base)
    for t in tables:
        if sorted(t) != machs:
            raise ValueError("RAS tables differ in their Mach grid")
    return machs, [[t[m] - base[m] for m in machs] for t in tables]


def scan(ras: Ras, key: str, d: cdx1.Design, ras_ft: float, run: Path) -> int:
    """Write run/surface.json from RAS at each altitude; the design must be loaded as key."""
    (run / "scan").mkdir(parents=True, exist_ok=True)
    alts = altitudes((d.site.get("Altitude", 0) + ras_ft) * MARGIN)
    tables = [ras.aero(key, d.nozzle_in, (run / "scan" / f"surface_{h}.csv").resolve(), altitude_ft=h) for h in alts]
    machs, dcx = changes(zero_alpha_cx(run / "ras_aero.csv"), [zero_alpha_cx(t) for t in tables])
    if max(map(abs, dcx[0])) > 1e-3:
        raise ValueError(f"{key}: the sea-level table is not the one FS flies")
    (run / "surface.json").write_text(json.dumps({"altitudes_ft": alts, "machs": machs, "dcx": dcx}))
    return alts[-1]


def main() -> None:
    ras = Ras()
    for r in json.loads((ROOT / "results" / "ras_cases.json").read_text()):
        if "fs_plain_ft" not in r:
            continue
        f = RAS_VENDOR / "examples" / f"{r['case']}.CDX1"
        d = cdx1.read(f)
        run = ROOT / "results" / "ras_cases" / r["case"].replace(" ", "_")
        ras.load(f, r["case"])
        print(r["case"], "altitudes up to", scan(ras, r["case"], d, r["ras_ft"], run), flush=True)
    ras.close()


if __name__ == "__main__":
    main()
