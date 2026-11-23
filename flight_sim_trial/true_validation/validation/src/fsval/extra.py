"""Held-out flights: none shaped any setup choice. Fixed before any was flown:
primary setup sea_re2_po1_w0_linear (built-in Reynolds, power-on table, linear nozzle, no wind, fin can as reference); RAS is scored as it flies the same file.
Flights: Hubbub, McGarvey, EZI65Hist-1 (RASAero's .alx1 files) and RocketPy's solid-motor flights with a recorded apogee (MIT; docs/examples, data/).
Also added before flying: PSAS Launch 10 (2013, .ork and two baro logs, sim/README: 33.742 kg, canards not modelled, no nozzle size) scored against the mean of its two baros (TeleMetrum 15091, ARTS 15485 ft);
Heart of Steel (Stanford SSI, 2017-06-22, Strato 30411 ft AGL) on the team's IREC_Current.CDX1, last changed three weeks before the flight. Launch weight flown is unpublished: the file's first row, others shown as @ rows, outside the means.
Stanford's test flights (FAR 2017-04-15, 2017-05-20, TCC 2017-05-19) are left out: which design row flew is not recorded. RASAero refused Valkyrie (flight error) and NDRT2020 (Transition, format unverified).
Left out: LOC2P1-1/2, EZI65Hist-2 (rasp.eng's J125 Hist has 0.0016 kg of propellant), Camoes (air brakes), Hedy (liquid), Defiance, Halcyon (hybrid), AeroPac104K (two stage).
Inferred for RocketPy flights, the same for RAS and FS: fins 5 mm thick and rounded, Smooth Paint, ISA air at the site, no wind (real wind not read), no rail guides (no sizes published, so both read high). Tail-hidden fins sit on the tube.
Propellant is the notebook's grains, or the .eng header's where they differ by over 20 %. A nozzle exit above 85 % of the base is taken as a wrong entry and dropped.
Usage: python -m fsval.extra, then python -m fsval.extra prepare for the tables and estimates fsval.matrix needs."""
import json
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import RAS_VENDOR, ROOT, aero, cdx1, eng, exhaust, fsrun, surface, throat
from .ras import Ras
from .units import FT, IN, LB

DATA = ROOT / "data" / "rocketpy"
OUT = ROOT / "results" / "extra"
SHAPES = {"Ogive": "Tangent Ogive", "Conic": "Conical"}
FIN_T = 0.005
CG_FRACTION = 0.63  # shortcut: .alx1 files with no CG, the usual share of length; upgrade if a flight's CG turns up


def grains(rho: float, ro: float, ri: float, h: float, n: int = 1) -> float:
    return rho * math.pi * (ro**2 - ri**2) * h * n


# lengths in m, masses in kg. fins: count, root, tip, span, sweep, leading edge above the base. cg from the nose, without the motor.
ROCKETS = {
    "Prometheus": dict(d=.1397, L=2.229, nose=(.742, "Von Karman Ogive"), fins=(3, .268, .136, .13, .066, .273), exit=.054, inc=80, rail=5.18, elev=1401, truth_m=3898, mass=13.93, cg=1.274, motor=("Cesaroni_7579M1520-P.eng", 3.737, 2.981), note="COTS altimeter, official"),
    "Andromeda": dict(d=.1507, L=2.4996, nose=(.3, "Von Karman Ogive"), fins=(3, .23, .11, .185, .06, .3546), exit=.05625, inc=84, rail=12, elev=160, truth_m=3443, mass=20.9767, cg=1.0998, motor=("andromeda_thrust.csv", grains(1468.9079, .0375, .01875, .893), 0), note="EuRoC official"),
    "Astra": dict(d=.094, L=1.8068, nose=(.27, "Von Karman Ogive"), fins=(4, .2, .118, .117, .041, .2), exit=.05625, inc=84, rail=12, elev=160, truth_m=3250, mass=10.6462, cg=1.1257, motor=("Cesaroni_4263L1350-P.eng", grains(1256.7753, .0375, .01875, .486), 0), note="EuRoC official"),
    "Cavour": dict(d=.104, L=2.7224, nose=(.52, "Von Karman Ogive"), fins=(4, .2, .07, .1, .065, .2104), exit=.067, inc=84, rail=12, elev=150, truth_m=2789, mass=8.219, cg=1.523, motor=("Cesaroni_3618L995-P.eng", grains(1653.53, .0325, .011375, .13244, 3), 0), note="EuRoC official"),
    "Genesis": dict(d=.094, L=2.372, nose=(.27, "Von Karman Ogive"), fins=(4, .2, .11, .105, .045, .25), exit=.0847, inc=84, rail=12, elev=160, truth_m=2916, mass=9.214, cg=1.477, motor=("Cesaroni_3618L995-P.eng", grains(1815, .033, .015, .12, 3), 0), note="EuRoC official"),
    "Lince": dict(d=.104, L=2.131417, nose=(.28, "Von Karman Ogive"), tail=(.022, .09704), fins=(4, .17, .0425, .0825, .06375, .192), exit=.067, inc=84, rail=12, elev=158, truth_m=3587, mass=10.6851352, cg=1.048, motor=("Cesaroni_M1101.eng", grains(1363, .035, .01, .16, 4), 0), note="EuRoC official"),
    "Erebus": dict(d=.0915, L=2.172432, nose=(.391113, "Von Karman Ogive"), tail=(.079119, .0715), fins=(4, .12, .05, .08, .035, .184), exit=.0405, inc=84, rail=12, elev=160, truth_m=3020, mass=5.82, cg=1.192, motor=("erebus_thrust.csv", grains(1196.6353, .027, .0135, .572), 0), note="EuRoC official"),
    "Juno3": dict(d=.131, L=2.771, nose=(.565, "Von Karman Ogive"), tail=(.068, .107), fins=(4, .2, .12, .13, .04, .366), exit=.067, inc=85, rail=5.2, elev=1480, truth_m=3213, mass=24.05, cg=1.477, motor=("mandioca_thrust_curve.csv", grains(1748.9, .0465, .016, .156, 5), 0), reshape=(5.8, 8800.0), note="Spaceport America Cup official"),
    "Valkyrie": dict(d=.11, L=1.99, nose=(.2, "Elliptical"), tail=(.15, .06), fins=(4, .17, .14, .0768, .1, .298), exit=.09, inc=87, rail=5, elev=592, truth_m=2098.02, mass=5.65, cg=.996, motor=("Cesaroni_1997K650-21A.eng", grains(1170, .025, .01, .0966, 5), .6449), note="recorded"),
    "NDRT2020": dict(d=.203, L=3.391, nose=(.61, "Tangent Ogive"), step=(.59, .127, .155), fins=(4, .152, .0762, .165, .0381, .341), exit=.0495, inc=90, rail=3.353, elev=206, truth_m=1316.736, mass=18.998, cg=1.3, motor=("Cesaroni_4895L1395-P.eng", grains(1519.708, .033, .015, .12, 5), 1.848), note="measured"),
    "BellaLui": dict(d=.156, L=2.6776, nose=(.242, "Tangent Ogive"), tail=(.05, .135), fins=(3, .28, .125, .2, .0775, .3856), exit=.0889, inc=89, rail=4.2, elev=407, truth_m=458.97, mass=18.226, cg=1.542, motor=("AeroTech_K828FJ.eng", grains(782.4, .042799, .033147, .1524, 3), .001), note="measured"),
    "PSASLaunch10": dict(d=.1397, L=3.536, nose=(1.0418, "Tangent Ogive"), fins=(3, .37, .2018, .151, .0912, .37), exit=0.0, inc=89, rail=3.65, elev=1390, truth_m=(15091.3 + 15484.9) / 2 * FT, mass=22.074, cg=2.01, rasp="N2500  (CTI)", note="mean of 2 baros"),
    "Valetudo": dict(d=.0809, L=2.158, nose=(.274, "Tangent Ogive"), fins=(3, .058, .018, .077, .02, .118), exit=.04328, inc=84.7, rail=5.7, elev=668, truth_m=860, mass=8.257, cg=1.134, motor=("keron_thrust_curve.csv", grains(1707, .0214, .00965, .12, 6), .001), note="measured"),
}


def curve(path: Path) -> tuple[np.ndarray, str]:
    """Thrust against time from a .eng or a CSV, and the .eng header if there is one."""
    rows, head = [], ""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        p = line.split(";")[0].replace(",", " ").split()
        try:
            if len(p) == 2:
                rows.append((float(p[0]), float(p[1])))
        except ValueError:
            pass
        if len(p) >= 6 and not head:
            head = line
    return np.array(rows), head


def motor(name: str, spec: dict) -> eng.Motor:
    file, prop, dry = spec["motor"]
    a, head = curve(DATA / file)
    if head and abs(float(head.split()[4]) / prop - 1) > 0.2:
        prop = float(head.split()[4])
    if "reshape" in spec:
        burn, impulse = spec["reshape"]
        a = a * [burn / a[-1, 0], 1.0]
        a = a * [1.0, impulse / np.trapezoid(a[:, 1], a[:, 0])]
    if len(a) > 60:  # RASAero reads short curves; 60 points hold the impulse
        t = np.linspace(a[0, 0], a[-1, 0], 60)
        a = np.column_stack((t, np.interp(t, a[:, 0], a[:, 1])))
    a = a[a[:, 0] > 0]
    a[-1, 1] = 0.0
    dia = float(head.split()[1]) if head else spec["d"] * 1000 * 0.7
    length = float(head.split()[2]) if head else spec["L"] * 300
    total = prop + max(dry, 0.001)
    tag = f"X{name[:9]}"
    text = f"{tag} {dia:g} {length:g} 0 {prop:.4f} {total:.4f} RPY\n" + "".join(f"{t:.4f} {f:.3f}\n" for t, f in a)
    return eng.Motor(f"{tag}  (RPY)", dia, length, prop, total, text)


def _part_nose(length: float, dia: float, shape: str, blunt: float = 0) -> str:
    return f"<NoseCone><PartType>NoseCone</PartType><Length>{length}</Length><Diameter>{dia}</Diameter><Shape>{shape}</Shape><BluntRadius>{blunt}</BluntRadius><Location>0</Location><Color>Black</Color></NoseCone>"


def _fin(f: dict) -> str:
    return f"<Fin><Count>{f['n']}</Count><Chord>{f['root']}</Chord><Span>{f['span']}</Span><SweepDistance>{f['sweep']}</SweepDistance><TipChord>{f['tip']}</TipChord><Thickness>{f['t']}</Thickness><LERadius>0</LERadius><Location>{f['loc']}</Location><AirfoilSection>{f['foil']}</AirfoilSection><FX1>{f['fx1']}</FX1><FX3>{f['fx3']}</FX3></Fin>"


def _tube(length: float, dia: float, loc: float, fin: str = "", guide: tuple[float, float] = (0, 0)) -> str:
    return f"<BodyTube><PartType>BodyTube</PartType><Length>{length}</Length><Diameter>{dia}</Diameter><LaunchLugDiameter>0</LaunchLugDiameter><LaunchLugLength>0</LaunchLugLength><RailGuideDiameter>{guide[0]}</RailGuideDiameter><RailGuideHeight>{guide[1]}</RailGuideHeight><LaunchShoeArea>0</LaunchShoeArea><Location>{loc}</Location><Color>Black</Color><BoattailLength>0</BoattailLength><BoattailRearDiameter>0</BoattailRearDiameter><BoattailOffset>0</BoattailOffset><Overhang>0</Overhang>{fin}</BodyTube>"


def document(parts: str, surface: str, nozzle: float, site: dict, sim: dict) -> str:
    s = "".join(f"<{k}>{v}</{k}>" for k, v in site.items())
    return f"""<RASAeroDocument><FileVersion>2</FileVersion><RocketDesign>{parts}<Surface>{surface}</Surface><CP>0</CP><ModifiedBarrowman>False</ModifiedBarrowman><Turbulence>False</Turbulence><SustainerNozzle>{nozzle}</SustainerNozzle><Booster1Nozzle>0</Booster1Nozzle><Booster2Nozzle>0</Booster2Nozzle><UseBooster1>False</UseBooster1><UseBooster2>False</UseBooster2><Comments></Comments></RocketDesign><LaunchSite>{s}</LaunchSite><Recovery><Altitude1>1000</Altitude1><Altitude2>1000</Altitude2><DeviceType1>None</DeviceType1><DeviceType2>None</DeviceType2><Event1>False</Event1><Event2>False</Event2><Size1>1</Size1><Size2>1</Size2><EventType1>None</EventType1><EventType2>None</EventType2><CD1>1.33</CD1><CD2>1.33</CD2></Recovery><MachAlt /><SimulationList><Simulation><SustainerEngine>{sim['engine']}</SustainerEngine><SustainerLaunchWt>{sim['wt']}</SustainerLaunchWt><SustainerNozzleDiameter>{nozzle}</SustainerNozzleDiameter><SustainerCG>{sim['cg']}</SustainerCG><SustainerIgnitionDelay>0</SustainerIgnitionDelay><Booster1LaunchWt>0</Booster1LaunchWt><Booster1SeparationDelay>0</Booster1SeparationDelay><Booster1IgnitionDelay>0</Booster1IgnitionDelay><Booster1CG>0</Booster1CG><Booster1NozzleDiameter>0</Booster1NozzleDiameter><IncludeBooster1>False</IncludeBooster1><Booster2LaunchWt>0</Booster2LaunchWt><Booster2Delay>0</Booster2Delay><Booster2CG>0</Booster2CG><Booster2NozzleDiameter>0</Booster2NozzleDiameter><IncludeBooster2>False</IncludeBooster2><FlightTime>0</FlightTime><TimetoApogee>0</TimetoApogee><MaxAltitude>0</MaxAltitude><MaxVelocity>0</MaxVelocity><OptimumWt>0</OptimumWt><OptimumMaxAlt>0</OptimumMaxAlt></Simulation></SimulationList></RASAeroDocument>"""


def from_rocketpy(name: str, s: dict, m: eng.Motor) -> str:
    """A RocketPy flight's numbers as a CDX1, in inches and pounds as the format wants."""
    i = lambda x: round(x / IN, 4)  # noqa: E731
    d, (nose_len, shape) = s["d"], s["nose"]
    tail_len, tail_rear = s.get("tail", (0.0, d))
    n, root, tip, span, sweep, le = s["fins"]
    fin_loc = max(le - tail_len, root)
    fin = _fin({"n": n, "root": i(root), "tip": i(tip), "span": i(span), "sweep": i(sweep), "t": i(FIN_T), "loc": i(fin_loc), "foil": "Rounded", "fx1": i(FIN_T), "fx3": 0})
    parts = _part_nose(i(nose_len), i(d), shape)
    if "step" in s:
        fore, trans, aft = s["step"]
        parts += _tube(i(fore), i(d), i(nose_len))
        parts += f"<Transition><PartType>Transition</PartType><Length>{i(trans)}</Length><Diameter>{i(d)}</Diameter><RearDiameter>{i(aft)}</RearDiameter><Location>{i(nose_len + fore)}</Location><Color>Black</Color></Transition>"
        parts += _tube(i(s["L"] - nose_len - fore - trans), i(aft), i(nose_len + fore + trans), fin)
        base = aft
    else:
        parts += _tube(i(s["L"] - nose_len - tail_len), i(d), i(nose_len), fin)
        base = tail_rear
    if tail_len:
        parts += f"<BoatTail><PartType>BoatTail</PartType><Length>{i(tail_len)}</Length><Diameter>{i(d)}</Diameter><RearDiameter>{i(tail_rear)}</RearDiameter><Location>{i(s['L'] - tail_len)}</Location><Color>Black</Color></BoatTail>"
    exit_m = s["exit"] if s["exit"] <= 0.85 * base else 0.0
    wt = s["mass"] + m.total_kg
    cg = (s["mass"] * s["cg"] + m.total_kg * (s["L"] - m.length_mm / 2000)) / wt
    temp_f = 59 - 3.566 * s["elev"] / FT / 1000  # ISA at the site
    site = {"Altitude": round(s["elev"] / FT, 1), "Pressure": 0, "RodAngle": round(90 - s["inc"], 3), "RodLength": round(s["rail"] / FT, 3), "Temperature": round(temp_f, 2), "WindSpeed": 0}
    return document(parts, "Smooth Paint", i(exit_m), site, {"engine": m.name, "wt": round(wt / LB, 3), "cg": i(cg)})


def from_alx1(path: Path) -> tuple[str, float | None]:
    """A RASAero 1 .alx1 file as a CDX1, and its CG if the file has none."""
    x = path.read_text(encoding="utf-8-sig", errors="replace")
    g = lambda k: re.search(rf"<{k}(?: [^>]*)?>([^<]*)<", x).group(1)  # noqa: E731
    f = lambda k: float(g(k))  # noqa: E731
    dia, nose, tube = f("MaxDiameter"), f("NC_length"), f("BodyTubeLength")
    end = nose + tube
    can = re.search(r"FinCanClass.*?</a1:FinCanClass>", x, re.S).group(0)
    tail = re.search(r"BoatTailClass.*?</a1:BoatTailClass>", x, re.S).group(0)
    num = lambda s, k: float(re.search(rf"<{k}(?: [^>]*)?>([^<]*)<", s).group(1))  # noqa: E731
    finx = {"n": int(f("Count")), "root": f("RootChord"), "tip": f("TipChord"), "span": f("Span"), "sweep": f("SweepDistance"), "t": f("Thickness"), "loc": end - f("OffsetfromNose"), "foil": g("Airfoiltype"), "fx1": f("FX1"), "fx3": f("FX3")}
    assert num(tail, "Length") == 0, "boattail not converted"
    parts = _part_nose(nose, dia, SHAPES.get(g("NC_type"), g("NC_type")), f("NC_BluntRadius"))
    length, guide = num(can, "Length"), (f("RailGuideDiameter"), f("RailGuideHeight"))
    if length:
        parts += _tube(tube, dia, nose, guide=guide)
        parts += f"<FinCan><PartType>FinCan</PartType><Length>{length}</Length><Diameter>{num(can, 'OuterDiameter')}</Diameter><InsideDiameter>{dia}</InsideDiameter><LaunchLugDiameter>0</LaunchLugDiameter><LaunchLugLength>0</LaunchLugLength><RailGuideDiameter>0</RailGuideDiameter><RailGuideHeight>0</RailGuideHeight><LaunchShoeArea>0</LaunchShoeArea><Location>{end}</Location><Color>Black</Color><ShoulderLength>{num(can, 'ShoulderLength')}</ShoulderLength><Offset>{-length}</Offset>{_fin(finx)}</FinCan>"
    else:
        parts += _tube(tube, dia, nose, _fin(finx), guide)
    site_x = re.search(r"LaunchSiteClass.*?</a1:LaunchSiteClass>", x, re.S).group(0)
    site = {k: num(site_x, k) for k in ("Altitude", "Pressure", "RodAngle", "RodLength", "Temperature", "WindSpeed")}
    cg = f("CGLoc") or round(CG_FRACTION * end, 2)
    return document(parts, g("SurfaceFinish"), f("NozzleDiameter"), site, {"engine": g("EngineName"), "wt": f("TotalWeight"), "cg": cg}), None if f("CGLoc") else cg


def fly_fs(job: tuple) -> dict:
    name, re_level, d, m, table = job
    run = OUT / name / f"sea_re{re_level}_po1_w0_linear"
    sim = fsrun.build(d, m, run, reynolds=bool(re_level))
    shutil.copy(table, run / "aero.csv")
    return {"case": name, "re": re_level, "ft": fsrun.fly(sim)["apogee_agl_m"] / FT}


def design(path: Path) -> cdx1.Design:
    d = cdx1.read(path)
    can = ET.fromstring(path.read_text()).find("RocketDesign/FinCan")
    return replace(d, ref_diameter_m=max(d.ref_diameter_m, float(can.findtext("Diameter")) * IN)) if can is not None else d


def main() -> None:
    (OUT / "designs").mkdir(parents=True, exist_ok=True)
    ras = Ras()
    ex = RAS_VENDOR / "examples"
    for case in ("EZI65-1", "Rabia-ShortFinCan"):  # the converter must fly a published file as RAS flies the file
        ras.load(ex / f"{case}.CDX1", case)
        made = OUT / "designs" / f"check_{case}.CDX1"
        made.write_text(from_alx1(ex / f"{case}.alx1")[0])
        ras.load(made, "made" + case)
        a, b = ras.fly(case)["max_alt_ft"], ras.fly("made" + case)["max_alt_ft"]
        print(f"converter check {case}: file {a:.0f} ft, converted {b:.0f} ft", flush=True)
        assert abs(b / a - 1) < 0.01, case
    motors = {n: eng.find(s["rasp"]) if "rasp" in s else motor(n, s) for n, s in ROCKETS.items()}
    extra_eng = OUT / "designs" / "rocketpy.eng"
    extra_eng.write_text("".join(motors[n].text for n, s in ROCKETS.items() if "rasp" not in s))
    ras.call(op="motors", files=[str(RAS_VENDOR / "rasp.eng"), str(extra_eng)])
    cases = []
    for n in ("Hubbub", "McGarvey", "EZI65Hist-1"):
        text, cg = from_alx1(ex / f"{n}.alx1")
        f = OUT / "designs" / f"{n}.CDX1"
        f.write_text(text)
        truth = float(re.search(r"Altitude = (\d+) ft", (ex / f"{n}.alx1").read_text(errors="replace")).group(1))
        cases.append((n, f, truth, eng.find(cdx1.read(f).engine), "alx1" + (" CG inferred" if cg else "")))
    for n, s in ROCKETS.items():
        f = OUT / "designs" / f"{n}.CDX1"
        f.write_text(from_rocketpy(n, s, motors[n]))
        cases.append((n, f, s["truth_m"] / FT, motors[n], s["note"]))
    src = (ROOT / "data" / "ssi" / "IREC_Current.CDX1").read_text(encoding="utf-8-sig", errors="replace")
    for tag, wt in (("HeartOfSteel", None), ("HeartOfSteel@68lb", "68"), ("HeartOfSteel@74.8lb", "74.8")):
        f = OUT / "designs" / f"{tag}.CDX1"
        f.write_text(re.sub(r"(<SustainerLaunchWt>)[^<]*", rf"\g<1>{wt}", src, count=1) if wt else src)
        cases.append((tag, f, 30411.0, eng.find("N2900-CL  (CTI)"), "Strato baro" + (" weight sensitivity" if wt else "")))
    rows, jobs = [], []
    for n, f, truth, m, note in cases:
        try:
            d = design(f)
            ras.load(f, n)
            r = ras.fly(n)
            (OUT / n).mkdir(exist_ok=True)
            tbl = ras.aero(n, d.nozzle_in, OUT / n / "ras_aero.csv")
            aero.to_fs_table(tbl, OUT / n / "aero.csv", d.ref_diameter_m)
        except Exception as e:  # noqa: BLE001
            print("RAS fail", n, str(e)[:160], flush=True)
            continue
        rows.append({"case": n, "truth_ft": truth, "ras_ft": r["max_alt_ft"], "note": note, "vmax_fps": r["max_vel_fps"]})
        jobs += [(n, lvl, d, m, OUT / n / "aero.csv") for lvl in (0, 2)]
    with ThreadPoolExecutor(10) as pool:
        out = {(o["case"], o["re"]): o["ft"] for o in pool.map(fly_fs, jobs)}
    ras.close()
    print(f"{'flight':14} {'truth ft':>8} {'Mach':>5} {'RAS %':>7} {'noRe %':>7} {'built %':>8}  source")
    for r in rows:
        t = r["truth_ft"]
        r["no_re_ft"], r["built_ft"] = out[(r["case"], 0)], out[(r["case"], 2)]
        print(f"{r['case']:14} {t:8.0f} {r['vmax_fps'] / 1125:5.2f} {100 * (r['ras_ft'] / t - 1):+7.2f} {100 * (r['no_re_ft'] / t - 1):+7.2f} {100 * (r['built_ft'] / t - 1):+8.2f}  {r['note']}")
    main_rows = [r for r in rows if "@" not in r["case"]]
    e = {k: 100 * (np.array([r[k] for r in main_rows]) / np.array([r["truth_ft"] for r in main_rows]) - 1) for k in ("ras_ft", "no_re_ft", "built_ft")}
    for k, v in e.items():
        print(f"{k:9} n {len(v)} mean |err| {abs(v).mean():.2f} median {np.median(abs(v)):.2f} bias {v.mean():+.2f}")
    print("built closer than RAS:", int((abs(e["built_ft"]) < abs(e["ras_ft"])).sum()), "of", len(main_rows))
    (OUT / "scores.json").write_text(json.dumps(rows, indent=1))


def prepare() -> None:
    """Mid and altitude tables from RAS, and the nozzle estimates, for every scored held-out flight. Flies nothing; a done flight is skipped."""
    ras = Ras()
    ras.call(op="motors", files=[str(RAS_VENDOR / "rasp.eng"), str(OUT / "designs" / "rocketpy.eng")])
    fits, ests = {}, {}
    for r in json.loads((OUT / "scores.json").read_text()):
        n = r["case"]
        if "@" in n:
            continue
        f, run = OUT / "designs" / f"{n}.CDX1", OUT / n
        d = cdx1.read(f)  # the body diameter, as results/ras_cases tables are; the fin can is a matrix factor
        aero.to_fs_table(run / "ras_aero.csv", run / "aero_plain.csv", d.ref_diameter_m)
        if not (run / "surface.json").exists():
            ras.load(f, n)
            mid = d.site.get("Altitude", 0) + 0.5 * r["ras_ft"]
            aero.to_fs_table(ras.aero(n, d.nozzle_in, (run / "ras_aero_mid.csv").resolve(), altitude_ft=mid), run / "aero_mid.csv", d.ref_diameter_m)
            print(n, "altitudes up to", surface.scan(ras, n, d, r["ras_ft"], run), flush=True)
        m = eng.find(d.engine)
        fits[n] = throat.motor_estimates(d, m) if d.nozzle_in > 0 else {}
        ests[n] = exhaust.entry(d, m, fits[n])
    ras.close()
    (OUT / "throat_estimates.json").write_text(json.dumps(fits, indent=1))
    (OUT / "exhaust_estimates.json").write_text(json.dumps(ests, indent=1))


if __name__ == "__main__":
    prepare() if sys.argv[1:] == ["prepare"] else main()
