"""AP02 power-on base pressure, after Moore and Hymer, NSWCDD/TR-00/67 (2001).

Pure functions on SI numbers. Table and equation numbers are the report's:
Table 1 (p.9), Table 2 and eq. 11b (p.9-10), Fig. 8 eqs. 2 and 9 (p.19-20), and
Fig. 7 (p.18) for the power-off base pressure coefficient.
"""

import math
from functools import lru_cache

import numpy as np

GAMMA_AIR = 1.4

# Table 1: C1 against C_T at each Mach row. Mach below 0.9 and above 4.0 clamp.
_MACH_ROWS = np.array([0.9, 1.0, 1.25, 1.65, 2.0, 2.5, 3.0, 4.0])
_CT_COLUMNS = np.array([1.0, 2.0, 20.0, 40.0, 70.0])
_C1 = np.array(
    [
        [0.19, 0.16, -0.06, 0.02, 0.0],
        [0.19, -0.085, -0.06, 0.02, 0.0],
        [0.19, -0.085, -0.01, 0.02, 0.0],
        [0.19, -0.175, -0.06, 0.04, 0.0],
        [0.19, -0.30, -0.20, 0.02, 0.0],
        [0.19, -0.45, -0.23, 0.01, 0.0],
        [0.19, -0.55, -0.22, -0.03, 0.0],
        [0.19, -0.65, -0.10, -0.04, 0.0],
    ]
)
# C2 at C_T <= 1 and >= 2, linear between
_C2_LOW = np.array([1.24, 1.28, 1.28, 1.28, 1.28, 1.28, 1.28, 1.28])
_C2_HIGH = np.array([1.24, 1.37, 1.47, 1.70, 1.90, 2.30, 2.50, 2.70])

# Fig. 7, -(C_PB) of a cylindrical body alone at zero alpha, read off the plot
# to about +-0.005
_CPB_MACH = np.array(
    [
        *(0.0, 0.5, 0.71, 0.84, 0.94, 1.06, 1.15, 1.26, 1.49),
        *(2.02, 2.5, 2.73, 3.2, 3.67, 4.09, 4.47, 4.5),
    ]
)
_CPB_OFF = np.array(
    [
        *(0.132, 0.136, 0.148, 0.158, 0.196, 0.226, 0.235, 0.229, 0.195),
        *(0.153, 0.111, 0.102, 0.0875, 0.0696, 0.060, 0.054, 0.054),
    ]
)

# Tail-off fade: a nozzle that is not flowing full stops relieving the base.
# Both ramps are engineering estimates, not fitted to data.
_SEPARATION_RAMP = (0.25, 0.45)  # P_j/P_inf
_UNCHOKE_RAMP = (1.9, 3.0)  # P_c/P_inf


def power_off_cpb(mach: float) -> float:
    """Return -C_PB of the body alone at zero alpha (Fig. 7), a positive number."""
    return float(np.interp(mach, _CPB_MACH, _CPB_OFF))


def jet_mach(area_ratio: float, gamma: float) -> float:
    """Return the supersonic jet exit Mach for an exit-to-throat area ratio (eq. 5).

    Raises:
        ValueError: If the area ratio is below 1.
    """
    if area_ratio < 1.0:
        raise ValueError(
            f"Nozzle exit must not be smaller than its throat: {area_ratio}"
        )
    return _jet_mach(float(area_ratio), float(gamma))


@lru_cache(maxsize=64)
def _jet_mach(area_ratio: float, gamma: float) -> float:
    """Bisect the supersonic root of the area-Mach relation."""
    exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))

    def ratio(mach: float) -> float:
        inner = 2.0 / (gamma + 1.0) * (1.0 + 0.5 * (gamma - 1.0) * mach**2)
        return float(inner**exponent / mach)

    low, high = 1.0, 100.0
    for _ in range(80):
        middle = 0.5 * (low + high)
        if ratio(middle) < area_ratio:
            low = middle
        else:
            high = middle
    return float(0.5 * (low + high))


def thrust_coefficient(
    thrust: float, mach: float, p_inf: float, area_ref: float
) -> float:
    """Return C_T = 2 T / (gamma P_inf M**2 A_ref) (eq. 14).

    M**2 is floored so the coefficient stays finite at rest; Table 1 clamps
    far below the value it then gives.
    """
    return 2.0 * thrust / (GAMMA_AIR * p_inf * max(mach**2, 1e-4) * area_ref)


def jet_pressure_ratio(
    thrust: float, p_inf: float, jet_area: float, gamma_j: float, mach_j: float
) -> float:
    """Return P_j / P_inf of the jet at the exit (eqs. 13 and 14 combined).

    Net thrust plus ambient pressure on the exit is the jet's momentum flux
    plus pressure force, P_j A_j (1 + gamma_j M_j**2). Mach drops out.
    """
    return (1.0 + thrust / (p_inf * jet_area)) / (1.0 + gamma_j * mach_j**2)


def chamber_pressure_ratio(pj_ratio: float, gamma_j: float, mach_j: float) -> float:
    """Return P_c / P_inf from isentropic flow to the jet exit."""
    return float(
        pj_ratio
        * (1.0 + 0.5 * (gamma_j - 1.0) * mach_j**2) ** (gamma_j / (gamma_j - 1.0))
    )


def _ramp(value: float, ramp: tuple[float, float]) -> float:
    low, high = ramp
    return min(max((value - low) / (high - low), 0.0), 1.0)


def nozzle_flow_fade(pj_ratio: float, pc_ratio: float) -> float:
    """Return s in [0, 1]: 1 with the nozzle flowing full, 0 once it separates."""
    return _ramp(pj_ratio, _SEPARATION_RAMP) * _ramp(pc_ratio, _UNCHOKE_RAMP)


def _c1(ct: float, mach: float) -> float:
    rows = [float(np.interp(ct, _CT_COLUMNS, row)) for row in _C1]
    return float(np.interp(mach, _MACH_ROWS, rows))


def _c2(ct: float, mach: float) -> float:
    low = float(np.interp(mach, _MACH_ROWS, _C2_LOW))
    high = float(np.interp(mach, _MACH_ROWS, _C2_HIGH))
    return low + (high - low) * min(max(ct - 1.0, 0.0), 1.0)


def boattail_factor(base_ratio: float, ct: float) -> float:
    """Return f(d_B / d_r) of Table 2: the boattail's effect on base pressure."""
    full = 3.5 / (1.0 + 2.5 * base_ratio**2)
    if base_ratio <= 1.0:
        start, end = 6.0, 12.0
    else:
        start, end = 25.0, 75.0
    if ct <= start:
        return full
    if ct >= end:
        return 1.0
    return 1.0 + (end - ct) / (end - start) * (full - 1.0)


def temperature_ratio(mach: float, gamma_j: float, mach_j: float) -> float:
    """Return T_j / T_j* with its lower limit below Mach 1.5 (eq. 3, eq. 11b)."""
    true = 0.5 * (gamma_j + 1.0) / (1.0 + 0.5 * (gamma_j - 1.0) * mach_j**2)
    if mach >= 1.5:
        return true
    floor = 0.7 if mach < 1.2 else 0.7 - (mach - 1.2) * (0.7 - true) / 0.3
    return max(true, floor)


def base_pressure_ratio(  # pylint: disable=too-many-arguments,too-many-locals
    mach: float,
    thrust: float,
    p_inf: float,
    *,
    area_ref: float,
    base_ratio: float,
    jet_ratio: float,
    gamma_j: float,
    mach_j: float,
    pj_ratio: float,
    exit_offset_ratio: float = 0.0,
    boattail_scale: float = 1.0,
) -> float:
    """Return P_B / P_inf with the jet on (Table 2).

    Args:
        mach (float): Freestream Mach.
        thrust (float): Net thrust in N.
        p_inf (float): Ambient pressure in Pa.
        area_ref (float): Reference area in m**2.
        base_ratio (float): Base diameter over reference diameter.
        jet_ratio (float): Jet exit diameter over reference diameter.
        gamma_j (float): Exhaust specific-heat ratio.
        mach_j (float): Jet exit Mach.
        pj_ratio (float): P_j / P_inf.
        exit_offset_ratio (float): Distance of the exit behind the base over
            the base diameter.
        boattail_scale (float): 0 drops the boattail factor, 1 keeps it.
    """
    ct = thrust_coefficient(thrust, mach, p_inf, area_ref)
    rmf_x = gamma_j * pj_ratio * jet_ratio**2 * mach_j**2 / GAMMA_AIR
    rmf_share = rmf_x / (rmf_x + max(mach**2, 1e-12))  # RMF / (1 + RMF)
    exponent = 1.0 if ct < 1.0 else max((12.0 - ct) / 11.0, 0.0)
    f = 1.0 + boattail_scale * (boattail_factor(base_ratio, ct) - 1.0)
    temperature = temperature_ratio(mach, gamma_j, mach_j) ** exponent
    offset = 0.047 * (5.0 - mach) * (2.0 * exit_offset_ratio + exit_offset_ratio**2)
    return float(temperature * (_c1(ct, mach) + _c2(ct, mach) * rmf_share) * f + offset)


def power_off_base_pressure_ratio(mach: float) -> float:
    """Return P_B / P_inf of the body alone (Fig. 8 eqs. 1 and 2, no bleed)."""
    return 1.0 - 0.5 * GAMMA_AIR * mach**2 * power_off_cpb(mach)


def area_ratio_from_diameters(exit_diameter: float, throat_diameter: float) -> float:
    """Return the nozzle's exit-to-throat area ratio."""
    return (exit_diameter / throat_diameter) ** 2


def circle_area(diameter: float) -> float:
    """Return the area of a circle of a diameter."""
    return 0.25 * math.pi * diameter**2
