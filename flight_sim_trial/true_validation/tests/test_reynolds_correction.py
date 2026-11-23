"""Reynolds number drag correction tests."""

from dataclasses import replace

import pytest
from support import truth

from flight_sim.config import build
from flight_sim.environment.atmosphere import StandardAtmosphere1976
from flight_sim.integration import IntegrationConfiguration, flight_point_si
from flight_sim.units import scalar, vector
from flight_sim.vehicle.reynolds_correction import (
    FinSet,
    ReynoldsCorrection,
    _plate_friction,
)
from flight_sim.vehicle.rocket_properties import RocketProperties
from flight_sim.vehicle.rocket_state import RocketState

_SEA_LEVEL = StandardAtmosphere1976().conditions(0.0)
_THIN = _SEA_LEVEL._replace(air_density=_SEA_LEVEL.air_density / 10)
_CORRECTION = ReynoldsCorrection(
    reference_area=scalar(0.01, "m**2"),
    body_length=scalar(3.0, "m"),
    body_diameter=scalar(0.11, "m"),
    body_wetted_area=scalar(1.0, "m**2"),
    roughness=scalar(0.0, "m"),
    fins=(FinSet(scalar(0.2, "m**2"), scalar(0.2, "m"), scalar(0.005, "m")),),
)


def test_plate_friction_matches_the_published_laws() -> None:
    """Blasius below transition, Schultz-Grunow above, Prandtl between."""
    assert _plate_friction(1e5, False) == pytest.approx(0.0042, abs=1e-5)
    assert _plate_friction(1e7, True) == pytest.approx(0.00294, abs=1e-5)
    # Laminar up to transition, so a long plate sits below all-turbulent
    assert _plate_friction(1e7, False) == pytest.approx(0.00294 - 0.00016, abs=2e-5)
    # Continuous at transition
    assert _plate_friction(5.0001e5, False) == pytest.approx(
        _plate_friction(5e5, False), rel=1e-3
    )


def test_correction_is_zero_at_sea_level_and_without_air_or_speed() -> None:
    """The table already holds sea-level friction."""
    assert _CORRECTION(0.5, _SEA_LEVEL) == pytest.approx(0.0)
    assert _CORRECTION(0.5, _THIN._replace(air_density=0.0)) == 0.0
    assert _CORRECTION(0.0, _THIN) == 0.0


def test_thin_air_adds_drag_and_compressibility_shrinks_it() -> None:
    """Skin friction rises as the Reynolds number falls, less so at speed."""
    subsonic, supersonic = _CORRECTION(0.5, _THIN), _CORRECTION(3.0, _THIN)
    assert subsonic < 0.0
    assert subsonic < supersonic < 0.0


def test_a_fully_rough_surface_stops_changing_with_reynolds_number() -> None:
    """Cf holds at the rough limit until the air is thin enough to leave it."""
    rough = replace(_CORRECTION, roughness=scalar(0.01, "m"))
    assert abs(rough(3.0, _THIN)) < abs(_CORRECTION(3.0, _THIN))
    assert rough(3.0, _THIN) == pytest.approx(0.0)


def test_tripped_flow_has_its_own_curve() -> None:
    """Tripped flow never goes laminar, so it keeps the turbulent trend."""
    tripped = replace(_CORRECTION, all_turbulent=True)
    assert tripped(0.5, _THIN) != pytest.approx(_CORRECTION(0.5, _THIN))
    assert tripped(0.5, _THIN) < 0.0


def test_zero_size_is_refused() -> None:
    """A surface needs a length to have a Reynolds number."""
    with pytest.raises(ValueError, match="positive"):
        replace(_CORRECTION, body_length=scalar(0.0, "m"))


def test_correction_builds_from_toml_tables() -> None:
    """A sim file gives the geometry, with its fins as a list of tables."""
    correction = build(
        {
            "type": "flight_sim.vehicle.reynolds_correction.ReynoldsCorrection",
            "reference_area": "0.01 m**2",
            "body_length": "3 m",
            "body_diameter": "0.11 m",
            "body_wetted_area": "1 m**2",
            "roughness": "0 in",
            "fins": [
                {
                    "wetted_area": "0.2 m**2",
                    "mean_chord": "0.2 m",
                    "thickness": "5 mm",
                }
            ],
        },
        ReynoldsCorrection | None,
    )
    assert correction(0.5, _THIN) == pytest.approx(_CORRECTION(0.5, _THIN))


def test_rocket_correction_adds_to_the_flight_cx(
    unpowered_rocket_properties: RocketProperties,
) -> None:
    """A rocket with a correction flies its table's Cx plus the correction."""
    config = IntegrationConfiguration(truth=truth())
    # High up, where the air is thin enough to correct
    state = RocketState(
        position=vector((5000.0, 0.0, 0.0), "m"),
        velocity=vector((100.0, 5.0, 0.0), "m/s"),
    )
    corrected = replace(unpowered_rocket_properties, reynolds_correction=_CORRECTION)

    plain = flight_point_si(0.0, state, unpowered_rocket_properties, config)
    point = flight_point_si(0.0, state, corrected, config)
    change = _CORRECTION(point.aero.mach, point.environment.atmosphere)

    assert change != 0.0
    assert point.aero.coefficients.cx == pytest.approx(
        plain.aero.coefficients.cx + change
    )
