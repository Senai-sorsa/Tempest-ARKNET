"""Mode P baseline (PHASE4 4.4): how close is ERA5 for the exact launch hour to what the balloon measured, and how much does the
station correction (balloon ~ a + b * ERA5, fitted on earlier years) improve the single best value?

    PYTHONPATH=. python scripts/p4_modeP_baseline.py [--map models/station_map_mix.npz] [--profiles data/pilot/profiles80.zarr]

Truth: IGRA 00Z soundings (Santa Teresa, Midland) in the development years 2024-25, on the 44 heights above the launch site.
Compared per variable x height band (MAE, RMSE, bias; day-block 95 % intervals on the MAE):
  raw ERA5 at that hour (nearest grid point),  ERA5 with the linear station correction a + b * ERA5,
  the climate generator's median (E12, no knowledge of the day) read from the sonde score file when present.
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station
from tempest.profiles.to_heights import HEIGHTS, PROFILE

BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]


def collect(profiles, igra, tmap, first=2024, last=2025):
    ds = xr.open_zarr(profiles)
    out = dict(obs=[], era=[], cor=[], day=[])
    for s, (sid, (lat, lon)) in enumerate(station.STATIONS.items()):
        t, prof, _ = station.read_igra(f"{igra}/{sid}-drvd.txt.zip", first, last)
        keep = np.asarray(t.hour == 0)
        t, prof = t[keep], prof[keep]
        era = station.era5_at(ds, station.nearest_point(ds, lat, lon), t)
        ok = np.isfinite(era).all((1, 2)) & np.isfinite(prof).all((1, 2))
        t, era, prof = t[ok], era[ok], prof[ok]
        g = station.group_id(np.full(len(t), s), t.month, np.zeros(len(t), int))
        cor = tmap["a"][g] + tmap["b"][g] * era
        cor[:, PROFILE.index("RH")] = np.clip(cor[:, PROFILE.index("RH")], 0, 100)
        out["obs"].append(prof), out["era"].append(era), out["cor"].append(cor)
        out["day"].append(t.year.to_numpy().astype(np.int64) * 1000 + t.dayofyear.to_numpy())
    return {k: np.concatenate(v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", default="models/station_map_mix.npz")
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--clim-score", default="models/e12_plain_new/generator_80_b0smix_sonde_cal2021_headline.csv")
    a = ap.parse_args()
    d = collect(a.profiles, a.igra, station.load(a.map))
    n = len(d["obs"])
    print(f"{n} complete 00Z soundings 2024-25 (both stations)")
    _, inv = np.unique(d["day"], return_inverse=True)
    nd = inv.max() + 1
    boot = np.vstack([np.ones(nd), np.random.default_rng(0).multinomial(nd, np.full(nd, 1 / nd), 500)])
    cnt = np.bincount(inv, minlength=nd)
    mean = lambda v: (boot @ np.bincount(inv, v, nd)) / (boot @ cnt)
    try:
        clim = pd.read_csv(a.clim_score).set_index(["var", "band"]).mae_unknown
    except FileNotFoundError:
        clim = None
    rows = []
    for i, v in enumerate(PROFILE):
        for b, lo, hi in BANDS:
            s = (HEIGHTS >= lo) & (HEIGHTS < hi)
            r = dict(var=v, band=b)
            for name in ("era", "cor"):
                e = d[name][:, i][:, s] - d["obs"][:, i][:, s]
                m = mean(np.abs(e).mean(1))
                r[f"mae_{name}"] = f"{m[0]:.3f} [{np.percentile(m[1:], 2.5):.3f}, {np.percentile(m[1:], 97.5):.3f}]"
                r[f"bias_{name}"] = e.mean()
                r[f"rmse_{name}"] = np.sqrt((e ** 2).mean())
            if clim is not None:
                r["mae_climate_model"] = clim.get((v, b.replace(" km", " km")), np.nan)
            rows.append(r)
    t = pd.DataFrame(rows)
    with pd.option_context("display.width", 250, "display.float_format", "{:.3f}".format):
        print(t.to_string(index=False))
    t.to_csv("models/p4_modeP_baseline.csv", index=False)


if __name__ == "__main__":
    main()
