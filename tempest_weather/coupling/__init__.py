"""Coupling types, one file each. `make(method, columns, table, marginals)` -> an object with draw(k, rng) and spec()."""
from tempest_weather.coupling.gaussian_copula import GaussianCopula
from tempest_weather.coupling.whole_sample import WholeSample

METHODS = {"whole_sample": WholeSample, "gaussian_copula": GaussianCopula}


def make(method, columns, table, marginals=None, key=None):
    if method not in METHODS:
        raise ValueError(f"unknown coupling method {method!r}; choose one of {sorted(METHODS)}")
    if method == "gaussian_copula":
        if marginals is None:
            raise ValueError("gaussian_copula needs the marginal specs (call distribution() first)")
        return GaussianCopula(columns, table, marginals)
    return WholeSample(columns, table, key=key)
