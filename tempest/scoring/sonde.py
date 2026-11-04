"""Scorecard against real weather balloons (IGRA radiosondes) in the held-out years: the honest test.

    python -m tempest.scoring.sonde --model models/generator_pilot.pt --data data/train/pilot.npz
                                    [--profiles data/pilot/profiles.zarr] [--m 50] [--device cpu]

Truth is each 00Z balloon (about 17 h local solar time; 12Z is ~05 h, outside the training window) at Santa
Teresa NM and Midland TX in the model's held-out years, on the 44 heights above the launch site. The model is
queried at the nearest grid point, surface T and pressure moved to the launch elevation. Baselines are built from the same station's balloons in the training years,
same calendar month: climatology (real past soundings) and a Gaussian (monthly mean + correlated spread,
Earth-GRAM / Range Reference Atmosphere style). Same scores and charts as tempest.scoring.score, saved to
<model>_sonde.score.csv and <model>_sonde_report/.
"""
import argparse

import numpy as np
import pandas as pd
import torch
import xarray as xr

from tempest.calibrate import spread
from tempest.calibrate.station import ELEV, STATIONS, nearest_point, read_igra
from tempest.generator.build_dataset import solar_hour
from tempest.generator.features import FEATURES, features
from tempest.generator.sample import SURFACE, Sampler, to_site
from tempest.generator.train import load_npz
from tempest.ingest import indices
from tempest.profiles.to_heights import HEIGHTS, PROFILE
from tempest.scoring.report import report
from tempest.scoring.score import BANDS, coverage90, crps_ensemble, gaussian_samples, physical_names, variogram_score

DRIVERS = ["oni", "wwv", "qbo30", "qbo50"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True, help="the training file, only for its year range")
    ap.add_argument("--profiles", default="data/pilot/profiles.zarr", help="for grid-point coordinates and elevation")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--indices", default="data/raw/indices")
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--m", type=int, default=50)
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--calib", help="range calibration from tempest.calibrate.spread (outputs get a _cal suffix)")
    ap.add_argument("--first-test-year", type=int, help="score only from this year (keep the calibration year out)")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    ckpt = torch.load(a.model, map_location="cpu", weights_only=True)
    sampler = Sampler(ckpt, device=a.device)
    histories = [c.get("history") for c in ckpt.get("members", [ckpt])]
    last = int(load_npz(a.data)["year"].max())
    held_from = max(last - ckpt.get("members", [ckpt])[0]["cfg"]["val_years"] + 1, a.first_test_year or 0)
    cal = spread.load(a.calib)
    draw = lambda rep, n: (spread.apply(cal, sampler.profiles(rep).reshape(n, a.m, -1)) if cal
                           else sampler.profiles(rep).reshape(n, a.m, -1))  # calibrated at grid elevation, then moved
    ds = xr.open_zarr(a.profiles)
    tbl = indices.load(a.indices)

    truth, clim, gauss, known, unknown = [], [], [], [], []
    for sid, (slat, slon) in STATIONS.items():
        t, prof, sfc = read_igra(f"{a.igra}/{sid}-drvd.txt.zip", a.first_year, last)
        phys = np.concatenate([prof.reshape(len(t), -1), sfc], 1)
        ok = (t.hour == 0) & np.isfinite(phys).all(1)
        t, phys = t[ok], phys[ok]
        tr, va = np.flatnonzero(t.year < held_from), np.flatnonzero(t.year >= held_from)
        print(f"{sid}: {len(va):,} complete held-out 00Z soundings {held_from}-{last}, {len(tr):,} training-year", flush=True)
        p = nearest_point(ds, slat, slon)
        lat, lon, z = (float(ds[k].values[p]) for k in ("lat", "lon", "z_sfc"))
        for mo in range(1, 13):
            v, r = va[t.month[va] == mo], tr[t.month[tr] == mo]
            if len(v) == 0:
                continue
            draws = r[rng.integers(0, len(r), (len(v), a.m))]
            truth.append(phys[v])
            clim.append(phys[draws])
            gauss.append(gaussian_samples(phys[r].astype(np.float64), len(v), a.m, rng))
            tv = t[v]
            cond = features(lat, lon, z, z, tv.dayofyear.to_numpy(), solar_hour(tv, np.array([lon]))[0],
                            tv.year.to_numpy(), *indices.at(tbl, tv)[:, [0, 3, 1, 2]].T)  # at(): oni, qbo30, qbo50, wwv
            rep = np.repeat(cond, a.m, axis=0)
            known.append(to_site(draw(rep, len(v)), z, ELEV[sid]))
            dc = [FEATURES.index(k) for k in DRIVERS]
            rep[:, dc] = features(0, 0, 0, 0, 0, 0, 0, *indices.at(tbl, t[draws.ravel()])[:, [0, 3, 1, 2]].T)[:, dc]
            unknown.append(to_site(draw(rep, len(v)), z, ELEV[sid]))
    truth = np.concatenate(truth)
    sets = [(k, np.concatenate(x)) for k, x in (("clim", clim), ("gauss", gauss), ("known", known), ("unknown", unknown))]
    print(f"{len(truth):,} balloon profiles scored, m = {a.m}", flush=True)

    res = pd.DataFrame({"column": physical_names()})
    n = len(HEIGHTS)
    vs = pd.DataFrame([{"var": v, **{f"vs_{k}": variogram_score(x[..., i * n:(i + 1) * n], truth[:, i * n:(i + 1) * n]).mean()
                                     for k, x in sets}} for i, v in enumerate(PROFILE)])
    for k in ("gauss", "known", "unknown"):
        vs[f"vs_skill_{k}"] = 1 - vs[f"vs_{k}"] / vs["vs_clim"]
    for k, x in sets:
        res[f"crps_{k}"] = crps_ensemble(x, truth).mean(0)
        res[f"cov90_{k}"] = coverage90(x, truth).mean(0)
        res[f"cov99_{k}"] = coverage90(x, truth, 0.99).mean(0)
    for k in ("gauss", "known", "unknown"):
        res[f"skill_{k}"] = 1 - res[f"crps_{k}"] / res["crps_clim"]
    stem = a.model.rsplit(".", 1)[0] + "_sonde" + ("_cal" if cal else "")
    res.to_csv(stem + ".score.csv", index=False)

    rows = []
    for i, v in enumerate(PROFILE):
        for b0, b1 in BANDS:
            sel = np.zeros(len(res), bool)
            sel[i * n:(i + 1) * n] = (HEIGHTS >= b0) & (HEIGHTS < b1)
            rows.append((v, f"{b0 / 1000:g}-{min(b1, 18000) / 1000:g} km", res[sel]))
    rows += [(s, "surface", res[res.column == s]) for s in SURFACE]
    summary = pd.DataFrame([dict(var=v, band=b, crps_clim=r.crps_clim.mean(), crps_known=r.crps_known.mean(),
                                 skill_gauss=1 - r.crps_gauss.mean() / r.crps_clim.mean(),
                                 skill_known=1 - r.crps_known.mean() / r.crps_clim.mean(),
                                 skill_unknown=1 - r.crps_unknown.mean() / r.crps_clim.mean(),
                                 cov90_known=r.cov90_known.mean(), cov90_clim=r.cov90_clim.mean(),
                                 cov90_gauss=r.cov90_gauss.mean(), cov99_known=r.cov99_known.mean(),
                                 cov99_clim=r.cov99_clim.mean(), cov99_gauss=r.cov99_gauss.mean()) for v, b, r in rows])
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(summary.to_string(index=False))
        print("\nprofile shape (variogram score, skill vs climatology):")
        print(vs.to_string(index=False))
    known = dict(sets)["known"]
    report(stem + "_report", res, vs, (known < truth[:, None]).sum(1), (truth[:3], known[:3]), histories, PROFILE,
           HEIGHTS, SURFACE, truth_label="truth (balloon)")
    summary.to_csv(f"{stem}_report/summary.csv", index=False)
    print(f"wrote {stem}.score.csv and charts to {stem}_report/")


if __name__ == "__main__":
    main()
