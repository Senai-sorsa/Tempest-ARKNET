"""RASP .eng motor lookup in RASAero's own motor file, so FS and RAS fly the same curve."""
from dataclasses import dataclass
from functools import cache

from . import RAS_VENDOR, ROOT


@dataclass(frozen=True)
class Motor:
    name: str  # "P9381  (LR-EX)" as RASAero names it
    diameter_mm: float
    length_mm: float
    propellant_kg: float
    total_kg: float
    text: str  # a one-motor .eng file


@cache
def _library() -> dict[str, Motor]:
    motors: dict[str, Motor] = {}
    head, body = None, []

    def flush() -> None:
        if head:
            f = head.split()
            name = f"{f[0]}  ({f[6]})" if len(f) > 6 else f[0]
            motors[name] = Motor(name, float(f[1]), float(f[2]), float(f[4]), float(f[5]),
                                 head + "\n" + "\n".join(body) + "\n")

    held_out = ROOT / "results" / "extra" / "designs" / "rocketpy.eng"  # thrust curves of the held-out flights
    text = (RAS_VENDOR / "rasp.eng").read_text(errors="replace") + (held_out.read_text() if held_out.exists() else "")
    for line in text.splitlines():
        s = line.split(";")[0].strip()
        if not s:
            continue
        p = s.split()
        if len(p) >= 6 and not _isnum(p[0]):
            flush()
            head, body = s, []
        elif head:
            body.append(s)
    flush()
    return motors


def _isnum(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def find(name: str) -> Motor:
    lib = _library()
    key = " ".join(name.split())
    for k, m in lib.items():
        if " ".join(k.split()) == key:
            return m
    raise KeyError(f"motor {name!r} not in rasp.eng")
