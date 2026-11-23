"""Factorial on/off of every add-on over all flights; FS is only run, never edited.
Factors: table (sea|mid|surface), re (0 off, 2 FS's built-in correction; 1 only tags surface runs, and old runs of the CSV correction FS no longer has), po (power-on Cx in burn, or FS's PowerOnBaseDrag model), wind (1/7 law), nozzle (none|linear|kb),
g (RAS's constant gravity: a diagnostic of the FS-RAS gap, not a physics improvement; WGS84 is the better model),
fincan (reference area from the fin can diameter, as RAS uses; a flight without a wider fin can reuses the off run).
Flights a factor cannot touch reuse the equivalent run: no wind -> wind off; no exit size -> nozzle none; no throat estimate -> no kb;
the surface replaces the Reynolds correction -> re on, as the surface works through that hook;
PowerOnBaseDrag needs a nozzle exit, which also adds pressure thrust -> nozzle none becomes linear, on an estimated exit if the file has none.
Resumable: a run with a fs.json is not flown again. Flies the 23 development and the scored held-out flights; matrix.json keeps the 23 so
matrix_score and tiers read as before, matrix_heldout.json has the rest. Usage: python -m fsval.matrix [case ...]"""
import csv
import io
import itertools
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import cache

from . import RAS_VENDOR, ROOT, cdx1, eng, fsrun
from .units import FT, IN, MPH
from .wind_addon import effective_speed

WORKERS = os.cpu_count()  # each flight is its own process, so these threads only wait on them
THROAT_KEY = "c*1500_g1.22"
RAS_G = 9.786  # RASAero II's constant g, recovered from its flight logs
BASE_DRAG = ("ap02", "blend", "ras")
FACTORS = {"table": ("sea", "mid", "surface"), "re": (0, 2), "po": (0, 1, *BASE_DRAG), "wind": (0, 1), "nozzle": ("none", "linear", "kb"), "g": (0, 1), "fincan": (0, 1)}


def combos() -> list[dict]:
    return [dict(zip(FACTORS, c)) for c in itertools.product(*FACTORS.values())]


def tag(c: dict) -> str:
    return f"{c['table']}_re{c['re']}_po{c['po']}_w{c['wind']}_{c['nozzle']}" + ("_gras" if c["g"] else "") + ("_fc" if c["fincan"] else "")  # off keeps the old run names


def effective(c: dict, has_wind: bool, exit_in: float, throat: float | None, has_fincan: bool) -> dict:
    """The run a combo really is on this flight, so duplicates are flown once."""
    nozzle = "none" if not exit_in else c["nozzle"]
    if c["po"] in BASE_DRAG:
        nozzle = "linear" if nozzle == "none" else nozzle
    if nozzle == "kb" and not throat:
        nozzle = "linear"
    return {**c, "wind": c["wind"] if has_wind else 0, "nozzle": nozzle, "re": 1 if c["table"] == "surface" else c["re"], "fincan": c["fincan"] if has_fincan else 0}


def cdx_path(case: str):
    f = RAS_VENDOR / "examples" / f"{case}.CDX1"
    return f if f.exists() else ROOT / "results" / "extra" / "designs" / f"{case}.CDX1"


def src_dir(case: str):
    run = ROOT / "results" / "ras_cases" / case.replace(" ", "_")
    return run if run.exists() else ROOT / "results" / "extra" / case


def flights() -> tuple[list[dict], list[dict]]:
    """Development and held-out flights, with what the matrix reads from each. The @ rows are weight sensitivities, outside the means."""
    dev = [r for r in json.loads((ROOT / "results" / "ras_cases.json").read_text()) if "fs_plain_ft" in r]
    held = [{**r, "fs_plain_ft": r["no_re_ft"], "wind_mph": cdx1.read(cdx_path(r["case"])).site.get("WindSpeed", 0)}
            for r in json.loads((ROOT / "results" / "extra" / "scores.json").read_text()) if "@" not in r["case"]]
    return dev, held


def fincan_design(d: cdx1.Design, case: str) -> cdx1.Design:
    f = cdx_path(case)
    fc = ET.fromstring(f.read_text(encoding="utf-8-sig", errors="replace")).find("RocketDesign/FinCan")
    return replace(d, ref_diameter_m=max(d.ref_diameter_m, float(fc.findtext("Diameter")) * IN)) if fc is not None else d


@cache
def _table_text(path, power_on: bool, calibers: float) -> str:
    """Cached, as thousands of runs share each table and this thread pool shares one interpreter."""
    rows = list(csv.DictReader(open(path, newline="")))
    for r in rows:
        if not power_on:
            r["CxPowerOn"] = r["Cx"]
        if calibers != 1:
            r["xCP"] = f"{float(r['xCP']) * calibers:.5f}"
    f = io.StringIO(newline="")
    w = csv.DictWriter(f, rows[0].keys())
    w.writeheader()
    w.writerows(rows)
    return f.getvalue()


def table(run, c: dict, out, calibers: float = 1.0) -> None:
    """calibers rescales xCP when the flight's reference diameter is not the table's, so the CP stays where it is on the rocket."""
    with open(out, "w", newline="") as f:
        f.write(_table_text(run / f"aero_{'mid' if c['table'] == 'mid' else 'plain'}.csv", bool(c["po"]), calibers))


@cache
def _design(case: str) -> cdx1.Design:
    return cdx1.read(cdx_path(case))


def fly_one(job: tuple) -> dict:
    r, c, throat, ex = job
    d = _design(r["case"])
    src = src_dir(r["case"])
    run = ROOT / "results" / "matrix" / r["case"].replace(" ", "_") / tag(c)
    if not (run / "fs.json").exists():
        site = dict(d.site)
        if c["wind"]:
            site["WindSpeed"] = effective_speed(d.site["WindSpeed"] * MPH, r["fs_plain_ft"] * FT) / MPH
        d2 = replace(d, site=site, nozzle_in=0.0 if c["nozzle"] == "none" else d.nozzle_in or ex["exit_mm"] / 25.4)
        d2 = fincan_design(d2, r["case"]) if c["fincan"] else d2
        base_mm = d2.ref_diameter_m * 1000 if c["fincan"] else ex["base_mm"]  # a fin can base kept at body diameter would be a false boattail
        physics = fsrun.base_drag(c["po"], ex["throat_mm"], base_mm, ex["gamma"]) if c["po"] in BASE_DRAG else ""
        sim = fsrun.build(d2, eng.find(d.engine), run, reynolds=bool(c["re"]), gravity_m_s2=RAS_G if c["g"] else None, physics=physics)
        table(src, c, run / "aero.csv", d.ref_diameter_m / d2.ref_diameter_m)
        fsrun.fly(sim, throat if c["nozzle"] == "kb" else None, src / "surface.json" if c["table"] == "surface" else None)
    return {"case": r["case"], "tag": tag(c), "ft": json.loads((run / "fs.json").read_text())["apogee_agl_m"] / FT}


def plan(res: list[dict]) -> tuple[dict, list]:
    """Each distinct run once, and which run every cell of the factorial reads."""
    extra = ROOT / "results" / "extra"
    est = {**json.loads((ROOT / "results" / "throat_estimates.json").read_text()), **json.loads((extra / "throat_estimates.json").read_text())}
    exhaust = {**json.loads((ROOT / "results" / "exhaust_estimates.json").read_text()), **json.loads((extra / "exhaust_estimates.json").read_text())}
    jobs, maps = {}, []
    for r in res:
        d = _design(r["case"])
        e = est.get(r["case"], {}).get("est", {}).get(THROAT_KEY)
        throat = e["throat_mm"] / 1000 if e else None
        has_fincan = fincan_design(d, r["case"]).ref_diameter_m > d.ref_diameter_m
        for c in combos():
            real = effective(c, bool(r["wind_mph"]), d.nozzle_in, throat, has_fincan)
            jobs[(r["case"], tag(real))] = (r, real, throat, exhaust[r["case"]])
            maps.append((r["case"], tag(c), tag(real)))
    return jobs, maps


def safe_fly(job: tuple) -> dict:
    """One bad flight must not lose a long run: it is logged, its cells stay empty, and a rerun retries it."""
    try:
        return fly_one(job)
    except Exception as e:  # noqa: BLE001
        return {"case": job[0]["case"], "tag": tag(job[1]), "error": str(e)[-500:]}


def main(only: list[str]) -> None:
    dev, held = flights()
    res = [r for r in dev + held if not only or r["case"] in only]
    jobs, maps = plan(res)
    print(len(maps), "cells,", len(jobs), "runs,", WORKERS, "workers", flush=True)
    done, failed, start = {}, [], time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, o in enumerate(pool.map(safe_fly, jobs.values())):
            if "error" in o:
                failed.append(o)
                print("FAILED", o, flush=True)
            else:
                done[(o["case"], o["tag"])] = o["ft"]
            if i % 500 == 0:
                print(i, f"{time.time() - start:.0f} s", flush=True)
    (ROOT / "results" / "matrix_errors.json").write_text(json.dumps(failed, indent=1))
    print(len(failed), "failed runs,", f"{time.time() - start:.0f} s", flush=True)
    out = [{"case": a, "tag": b, "ft": done[(a, real)]} for a, b, real in maps if (a, real) in done]
    names = {r["case"] for r in dev}
    if only:
        (ROOT / "results" / "matrix_test.json").write_text(json.dumps(out))
    else:
        (ROOT / "results" / "matrix.json").write_text(json.dumps([c for c in out if c["case"] in names]))
        (ROOT / "results" / "matrix_heldout.json").write_text(json.dumps([c for c in out if c["case"] not in names]))


if __name__ == "__main__":
    main(sys.argv[1:])
