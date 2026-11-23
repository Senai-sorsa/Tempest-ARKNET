import sys
sys.path.insert(0, r"C:\Users\Senai\Tempest-ARKNET\flight_sim_trial\src\src")
from flight_sim.simulation import Simulation
from flight_sim.utilities.dcm import world_direction
import numpy as np
print("world_direction(0, 90deg):", world_direction(0.0, np.pi/2), "(0, 0):", world_direction(0.0, 0.0), "(up 90):", world_direction(np.pi/2, 0.0))
sim = Simulation.from_file(r"C:\Users\Senai\Tempest-ARKNET\flight_sim_trial\src\examples\sol_invictus\sim.toml")
f = sim.run()
df = f.to_dataframe()
print([c for c in df.columns if any(k in c.lower() for k in ("alt","position","mach","dynamic","density","temperature","wind","air"))][:30])
print(f.summary())
print(type(sim.config.truth.atmosphere).__name__, type(sim.config.truth.wind).__name__)
