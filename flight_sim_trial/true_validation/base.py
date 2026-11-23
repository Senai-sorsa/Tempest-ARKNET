import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from flight_sim.simulation import Simulation
FT = 0.3048
for c, truth in (("Prometheus", 12788.714), ("Juno3", 10541.339), ("HeartOfSteel", 30411.0)):
    d = os.path.join("validation", "results", "matrix", c, "sea_re2_po1_w0_linear")
    cwd = os.getcwd(); os.chdir(d)
    sim = Simulation.from_file("sim.toml"); f = sim.run(); df = f.to_dataframe()
    alt = df["environment.altitude [m]"]
    ap = (alt.max() - alt.iloc[0]) / FT
    os.chdir(cwd)
    print(f"{c:13} FS apogee AGL {ap:9.1f} ft  truth {truth:9.1f}  err {100*(ap/truth-1):+.2f} %   (branch reports {json.load(open(os.path.join(d,'fs.json'))).get('apogee_ft', json.load(open(os.path.join(d,'fs.json'))))})")
