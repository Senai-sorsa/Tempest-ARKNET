"""Read what the harness needs from a RASAero .CDX1 file (an XML document)."""
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .units import IN


ROUGHNESS_IN = {  # RASAero II manual, Table 1
    "Smooth (Zero Roughness)": 0.0, "Polished": 0.00005, "Sheet Metal": 0.00016, "Smooth Paint": 0.00025,
    "Camouflage Paint": 0.0004, "Rough Camouflage Paint": 0.0012, "Galvanized Metal": 0.006, "Cast Iron (Very Rough)": 0.01,
}


@dataclass(frozen=True)
class Skin:
    """The geometry FS's built-in Reynolds correction needs, in m."""
    diameter_m: float  # widest part, fin can included
    body_wetted_m2: float
    roughness_m: float
    all_turbulent: bool
    fins: tuple[tuple[float, float, float], ...]  # wetted area, mean chord, thickness


def skin(rd: ET.Element) -> Skin:
    """Wetted areas as RASAero's parts lay them out; the fin can sits over the tube, adding only its annulus."""
    t = lambda e, k: float(e.findtext(k) or 0.0)  # noqa: E731
    wetted, widest, fins = 0.0, 0.0, []
    for part in rd:
        length, d = t(part, "Length"), t(part, "Diameter")
        if part.tag == "NoseCone":
            wetted += math.pi * d / 2 * math.hypot(length, d / 2)
        elif part.tag == "BodyTube":
            wetted += math.pi * d * length
        elif part.tag == "FinCan":
            wetted += math.pi * (d - t(part, "InsideDiameter")) * length
        elif part.tag == "BoatTail":
            rear = t(part, "RearDiameter")
            wetted += math.pi * (d + rear) / 2 * math.hypot(length, (d - rear) / 2)
        elif part.tag == "Transition":
            rear = t(part, "RearDiameter")
            wetted += math.pi * (d + rear) / 2 * math.hypot(length, (d - rear) / 2)
        else:
            continue
        widest = max(widest, d)
        for fin in part.findall("Fin"):
            root, tip = t(fin, "Chord"), t(fin, "TipChord")
            fins.append((t(fin, "Count") * (root + tip) * t(fin, "Span") * IN**2, (root + tip) / 2 * IN, t(fin, "Thickness") * IN))
    return Skin(widest * IN, wetted * IN**2, ROUGHNESS_IN[rd.findtext("Surface")] * IN, rd.findtext("Turbulence") == "True", tuple(fins))


@dataclass(frozen=True)
class Design:
    name: str
    ref_diameter_m: float
    length_m: float
    n_stages: int
    engine: str
    launch_wt_lb: float
    cg_in: float
    nozzle_in: float
    base_m: float
    site: dict[str, float]
    comments: str
    truth_ft: float | None
    truth_note: str
    skin: Skin


_NUM = r"([\d,]+(?:\.\d+)?)\s*ft"


def _truth(comments: str) -> tuple[float | None, str]:
    """Measured apogee quoted in the file's own comments; the most specific line wins."""
    lines = [l for l in comments.splitlines() if "redict" not in l and re.search(_NUM, l)]
    for key in ("Final Altitude", "Average", "Apogee Altitude", "Altitude"):
        for l in lines:
            if key in l:
                return float(re.search(_NUM, l).group(1).replace(",", "")), l.strip()
    return None, ""


def read(path: Path) -> Design:
    root = ET.fromstring(path.read_text(encoding="utf-8-sig", errors="replace"))
    rd = root.find("RocketDesign")
    t = lambda e, k, d=0.0: float(e.findtext(k) or d)  # noqa: E731
    diam, end = 0.0, 0.0
    for part in rd:
        if part.tag in ("NoseCone", "BodyTube", "Transition", "BoatTail"):
            diam = max(diam, t(part, "Diameter"), t(part, "RearDiameter") if part.tag == "Transition" else 0)
            end = max(end, t(part, "Location") + t(part, "Length"))
    tail = rd.find("BoatTail")
    sim = root.find("SimulationList/Simulation")
    site = {c.tag: float(c.text or 0) for c in root.find("LaunchSite")}
    truth, note = _truth(rd.findtext("Comments") or "")
    return Design(
        name=path.stem,
        ref_diameter_m=diam * IN,
        length_m=end * IN,
        n_stages=1 + (rd.findtext("UseBooster1") == "True") + (rd.findtext("UseBooster2") == "True"),
        engine=sim.findtext("SustainerEngine"),
        launch_wt_lb=t(sim, "SustainerLaunchWt"),
        cg_in=t(sim, "SustainerCG"),
        nozzle_in=t(sim, "SustainerNozzleDiameter"),
        base_m=(t(tail, "RearDiameter") if tail is not None else diam) * IN,
        site=site,
        comments=rd.findtext("Comments") or "",
        truth_ft=truth,
        truth_note=note,
        skin=skin(rd),
    )
