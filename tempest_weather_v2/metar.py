"""METAR / SPECI parser for launch-day observations (spec R2, the offline half): paste a report, get wind, temperature and pressure for `Launch.observe`.

    parse("KTCS 241553Z 19002KT 10SM CLR 23/12 A3012 RMK AO2")
    -> Metar(station="KTCS", day=24, hour=15, minute=53, wind_from_deg=190, wind_speed_ms=1.03, gust_ms=None, temp_c=23.0, dew_c=12.0, altimeter_hpa=1020.4, variable=False)

Understands dddff[Ggg]KT / MPS / KMH winds, VRB winds (direction unknown), calm (00000KT), temperature / dew point with M for minus, altimeter A#### (inHg x 100) and Q#### (hPa).
Anything it cannot read stays None; `observation_kwargs` lists what could be used. stdlib only.
"""
import re
from dataclasses import dataclass

__all__ = ["Metar", "parse", "MetarError"]

KT, KMH = 0.514444, 1.0 / 3.6


class MetarError(ValueError):
    """The text does not look like a METAR with at least a wind, a temperature or a pressure."""


@dataclass(frozen=True)
class Metar:
    station: str = None
    day: int = None
    hour: int = None
    minute: int = None
    wind_from_deg: float = None
    wind_speed_ms: float = None
    gust_ms: float = None
    temp_c: float = None
    dew_c: float = None
    altimeter_hpa: float = None
    variable: bool = False

    def observation_kwargs(self, units="si"):
        """Keyword arguments for `Launch.observe` (in the Launch's units): wind_10m, wind_from_deg (only when the direction is known), temperature, altimeter."""
        out = {}
        if self.wind_speed_ms is not None:
            if self.wind_speed_ms == 0.0:                                     # calm: the direction does not matter
                out["wind_10m"], out["wind_from_deg"] = "0 m/s", 0.0
            elif self.wind_from_deg is not None and not self.variable:
                out["wind_10m"], out["wind_from_deg"] = f"{self.wind_speed_ms:.3f} m/s", self.wind_from_deg
            # variable direction (VRB): a speed without a direction cannot condition the wind, so it is left out
        if self.temp_c is not None:
            out["temperature"] = f"{self.temp_c:.2f} C"
        if self.altimeter_hpa is not None:
            out["altimeter"] = f"{self.altimeter_hpa:.2f} hPa"
        return out


_WIND = re.compile(r"^(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)$")
_TEMP = re.compile(r"^(M?\d{1,2})/(M?\d{1,2})?$")
_TIME = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")


def _t(s):
    return -float(s[1:]) if s.startswith("M") else float(s)


def parse(text):
    """Parse one METAR/SPECI report (everything after RMK is ignored)."""
    tokens = str(text).replace("\n", " ").strip().split()
    if "RMK" in tokens:
        tokens = tokens[: tokens.index("RMK")]
    if tokens and tokens[0] in ("METAR", "SPECI"):
        tokens = tokens[1:]
    f = {}
    for i, tok in enumerate(tokens):
        m = _TIME.match(tok)
        if m and "day" not in f:
            f.update(day=int(m.group(1)), hour=int(m.group(2)), minute=int(m.group(3)))
            if i > 0 and re.fullmatch(r"[A-Z0-9]{4}", tokens[0]):
                f["station"] = tokens[0]
            continue
        m = _WIND.match(tok)
        if m and "wind_speed_ms" not in f:
            k = {"KT": KT, "MPS": 1.0, "KMH": KMH}[m.group(4)]
            f["wind_speed_ms"] = int(m.group(2)) * k
            f["variable"] = m.group(1) == "VRB"
            f["wind_from_deg"] = None if m.group(1) == "VRB" else float(m.group(1))
            if m.group(3):
                f["gust_ms"] = int(m.group(3)) * k
            continue
        m = _TEMP.match(tok)
        if m and "temp_c" not in f:
            f["temp_c"] = _t(m.group(1))
            if m.group(2):
                f["dew_c"] = _t(m.group(2))
            continue
        if re.fullmatch(r"A\d{4}", tok) and "altimeter_hpa" not in f:
            f["altimeter_hpa"] = int(tok[1:]) / 100.0 * 33.8639
        elif re.fullmatch(r"Q\d{4}", tok) and "altimeter_hpa" not in f:
            f["altimeter_hpa"] = float(tok[1:])
    if not any(k in f for k in ("wind_speed_ms", "temp_c", "altimeter_hpa")):
        raise MetarError(f"cannot find a wind, temperature or pressure group in {text!r} (expected something like 'KTCS 241553Z 19002KT 10SM CLR 23/12 A3012')")
    return Metar(**f)
