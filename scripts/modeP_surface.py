"""F-12: surface values for past dates (mode P). The network covers the 176 profile columns only; the tool left sp with zero spread and shifted t2m / rh2m by the 10 m residual.
Here the balloon's launch-level temperature, pressure and RH are compared with ERA5's t2m, sp, rh2m moved to the station's launch height (to_site); the residuals of the training
years (<= 2020) are kept as a joint empirical pool per station x season x launch hour (rows are drawn whole, so the three keep their correlation). Evaluation on 00Z soundings of 2024-25:
CRPS and coverage of ERA5 alone (one value) against ERA5 + pool.

    PYTHONPATH=. python scripts/modeP_surface.py [--out models/modeP_sfc_pool.npz]
"""
import argparse

import numpy as np
import pandas as pd
import xarray as xr

from tempest.calibrate import station
from tempest.generator.sample import to_site
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.score import coverage90, crps_ensemble

NH = len(HEIGHTS)
J = NH * len(PROFILE)


def era_surface(ds, point, times, z_site):
    """ERA5 (S, 3) t2m K, sp Pa, rh2m % at the grid point, moved to the launch height z_site (m)."""
    have = times.isin(pd.DatetimeIndex(ds.time.values))
    out = np.full((len(times), 3), np.nan)
    b = ds[["t2m", "sp", "rh2m"]].isel(point=point).sel(time=times[have]).load()
    out[have] = np.stack([b.t2m.values, b.sp.values, b.rh2m.values], 1)
    phys = np.zeros((len(times), J + 3))
    phys[:, PROFILE.index("T") * NH:(PROFILE.index("T") + 1) * NH] = 250.0
    phys[:, PROFILE.index("RH") * NH:(PROFILE.index("RH") + 1) * NH] = 50.0
    phys[:, J:] = out
    z_grid = float(ds.z_sfc.isel(point=point).values)
    to_site(phys, z_grid, z_site)
    return phys[:, J:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="data/pilot/profiles80.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--out", default="models/modeP_sfc_pool.npz")
    ap.add_argument("--m", type=int, default=199)
    a = ap.parse_args()
    ds = xr.open_zarr(a.profiles)
    rows = []
    for s, (sid, (lat, lon)) in enumerate(station.STATIONS.items()):
        t, _, sfc = station.read_igra(f"{a.igra}/{sid}-drvd.txt.zip", 1991, 2025)
        era = era_surface(ds, station.nearest_point(ds, lat, lon), t, station.ELEV[sid])
        ok = np.isfinite(era).all(1) & np.isfinite(sfc).all(1)
        # sfc order from read_igra: T (K), p (Pa), RH (%) -> reorder to t2m, sp, rh2m
        obs = sfc[:, [0, 1, 2]]
        rows.append(pd.DataFrame(dict(time=t[ok], station=s, e_t=era[ok, 0], e_p=era[ok, 1], e_r=era[ok, 2], o_t=obs[ok, 0], o_p=obs[ok, 1], o_r=obs[ok, 2])))
    d = pd.concat(rows, ignore_index=True)
    d["season"] = station.season(pd.DatetimeIndex(d.time).month)
    d["hour12"] = (pd.DatetimeIndex(d.time).hour == 12).astype(int)
    d["key"] = (d.station * 4 + d.season) * 2 + d.hour12
    res = d[["o_t", "o_p", "o_r"]].to_numpy() - d[["e_t", "e_p", "e_r"]].to_numpy()
    yr = pd.DatetimeIndex(d.time).year.to_numpy()
    d["bad"] = ~np.isfinite(res).all(1) | (np.abs(res[:, 0]) > 25) | (np.abs(res[:, 1]) > 6000) | (np.abs(res[:, 2]) > 100)    # unit slips in old IGRA records
    print(f"{len(d):,} paired soundings, {int(d.bad.sum())} dropped as implausible; residual sd by variable (train years): "
          f"{np.round(res[(yr <= 2020) & ~d.bad.to_numpy()].std(0), 3)} (K, Pa, %)")
    tr = (yr <= 2020) & ~d.bad.to_numpy()
    te = (yr >= 2024) & (d.hour12.to_numpy() == 0) & ~d.bad.to_numpy()
    np.savez(a.out, res=res[tr].astype(np.float32), key=d.key.to_numpy()[tr].astype(np.int16), years="<=2020", stations=np.array(list(station.STATIONS)))
    rng = np.random.default_rng(0)
    pool = {k: res[tr][d.key.to_numpy()[tr] == k] for k in np.unique(d.key.to_numpy())}
    era_te, obs_te = d.loc[te, ["e_t", "e_p", "e_r"]].to_numpy(), d.loc[te, ["o_t", "o_p", "o_r"]].to_numpy()
    ens = np.stack([era_te[i] + pool[k][rng.integers(0, len(pool[k]), a.m)] for i, k in enumerate(d.key.to_numpy()[te])])     # (S, m, 3)
    ens[..., 2] = np.clip(ens[..., 2], 0, 100)
    point = np.repeat(era_te[:, None], 2, 1)
    out = []
    for name, x in (("ERA5 at the site (one value)", point), ("ERA5 + residual pool", ens)):
        cr = crps_ensemble(x, obs_te).mean(0)
        cv = coverage90(x, obs_te, 0.99).mean(0) if x.shape[1] > 2 else np.full(3, np.nan)
        c9 = coverage90(x, obs_te, 0.90).mean(0) if x.shape[1] > 2 else np.full(3, np.nan)
        out.append(dict(method=name, crps_t2m_K=cr[0], crps_sp_Pa=cr[1], crps_rh2m_pct=cr[2], cov90_t2m=c9[0], cov90_sp=c9[1], cov90_rh2m=c9[2], cov99_t2m=cv[0], cov99_sp=cv[1], cov99_rh2m=cv[2]))
    t = pd.DataFrame(out)
    with pd.option_context("display.width", 220):
        print(f"test soundings 2024-25 00Z: {int(te.sum())}")
        print(t.round(4).to_string(index=False))
    t.to_csv(a.out.rsplit(".", 1)[0] + "_eval.csv", index=False)


if __name__ == "__main__":
    main()
