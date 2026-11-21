"""Fit the NOW2 nowcast (new_plan_kit/b63) on 2018-2025 and save tempest_weather_v2/data/nowcast.npz: per station month x UTC-hour climatology (u, v mean and sd)
and, per station / lead / day-night, the ridge weights and residual sd. Run (about a minute, needs data/raw/asos):
    PYTHONPATH=".;new_plan_kit;scripts" .venv/Scripts/python -W ignore scripts/build_nowcast_asset.py"""
import numpy as np

from b61_nowcast_stage0 import LEADS, station_series
from b62_nowcast_stage1 import NB
from b63_nowcast_stage2 import FIT2, fit_one
from tempest_weather_v2.obs import STATIONS, haversine_km

OUT = "tempest_weather_v2/data/nowcast.npz"


def main():
    years = list(FIT2)
    S = {st: station_series(st, lon, years, fit_years=FIT2) for st, (lat, lon, el) in STATIONS.items()}
    nbrs = {st: sorted((o for o in STATIONS if o != st), key=lambda o: haversine_km(*STATIONS[st][:2], *STATIONS[o][:2]))[:NB] for st in STATIONS}
    out, names = {}, sorted(STATIONS)
    n = len(S[names[0]][2])
    mon = np.array([(np.datetime64("2015-01-01T00") + np.timedelta64(i, "h")).astype("datetime64[M]").astype(int) % 12 for i in range(n)])
    hr = np.arange(n) % 24                                          # series starts 2015-01-01 00 UTC
    for st in names:
        out[f"{st}_mu"], out[f"{st}_sd"] = (np.stack([[a[(mon == m) & (hr == h)][0] for h in range(24)] for m in range(12)]) for a in (S[st][2], S[st][3]))
        out[f"{st}_nbrs"] = np.array(nbrs[st])
        for lead in LEADS:
            W = fit_one(S, nbrs, st, lead)
            for nt in (False, True):
                out[f"{st}_B_{lead}_{int(nt)}"], out[f"{st}_S_{lead}_{int(nt)}"] = W[nt]
    np.savez_compressed(OUT, stations=np.array(names), leads=np.array(LEADS), **out)
    print("wrote", OUT, len(out), "arrays")


if __name__ == "__main__":
    main()
