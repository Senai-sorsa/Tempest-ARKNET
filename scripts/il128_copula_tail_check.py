import numpy as np
from tempest_weather import _core
from tempest_weather.flight import TempestFlightSimEngine

NH = _core.NH
z = np.asarray(_core.HEIGHTS, float)
rng = np.random.default_rng(0)
n = 4000
# pool with TAIL DEPENDENCE: wind at every height driven by a heavy-tailed common factor (t, 3 dof) -> big shear events happen at all heights together
common = rng.standard_t(3, (n, 1))
u = 3 + 2 * common * np.exp(-z / 8000)[None] + 0.3 * rng.standard_normal((n, NH))
v = 0.5 * common + 0.3 * rng.standard_normal((n, NH))
T = 288 - 0.0065 * z[None] + 0.5 * rng.standard_normal((n, NH))
RH = np.clip(50 + 8 * rng.standard_normal((n, NH)), 1, 99)
pool = dict(u=u, v=v, T=T, RH=RH, t2m=T[:, 0] + .3, sp=95000 + 0 * u[:, 0] + 100 * rng.standard_normal(n), rh2m=RH[:, 0])
e = TempestFlightSimEngine(atm=pool, info={"elevation_m": 1300.0})
big = e.sample_sobol(np.random.default_rng(1).random((20000, 6)))


def shear(a):
    return np.hypot(np.diff(a["u"], axis=1), np.diff(a["v"], axis=1)) / (np.diff(z) / 1000.0)[None]


sp, sg = shear(pool), shear(big)
print("layer band            pool 99.9th   copula-sample 99.9th   ratio")
for lo, hi in ((10, 500), (500, 2000), (2000, 6000), (6000, 18000)):
    m = (z[1:] >= lo) & (z[1:] < hi)
    a, b = np.quantile(sp[:, m], 0.999), np.quantile(sg[:, m], 0.999)
    print(f"{lo:>5}-{hi:<6} m   {a:10.2f}   {b:14.2f}   {b / a:6.2f}")
print("max wind  pool", np.hypot(pool['u'], pool['v']).max().round(1), " sample", np.hypot(big['u'], big['v']).max().round(1))
