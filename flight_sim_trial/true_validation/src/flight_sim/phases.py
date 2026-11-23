"""Flight phases: physics that changes with the motor on.

Select one per segment with
``config.physics = { type = "flight_sim.phases.PowerOnBaseDrag", ... }``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Annotated, Literal

import numpy as np

from flight_sim import ap02
from flight_sim.environment.atmosphere import AtmosphereConditions
from flight_sim.flight_point import AeroPointSI
from flight_sim.physics import RocketPhysics, coefficient_loads
from flight_sim.units import Scalar, UnitChecked, scalar
from flight_sim.utilities.data_loader import AeroTable
from flight_sim.vehicle.rocket_properties import RocketProperties


def _smoothstep(value: float, low: float, high: float) -> float:
    x = min(max((value - low) / (high - low), 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


@dataclass(frozen=True)
class PowerOnBaseDrag(RocketPhysics, UnitChecked):
    """Rocket physics with the exhaust jet's effect on the base drag.

    The aero table holds power-off drag, whose base pressure the jet raises.
    ``model`` picks how that relief is found:

    - ``ap02``: base pressure from Moore and Hymer's correlation (``ap02.py``).
    - ``ras``: the table's own power-on Cx, faded in with the nozzle flow.
    - ``blend``: the power-off base drag removed, the whole base below Mach 1.2
      and only the jet exit's share above Mach 1.6.
    - ``coast``: no relief, the table's power-off drag.

    The fade ``s`` takes the relief off once the nozzle separates or unchokes,
    as in the tail-off.
    """

    model: Literal["ap02", "ras", "blend", "coast"]
    throat_diameter: Annotated[Scalar, "m"]  # Nozzle throat
    base_diameter: Annotated[Scalar, "m"]  # Base annulus the jet exits through
    exit_offset: Annotated[Scalar, "m"] = field(
        default_factory=lambda: scalar(0.0, "m")
    )  # Exit plane behind the base
    exhaust_gamma: float = 1.22
    # 0 drops the boattail factor f(dB/dr); 1 is the correlation as published
    boattail_scale: float = 1.0
    # Scales the relief below Mach 0.9, fading to 1 by Mach 1.2
    subsonic_scale: float = 1.0

    def __post_init__(self) -> None:
        """Check the model name and the nozzle inputs.

        Raises:
            ValueError: If the model is unknown, a diameter is not positive or
                the exhaust gamma is not above 1.
        """
        super().__post_init__()
        if self.throat_diameter.m_as("m") <= 0 or self.base_diameter.m_as("m") <= 0:
            raise ValueError("Throat and base diameters must be positive")
        if self.model not in ("ap02", "ras", "blend", "coast"):
            raise ValueError(f"Unknown base drag model: {self.model!r}")
        if self.exhaust_gamma <= 1.0:
            raise ValueError(f"exhaust_gamma must be above 1: {self.exhaust_gamma}")

    def aero(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        time: float,
        air_velocity: np.ndarray,
        conditions: AtmosphereConditions,
        to_body: np.ndarray,
        cg_location: np.ndarray,
        properties: RocketProperties,
        thrust: float,
    ) -> AeroPointSI:
        """Return the table's power-off aero plus the jet's relief of the base.

        The relief changes Cx so the coefficients still explain the force.
        """
        table = properties.aero_table
        off = super().aero(
            time, air_velocity, conditions, to_body, cg_location, properties, 0.0
        )
        q = off.dynamic_pressure
        if thrust <= 0.0 or self.model == "coast" or q <= 0.0:
            return off
        if self.model == "ras":
            on = super().aero(
                time, air_velocity, conditions, to_body, cg_location, properties, thrust
            )
            *_, pj, pc = self._jet(thrust, conditions, properties)
            s = ap02.nozzle_flow_fade(pj, pc)
            cx = off.coefficients.cx + s * (on.coefficients.cx - off.coefficients.cx)
        else:
            delta = self._relief(off.mach, thrust, q, conditions, table, properties)
            cx = off.coefficients.cx + delta / (q * table.reference_area_m2)
        c = replace(off.coefficients, cx=cx)
        force, torque = coefficient_loads(c, q, table, cg_location)
        return off._replace(coefficients=c, force=force, torque=torque)

    def _nozzle(self, properties: RocketProperties) -> tuple[float, float]:
        """Return the jet exit area in m**2 and the Mach it leaves at."""
        exit_area = float(properties.engine.nozzle_exit_area.m_as("m**2"))  # type: ignore[attr-defined]
        if exit_area <= 0.0:
            raise ValueError("PowerOnBaseDrag needs an engine with a nozzle_exit_area")
        throat = ap02.circle_area(float(self.throat_diameter.m_as("m")))
        return exit_area, ap02.jet_mach(exit_area / throat, self.exhaust_gamma)

    def _jet(
        self,
        thrust: float,
        conditions: AtmosphereConditions,
        properties: RocketProperties,
    ) -> tuple[float, float, float, float]:
        """Return exit area, jet Mach, P_j / P_inf and P_c / P_inf."""
        exit_area, mach_j = self._nozzle(properties)
        pj = ap02.jet_pressure_ratio(
            thrust, conditions.pressure, exit_area, self.exhaust_gamma, mach_j
        )
        return (
            exit_area,
            mach_j,
            pj,
            ap02.chamber_pressure_ratio(pj, self.exhaust_gamma, mach_j),
        )

    def _relief(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        mach: float,
        thrust: float,
        q: float,
        conditions: AtmosphereConditions,
        table: AeroTable,
        properties: RocketProperties,
    ) -> float:
        """Return the extra force along +X in N from the jet on the base."""
        area_ref = table.reference_area_m2
        d_ref = math.sqrt(4.0 * area_ref / math.pi)
        d_base = float(self.base_diameter.m_as("m"))
        base_ratio = d_base / d_ref
        exit_area, mach_j, pj, pc = self._jet(thrust, conditions, properties)
        s = ap02.nozzle_flow_fade(pj, pc)
        jet_ratio = math.sqrt(4.0 * exit_area / math.pi) / d_ref
        p_inf = conditions.pressure
        # Force the table already holds from the base, along +X (suction: negative)
        cp_off = -ap02.power_off_cpb(mach)
        off_force = cp_off * q * area_ref * base_ratio**3
        if self.model == "blend":
            m = _smoothstep(mach, 1.2, 1.6)
            share = (1.0 - m) + m * (jet_ratio / base_ratio) ** 2
            relief = -share * off_force
        else:
            ratio = ap02.base_pressure_ratio(
                mach,
                thrust,
                p_inf,
                area_ref=area_ref,
                base_ratio=base_ratio,
                jet_ratio=jet_ratio,
                gamma_j=self.exhaust_gamma,
                mach_j=mach_j,
                pj_ratio=pj,
                exit_offset_ratio=float(self.exit_offset.m_as("m")) / d_base,
                boattail_scale=self.boattail_scale,
            )
            relief = (ratio - 1.0) * p_inf * area_ref * (
                base_ratio**2 - jet_ratio**2
            ) - off_force
            # Subsonic data is thin: scale it below Mach 0.9, back to 1 by 1.2
            relief *= 1.0 + (self.subsonic_scale - 1.0) * (
                1.0 - _smoothstep(mach, 0.9, 1.2)
            )
        # Weight M**2 keeps dCx = relief / q finite as the rocket starts from rest
        return float(s * min(mach / 0.3, 1.0) ** 2 * relief)
