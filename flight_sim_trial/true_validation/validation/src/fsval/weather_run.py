"""Fly the flights whose launch date and site are known through that day's air, and score them against measured apogee.

    python -m fsval.weather_run fetch | sondes | fly | ras | score

The flight list, dates and launch hour are fixed from public launch records, not from the errors. A flight known only to
an event window is flown on each day of the window and scored on the mean. Flights with no date or no site are left out:
guessing their air would be tuning. Baro truth is scored as read and as converted to height through the day's air, for
every model alike; this assumes a standard-atmosphere altimeter, which no file states.
shortcut: 18 UTC (late morning) stands in for the launch hour except Qu8k's, where it is the known one; upgrade if launch logs turn up."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import numpy as np

from . import RAS_VENDOR, ROOT, cdx1, eng, fsrun, matrix, weather
from .ras import Ras
from .units import FT

OUT = ROOT / "results" / "weather"
BEST = {"table": "surface", "re": 1, "po": 1, "wind": 0, "nozzle": "linear", "g": 0}
HOUR = 18
LDRS26 = [date(2007, 7, d) for d in range(12, 18)]  # Jean, NV
BALLS21 = [date(2012, 9, d) for d in (21, 22, 23)]
PROTEUS = [date(2008, 9, d) for d in (26, 27, 28)] + [date(2008, 10, d) for d in (3, 4, 5)]  # weekends before the 6 Oct post: weakest date here
FLIGHTS = {
    "Qu8k": ("black rock", [date(2011, 9, 30)]),
    "DontDebateThisN5800MinDia": ("black rock", BALLS21),
    "Proteus6": ("black rock", PROTEUS),
    **{c: ("jean", LDRS26) for c in ("Byrum", "CancerDescending", "EZI65-1", "Gibb", "IonDrive", "Raven", "Thunder&Lightning")},
}
# variant: (air profile, wind profile, fin can diameter)
VARIANTS = {"filed": (0, 0, 1), "air": (1, 0, 1), "air_wind": (1, 1, 1), "filed_today": (0, 0, 0), "air_wind_today": (1, 1, 0)}
STATIONS = {"black rock": ("USM00072489", 39.5681, -119.7966), "jean": ("USM00072387", 36.6206, -116.0278)}  # Reno; Desert Rock, as Las Vegas has none in 2007


def design(case: str) -> cdx1.Design:
    return cdx1.read(RAS_VENDOR / "examples" / f"{case}.CDX1")


def profile_file(case: str, day: date):
    return OUT / case.replace(" ", "_") / str(day) / "profile.json"


def launch_time(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=HOUR)


def fetch() -> None:
    for case, (site, days) in FLIGHTS.items():
        lat, lon, _ = weather.SITES[site]
        for day in days:
            f = profile_file(case, day)
            if not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(weather.air_profile(lat, lon, design(case).site.get("Altitude", 0) * FT, launch_time(day))))
                print(case, day, flush=True)


def sondes() -> None:
    """ERA5 at the station and hour of each sounding against the measured sounding, on the standard pressure levels."""
    res = []
    for site, (station, lat, lon) in STATIONS.items():
        days = {d for s, ds in FLIGHTS.values() if s == site for d in ds}
        found = weather.igra_soundings(station, days)
        for when in sorted(found):
            era = weather.era5_levels(lat, lon, when)
            levels = {round(x["pressure_pa"] / 100): x for x in found[when]}
            for i, hpa in enumerate(era["level_hpa"]):
                if int(hpa) in levels and hpa <= 850:
                    x = levels[int(hpa)]
                    res.append({"site": site, "when": str(when), "hpa": hpa, "dT": era["temperature"][i] - x["temperature_k"],
                                "dz": float(weather.geometric_m(era["geopotential"][i] / weather.G0)) - x["height_m"], "T": x["temperature_k"]})
        print(site, len(found), "soundings", flush=True)
    (OUT / "sondes.json").write_text(json.dumps(res))
    for site in STATIONS:
        for lo, hi in ((700, 850), (300, 500), (100, 250), (10, 70)):
            r = [x for x in res if x["site"] == site and lo <= x["hpa"] <= hi]
            if r:
                dt, dz = np.array([x["dT"] for x in r]), np.array([x["dz"] for x in r])
                print(f"{site:11} {lo}-{hi} hPa n {len(r):3}  ERA5-sonde T {dt.mean():+.2f} rms {np.sqrt((dt**2).mean()):.2f} K  height {dz.mean():+.0f} rms {np.sqrt((dz**2).mean()):.0f} m")


def fly_one(job: tuple) -> dict:
    case, day, variant = job
    air, wind, fincan = VARIANTS[variant]
    key = case.replace(" ", "_")
    run = OUT / key / (str(day) if air else "filed") / variant
    if not (run / "fs.json").exists():
        d = design(case)
        src = ROOT / "results" / "ras_cases" / key
        sim = fsrun.build(matrix.fincan_design(d, case) if fincan else d, eng.find(d.engine), run, reynolds=True, air_profile=bool(air), wind_profile=bool(wind))
        matrix.table(src, BEST, run / "aero.csv")
        if air:
            (run / "profile.json").write_bytes(profile_file(case, day).read_bytes())
        fsrun.fly(sim, None, src / "surface.json", profile=bool(air))
    return {"case": case, "day": str(day), "variant": variant, "ft": json.loads((run / "fs.json").read_text())["apogee_agl_m"] / FT}


def fly(only: list[str]) -> None:
    jobs = [(c, days[0] if not VARIANTS[v][0] else day, v) for c, (_, days) in FLIGHTS.items() for v in VARIANTS for day in (days if VARIANTS[v][0] else days[:1])]
    jobs = [j for j in jobs if not only or j[0] in only]
    print(len(jobs), "flights", flush=True)
    with ThreadPoolExecutor(matrix.WORKERS) as pool:
        res = list(pool.map(fly_one, jobs))
    (OUT / ("fly_test.json" if only else "fly.json")).write_text(json.dumps(res))


def ras() -> None:
    """RAS on a copy of its file with the day's surface temperature, pressure and wind, which is all it accepts."""
    r = Ras()
    res = []
    for case, (_, days) in FLIGHTS.items():
        text = (RAS_VENDOR / "examples" / f"{case}.CDX1").read_text(encoding="utf-8-sig", errors="replace")
        site_m = design(case).site.get("Altitude", 0) * FT
        for day in days:
            p = json.loads(profile_file(case, day).read_text())
            s = text
            pressure = p["pressure_pa"][0] * weather.SEA_LEVEL_PA / weather.standard_pressure(site_m) / 3386.39
            wind_mph = float(np.hypot(p["east_m_s"][0], p["north_m_s"][0])) / 0.44704
            for tag, value in (("Temperature", p["temperature_k"][0] * 1.8 - 459.67), ("Pressure", pressure), ("WindSpeed", wind_mph)):
                s, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value:.2f}</{tag}>", s)
                assert n == 1, (case, tag, n)
            f = profile_file(case, day).with_name(f"{case}.CDX1")
            f.write_text(s, encoding="utf-8")
            r.load(f.resolve(), f"{case}|{day}")
            res.append({"case": case, "day": str(day), "ft": r.fly(f"{case}|{day}")["max_alt_ft"]})
            print(res[-1], flush=True)
    r.close()
    (OUT / "ras.json").write_text(json.dumps(res))


def is_baro(case: str) -> bool:
    d = design(case)
    return ("arometric" in d.truth_note or "Barometric" in d.comments.split("RASAero")[0]) and case != "Proteus6"


def true_height_ft(reading_ft: float, p: dict) -> float:
    """Height gain in the day's air that gives this standard-altimeter reading."""
    z = np.linspace(p["z_m"][0], p["z_m"][0] + reading_ft * FT * 1.5, 3001)
    pressure = np.exp(np.interp(z, p["z_m"], np.log(p["pressure_pa"])))
    read = weather.isa_altitude_m(pressure) - weather.isa_altitude_m(pressure[0])
    return float(np.interp(reading_ft * FT, read, z - z[0])) / FT


def stats(e: dict) -> str:
    a = np.array(list(e.values()))
    return f"bias {a.mean():+6.2f}  mean|e| {abs(a).mean():5.2f}  median {np.median(abs(a)):5.2f}"


def score() -> None:
    from scipy import stats as sp  # shortcut: not imported at the top, fly and fetch run without it

    cases = {r["case"]: r for r in json.loads((ROOT / "results" / "ras_cases.json").read_text())}
    fs: dict = {}
    for x in json.loads((OUT / "fly.json").read_text()):
        fs.setdefault(x["variant"], {}).setdefault(x["case"], {})[x["day"]] = x["ft"]
    fs["ras_day"] = {}
    for x in json.loads((OUT / "ras.json").read_text()):
        fs["ras_day"].setdefault(x["case"], {})[x["day"]] = x["ft"]
    fs["ras_filed"] = {c: {str(FLIGHTS[c][1][0]): cases[c]["ras_ft"]} for c in FLIGHTS}
    truth = {c: {"raw": cases[c]["truth_ft"]} for c in FLIGHTS}
    for c, (_, days) in FLIGHTS.items():
        heights = [true_height_ft(cases[c]["truth_ft"], json.loads(profile_file(c, d).read_text())) for d in days]
        truth[c]["height"] = float(np.mean(heights)) if is_baro(c) else cases[c]["truth_ft"]
    out = {}
    for name in ("raw", "height"):
        print(f"\ntruth {name}" + (": baro converted through the day's air, assuming an ISA altimeter" if name == "height" else ": as filed"))
        base = None
        for v in ("ras_filed", "ras_day", "filed_today", "filed", "air", "air_wind", "air_wind_today"):
            e = {c: 100 * (np.mean(list(fs[v][c].values())) / truth[c][name] - 1) for c in FLIGHTS}
            base = base if base is not None else np.abs(list(e.values()))
            closer = int((np.abs(list(e.values())) < base).sum())
            p = sp.wilcoxon(np.abs(list(e.values())), base).pvalue if v != "ras_filed" else float("nan")
            print(f"{v:15} {stats(e)}  closer than RAS filed {closer:2}/{len(e)}  p {p:.2f}")
            out[f"{name}|{v}"] = e
    print("\nper flight, % error on raw truth, then spread of the flown days (max-min, %)")
    for c in FLIGHTS:
        print(f"{c[:26]:26} {'baro' if is_baro(c) else 'imu ':4} truth {cases[c]['truth_ft']:7.0f} height {truth[c]['height']:7.0f} | "
              + " ".join(f"{v} {out['raw|' + v][c]:+6.1f}" for v in ("ras_filed", "filed", "air", "air_wind"))
              + f" | spread {100 * (max(fs['air_wind'][c].values()) / min(fs['air_wind'][c].values()) - 1):.1f}")
    (OUT / "scores.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"fetch": fetch, "sondes": sondes, "fly": lambda: fly(sys.argv[2:]), "ras": ras, "score": score}[sys.argv[1]]()
