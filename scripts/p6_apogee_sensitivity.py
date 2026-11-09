"""P6: apogee-sensitivity weights by height. Which layers of the wind actually move the apogee and the landing point, and so which observation heights and loss weights matter?
(Replaces the guessed "3x weight below 300 m".) Simulator: the tamusrt flight_sim clone in flight_sim_trial/src (untracked, never committed; its own virtualenv), the example rocket
Sol Invictus (Loki M3464, 17 ft rail pointing north) at Spaceport America, through the readers of tempest_weather.flight_sim_readers. Base = the MEDIAN of 200 Tempest climate
atmospheres for 2025-06-24 20 UTC (14 h local). Then +3 m/s of east or north wind is added in ONE height band at a time (model heights inside the band) and the rocket is flown again.
Output per band: d apogee / d wind (m per m/s), landing shift (m per m/s), and the share of the apogee variance that the band's real wind variability (sd of u and v over the 200
samples, averaged over the band) would cause, sum(sensitivity^2 x sd^2) normalised. One rocket and one day: an example of the method, not a general law.
    cd flight_sim_trial/src ; .venv/Scripts/python -I ../../scripts/p6_apogee_sensitivity.py
"""
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIAL = os.path.join(REPO, "flight_sim_trial")
sys.path.insert(0, os.path.join(TRIAL, "src", "src"))
sys.path.insert(0, REPO)
sys.path.insert(0, TRIAL)
from experiment import LAT, LON, PAD_M, fly, metrics   # noqa: E402
from tempest_weather import _core, api   # noqa: E402
from tempest_weather.flight_sim_readers import TempestAtmosphere, TempestWind   # noqa: E402

BANDS = [(0, 50), (50, 150), (150, 300), (300, 600), (600, 1000), (1000, 2000), (2000, 3000), (3000, 5000)]
DW = 3.0


def main():
    atm, info = api.atmosphere_set(LAT, LON, "2025-06-24T20:00:00+00:00", n=200, mode="ai", seed=1, elevation=PAD_M)
    H = np.asarray(_core.HEIGHTS, float)
    med = {k: np.median(np.asarray(atm[k], float), axis=0)[None] for k in ("u", "v", "T", "RH", "p")}
    med["w"] = np.zeros_like(med["u"])
    med["height_agl"] = H.astype(np.float32)
    med["height_asl"] = (PAD_M + H).astype(np.float32)
    sd = {k: np.asarray(atm[k], float).std(0) for k in ("u", "v")}

    def run(du=None, dv=None):
        s = dict(med)
        s["u"] = med["u"] + (0 if du is None else du)
        s["v"] = med["v"] + (0 if dv is None else dv)
        return metrics(fly(TempestAtmosphere(s, 0), TempestWind(s, 0)))
    b = run()
    print(f"base (median atmosphere, mode {info['mode']}): apogee {b['apogee_agl_m']:.1f} m AGL, landing east {b['east_m']:.0f} m, north {b['north_m']:.0f} m")
    rows = []
    for lo, hi in BANDS:
        m = ((H >= lo) & (H < hi)).astype(float)[None]
        if m.sum() == 0:
            continue
        e, n = run(du=DW * m), run(dv=DW * m)
        sa_e, sa_n = (e["apogee_agl_m"] - b["apogee_agl_m"]) / DW, (n["apogee_agl_m"] - b["apogee_agl_m"]) / DW
        sl_e = np.hypot(e["east_m"] - b["east_m"], e["north_m"] - b["north_m"]) / DW
        sl_n = np.hypot(n["east_m"] - b["east_m"], n["north_m"] - b["north_m"]) / DW
        sdb = (sd["u"][m[0] > 0].mean(), sd["v"][m[0] > 0].mean())
        rows.append(((lo, hi), sa_e, sa_n, sl_e, sl_n, sdb, (sa_e * sdb[0]) ** 2 + (sa_n * sdb[1]) ** 2, (sl_e * sdb[0]) ** 2 + (sl_n * sdb[1]) ** 2))
    va, vl = sum(r[6] for r in rows), sum(r[7] for r in rows)
    print("\nband (m AGL)   d apogee / d wind (m per m/s) east / north   landing shift (m per m/s) east / north   wind sd u / v (m/s)   share of apogee variance   share of landing variance")
    for (lo, hi), sa_e, sa_n, sl_e, sl_n, sdb, va_b, vl_b in rows:
        print(f"  {lo:5d}-{hi:<5d}     {sa_e:+7.2f} / {sa_n:+7.2f}                             {sl_e:6.1f} / {sl_n:6.1f}                       {sdb[0]:4.1f} / {sdb[1]:4.1f}            {100 * va_b / va:5.1f} %                  {100 * vl_b / vl:5.1f} %")


if __name__ == "__main__":
    main()
