"""Readers v2: parity with the original readers, exactness on the 10 m grid, frames / units / reference / direction, above_top policies, F3 schema, F10 anchor."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tests"))
from tempest_weather import _core                                     # noqa: E402
from tempest_weather_v2.readers import Atmosphere, AboveTopError, normalise_samples   # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind        # noqa: E402

NH = _core.NH
ELEV = 1400.6


def make_samples(n=6, seed=0, with_w=True):
    rng = np.random.default_rng(seed)
    z = np.asarray(_core.HEIGHTS, float)
    T = 305 - 0.0065 * z[None] + rng.normal(0, 1, (n, NH))
    u = rng.normal(4, 3, (n, 1)) + np.linspace(0, 20, NH)[None] + rng.normal(0, 0.5, (n, NH))
    v = rng.normal(0, 2, (n, NH))
    RH = np.clip(rng.normal(30, 10, (n, NH)), 1, 99)
    t2m, sp, rh2m = T[:, 0] + 0.5, np.full(n, 85000.0), RH[:, 0] - 2
    th = _core.thermo_column(z, T, RH, sp, t_sfc=t2m, rh_sfc=rh2m, z_sfc=ELEV)
    s = dict(u=u, v=v, T=T, RH=RH, p=th["p"], t2m=t2m, sp=sp, rh2m=rh2m, height_agl=z.astype(np.float32), height_asl=(ELEV + z).astype(np.float32))
    if with_w:
        s["w"] = rng.normal(0, 0.1, (n, NH))
    return s


def test_every_model_height_is_a_multiple_of_10_m_so_the_10m_grid_is_exact():
    assert np.all(np.asarray(_core.HEIGHTS) % 10 == 0)
    s = make_samples()
    atm = Atmosphere(s, 2)
    for j in (0, 5, 12, 30, 43):
        zasl = ELEV + float(_core.HEIGHTS[j])
        assert np.allclose(atm.wind(zasl)[1:], [s["u"][2, j], s["v"][2, j]], atol=1e-4)
        assert abs(atm.air(zasl)[0] - s["T"][2, j]) < 1e-3
        assert abs(atm.air(zasl)[1] / s["p"][2, j] - 1) < 1e-5


def test_matches_the_original_readers_between_and_above_the_grid():
    s = make_samples()
    s_old = dict(s)
    old_a, old_w = TempestAtmosphere(s_old, 3), TempestWind(s_old, 3)      # both with the pad node and geopotential tail (the defaults since 2026-11-08)
    new = Atmosphere(s, 3)
    rng = np.random.default_rng(1)
    for alt in np.concatenate([ELEV + rng.uniform(0, 17900, 60), [ELEV, ELEV + 18000, 21000, 30000, 45000, 60000]]):
        c = old_a.conditions(alt)
        n = new.conditions(alt)
        assert abs(n.temperature - c.temperature) < 0.02, alt
        assert abs(n.pressure / c.pressure - 1) < 1e-4, alt
        assert abs(n.air_density / c.air_density - 1) < 5e-4, alt
        assert abs(n.speed_of_sound / c.speed_of_sound - 1) < 5e-4, alt
        assert np.allclose(new.velocity(alt), old_w.velocity(alt), atol=2e-3), alt


def test_vectorised_calls_equal_scalar_calls():
    s = make_samples()
    atm = Atmosphere(s, 1)
    alts = ELEV + np.array([0.0, 7.0, 123.0, 4567.0, 12000.0, 17990.0, 25000.0])
    w, a = atm.wind_many(alts), atm.air_many(alts)
    for i, z in enumerate(alts):
        assert np.allclose(w[i], atm.wind(z)) and np.allclose(a[i], atm.air(z))


def test_frames_units_reference_direction():
    s = make_samples()
    base = Atmosphere(s, 0)
    z = ELEV + 3000.0
    up, east, north = base.wind(z)
    assert np.allclose(Atmosphere(s, 0, frame="enu").wind(z), [east, north, up])
    assert np.allclose(Atmosphere(s, 0, frame="ned").wind(z), [north, east, -up])
    assert np.allclose(Atmosphere(s, 0, direction="from").wind(z), -base.wind(z))
    agl = Atmosphere(s, 0, reference="agl")
    assert np.allclose(agl.wind(3000.0), base.wind(z)) and np.allclose(agl.air(3000.0), base.air(z))
    us = Atmosphere(s, 0, units="us")
    T, p, rho, a = base.air(z)
    Tu, pu, rhou, au = us.air(z / 0.3048)
    assert abs(Tu - ((T - 273.15) * 1.8 + 32)) < 1e-2 and abs(pu - p / 3386.389) < 1e-3 and abs(au - a / 0.3048) < 0.05 and abs(rhou - rho / 515.378819) < 1e-6
    assert np.allclose(us.wind(z / 0.3048), base.wind(z) / 0.3048, atol=1e-3)
    for bad in (dict(frame="xyz"), dict(units="km"), dict(reference="msl"), dict(direction="up"), dict(above_top="fly")):
        with pytest.raises(ValueError):
            Atmosphere(s, 0, **bad)


def test_above_top_policies_and_pad_hold():
    s = make_samples()
    top = ELEV + 18000.0
    hold, decay, clim, rais = (Atmosphere(s, 0, above_top=p) for p in ("hold", "decay", "climatology", "raise"))
    assert np.allclose(hold.wind(top + 5000), hold.wind(top), atol=1e-4)
    assert np.linalg.norm(decay.wind(top + 20000)) < 0.05 * np.linalg.norm(decay.wind(top)) + 1e-3
    assert abs(hold.air(top + 100)[0] - hold.air(top)[0]) < 1.0 and hold.air(40000)[1] < hold.air(30000)[1] < hold.air(top)[1]
    with pytest.raises(AboveTopError):
        rais.wind(top + 1.0)
    with pytest.raises(AboveTopError):
        rais.air(top + 1.0)
    below = hold.air(ELEV - 50.0)                                     # below the pad: the pad values are held
    assert np.allclose(below, hold.air(ELEV))


def test_pad_node_gives_the_surface_state_and_old_behaviour_is_reachable():
    s = make_samples()
    atm = Atmosphere(s, 4)
    T, p, _, _ = atm.air(ELEV)
    assert abs(T - s["t2m"][4]) < 1e-3 and abs(p - s["sp"][4]) < 0.5
    assert abs(atm.wind(ELEV)[0]) < 1e-5
    old = Atmosphere(s, 4, pad_node=False)
    assert abs(old.air(ELEV)[0] - s["T"][4, 0]) < 1e-3


def test_schema_aliases_and_anchor_and_missing_w():
    s = make_samples(with_w=False)
    s2 = {k: v for k, v in s.items() if k not in ("height_asl",)}
    s2["z"] = s2.pop("height_agl")
    s2["elevation_m"] = ELEV                                         # the producers' schema (z, elevation_m)
    n = normalise_samples(s2)
    assert np.allclose(n["height_asl"], ELEV + n["height_agl"])
    atm = Atmosphere(s2, 0)
    assert abs(atm.wind(ELEV + 500)[0]) < 1e-9                       # no w in the samples: zero updraft
    with pytest.raises(KeyError):
        normalise_samples({"u": 1})
    atm.anchor(ELEV + 5)
    with pytest.raises(ValueError, match="site elevation"):
        atm.anchor(ELEV + 50)
    atm.anchor(ELEV + 50, on_mismatch="shift")
    assert abs(atm.elevation_m - (ELEV + 50)) < 1e-9


def test_openrocket_csv_export(tmp_path):
    s = make_samples()
    p = Atmosphere(s, 0).to_openrocket_csv(str(tmp_path / "p.csv"), step_m=500.0)
    rows = open(p).read().strip().splitlines()
    assert rows[0] == "altitude_m,temp_K,pressure_Pa,wind_speed_ms,wind_from_deg" and len(rows) > 30
    first = rows[1].split(",")
    assert abs(float(first[0]) - ELEV) < 0.1 and 0 <= float(first[4]) <= 360


def test_standard_air_keeps_the_wind_and_matches_the_1976_atmosphere():
    import numpy as np
    from tempest_weather_v2.readers import Atmosphere, standard_air_samples
    n, H = 3, np.array([10.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 3000.0, 8000.0])
    rng = np.random.default_rng(0)
    s = dict(height_agl=H, elevation_m=1401.0, u=rng.normal(size=(n, len(H))), v=rng.normal(size=(n, len(H))), T=np.full((n, len(H)), 300.0), RH=np.full((n, len(H)), 50.0), p=np.full((n, len(H)), 80000.0),
             t2m=np.full(n, 310.0), sp=np.full(n, 86000.0), rh2m=np.full(n, 30.0))
    model, std = Atmosphere(s, 1), Atmosphere(s, 1, air="standard")
    assert std.air_source == "standard"
    for alt in (1401.0, 2500.0, 5000.0):
        assert model.wind(alt) == pytest.approx(std.wind(alt))                    # the wind is untouched
    T, p, rho, a = std.air(1401.0)
    assert T == pytest.approx(288.15 - 0.0065 * 1400.0, abs=0.2) and p == pytest.approx(85600.0, rel=0.004) and rho == pytest.approx(1.0689, rel=0.004)    # ISA at 1401 m: 279.05 K, about 856 hPa, 1.069 kg/m3
    assert std.air(5401.0)[0] == pytest.approx(288.15 - 0.0065 * 5400.0, abs=0.3)
    off = Atmosphere(s, 1, air="standard", delta_t_k=10.0)
    assert off.air(1401.0)[0] == pytest.approx(T + 10.0, abs=0.01) and off.air(1401.0)[2] < rho
    with pytest.raises(ValueError):
        Atmosphere(s, 1, air="bogus")
    assert standard_air_samples(s)["RH"].max() == 0.0


def test_perturbation_is_added_to_the_wind_and_zero_at_the_ground():
    import numpy as np
    from tempest_weather_v2.readers import Atmosphere
    H = np.array([10.0, 50.0, 100.0, 200.0, 500.0])
    s = dict(height_agl=H, elevation_m=1000.0, u=np.ones((1, 5)), v=np.zeros((1, 5)), T=np.full((1, 5), 290.0), RH=np.full((1, 5), 40.0), p=np.full((1, 5), 90000.0),
             t2m=np.array([291.0]), sp=np.array([91000.0]), rh2m=np.array([40.0]))
    pz = np.arange(10.0, 600.0, 2.0)
    base = Atmosphere(s, 0)
    pert = Atmosphere(s, 0, perturbation=dict(z=pz, east=np.full(len(pz), 2.0), north=np.full(len(pz), -1.0), up=np.full(len(pz), 0.5)))
    b, q = base.wind(1000.0 + 300.0), pert.wind(1000.0 + 300.0)                  # (up, east, north)
    assert q[1] - b[1] == pytest.approx(2.0, abs=1e-4) and q[2] - b[2] == pytest.approx(-1.0, abs=1e-4) and q[0] - b[0] == pytest.approx(0.5, abs=1e-4)
    assert pert.wind(1000.0)[1] == pytest.approx(base.wind(1000.0)[1], abs=1e-4)     # nothing is added at the pad node


def test_rocketpy_inputs_are_one_coherent_atmosphere_in_si():
    """M17: pairs of (altitude ASL, value) for pressure, temperature, wind_u (east) and wind_v (north) that agree with the reader's own lookups."""
    import numpy as np
    from tempest_weather_v2 import Launch
    atm = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=20, seed=2, units="us").atmospheres(20)[3]
    d = atm.rocketpy_inputs(step_m=250.0)
    assert set(d) == {"pressure", "temperature", "wind_u", "wind_v"}
    assert all(len(v) == len(d["pressure"]) > 10 for v in d.values())
    assert d["pressure"][0][0] == atm.elevation_m and d["pressure"][0][1] > 70000 and 250 < d["temperature"][0][1] < 330
    assert d["pressure"][-1][1] < d["pressure"][0][1]
    ref = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=20, seed=2, units="si").atmospheres(20)[3]
    alt, u = d["wind_u"][8]
    assert np.isclose(ref.wind(alt)[1], u, atol=1e-3) and np.isclose(ref.wind(alt)[2], d["wind_v"][8][1], atol=1e-3)


def test_rocketpy_inputs_reference_can_be_agl():
    from tempest_weather_v2 import Launch
    atm = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=20, seed=2).atmospheres(20)[1]
    a, g = atm.rocketpy_inputs(250.0), atm.rocketpy_inputs(250.0, reference="agl")
    assert g["pressure"][0][0] == 0.0 and abs(a["pressure"][0][0] - atm.elevation_m) < 1e-6 and a["wind_u"][5][1] == g["wind_u"][5][1]
    import pytest
    with pytest.raises(ValueError):
        atm.rocketpy_inputs(reference="x")
