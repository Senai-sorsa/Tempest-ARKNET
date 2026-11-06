"""Stage 6, modules 3-5: Dryden turbulence and gust, barometric altimeter bias and refractivity, acoustic rays. Physics checks against closed forms."""
import numpy as np

from tempest_weather.flight import acoustics, avionics, dryden


def test_dryden_variance_and_correlations_match_the_theory():
    z = np.arange(10.0, 3001.0, 10.0)
    N = 400
    u = np.tile(np.full(len(z), 6.0), (N, 1))
    v = np.zeros_like(u)
    T = np.tile(288.0 - 0.0065 * z, (N, 1))
    f = dryden.synthesize(z, u, v, T, dz=2.0, seed=3)
    zf = f["z"]
    sel = (zf > 120) & (zf < 140)                                                         # a thin layer where sigma and L are nearly constant
    i0 = np.flatnonzero(sel)[0]
    sig_w = f["sigma_w"][0, i0]
    assert abs(f["w_turb"][:, sel].std() / sig_w - 1) < 0.12                              # variance of the along-path component
    sig_u = f["sigma_u"][0, i0]
    assert abs(f["u_turb"][:, sel].std() / sig_u - 1) < 0.15                              # and of the transverse components
    L_w, L_u = f["L_w"][0, i0], f["L_u"][0, i0]
    lag = 20.0                                                                             # metres
    k = int(lag / 2.0)
    c_w = np.corrcoef(f["w_turb"][:, i0], f["w_turb"][:, i0 + k])[0, 1]
    assert abs(c_w - np.exp(-lag / L_w)) < 0.1                                             # first-order: exp(-d / L)
    c_u = np.corrcoef(f["u_turb"][:, i0], f["u_turb"][:, i0 + k])[0, 1]
    assert abs(c_u - (1 - lag / (2 * L_u)) * np.exp(-lag / L_u)) < 0.12                    # second-order: (1 - d / 2L) exp(-d / L)
    assert np.array_equal(f["u_turb"], dryden.synthesize(z, u, v, T, dz=2.0, seed=3)["u_turb"])


def test_one_minus_cos_gust_shape_and_clear_air_turbulence_trigger():
    z = np.linspace(0, 1000, 2001)
    g = dryden.one_minus_cos(z, 300.0, 50.0, 8.0)
    assert g.max() == 8.0 or abs(g.max() - 8.0) < 1e-6
    assert g[z < 300].max() == 0 and g[z > 400].max() == 0 and abs(g[np.argmin(np.abs(z - 350))] - 8.0) < 1e-6
    zc = np.arange(10.0, 4001.0, 100.0)
    u = np.tile(5 + 0.025 * zc, (1, 1))                                                    # strong shear (25 m/s per km) with a steep lapse rate: Ri below 0.25
    v = np.zeros_like(u)
    T_unstable = np.tile(288 - 0.007 * zc, (1, 1))
    T_calm = np.tile(288 - 0.0035 * zc, (1, 1))
    e = dryden.envelopes(zc, u, v, T_unstable)
    e0 = dryden.envelopes(zc, u, v, T_calm)
    k = int(np.argmin(np.abs(zc - 3000)))
    assert (e["ri"][0, k] < 0.25) and (e0["ri"][0, k] > 0.25)
    assert e["sigma_w"][0, k] > 4 * e0["sigma_w"][0, k] and e["sigma_w"][0, k] > 0.15      # clear-air turbulence appears only where Ri is small
    f = dryden.synthesize(zc, u, v, T_unstable, dz=5.0, seed=1, gust=(0.5, 0.5, 0.0, 0.5))
    assert np.abs(f["gust_u"]).max() > 5.0 and np.abs(f["gust_v"]).max() < 1e-9           # direction 0: along u


def test_barometric_altimeter_bias_signs_and_isa_consistency():
    z = np.array([0.0, 500, 1000, 3000, 8000, 12000.0])
    isa_T = np.where(z < 11000, 288.15 - 0.0065 * z, 216.65)
    isa_p = np.where(z < 11000, 101325 * (isa_T / 288.15) ** 5.25588, 22632.06 * np.exp(-9.80665 * (z - 11000) / (287.05287 * 216.65)))
    r = avionics.compute(z, isa_p, isa_T)
    assert np.abs(r["altimeter_bias_m"]).max() < 1.0                                       # a standard day has no bias
    warm = avionics.compute(z, isa_p, isa_T + 15.0 * (z < 11000))                          # same pressures: only temperature differs, bias unchanged by temperature
    assert np.allclose(warm["z_baro_agl_m"], r["z_baro_agl_m"])
    # a real warm column: pressure at height z for a +15 K atmosphere is higher than ISA, so the altimeter reads low
    Tw = 303.15 - 0.0065 * z
    pw = 101325 * (Tw / 303.15) ** 5.25588
    bw = avionics.compute(z, pw, Tw)
    tc = 273.15 - 0.0065 * z
    pc = 101325 * (tc / 273.15) ** 5.25588
    bc = avionics.compute(z, pc, tc)
    assert bw["altimeter_bias_m"][0, 3] < -50 and bc["altimeter_bias_m"][0, 3] > 50       # warm: reads low, cold: reads high


def test_refractivity_horizon_and_k_factor():
    z = np.array([0.0, 100.0, 1000.0])
    r = avionics.compute(z, np.array([101325.0, 100130.0, 89875.0]), np.array([288.15, 287.5, 281.65]), np.array([50.0, 50.0, 50.0]))
    assert 280 < r["refractivity_N"][0, 0] < 340                                           # typical surface refractivity
    assert 1.2 < r["k_factor"][0, 1] < 1.6                                                 # about 4/3 for a standard gradient
    assert abs(r["radio_horizon_km"][0, 1] - np.sqrt(2 * r["k_factor"][0, 1] * 6371000 * 100) / 1000) < 1e-6


def test_acoustic_rays_straight_in_still_air_circular_in_a_gradient_and_shadow_zone():
    z = np.linspace(0, 20000, 401)
    T0 = np.full_like(z, 288.15)
    tr = acoustics.AcousticRayTracer(z, T0, np.zeros_like(z), np.zeros_like(z))
    r = tr.trace_ray_fan(10000.0, [90.0], [30.0, 60.0])
    c = np.sqrt(acoustics.GAMMA_R * 288.15)
    assert np.allclose(r["x_east_m"][0], 10000.0 / np.tan(np.deg2rad([30.0, 60.0])), rtol=2e-3)       # straight ray: x = z / tan(beta), still air, isothermal
    assert np.allclose(r["travel_time_s"][0], 10000.0 / (c * np.sin(np.deg2rad([30.0, 60.0]))), rtol=2e-3)
    assert r["reaches_ground"].all() and np.abs(r["y_north_m"]).max() < 1e-6
    # c_eff growing toward the ground (a low-level jet / inversion): shallow downward rays turn up and miss the ground
    wind = np.where(z < 3000, 30.0 * (1 - z / 3000), 0.0)            # wind blowing toward +x, strongest at the ground
    tj = acoustics.AcousticRayTracer(z, T0, wind, np.zeros_like(z))
    rj = tj.trace_ray_fan(3000.0, [90.0, 270.0], [3.0, 40.0])
    assert not rj["reaches_ground"][0, 0] and rj["reaches_ground"][0, 1]                # downwind shallow ray is bent back up, a steep one gets down
    assert rj["reaches_ground"][1, 0]                                                    # upwind (c_eff decreasing toward the ground) it reaches the ground
    # a cross wind advects the sound sideways
    tw = acoustics.AcousticRayTracer(z, T0, np.zeros_like(z), np.full_like(z, 10.0))
    rw = tw.trace_ray_fan(5000.0, [90.0], [45.0])
    assert rw["y_north_m"][0, 0] > 0
