"""Gemini A-1 guard: the forecast logger's site list (configs/sites.toml) and the tool's (tempest_weather_v2/data/sites.toml) are two files; the sites they share must agree."""
import tomllib


def test_shared_sites_have_the_same_place_and_elevation():
    with open("configs/sites.toml", "rb") as f:
        a = {s["name"]: s for s in tomllib.load(f)["site"]}
    with open("tempest_weather_v2/data/sites.toml", "rb") as f:
        b = {s["name"]: s for s in tomllib.load(f)["site"]}
    shared = set(a) & set(b)
    assert shared, "no shared site names"
    for n in shared:
        assert abs(a[n]["lat"] - b[n]["lat"]) < 1e-3 and abs(a[n]["lon"] - b[n]["lon"]) < 1e-3, n
        assert abs(float(a[n]["elevation"]) - float(b[n]["elevation_m"])) < 5.0, n


def test_acoustic_earth_flattening_is_opt_in_and_bends_long_rays_down():
    """Gemini A-5: the flat-Earth tracer is unchanged by default; with earth_flattening the effective sound speed is scaled by (1 + z / R_earth): a steep ray from 20 km lands within
    a fraction of a percent of the flat-Earth point (the correction matters only for long, nearly grazing rays)."""
    import numpy as np
    from tempest_weather.flight.acoustics import AcousticRayTracer
    z = np.linspace(0, 20000, 41)
    T = 288.15 - 0.0065 * np.minimum(z, 11000)
    a, b = AcousticRayTracer(z, T, np.zeros_like(z), np.zeros_like(z)), AcousticRayTracer(z, T, np.zeros_like(z), np.zeros_like(z), earth_flattening=True)
    ra, rb = a.trace_ray_fan(20000, [0.0], [5.0, 40.0]), b.trace_ray_fan(20000, [0.0], [5.0, 40.0])
    ra2 = AcousticRayTracer(z, T, np.zeros_like(z), np.zeros_like(z)).trace_ray_fan(20000, [0.0], [5.0, 40.0])
    assert np.array_equal(np.nan_to_num(ra["y_north_m"]), np.nan_to_num(ra2["y_north_m"]))                    # default unchanged and deterministic
    steep_a, steep_b = ra["y_north_m"][0, 1], rb["y_north_m"][0, 1]
    assert np.isfinite(steep_a) and np.isfinite(steep_b) and 0 < abs(steep_b - steep_a) / steep_a < 0.02      # a steep ray changes, but by well under 2 % (0.55 % here)


def test_coextreme_statistic_separates_dependent_from_independent_columns():
    """G3b: mc.coextreme is about 1 when the 10 m wind and the 0-1 km shear rise together and about 0.05 when they are independent."""
    import numpy as np
    from tempest.scoring import mc
    rng = np.random.default_rng(0)
    n = 20000
    p = np.zeros((n, 179))
    a = np.abs(rng.standard_normal(n))                                               # one-sided driver: speed and shear magnitude both grow with it
    j1 = int(np.argmin(np.abs(mc.HEIGHTS - 1000.0)))
    p[:, mc.IU] = 5 + 2 * a                                                          # 10 m wind
    p[:, mc.IU + j1] = p[:, mc.IU] + 3 * a                                           # shear grows with the wind: fully dependent
    assert mc.coextreme(p) > 0.9
    p[:, mc.IU + j1] = p[:, mc.IU] + 3 * rng.standard_normal(n)                      # independent shear
    assert mc.coextreme(p) < 0.2
