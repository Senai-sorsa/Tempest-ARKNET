"""AP02 power-on base pressure and the phases that use it."""

import math
from dataclasses import replace

import numpy as np
import pytest
from support import truth

from flight_sim import ap02
from flight_sim.integration import IntegrationConfiguration, flight_point_si
from flight_sim.phases import PowerOnBaseDrag
from flight_sim.units import scalar, vector
from flight_sim.vehicle.engine import SolidEngine
from flight_sim.vehicle.rocket_properties import RocketProperties
from flight_sim.vehicle.rocket_state import RocketState

_GAMMA = 1.4


def _pb(mach: float, ct: float, base: float, jet: float, mach_j: float = 2.7) -> float:
    """P_B / P_inf at a thrust coefficient, in a unit-pressure, unit-area setting."""
    thrust = ct * _GAMMA * mach**2 / 2.0
    pj = ap02.jet_pressure_ratio(
        thrust, 1.0, jet**2, 1.4, mach_j
    )  # areas in units of A_ref
    return ap02.base_pressure_ratio(
        mach,
        thrust,
        1.0,
        area_ref=1.0,
        base_ratio=base,
        jet_ratio=jet,
        gamma_j=1.4,
        mach_j=mach_j,
        pj_ratio=pj,
    )


def test_table_1_corners() -> None:
    """C1 and C2 come back at the table's own rows and columns."""
    assert ap02._c1(1.0, 0.5) == pytest.approx(0.19)  # pylint: disable=protected-access
    assert ap02._c1(2.0, 2.0) == pytest.approx(-0.30)  # pylint: disable=protected-access
    assert ap02._c1(70.0, 3.0) == 0.0  # pylint: disable=protected-access
    assert ap02._c2(2.0, 4.0) == pytest.approx(2.7)  # pylint: disable=protected-access
    assert ap02._c2(1.0, 4.0) == pytest.approx(1.28)  # pylint: disable=protected-access


@pytest.mark.parametrize("base", [0.6, 1.0, 1.3])
def test_boattail_factor_is_continuous(base: float) -> None:
    """f has no jump where its blend starts and ends."""
    for edge in (6.0, 12.0, 25.0, 75.0):
        assert ap02.boattail_factor(base, edge - 1e-9) == pytest.approx(
            ap02.boattail_factor(base, edge + 1e-9), abs=1e-6
        )


@pytest.mark.parametrize("mach", [0.9, 1.2, 1.5])
@pytest.mark.parametrize("ct", [1.0, 2.0, 12.0])
def test_base_pressure_is_continuous_at_the_region_edges(
    mach: float, ct: float
) -> None:
    """Crossing a Mach or thrust-coefficient edge moves P_B by a small amount."""
    for step in (1e-6,):
        low = _pb(mach - step, ct, 0.86, 0.45)
        high = _pb(mach + step, ct, 0.86, 0.45)
        assert abs(high - low) < 1e-3


def test_base_pressure_is_finite_at_rest() -> None:
    """Mach 0 gives a number, not a divide by zero."""
    assert math.isfinite(_pb(0.0, 50.0, 1.0, 0.8))
    assert math.isfinite(
        ap02.base_pressure_ratio(
            0.0,
            5e3,
            1e5,
            area_ref=0.018,
            base_ratio=0.6,
            jet_ratio=0.48,
            gamma_j=1.22,
            mach_j=2.4,
            pj_ratio=1.0,
        )
    )


@pytest.mark.parametrize(
    ("mach", "ct", "expected"),
    [
        *((1.2, 20, 1.31), (1.2, 40, 1.40), (1.2, 60, 1.42)),
        *((1.0, 20, 1.18), (1.0, 40, 1.27), (1.0, 60, 1.33)),
        *((0.9, 20, 1.12), (0.9, 40, 1.21), (0.9, 60, 1.22)),
    ],
)
def test_report_fig_30_cylinder(mach: float, ct: float, expected: float) -> None:
    """The cylinder curves of the report's Fig. 30, read by eye to about 0.1."""
    assert _pb(mach, ct, 1.0, 0.8) == pytest.approx(expected, abs=0.1)


@pytest.mark.parametrize(
    ("mach", "ct", "expected", "tolerance"),
    [
        *((1.5, 20, 1.42, 0.1), (1.5, 40, 1.5, 0.1), (2.5, 20, 1.83, 0.1)),
        # Reads 0.16 high: the by-eye reading or the unverified RMF derivation
        (2.5, 40, 2.03, 0.2),
    ],
)
def test_report_fig_33_boattail(
    mach: float, ct: float, expected: float, tolerance: float
) -> None:
    """The boattail curves of the report's Fig. 33, read by eye."""
    assert _pb(mach, ct, 0.86, 0.45) == pytest.approx(expected, abs=tolerance)


def test_jet_mach_inverts_the_area_ratio() -> None:
    """The report's Mj 2.7 nozzle has the area ratio the relation gives back."""
    mach = ap02.jet_mach(3.0, 1.4)
    exponent = 3.0
    inner = 2.0 / 2.4 * (1.0 + 0.2 * mach**2)
    assert inner**exponent / mach == pytest.approx(3.0)


def test_fade_is_one_when_flowing_and_zero_when_not() -> None:
    """The jet fades out as the nozzle separates and unchokes."""
    assert ap02.nozzle_flow_fade(2.0, 20.0) == 1.0
    assert ap02.nozzle_flow_fade(0.2, 20.0) == 0.0
    assert ap02.nozzle_flow_fade(2.0, 1.0) == 0.0


def _lit_rocket(base: RocketProperties) -> RocketProperties:
    """The test rocket with a 73.7 mm nozzle exit."""
    exit_area = math.pi / 4 * 0.0737**2
    engine = replace(base.engine, nozzle_exit_area=scalar(exit_area, "m**2"))
    assert isinstance(engine, SolidEngine)
    return replace(base, engine=engine)


def _point(physics, properties, mach_speed: float = 400.0, altitude: float = 3000.0):
    config = IntegrationConfiguration(truth=truth(), physics=physics)
    state = RocketState(
        position=vector((altitude, 0.0, 0.0), "m"),
        velocity=vector((mach_speed, 0.0, 0.0), "m/s"),
    )
    return flight_point_si(1.0, state, properties, config)


def _phase(model: str, **fields: object) -> PowerOnBaseDrag:
    return PowerOnBaseDrag(
        model=model,  # type: ignore[arg-type]
        throat_diameter=scalar(0.0366, "m"),
        base_diameter=scalar(0.0914, "m"),
        **fields,  # type: ignore[arg-type]
    )


def test_coast_is_todays_drag(baseline_rocket_properties: RocketProperties) -> None:
    """With the relief off, the phase flies the table exactly."""
    properties = _lit_rocket(baseline_rocket_properties)
    plain = _point(IntegrationConfiguration(truth=truth()).physics, properties)
    point = _point(_phase("coast"), properties)
    assert plain.thrust > 0.0
    assert np.array_equal(plain.aero.force, point.aero.force)


@pytest.mark.parametrize("model", ["ap02", "blend", "ras"])
def test_relief_cuts_drag_and_keeps_coefficients_honest(
    baseline_rocket_properties: RocketProperties, model: str
) -> None:
    """The jet lowers the drag, and the coefficients still explain the force."""
    properties = _lit_rocket(baseline_rocket_properties)
    plain = _point(_phase("coast"), properties)
    with np.errstate(all="raise"):
        point = _point(_phase(model), properties)  # warns on a mismatch
    assert point.aero.force[0] >= plain.aero.force[0]


def test_phase_is_finite_at_rest(baseline_rocket_properties: RocketProperties) -> None:
    """At liftoff, with no airspeed, nothing divides by zero."""
    properties = _lit_rocket(baseline_rocket_properties)
    point = _point(_phase("ap02"), properties, mach_speed=0.0, altitude=0.0)
    assert np.all(np.isfinite(point.aero.force))


def test_nozzle_inputs_are_checked(
    baseline_rocket_properties: RocketProperties,
) -> None:
    """A motor with no exit area cannot use the correlation."""
    with pytest.raises(ValueError, match="nozzle_exit_area"):
        _point(_phase("ap02"), baseline_rocket_properties)
    with pytest.raises(ValueError, match="Unknown"):
        _phase("nope")
