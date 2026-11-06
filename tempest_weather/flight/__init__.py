"""Stage 6: tools for a flight simulator, built on the finished weather system (docs/plans/STAGE6_PLAN.md). Nothing here changes the weather model and nothing is
vehicle-specific. numpy only, like the rest of tempest_weather.

    from tempest_weather.flight import TempestFlightSimEngine
    eng = TempestFlightSimEngine(32.99, -106.97, "2027-06-15 15:00")      # a pool of coupled atmospheres for one place and time
    eng.condition_on_observations({("wind_u", 10.0): 3.8, ("temp_K", 2.0): 304.2})
    batch = eng.sample_sobol(u_matrix)                                    # the simulator's own quasi-random numbers drive the leading atmosphere modes
    fine = dryden.synthesize(batch, ...)                                  # Dryden turbulence and a 1-cos gust on a fine height grid
    cols = avionics.compute(...); acoustics.AcousticRayTracer(...)        # barometric altimeter bias, radio refractivity; sonic-boom ray fans
"""
from tempest_weather.flight.engine import TempestFlightSimEngine  # noqa: F401
