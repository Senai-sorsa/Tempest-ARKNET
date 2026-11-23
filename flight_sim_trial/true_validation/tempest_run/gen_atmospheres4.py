"""Rerun 2026-11-10 (copy of the 2026-11-08 script, all-hours tool; writes inputs4 / flights4 / summary4, the 2026-11-08 outputs untouched); was: Rerun 2026-11-08 (step A, project venv): atmospheres for the 3 testable flights with the CURRENT tool, plus the new ways of using real-day information.

    cd <repo> ; TEMPEST_ERA5_STORE=data/pilot/profiles.zarr .venv/Scripts/python -W ignore flight_sim_trial/true_validation/tempest_run/gen_atmospheres4.py [--n 100]

Scenarios written to inputs4/<flight>__<scenario>.npz:
 ai          climate distribution for the date and hour
 past        ERA5 for that hour corrected to balloons
 past_pin    past, then the nearest ASOS (TCS) wind + temperature PINNED (the old S4)
 past_w      past, then the same ASOS values entered with the fitted weights of obs.py (distance 51 km, +78 m, age 0; soft conditioning)
 ai_w        climate, then the same weighted ASOS values
 past_hrrr   past, then the ground wind (< 300 m) anchored to HRRR 10 m wind (archive; optimistic, see docs/AI_MISTAKES_CHECKLIST.md B16)
 past_s12    past with the past-mode wind spread x1.2 (C4a flag)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_atmospheres as G   # noqa: E402
from tempest_weather_v2 import Launch, Window, obs as O   # noqa: E402

OUT = os.path.join(HERE, "inputs4")


def save(L, name, extra):
    pool = L._ensure_pool()
    if extra.get("scenario", "").startswith("past"):                      # B24 (2026-11-10 copy): a past scenario must really be past mode (silent fallback otherwise)
        assert pool["modes"] == {"past": 1.0}, f"{name}: modes {pool['modes']}"
    arrays = {k: np.asarray(v) for k, v in pool["samples"].items()}
    np.savez(os.path.join(OUT, name + ".npz"), **arrays)
    json.dump(dict(trust=L.trust, flags=pool["flags"], modes=pool["modes"], window=pool["window"], n=int(len(arrays["u"])), **extra), open(os.path.join(OUT, name + ".json"), "w"), indent=1, default=str)
    print(f"  {name}: {len(arrays['u'])} atmospheres; flags {pool['flags'][:6]}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not os.environ.get("TEMPEST_ERA5_STORE"):
        os.environ["TEMPEST_ERA5_STORE"] = os.path.join(G.REPO, "data", "pilot", "profiles.zarr")
    dist_km, dz = O.haversine_km(G.SITE["lat"], G.SITE["lon"], *O.STATIONS["TCS"][:2]), O.STATIONS["TCS"][2] - G.SITE["elev_m"]
    print(f"TCS is {dist_km:.0f} km from the pad and {dz:+.0f} m higher", flush=True)
    for fl, spec in G.FLIGHTS.items():
        when = spec["when"] if isinstance(spec["when"], str) else Window(earliest=spec["when"][0], latest=spec["when"][1])
        kw = dict(units="si", elevation=G.SITE["elev_m"], tz=G.SITE["tz"], n=a.n, seed=1)
        print(fl, spec["note"], flush=True)
        base = dict(flight=fl, truth_ft=spec["truth_ft"])
        Lai = Launch(G.SITE["lat"], G.SITE["lon"], when, mode="ai", **kw)
        Lp = Launch(G.SITE["lat"], G.SITE["lon"], when, mode="past", **kw)
        r = Lp.resolved_window()
        mid = r.cells_utc[0 if isinstance(spec["when"], str) else len(r.cells_utc) // 2].astype(datetime).replace(tzinfo=timezone.utc)
        ob = G.asos("TCS", mid)
        temp_pad = ob["temp_c"] + 0.0065 * dz
        wk = dict(wind_10m=f"{max(ob['speed_ms'], 0.1):.2f} m/s", wind_from_deg=ob["from_deg"], temperature=f"{temp_pad:.2f} C")
        save(Lai, f"{fl}__ai", dict(scenario="ai", **base))
        save(Lp, f"{fl}__past", dict(scenario="past", **base))
        save(Lp.observe(**wk), f"{fl}__past_pin", dict(scenario="past_pin", asos=ob, **base))
        save(Lp.observe(**wk, age_hours=0.0, distance_km=dist_km, elevation_diff_m=dz, source="ASOS TCS"), f"{fl}__past_w", dict(scenario="past_w", asos=ob, **base))
        save(Lai.observe(**wk, age_hours=0.0, distance_km=dist_km, elevation_diff_m=dz, source="ASOS TCS"), f"{fl}__ai_w", dict(scenario="ai_w", asos=ob, **base))
        if isinstance(spec["when"], str):                                  # observe_hrrr needs a single launch time
            try:
                save(Lp.observe_hrrr(now=datetime.now(timezone.utc)), f"{fl}__past_hrrr", dict(scenario="past_hrrr", **base))
            except Exception as e:                                         # noqa: BLE001
                print("  past_hrrr failed:", e, flush=True)
        save(Launch(G.SITE["lat"], G.SITE["lon"], when, mode="past", past_wind_spread=1.2, **kw), f"{fl}__past_s12", dict(scenario="past_s12", **base))


if __name__ == "__main__":
    main()
