"""tempest_weather v2 (Section 2 of docs/plans/SECTIONS_PLAN.md): additive package next to tempest_weather. It imports tempest_weather and changes nothing in it.

Built in the order of the plan: 2A flexibility, 2B speed, 2C usage. See tempest_weather_v2/README.md for the module map and status.

    from tempest_weather_v2 import Launch, Window
    launch = Launch("spaceport_america", "2027-06-16 10:00")
    print(launch.weather())
"""
__version__ = "2.0.0.dev0"


def __getattr__(name):                      # lazy: importing the package must stay cheap and must not need the model assets
    if name in ("Launch", "Window", "AtmosphereSet", "Launches"):
        from tempest_weather_v2 import launch
        return getattr(launch, name)
    raise AttributeError(f"module 'tempest_weather_v2' has no attribute {name!r}")
