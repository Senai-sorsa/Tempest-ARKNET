"""Why FS and RAS differ on the same inputs: compare their ascents flight by flight.
Flies each file's RAS row with its history, reads the FS run already made by fsval.matrix, and splits the gap into impulse,
mass, drag coefficient and implied density. Run after fsval.matrix. Usage: python -m fsval.trace [tag] [case ...]
Writes results/trace.json."""
import base64
import json
import sys

import numpy as np

from . import RAS_VENDOR, ROOT, cdx1
from .matrix import THROAT_KEY, combos, effective, tag as run_tag
from .ras import Ras
from .units import FT, LB

LBF_N = 4.4482216
DEFAULT_TAG = "surface_re1_po1_w0_linear"


def ras_history(ras: Ras, f, key: str) -> dict[str, np.ndarray]:
    ras.load(f, key)
    reply = ras.call(op="fly", design=key, inline_history=True)
    row = reply["rows"][0]
    if row["error"]:
        raise RuntimeError(row["error"])
    cols = reply["history_cols"]
    block = np.frombuffer(base64.b64decode(row["history_rows"]), dtype="<f8").reshape(-1, len(cols))
    return {c: block[:, i] for i, c in enumerate(cols)}


def impulse(t: np.ndarray, thrust_n: np.ndarray) -> float:
    return float(np.sum(0.5 * (thrust_n[1:] + thrust_n[:-1]) * np.diff(t)))


def compare(h: dict[str, np.ndarray], s: dict[str, list[float]], area_m2: float) -> dict:
    """RAS history (its units) against an FS series, up to each one's apogee."""
    ras_alt = (h["Altitude (ft)"] - h["Altitude (ft)"][0]) * FT
    top = int(np.argmax(ras_alt)) + 1
    t_r, alt_r = h["Time (sec)"][:top], ras_alt[:top]
    mach_r, cd_r = h["Mach Number"][:top], h["CD"][:top]
    vel_r = h["Velocity (ft/sec)"][:top] * FT
    thrust_r, mass_r = h["Thrust (lb)"][:top] * LBF_N, h["Weight (lb)"][:top] * LB
    drag_r = h["Drag (lb)"][:top] * LBF_N

    f = {k: np.array(v) for k, v in s.items()}
    top_f = int(np.argmax(f["alt_agl"])) + 1
    f = {k: v[:top_f] for k, v in f.items()}
    burn_r = float(t_r[np.flatnonzero(thrust_r > 0)[-1]])
    burn_f = float(f["t"][np.flatnonzero(f["thrust"] > 0)[-1]])
    at_burn = lambda t, x: float(np.interp(burn_r, t, x))
    coasting = (mach_r > 0.3) & (t_r > burn_r)
    cd_f = -f["force_x"] / np.maximum(f["q"] * area_m2, 1e-9)
    order = np.argsort(f["mach"][f["t"] > burn_f])
    # Same Mach, each at its own altitude: a Cd gap here is drag, not trajectory
    cd_f_at_r = np.interp(mach_r[coasting], f["mach"][f["t"] > burn_f][order], cd_f[f["t"] > burn_f][order])
    rho_r = drag_r / np.maximum(0.5 * cd_r * vel_r**2 * area_m2, 1e-9)
    use = (vel_r > 50) & (drag_r > 0)
    rho_f = np.interp(alt_r[use], f["alt_agl"], f["rho"])
    return {
        "apogee_gap_pct": 100 * float(f["alt_agl"].max() / alt_r.max() - 1),
        "impulse_gap_pct": 100 * (impulse(f["t"], f["thrust"]) / impulse(t_r, thrust_r) - 1),
        "liftoff_mass_gap_pct": 100 * float(f["mass"][0] / mass_r[0] - 1),
        "burnout_mass_gap_pct": 100 * (at_burn(f["t"], f["mass"]) / at_burn(t_r, mass_r) - 1),
        "burnout_speed_gap_pct": 100 * (at_burn(f["t"], f["speed"]) / at_burn(t_r, vel_r) - 1),
        "burnout_alt_gap_pct": 100 * (at_burn(f["t"], f["alt_agl"]) / at_burn(t_r, alt_r) - 1),
        "coast_cd_gap_pct": 100 * float(np.mean(cd_f_at_r / cd_r[coasting] - 1)) if coasting.any() else None,
        "density_gap_pct": 100 * float(np.mean(rho_f / rho_r[use] - 1)) if use.any() else None,
        "max_alpha_deg": float(np.nanmax(np.abs(f["alpha_deg"]))),
        "ras_max_alpha_deg": float(np.abs(h["Angle of Attack (deg)"][:top]).max()),
    }


def main(tag: str, only: list[str]) -> None:
    ras = Ras()
    out = {}
    combo = next(c for c in combos() if run_tag(c) == tag)
    throats = json.loads((ROOT / "results" / "throat_estimates.json").read_text())
    for row in json.loads((ROOT / "results" / "ras_cases.json").read_text()):
        if "fs_plain_ft" not in row or (only and row["case"] not in only):
            continue
        f = RAS_VENDOR / "examples" / f"{row['case']}.CDX1"
        d = cdx1.read(f)
        real = effective(combo, bool(row["wind_mph"]), d.nozzle_in, throats.get(row["case"], {}).get("est", {}).get(THROAT_KEY))
        fs = json.loads((ROOT / "results" / "matrix" / row["case"].replace(" ", "_") / run_tag(real) / "fs.json").read_text())
        out[row["case"]] = compare(ras_history(ras, f, row["case"]), fs["series"], np.pi * d.ref_diameter_m**2 / 4)
        print(row["case"][:26].ljust(26), {k: round(v, 2) for k, v in out[row["case"]].items() if v is not None}, flush=True)
    ras.close()
    (ROOT / "results" / "trace.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TAG, sys.argv[2:])
