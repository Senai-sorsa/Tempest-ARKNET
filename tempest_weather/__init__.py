"""tempest_weather: probabilistic atmosphere for the pilot box (31-34 N, 108-101 W), from a place and a time.

    from tempest_weather import values, distribution, couple, atmosphere
Needs numpy only. See README.md.
"""
__version__ = "0.1.0"


def __getattr__(name):                     # lazy: importing the package stays cheap and does not need the model assets
    if name in ("values", "distribution", "couple", "atmosphere"):
        from tempest_weather import api
        return getattr(api, name)
    raise AttributeError(name)
