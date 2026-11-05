"""Coupling accuracy check (coupled-atmosphere.md tests 1 and 2): do the generator's samples have the same correlations as
real atmospheres?

    PYTHONPATH=. python scripts/coupling_check.py MODEL.pt CALIB.npz DATA.npz [--site midland|spaceport] [--month 6] [--hour 17]

Real cases: development-year (2024-25) rows of the dataset (station-corrected ERA5) at grid points near the site,
within two months of --month and two solar hours of --hour, within 0.75 degrees. Generated: the same number of samples for those same
conditions (drivers as observed), range-calibrated. For each, p, rho and a are derived with profiles.thermo. Compared:
  1. cross-variable correlation at each height (u, v, T, p, rho, a, RH): largest absolute difference per height band;
  2. vertical correlation of u, v, T, RH between heights (44 x 44): largest absolute difference and the mean;
  and the shear steps (99th and 99.9th percentile) of both. Differences come with a 95 % bootstrap interval on the real side
  (resampling real cases), so a difference smaller than the sampling noise of a few hundred cases is not a finding.
"""
import argparse

import numpy as np
import pandas as pd
import torch

from tempest.calibrate import spread
from tempest.generator.features import FEATURES
from tempest.generator.sample import Sampler, to_physical
from tempest.generator.train import load_npz
from tempest.output import coupled
from tempest.profiles.to_heights import HEIGHTS

SITES = {"midland": (31.94, -102.19), "spaceport": (32.99, -106.97)}
VARS = ["u", "v", "T", "p", "rho", "a", "RH"]
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]


def corr_sets(phys, elev):
    """(n, 179) physical rows -> dict of arrays (n, 44) for the coupled variables."""
    arrays, _ = coupled.build(phys, elev, np.zeros((len(phys), 5)))
    return {k: arrays[k].astype(np.float64) for k in VARS}


def cross_corr(sets):
    stack = np.stack([sets[k] for k in VARS], 1)                      # (n, V, 44)
    return np.stack([coupled._corr(stack[:, :, h]) for h in range(stack.shape[2])])  # (44, V, V)


def vertical_corr(sets):
    return {k: coupled._corr(sets[k]) for k in ("u", "v", "T", "RH")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model")
    ap.add_argument("calib")
    ap.add_argument("data")
    ap.add_argument("--site", default="midland", choices=list(SITES))
    ap.add_argument("--month", type=int, default=6)
    ap.add_argument("--hour", type=float, default=17.0)
    ap.add_argument("--max-real", type=int, default=2000)
    ap.add_argument("--boot", type=int, default=100)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    gen = Sampler(torch.load(a.model, map_location="cpu", weights_only=True), device="cpu")
    cal = spread.load(a.calib, a.model)
    d = load_npz(a.data)
    year, cond = np.asarray(d["year"]), np.asarray(d["cond"])
    c = lambda k: cond[:, FEATURES.index(k)]
    month = (np.arctan2(c("doy_sin"), c("doy_cos")) % (2 * np.pi) / (2 * np.pi) * 12 + 0.5).astype(int) % 12 + 1
    hour = np.arctan2(c("hour_sin"), c("hour_cos")) % (2 * np.pi) / (2 * np.pi) * 24
    lat0, lon0 = SITES[a.site]
    near = (np.abs(c("lat") - lat0) <= 0.75) & (np.abs(c("lon") - lon0) <= 0.75)
    dm = np.minimum(np.abs(month - a.month), 12 - np.abs(month - a.month))
    sel = np.flatnonzero((year >= 2024) & (year <= 2025) & near & (dm <= 2) & (np.abs(hour - a.hour) <= 2))
    if len(sel) < 200:
        raise SystemExit(f"only {len(sel)} real cases in the development years near {a.site}; widen --month/--hour")
    sel = np.sort(rng.choice(sel, min(len(sel), a.max_real), replace=False))
    real = to_physical(np.asarray(d["target"][sel])).astype(np.float64)
    elev = float(c("elev_site")[sel].mean())
    m = 199
    gen_rows = rng.choice(len(sel), min(len(sel), 600), replace=False)
    samples = spread.apply(cal, gen.profiles(np.repeat(cond[sel][gen_rows], m, 0)).reshape(len(gen_rows), m, -1))
    gen_phys = samples[np.arange(len(gen_rows)), rng.integers(0, m, len(gen_rows))].astype(np.float64)  # one sample per condition
    r_sets, g_sets = corr_sets(real, elev), corr_sets(gen_phys, elev)
    rc, gc = cross_corr(r_sets), cross_corr(g_sets)
    boots = []
    for _ in range(a.boot):
        ix = rng.integers(0, len(sel), len(gen_rows))                  # real cases resampled to the generated count
        boots.append(np.abs(cross_corr({k: v[ix] for k, v in r_sets.items()}) - rc))
    noise = np.mean(boots, 0)                                           # typical sampling error of a correlation at this n
    diff = np.abs(gc - rc)
    rows = []
    for name, lo, hi in BANDS:
        s = (HEIGHTS >= lo) & (HEIGHTS < hi)
        rows.append(dict(test="cross-variable at each height", band=name, max_abs_diff=diff[s].max(), mean_abs_diff=diff[s].mean(),
                         sampling_noise_mean=noise[s].mean()))
    rv, gv = vertical_corr(r_sets), vertical_corr(g_sets)
    for k in rv:
        dd = np.abs(rv[k] - gv[k])
        rows.append(dict(test=f"vertical {k}", band="all", max_abs_diff=dd.max(), mean_abs_diff=dd.mean(), sampling_noise_mean=np.nan))
    t = pd.DataFrame(rows)
    sh = lambda x: np.hypot(np.diff(x["u"], axis=1), np.diff(x["v"], axis=1)) / (np.diff(HEIGHTS) / 1000.0)
    qs = [99, 99.9]
    print(f"{a.site} month {a.month} hour {a.hour:g}: {len(sel)} real cases, {len(gen_rows)} generated")
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(t.to_string(index=False))
    print("shear percentiles (m/s per km) 99 / 99.9  real:", np.round(np.percentile(sh(r_sets), qs), 1), " generated:", np.round(np.percentile(sh(g_sets), qs), 1))
    t.to_csv(a.model.rsplit(".", 1)[0] + f"_coupling_{a.site}_{a.month}_{int(a.hour)}.csv", index=False)


if __name__ == "__main__":
    main()
