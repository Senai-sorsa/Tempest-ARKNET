"""Correction of tabulated drag for the Reynolds number of the flight."""

import math
from dataclasses import dataclass
from functools import cached_property
from typing import Annotated

from flight_sim.environment.atmosphere import (
    AtmosphereConditions,
    StandardAtmosphere1976,
    dynamic_viscosity,
)
from flight_sim.units import Scalar, UnitChecked

# Reynolds number per unit Mach and length scales with density * a / mu
_SEA_LEVEL = StandardAtmosphere1976().conditions(0.0)
_SEA_LEVEL_RHO_A_OVER_MU = (
    _SEA_LEVEL.air_density
    * _SEA_LEVEL.speed_of_sound
    / dynamic_viscosity(_SEA_LEVEL.temperature)
)

# The flat plate value the RASAero II manual gives for its transition
_TRANSITION_REYNOLDS = 5e5

# Van Driest II for an adiabatic wall in air: (gamma - 1) / 2, the turbulent
# recovery factor and the viscosity's power of temperature
_GAMMA_TERM = 0.2
_RECOVERY_FACTOR = 0.89
_VISCOSITY_EXPONENT = 0.76


def _laminar(reynolds: float) -> float:
    """Return the Blasius mean skin friction of a flat plate."""
    return 1.328 / math.sqrt(reynolds)


def _turbulent(reynolds: float) -> float:
    """Return the Schultz-Grunow mean skin friction of a flat plate."""
    return 0.427 / math.pow(math.log10(reynolds) - 0.407, 2.64)


def _plate_friction(reynolds: float, all_turbulent: bool) -> float:
    """Return a flat plate's incompressible mean skin friction.

    Args:
        reynolds (float): Reynolds number on the plate's length.
        all_turbulent (bool): Whether the flow trips at the leading edge.

    Returns:
        float: Laminar up to transition, then turbulent less Prandtl's
            allowance for the laminar length.
    """
    if all_turbulent:
        # shortcut: held at the transition value as the law fails near Re 3,
        # upgrade if a tripped flight matters at such low Reynolds numbers
        return _turbulent(max(reynolds, _TRANSITION_REYNOLDS))
    if reynolds <= _TRANSITION_REYNOLDS:
        return _laminar(reynolds)
    return _turbulent(reynolds) - (_TRANSITION_REYNOLDS / reynolds) * (
        _turbulent(_TRANSITION_REYNOLDS) - _laminar(_TRANSITION_REYNOLDS)
    )


@dataclass(frozen=True)
class FinSet(UnitChecked):
    """All the fins at one station."""

    # Both sides of every fin
    wetted_area: Annotated[Scalar, "m**2"]

    mean_chord: Annotated[Scalar, "m"]
    thickness: Annotated[Scalar, "m"]


@dataclass(frozen=True)
class ReynoldsCorrection(UnitChecked):
    """Change in Cx moving an aero table's skin friction from sea-level air to
    the flight's.

    The table is for sea-level air at each Mach, as RASAero II gives it. The
    correction is the skin friction drag in the flight's air less that in
    sea-level air, from the rocket's geometry alone: no drag data goes in.

    Each surface is a flat plate on its own length: Schultz-Grunow turbulent,
    Blasius laminar and Prandtl's transition, moved to the flight's Mach by
    Van Driest II, and held at Hoerner's fully rough limit. Barrowman's form
    factors carry the plate to the body and fins. These are published
    correlations, not fits to RASAero II, whose own law is unpublished; it
    changes with altitude 10 to 25 % more than this does.
    """

    # The aero table's reference area
    reference_area: Annotated[Scalar, "m**2"]

    body_length: Annotated[Scalar, "m"]
    body_diameter: Annotated[Scalar, "m"]
    body_wetted_area: Annotated[Scalar, "m**2"]

    # Equivalent sand grain roughness, 0 for a smooth surface
    roughness: Annotated[Scalar, "m"]

    fins: tuple[FinSet, ...] = ()

    # The flow trips at the nose, as RASAero II's All Turbulent Flow option
    all_turbulent: bool = False

    def __post_init__(self) -> None:
        """Check the geometry.

        Raises:
            ValueError: If an area or length is not positive.
        """
        super().__post_init__()
        sizes = [self.reference_area, self.body_length, self.body_diameter]
        sizes += [self.body_wetted_area]
        sizes += [fin.mean_chord for fin in self.fins]
        sizes += [fin.wetted_area for fin in self.fins]
        if any(size.magnitude <= 0.0 for size in sizes):
            raise ValueError("ReynoldsCorrection needs positive areas and lengths")

    @cached_property
    def _surfaces(self) -> tuple[tuple[float, float, float], ...]:
        """Weight on Cf, length in m and rough limit of Cf for each surface."""
        reference_m2 = self.reference_area.m_as("m**2")
        roughness_m = self.roughness.m_as("m")
        length_m = self.body_length.m_as("m")
        fineness = length_m / self.body_diameter.m_as("m")
        surfaces = [
            (
                self.body_wetted_area.m_as("m**2") * (1.0 + 0.5 / fineness),
                length_m,
            )
        ]
        for fin in self.fins:
            chord_m = fin.mean_chord.m_as("m")
            form_factor = 1.0 + 2.0 * fin.thickness.m_as("m") / chord_m
            surfaces.append((fin.wetted_area.m_as("m**2") * form_factor, chord_m))
        return tuple(
            (area / reference_m2, length, 0.032 * (roughness_m / length) ** 0.2)
            for area, length in surfaces
        )

    def _skin_friction_cx(self, reynolds_per_m: float, mach: float) -> float:
        """Return the skin friction drag coefficient, positive for drag.

        Args:
            reynolds_per_m (float): Reynolds number per metre, above zero.
            mach (float): Mach number, above zero.

        Returns:
            float: Skin friction drag over the reference area.
        """
        recovery = _GAMMA_TERM * _RECOVERY_FACTOR * mach**2
        friction_factor = (
            recovery / math.asin(math.sqrt(recovery / (1.0 + recovery))) ** 2
        )
        reynolds_factor = (1.0 + recovery) ** -_VISCOSITY_EXPONENT / friction_factor
        return sum(
            weight
            * max(
                _plate_friction(
                    reynolds_per_m * length * reynolds_factor, self.all_turbulent
                ),
                rough_limit,
            )
            / friction_factor
            for weight, length, rough_limit in self._surfaces
        )

    def __call__(self, mach: float, air: AtmosphereConditions) -> float:
        """Return the change in Cx at a Mach number in the flight's air.

        Args:
            mach (float): Mach number.
            air (AtmosphereConditions): Air the vehicle flies through.

        Returns:
            float: Change in Cx, zero without air or speed. Cx is negative for
                drag, so more drag is a negative change.
        """
        if air.air_density <= 0.0 or mach <= 0.0:
            return 0.0
        flight = (
            air.air_density * air.speed_of_sound / dynamic_viscosity(air.temperature)
        )
        return self._skin_friction_cx(
            mach * _SEA_LEVEL_RHO_A_OVER_MU, mach
        ) - self._skin_friction_cx(mach * flight, mach)
