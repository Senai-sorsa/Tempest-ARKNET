"""IL-201 (2026-11-10, CPU): does the 100-300 m SHEAR matter for apogee and landing? IL-200 found the tool about 25 % too sharp in that layer. Same simulator and rocket as scripts/p6_apogee_sensitivity.py
(tamusrt flight_sim clone in flight_sim_trial/src, untracked; Sol Invictus at Spaceport America). N tool climate atmospheres for 2025-06-24 20 UTC; each is flown twice: as sampled, and with the structure of
u and v between 100 and 300 m flattened: the values at 150 and 200 m are moved so that the departure from the straight line between the 100 m and 300 m values is 0.8 of what it was (the endpoints, hence every
wind at or above 300 m and at or below 100 m, are unchanged). Output: the change in apogee and in the landing point (mean absolute and mean) against the spread of apogee / landing across the samples.
    cd flight_sim_trial/src ; .venv/Scripts/python -I ../../scripts/il201_shear_apogee.py [--n 30]"""
import argparse
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIAL = os.path.join(REPO, "flight_sim_trial")
sys.path.insert(0, os.path.join(TRIAL, "src", "src"))
sys.path.insert(0, REPO)
sys.path.insert(0, TRIAL)
from experiment import LAT, LON, PAD_M, fly, metrics   # noqa: E402
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--k", type=float, default=0.8, help="fraction of the departure from the straight line that is kept at 150 and 200 m")
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "results", "logs", "il201_shear_apogee.log"))
    a = ap.parse_args()
    atm, info = api.atmosphere_set(LAT, LON, "2025-06-24T20:00:00+00:00", n=a.n, mode="ai", seed=1, elevation=PAD_M)
    H = np.asarray(_core.HEIGHTS, float)
    i100, i150, i200, i300 = (int(np.argmin(np.abs(H - z))) for z in (100, 150, 200, 300))
    base = {k: np.asarray(atm[k], float) for k in ("u", "v", "T", "RH", "p")}
    rows = []
    t0 = time.time()
    for i in range(a.n):
        s = {k: v[i:i + 1].copy() for k, v in base.items()}
        s["w"] = np.zeros_like(s["u"])
        s["height_agl"] = H.astype(np.float32)
        s["height_asl"] = (PAD_M + H).astype(np.float32)
        s2 = {k: v.copy() for k, v in s.items()}
        for c in ("u", "v"):
            for j in (i150, i200):
                f = (H[j] - H[i100]) / (H[i300] - H[i100])
                lin = s[c][0, i100] + f * (s[c][0, i300] - s[c][0, i100])
                s2[c][0, j] = lin + a.k * (s[c][0, j] - lin)
        m0 = metrics(fly(TempestAtmosphere(s, 0), TempestWind(s, 0)))
        m1 = metrics(fly(TempestAtmosphere(s2, 0), TempestWind(s2, 0)))
        rows.append((m0["apogee_agl_m"], m1["apogee_agl_m"], m0["east_m"], m0["north_m"], m1["east_m"], m1["north_m"]))
        if i == 0:
            print(f"one pair of flights took {time.time() - t0:.0f} s", flush=True)
    r = np.array(rows)
    da = r[:, 1] - r[:, 0]
    dl = np.hypot(r[:, 4] - r[:, 2], r[:, 5] - r[:, 3])
    sa = r[:, 0].std()
    sl = np.hypot(r[:, 2] - r[:, 2].mean(), r[:, 3] - r[:, 3].mean()).mean()
    lines = [f"IL-201: {a.n} tool atmospheres (mode {info['mode']}), 2025-06-24 20 UTC, Sol Invictus; structure at 150 / 200 m flattened to {a.k:.1f} of its departure from the 100-300 m line",
             f"  apogee: sd across samples {sa:.1f} m; change mean {da.mean():+.2f} m, mean abs {np.abs(da).mean():.2f} m, max abs {np.abs(da).max():.1f} m  (mean abs change / sd = {100 * np.abs(da).mean() / sa:.1f} %)",
             f"  landing: mean distance from the mean landing {sl:.0f} m; landing shift mean {dl.mean():.1f} m, max {dl.max():.1f} m  (mean shift / spread = {100 * dl.mean() / sl:.1f} %)"]
    for l in lines:
        print(l)
    with open(a.out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
