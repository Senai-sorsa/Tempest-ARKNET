"""Soak-history check (PHASED_PLAN 3.4): does the diurnal library + the generator's launch temperature reproduce ERA5's
real 24 h pad history on the development years?

    PYTHONPATH=. python scripts/soak_check.py MODEL.pt CALIB.npz DATA.npz [--rows 1500] [--m 100] [--k 10]
                                              [--lib-first 1991] [--lib-last 2023] [--first-test 2024] [--last-test 2025]

For each test row (a place, an hour, a day): m samples of launch t2m from the generator (range-calibrated), one real
history from the library per sample (library years only, none from the test years), and T_soak / overnight minimum
compared with ERA5's actual history. Baseline: the same library with NO matching to the launch temperature (all
candidate days equally likely). Reports CRPS, MAE of the median, and 90/99 % coverage with day-block 95 % intervals.
"""
import argparse

import numpy as np

from tempest import region
import pandas as pd
import torch
import xarray as xr

from tempest.calibrate import spread
from tempest.generator.features import FEATURES
from tempest.generator.sample import Sampler
from tempest.generator.train import load_npz
from tempest.output import soak
from tempest.scoring.score import coverage90, crps_ensemble

T2M_COL = 176  # t2m in the physical layout: 4 variables x 44 heights, then t2m, sp, rh2m


def row_times(cond, year):
    """Rows -> grid point index and UTC launch time (hour precision), from the features (solar time and place)."""
    c = lambda k: cond[:, FEATURES.index(k)]
    doy = np.round(np.arctan2(c("doy_sin"), c("doy_cos")) % (2 * np.pi) / (2 * np.pi) * 365.25).astype(int)
    sh = np.arctan2(c("hour_sin"), c("hour_cos")) % (2 * np.pi) / (2 * np.pi) * 24
    lat, lon = np.round(c("lat") * 4) / 4, np.round(c("lon") * 4) / 4
    point = region.load().point_index(lat, lon)
    t_solar = pd.to_datetime(pd.Series(year.astype(str)) + "-01-01") + pd.to_timedelta(doy - 1, "D") + pd.to_timedelta(sh, "h")
    return point, pd.DatetimeIndex(t_solar - pd.to_timedelta(c("lon") / 15.0, "h")).round("h")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--surface", default="data/pilot/surface_hourly.zarr")
    ap.add_argument("--rows", type=int, default=1500)
    ap.add_argument("--m", type=int, default=100)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--lib-first", type=int, default=1991)
    ap.add_argument("--lib-last", type=int, default=2023)
    ap.add_argument("--first-test", type=int, default=2024)
    ap.add_argument("--last-test", type=int, default=2025)
    ap.add_argument("--taus", type=float, nargs="+", default=[3, 6, 12])
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    sampler = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device="cpu")
    d = load_npz(a.data)
    cal = spread.load(a.calib, a.model)
    surf = xr.open_zarr(a.surface)
    year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
    rows = np.sort(rng.choice(np.flatnonzero((year >= a.first_test) & (year <= a.last_test)), a.rows, replace=False))
    point, utc = row_times(cond[rows], year[rows])
    libs = {"matched": soak.Library(surf, a.lib_first, a.lib_last, k=a.k), "unmatched": soak.Library(surf, a.lib_first, a.lib_last, k=10 ** 6)}
    full = surf["t2m"].load()
    t_first = pd.Timestamp(full.time.values[0])
    tpos = ((utc - t_first) / pd.Timedelta(hours=1)).astype(int)
    truth_hist = np.stack([full.values[p, t - soak.HOURS + 1:t + 1] for p, t in zip(point, tpos)])
    n = len(rows)
    phys = spread.apply(cal, sampler.profiles(np.repeat(cond[rows], a.m, 0)).reshape(n, a.m, -1))
    t_launch = phys[..., T2M_COL]
    hists = {name: np.stack([L.draw(p, u, t_launch[i], rng)[0] for i, (p, u) in enumerate(zip(point, utc))]) for name, L in libs.items()}
    day = year[rows].astype(np.int64) * 1000 + utc.dayofyear.to_numpy()
    _, inv = np.unique(day, return_inverse=True)
    nd = inv.max() + 1
    boot = np.vstack([np.ones(nd), np.random.default_rng(0).multinomial(nd, np.full(nd, 1 / nd), 500)])
    cnt = np.bincount(inv, minlength=nd)

    def stat(per_row):  # day-block bootstrap mean with 95 % interval
        m = (boot @ np.bincount(inv, per_row, nd)) / (boot @ cnt)
        return m[0], np.percentile(m[1:], 2.5), np.percentile(m[1:], 97.5)

    def line(label, name, x, truth):
        x = x[..., None]
        y = truth[:, None]
        return dict(quantity=label, library=name, crps=stat(crps_ensemble(x, y)[:, 0]), mae_K=stat(np.abs(np.median(x[..., 0], 1) - truth)),
                    cov90=stat(coverage90(x, y, 0.9)[:, 0].astype(float)), cov99=stat(coverage90(x, y, 0.99)[:, 0].astype(float)))

    out = []
    for tau in a.taus:
        for name in libs:
            out.append(line(f"T_soak tau={tau:g}h", name, soak.t_soak(hists[name], tau), soak.t_soak(truth_hist, tau)))
    for name in libs:
        out.append(line("overnight min", name, hists[name].min(-1), truth_hist.min(-1)))
    fmt = lambda t: f"{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]"
    t = pd.DataFrame([{k: (fmt(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in out])
    with pd.option_context("display.width", 200, "display.max_colwidth", 40):
        print(t.to_string(index=False))
    t.to_csv(a.model.rsplit(".", 1)[0] + "_soak_check.csv", index=False)


if __name__ == "__main__":
    main()
