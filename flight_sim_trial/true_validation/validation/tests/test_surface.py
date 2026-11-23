"""Pure math of the drag surface, the matrix mapping and the FS-RAS split: nothing here flies."""
import runpy
from pathlib import Path

import numpy as np
import pytest

from fsval.exhaust import EPS_TYPICAL, from_pressure
from fsval.matrix import combos, effective, tag
from fsval.surface import altitudes, changes
from fsval.surface_lookup import Surface
from fsval.trace import LBF_N, compare, impulse
from fsval.units import FT, LB

S = Surface([-2.0, 0.0], [0.5, 1.0, 2.0], [[0.0, 0.1, 0.2], [0.4, 0.5, 0.8]])


def test_lookup_hits_grid_midpoints_and_holds_at_the_ends():
    assert S(0.0, 2.0) == pytest.approx(0.8)
    assert S(-2.0, 0.5) == pytest.approx(0.0)
    assert S(-1.0, 1.5) == pytest.approx((0.15 + 0.65) / 2)
    assert S(-9.0, 0.1) == S(-2.0, 0.5)
    assert S(9.0, 9.0) == S(0.0, 2.0)


def test_lookup_survives_how_the_worker_loads_it():
    path = Path(__file__).parents[1] / "src" / "fsval" / "surface_lookup.py"
    loaded = runpy.run_path(str(path))["Surface"]([0.0, 1.0], [0.0, 1.0], [[0.0, 0.0], [1.0, 1.0]])
    assert loaded(0.5, 0.5) == pytest.approx(0.5)


def test_unsorted_axis_is_refused():
    with pytest.raises(ValueError):
        Surface([0.0, -1.0], [0.5, 1.0], [[0.0, 0.0], [0.0, 0.0]])


def test_altitudes_cover_the_top():
    assert altitudes(1000) == [0, 2500]
    assert altitudes(2500) == [0, 2500]
    assert altitudes(142000)[-1] == 150000
    with pytest.raises(ValueError):
        altitudes(1e6)


def test_changes_are_from_the_base():
    machs, dcx = changes({1.0: -0.5, 0.5: -0.4}, [{0.5: -0.4, 1.0: -0.5}, {0.5: -0.5, 1.0: -0.7}])
    assert machs == [0.5, 1.0]
    assert dcx == [[0.0, 0.0], [pytest.approx(-0.1), pytest.approx(-0.2)]]
    with pytest.raises(ValueError):
        changes({1.0: 0.0}, [{2.0: 0.0}])


def test_effective_maps_surface_onto_one_run_and_old_tags_survive():
    c = {"table": "surface", "re": 0, "po": 1, "wind": 1, "nozzle": "kb", "g": 0, "fincan": 0}
    real = effective(c, False, 0.0, None, False)
    assert (real["re"], real["wind"], real["nozzle"]) == (1, 0, "none")
    assert effective({**c, "table": "sea"}, True, 2.0, None, False)["re"] == 0
    assert tag({**c, "table": "sea"}) == "sea_re0_po1_w1_kb"
    assert tag({**c, "g": 1}) == "surface_re0_po1_w1_kb_gras"
    assert tag({**c, "fincan": 1}) == "surface_re0_po1_w1_kb_fc"
    assert effective({**c, "fincan": 1}, False, 0.0, None, False)["fincan"] == 0
    assert effective({**c, "fincan": 1}, False, 0.0, None, True)["fincan"] == 1
    assert len(combos()) == 720


def test_base_drag_runs_always_have_a_nozzle():
    c = {"table": "sea", "re": 1, "po": "ap02", "wind": 0, "nozzle": "none", "g": 0, "fincan": 0}
    assert effective(c, False, 0.0, None, False)["nozzle"] == "linear"
    assert tag(c) == "sea_re1_poap02_w0_none"
    assert effective({**c, "po": 1}, False, 0.0, None, False)["nozzle"] == "none"


def test_exhaust_estimate_balances_thrust_and_keeps_the_given_exit():
    area = lambda d_mm: np.pi * (d_mm / 2000) ** 2
    free = from_pressure(500.0, 1000.0, 7e6, 0.0, 1.22)
    assert free["eps"] == pytest.approx(EPS_TYPICAL)
    assert free["pc_avg_MPa"] == pytest.approx(3.5)
    fixed = from_pressure(500.0, 1000.0, 7e6, area(free["exit_mm"]), 1.22)
    assert fixed["throat_mm"] == pytest.approx(free["throat_mm"], rel=1e-3)
    assert from_pressure(500.0, 1000.0, 1e6, area(5.0), 1.22) is None


def test_compare_finds_each_planted_gap():
    t = np.arange(0.0, 20.0, 0.1)
    area, cd, rho = 0.01, 0.5, 1.0
    thrust = np.where(t < 2.0, 1000.0, 0.0)
    mass = 20.0 - 2.0 * np.minimum(t, 2.0)
    speed = np.maximum(300.0 - 15.0 * np.abs(t - 2.0), 1.0)
    alt = 10.0 * t * (20.0 - t)
    mach = speed / 300.0
    q = 0.5 * rho * speed**2
    h = {"Time (sec)": t, "Altitude (ft)": alt / FT + 2000.0, "Mach Number": mach, "CD": np.full_like(t, cd),
         "Velocity (ft/sec)": speed / FT, "Thrust (lb)": thrust / LBF_N, "Weight (lb)": mass / LB,
         "Drag (lb)": q * cd * area / LBF_N, "Angle of Attack (deg)": np.full_like(t, -2.0)}
    alpha = np.full_like(t, -3.0)
    alpha[:5] = np.nan
    s = {"t": t, "alt_agl": alt * 1.02, "speed": speed, "mach": mach, "thrust": thrust * 1.03, "mass": mass * 1.04,
         "force_x": -q * cd * 1.05 * area, "q": q, "rho": np.full_like(t, rho * 1.06), "alpha_deg": alpha}
    r = compare(h, {k: v.tolist() for k, v in s.items()}, area)
    assert r["apogee_gap_pct"] == pytest.approx(2.0, abs=0.01)
    assert r["impulse_gap_pct"] == pytest.approx(3.0, abs=0.01)
    assert r["liftoff_mass_gap_pct"] == pytest.approx(4.0, abs=0.01)
    assert r["coast_cd_gap_pct"] == pytest.approx(5.0, abs=0.01)
    assert r["density_gap_pct"] == pytest.approx(6.0, abs=0.01)
    assert (r["max_alpha_deg"], r["ras_max_alpha_deg"]) == (3.0, 2.0)
    assert impulse(np.array([0.0, 1.0]), np.array([0.0, 2.0])) == 1.0
