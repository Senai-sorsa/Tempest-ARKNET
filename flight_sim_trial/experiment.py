"""Trial: fly the flight_sim example rocket (Sol Invictus, Spaceport America) through (S0) the plain standard atmosphere, (S1) a careful
conventional setup (standard atmosphere scaled to the site's surface temperature / pressure / humidity + one uniform wind) and (S2) N
atmospheres sampled from the Tempest tool. This folder is a deletable experiment: nothing here is imported by the project.

    cd flight_sim_trial/src ; .venv/Scripts/python -I ../experiment.py [--n 200] [--when 2025-06-24T20:00:00+00:00] [--tag afternoon]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src", "src"))       # the cloned flight_sim sources
sys.path.insert(0, os.path.dirname(HERE))                  # the Tempest-ARKNET repo (tempest_weather, numpy only)

from flight_sim.environment import atmosphere as fs_atm     # noqa: E402
from flight_sim.environment.atmosphere import StandardAtmosphere1976   # noqa: E402
from flight_sim.environment.wind import UniformWind          # noqa: E402
from flight_sim.simulation import Simulation                 # noqa: E402
from flight_sim.units import scalar                          # noqa: E402
from tempest_weather import _core, api                       # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402

SIM = os.path.join(HERE, "src", "examples", "sol_invictus", "sim.toml")   # --sim chooses another input file
LAT, LON, PAD_M = 32.99, -106.97, 4595 * 0.3048             # the example's site: Spaceport America, launch elevation 4595 ft


def metrics(flight):
    df = flight.to_dataframe()
    alt = df["environment.altitude [m]"].to_numpy()
    y, z = df["state.position_y [m]"].to_numpy(), df["state.position_z [m]"].to_numpy()   # world frame (up, east, north)
    wx, wy, wz = (df[f"environment.wind_{a} [m/s]"].to_numpy() for a in "xyz")
    s = flight.summary()
    return dict(apogee_asl_m=float(alt.max()), apogee_agl_m=float(alt.max() - alt[0]), max_speed=s["max_speed_m_s"], max_mach=s["max_mach"],
                max_q_pa=s["max_dynamic_pressure_pa"], flight_time_s=s["flight_time_s"], east_m=float(y[-1]), north_m=float(z[-1]),
                drift_m=float(np.hypot(y[-1], z[-1])), max_wind=float(np.hypot(wy, wz).max()), max_updraft=float(np.abs(wx).max()),
                rho_pad=float(df["environment.atmosphere.air_density [kg/m**3]"].iloc[0]), T_pad=float(df["environment.atmosphere.temperature [K]"].iloc[0]))


def fly(atmosphere=None, wind=None):
    sim = Simulation.from_file(SIM)
    if atmosphere is not None:
        sim.config.truth.atmosphere = atmosphere
    if wind is not None:
        sim.config.truth.wind = wind
    return sim.run()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--when", default="2025-06-24T20:00:00+00:00")   # 14:00 local, a normal launch hour
    ap.add_argument("--tag", default="afternoon")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sim", default=None, help="another sim.toml (e.g. dummy_light/sim.toml)")
    a = ap.parse_args()
    global SIM
    if a.sim:
        SIM = os.path.abspath(a.sim)
    out = os.path.join(HERE, "results")
    os.makedirs(out, exist_ok=True)

    t0 = time.time()
    atm, info = api.atmosphere_set(LAT, LON, a.when, n=a.n, mode="ai", seed=a.seed, elevation=PAD_M)   # elevation pinned to the sim's pad (tool's own lookup says 1493 m)
    nh = _core.NH
    samples = {k: atm[k] for k in ("u", "v", "T", "RH", "p", "t2m", "sp", "rh2m")}
    samples["w"] = atm["w"] if atm.get("w") is not None else np.zeros_like(atm["u"])
    samples["height_agl"] = np.asarray(_core.HEIGHTS, np.float32)
    samples["height_asl"] = (PAD_M + np.asarray(_core.HEIGHTS)).astype(np.float32)
    print(f"tool: {a.n} atmospheres in {time.time() - t0:.1f} s, mode {info['mode']}, pad {info['elevation_m']:.1f} m, quality {info.get('quality')}", flush=True)

    rows = []
    # S0: the plain standard day, no wind (the sim's defaults)
    m = metrics(fly())
    rows.append(dict(scenario="S0 standard atmosphere, no wind", k=-1, **m))
    print("S0", {k: round(v, 1) for k, v in m.items()}, flush=True)

    # S1: the careful conventional setup: standard atmosphere scaled to the site's median surface state + one uniform wind from the median 10 m wind
    t_site, p_site, rh_site = float(np.median(atm["t2m"])), float(np.median(atm["sp"])), float(np.median(atm["rh2m"]))
    std_p = fs_atm._standard_conditions(PAD_M).pressure
    u10, v10 = float(np.median(atm["u"][:, 0])), float(np.median(atm["v"][:, 0]))
    spd, frm = float(np.hypot(u10, v10)), float(np.degrees(np.arctan2(-u10, -v10)) % 360.0)     # azimuth the wind blows FROM
    s1_atm = StandardAtmosphere1976(launch_temperature=scalar(t_site, "K"), barometric_pressure=scalar(p_site * fs_atm._SEA_LEVEL_PRESSURE_PA / std_p, "Pa"),
                                    relative_humidity=min(max(rh_site / 100.0, 0.0), 1.0))
    s1_wind = UniformWind(speed=scalar(spd, "m/s"), from_azimuth=scalar(frm, "deg"))
    m = metrics(fly(s1_atm, s1_wind))
    rows.append(dict(scenario="S1 scaled standard + uniform median wind", k=-1, **m))
    print(f"S1 (T {t_site - 273.15:.1f} C, p {p_site / 1000:.2f} kPa, RH {rh_site:.0f} %, wind {spd:.1f} m/s from {frm:.0f} deg)", {k: round(v, 1) for k, v in m.items()}, flush=True)

    # S2: our samples, one coupled atmosphere per flight
    for k in range(a.n):
        m = metrics(fly(TempestAtmosphere(samples, k), TempestWind(samples, k)))
        rows.append(dict(scenario="S2 tempest samples", k=k, **m))
        if k % 25 == 0:
            print(f"S2 {k + 1}/{a.n}  apogee {m['apogee_asl_m']:.0f} m  drift {m['drift_m']:.0f} m  ({time.time() - t0:.0f} s)", flush=True)

    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out, f"flights_{a.tag}.csv"), index=False)
    np.savez(os.path.join(out, f"atmosphere_{a.tag}.npz"), **{k: np.asarray(v) for k, v in samples.items()}, pad_m=PAD_M)
    json.dump(dict(when=a.when, n=a.n, info={k: str(v) for k, v in info.items()}, s1=dict(T=t_site, p=p_site, rh=rh_site, wind=spd, from_deg=frm)),
              open(os.path.join(out, f"meta_{a.tag}.json"), "w"), indent=1)
    print("done", f"{time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
