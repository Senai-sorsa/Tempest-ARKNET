"""Atmospheres for the flight-impact comparison (flight_sim_trial/gram_flights.py flies them). REPORT ONLY, writes data/kit/flight_inputs.npz.
Cases: b9 cases (2024-25 balloons, development set, reused) whose balloon profile has u, v, T, p at all 44 heights; --per-station cases per station,
spread evenly over the sorted case list (deterministic). Per case: the observed balloon profile ('truth') and --m members each of
  gram_ncep        real Earth-GRAM 2016 (first m MC members)                 data/kit/earthgram_ncep.npz
  gram_ncep_ru1.35 the same with the wind perturbations scaled by 1.35 (b9_earthgram_scale.py)
  tool             the installed tool, climate mode, seed 11
All sources are flown DRY (RH 0) and without vertical wind, so humidity and w do not differ between sources (balloons and GRAM have no w; GRAM RH was not saved).

    PYTHONPATH=".;new_plan_kit" .venv/Scripts/python -W ignore new_plan_kit/b9_flight_inputs.py --per-station 40 --m 50
"""
import argparse
import os

import numpy as np
import pandas as pd

import kit_common as K

SRC = {"gram_ncep": "earthgram_ncep.npz", "gram_ncep_ru1.35": "earthgram_ncep_ru1.35.npz"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-station", type=int, default=40)
    ap.add_argument("--m", type=int, default=50)
    a = ap.parse_args()
    cases = pd.read_csv(os.path.join(K.OUT, "gram_cases.csv")).sort_values("case").reset_index(drop=True)
    bal = {s: K.balloon(s) for s in cases.station.unique()}
    ok = []
    for c in cases.itertuples():
        t, b = bal[c.station]
        k = t.get_loc(pd.Timestamp(c.time_utc))
        ok.append(all(np.isfinite(b[q][k]).all() for q in ("u", "v", "T", "p")))
    full = cases[np.array(ok)]
    pick = pd.concat([g.iloc[np.linspace(0, len(g) - 1, min(a.per_station, len(g))).round().astype(int)] for _, g in full.groupby("station")])
    print(f"{len(full)} of {len(cases)} cases have complete balloon profiles; picked {len(pick)}")
    src = {}
    for name, f in SRC.items():
        d = np.load(os.path.join(K.OUT, f))
        ids = {str(c): i for i, c in enumerate(d["case"])}
        src[name] = (ids, d)
    out = {q: {s: [] for s in ["truth", *SRC, "tool"]} for q in ("u", "v", "T", "p")}
    for c in pick.itertuples():
        t, b = bal[c.station]
        k = t.get_loc(pd.Timestamp(c.time_utc))
        for q in out:
            out[q]["truth"].append(b[q][k][None])
        for name, (ids, d) in src.items():
            for q in out:
                out[q][name].append(d[q][ids[c.case], :a.m])
        atm = K.tool(c.lat, c.lon, c.time_utc, seed=11, n=a.m, elevation=c.elevation_m)
        for q in out:
            out[q]["tool"].append(np.asarray(atm[q], float))
    save = dict(case=np.array(pick.case.tolist(), dtype=str), station=np.array(pick.station.tolist(), dtype=str), lat=pick.lat.values,
                elevation_m=pick.elevation_m.values, time_utc=np.array(pick.time_utc.astype(str).tolist(), dtype=str), height_agl=K.H,
                sources=np.array(list(out["u"]), dtype=str))
    for q, by in out.items():
        for s, arrs in by.items():
            save[f"{s}__{q}"] = np.stack(arrs).astype(np.float32)      # (cases, members, 44)
    np.savez_compressed(os.path.join(K.OUT, "flight_inputs.npz"), **save)
    print("wrote data/kit/flight_inputs.npz", {s: save[f'{s}__u'].shape for s in save["sources"]})


if __name__ == "__main__":
    main()
