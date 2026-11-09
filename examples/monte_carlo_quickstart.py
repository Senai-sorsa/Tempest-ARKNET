"""Monte Carlo quickstart (roadmap A9): from a place and a time to an apogee distribution, the inputs that drive it, a rare-wind probability and a storm scenario.

    PYTHONPATH=. .venv/Scripts/python examples/monte_carlo_quickstart.py

The simulator below is a TOY (vertical point mass with drag, a crude wind loss): replace `simulate` with your own (RocketPy, OpenRocket, RASAero, ...). Every atmosphere is a reader
with .wind(alt) / .air(alt) (altitudes above sea level, metres in units='si'); `Atmosphere.rocketpy_inputs()` and `to_openrocket_csv()` export one atmosphere for those tools.
"""
import numpy as np

from tempest_weather_v2 import Launch
from tempest_weather_v2.montecarlo import VehiclePriors, run, run_importance


def simulate(atm, drag_scale=1.0, impulse_scale=1.0, mass_scale=1.0):
    """TOY rocket: 25 kg, 2.5 kN for 4 s, Cd 0.45 on 0.018 m2, flown straight up through this atmosphere's density; the mean wind of the lowest 200 m costs 1.5 % of apogee per m/s
    (weathercocking). Returns the apogee above the pad in metres."""
    z0 = atm.elevation_m
    z, v, t, dt = 0.0, 0.0, 0.0, 0.05
    m, thrust, burn = 25.0 * mass_scale, 2500.0 * impulse_scale, 4.0
    k = 0.5 * 0.45 * drag_scale * 0.018
    while v >= 0.0 or t < burn:
        rho = float(atm.air(z0 + max(z, 1.0))[2])
        f = (thrust if t < burn else 0.0) - k * rho * v * abs(v) - m * 9.80665
        v += f / m * dt
        z += v * dt
        t += dt
        if t > 120:
            break
    wind = float(np.mean(np.linalg.norm(np.asarray(atm.wind_many(z0 + np.linspace(10.0, 200.0, 12))), axis=-1)))
    return z * (1.0 - 0.015 * wind)


def main():
    pad = Launch("spaceport_america", "2027-06-16 10:00", mode="ai", n=400, units="si", seed=1)       # climate mode: any future date; add .observe(...) on launch day
    atms = pad.atmospheres(400)
    priors = VehiclePriors(drag_scale=("lognormal", 0.05), impulse_scale=("lognormal", 0.03), mass_scale=("normal", 0.02))
    res = run(simulate, atms, priors, n=400, seed=1)
    print("apogee (m):", {k: round(v, 1) for k, v in res.summary().items()})
    print("90 % interval:", tuple(round(x) for x in res.interval(90)))
    print("what drives the spread (share of variance, rank regression):", {k: round(v, 2) for k, v in res.contributions().items()})

    # a rare outcome (the 1 % low tail of apogee): 300 tilted runs toward strong ground wind instead of thousands of plain ones. Check effective n; the vehicle priors drive part of this
    # outcome too, so the reported +- can be optimistic (3000 crude runs gave 0.0080 for this setup, 300 tilted runs 0.0080 +- 0.0023)
    limit = res.interval(98)[0]
    big = pad.atmospheres(3000)
    imp = run_importance(simulate, big, limit, priors=priors, n=300, tilt=2.0, metric="mean_wind_0_200m", seed=3)
    p, se = imp.probability(above=False)
    print(f"P(apogee < {limit:.0f} m) = {p:.4f} +- {se:.4f} (effective n {imp.effective_n():.0f})")

    # a 1-in-1000 ground-wind storm at this hour: coherent atmospheres conditioned on it
    storm = pad.stress("wind_10m", quantile=0.999, n=40)
    ap = [simulate(a) for a in storm]
    print(f"storm scenario: 10 m wind {min(storm.stress['values']):.1f}-{max(storm.stress['values']):.1f} m/s, apogee median {np.median(ap):.0f} m "
          f"(probability of a storm at least this strong {storm.stress['probability']:.3f})")


if __name__ == "__main__":
    main()
