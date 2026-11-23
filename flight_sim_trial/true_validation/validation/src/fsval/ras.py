"""Client for RPA's headless RASAero II host (JSON lines over stdin/stdout)."""
import json
import subprocess
from pathlib import Path

from . import RAS_HOST, RAS_VENDOR, RPA


class Ras:
    def __init__(self) -> None:
        self.p = subprocess.Popen(["dotnet", str(RAS_HOST)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, cwd=RPA)
        info = self.call(op="ping")
        assert info["version"] == "1.0.2.0", info
        self.engine = info["engine"]
        self.call(op="motors", files=[str(RAS_VENDOR / "rasp.eng")])

    def call(self, **req) -> dict:
        self.p.stdin.write(json.dumps(req) + "\n")
        self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        if not r.get("ok"):
            raise RuntimeError(r)
        return r

    def load(self, cdx1: Path, key: str) -> dict:
        return self.call(op="design", cdx1=str(cdx1), design=key)

    def fly(self, key: str, **kw) -> dict:
        """Fly the file's own simulation row; apogee is feet AGL."""
        row = self.call(op="fly", design=key, **kw)["rows"][0]
        if row["error"]:
            raise RuntimeError(row["error"])
        return row

    def aero(self, key: str, nozzle_in: float, out: Path, altitude_ft: float = 0, mach_max: float = 5.0) -> Path:
        self.call(op="aero", design=key, config="sustainer", altitude_ft=altitude_ft, nozzle_in=nozzle_in,
                  mach_max=mach_max, csv=str(out))
        return out

    def close(self) -> None:
        self.p.stdin.close()
        self.p.wait(timeout=10)
