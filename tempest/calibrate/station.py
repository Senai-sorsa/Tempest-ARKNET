"""Phase 6 S4: correct ERA5 profiles toward weather balloons (IGRA radiosondes).

    python -m tempest.calibrate.station [--profiles data/pilot/profiles.zarr] [--out models/station_map.npz]
                                        [--first-year 1991] [--last-year 2020] [--check-to 2025]

ERA5 is smooth in the vertical: its pressure levels miss the sharp wind shear and inversions a balloon sees, and
a grid box is not a point. For each IGRA station, ERA5 at the nearest grid point and the balloon at the same
00Z / 12Z launch are put on the same 44 heights above ground. Per (station, season, launch hour, variable,
height) a straight line balloon ~ a + b * ERA5 is fitted; the leftovers (balloon minus line) are kept as whole
profiles. A corrected profile is a + b * ERA5 plus one leftover profile drawn from the same group: by
construction its mean and spread at every height match the balloons, and the leftover carries the balloons'
real fine-scale structure (shear, inversions) with its real vertical pattern.
(Mapping each height step's quantiles on its own was tried first: steps matched, but whole-profile spread grew
20-140 % because ERA5's smooth steps lean the same way and add up.)
Fit years end at --last-year so the later years up to --check-to give an honest before/after check.
"""
import argparse
import io
import os
import zipfile

import numpy as np
import pandas as pd
import xarray as xr

from tempest.profiles.diff import from_diff, to_diff
from tempest.profiles.to_heights import G0, HEIGHTS, PROFILE, geometric_height

STATIONS = {"USM00072364": (31.8728, -106.6981), "USM00072265": (31.9475, -102.1894)}  # Santa Teresa NM, Midland TX
ELEV = {"USM00072364": 1254.0, "USM00072265": 874.0}  # m, launch-level height in the IGRA files (2015+)
MAX_GAP = 2000.0  # m between usable balloon levels; wider gaps are left missing instead of drawn as a straight line


def season(month):
    """1..12 -> 0 DJF, 1 MAM, 2 JJA, 3 SON."""
    return (np.asarray(month) % 12) // 3


def to_grid(h, x):
    """One balloon variable at heights h (m above launch) -> values on HEIGHTS (NaN outside data or in wide gaps)."""
    ok = np.isfinite(h) & np.isfinite(x)
    h, i = np.unique(h[ok], return_index=True)
    x = x[ok][i]
    if len(h) < 2:
        return np.full(len(HEIGHTS), np.nan, np.float32)
    y = np.interp(HEIGHTS, h, x, left=np.nan, right=np.nan)
    j = np.searchsorted(h, HEIGHTS).clip(1, len(h) - 1)
    y[(h[j] - h[j - 1] > MAX_GAP) & ~np.isin(HEIGHTS, h)] = np.nan
    return y.astype(np.float32)


def read_igra(path, first_year, last_year):
    """IGRA2 derived-parameter zip -> (UTC times (S,), profiles (S, 4, 44) u, v, T, RH on HEIGHTS above the launch
    surface, surface (S, 3) T (K), pressure (Pa), RH (%)). Only nominal 00Z / 12Z soundings are kept."""
    times, profs, sfcs = [], [], []
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
        lines = io.TextIOWrapper(f, "ascii", errors="replace")
        for line in lines:
            if not line.startswith("#"):
                continue
            year, hour, n = int(line[13:17]), int(line[24:26]), int(line[31:36])
            block = [next(lines) for _ in range(n)]
            if not (first_year <= year <= last_year and hour in (0, 12)) or n < 3:
                continue
            # fields are 7 wide + 1 space: 0 PRESS Pa, 2 CALCGPH m, 3 TEMP K*10, 12 CALCRH %*10, 14 UWND, 16 VWND m/s*10
            a = np.array([[int(r[8 * i:8 * i + 7]) for i in (0, 2, 3, 12, 14, 16)] for r in block], float)
            a[a <= -9999] = np.nan
            p, gph, t, rh, u, v = a.T
            if not np.isfinite(gph[0]):
                continue
            h = geometric_height(gph * G0) - geometric_height(gph[0] * G0)
            profs.append([to_grid(h, u / 10), to_grid(h, v / 10), to_grid(h, t / 10), to_grid(h, rh / 10)])
            sfcs.append([t[0] / 10, p[0], rh[0] / 10])
            times.append(f"{line[13:17]}-{line[18:20]}-{line[21:23]}T{hour:02d}")
    return (pd.DatetimeIndex(np.array(times, "datetime64[h]")),
            np.array(profs, np.float32).reshape(-1, 4, len(HEIGHTS)), np.array(sfcs, np.float32).reshape(-1, 3))


def nearest_point(ds, lat, lon):
    return int(np.argmin((ds.lat.values - lat) ** 2 + (ds.lon.values - lon) ** 2))


def era5_at(ds, point, times):
    """ERA5 profiles (S, 4, 44) at one grid point and the given times (NaN where the store has no such hour)."""
    have = times.isin(pd.DatetimeIndex(ds.time.values))
    out = np.full((len(times), len(PROFILE), len(HEIGHTS)), np.nan, np.float32)
    b = ds[PROFILE].isel(point=point).sel(time=times[have]).load()
    out[have] = np.stack([b[v].values for v in PROFILE], 1)
    return out


def moisture(levels):
    """Mean RH 5-13 km of level-space rows (N, 4, 44): how moist the mid/upper air is."""
    return levels[:, PROFILE.index("RH"), (HEIGHTS >= 5000) & (HEIGHTS <= 13000)].mean(1)


def fit(era, obs, groups, n_groups, pool_max=3000, seed=0):
    """Paired level-space profiles (S, 4, 44) + group per sounding -> dict a, b (G, 4, 44) of balloon ~ a + b * ERA5
    (least squares per height; identity where < 50 pairs), moisture tercile cuts (G, 2) of ERA5 RH 5-13 km and
    pool (G, 3, pool_max, 4, 44) of complete leftover profiles per tercile, n (G, 3) of them (0 = none added).
    Leftovers come from soundings as moist as the one corrected: balloon-vs-ERA5 RH scatter is much larger in moist
    air (2023-25 check: RH CRPS 9-18 km -8 %, other variables equal or slightly better)."""
    rng = np.random.default_rng(seed)
    shape = (n_groups,) + era.shape[1:]
    a, b = np.zeros(shape, np.float32), np.ones(shape, np.float32)
    pool, n = np.zeros((n_groups, 3, pool_max) + era.shape[1:], np.float32), np.zeros((n_groups, 3), np.int64)
    cuts = np.zeros((n_groups, 2), np.float32)
    for g in range(n_groups):
        E, O = era[groups == g], obs[groups == g]
        for i in range(E.shape[1]):
            for k in range(E.shape[2]):
                ok = np.isfinite(E[:, i, k]) & np.isfinite(O[:, i, k])
                if ok.sum() >= 50:
                    e, o = E[ok, i, k].astype(np.float64), O[ok, i, k].astype(np.float64)
                    b[g, i, k] = np.cov(e, o)[0, 1] / max(e.var(ddof=1), 1e-9)
                    a[g, i, k] = o.mean() - b[g, i, k] * e.mean()
        R = O - (a[g] + b[g] * E)
        keep = np.isfinite(R).all((1, 2))
        if keep.sum() < 50:
            continue
        R, wet = R[keep], moisture(E[keep])
        cuts[g] = np.quantile(wet, [1 / 3, 2 / 3])
        tercile = (wet > cuts[g, 0]).astype(int) + (wet > cuts[g, 1])
        for j in range(3):
            Rj = R[tercile == j] if (tercile == j).sum() >= 50 else R
            Rj = Rj[rng.permutation(len(Rj))[:pool_max]]
            n[g, j] = len(Rj)
            pool[g, j, :n[g, j]] = Rj
    return dict(a=a, b=b, pool=pool, n=n, cuts=cuts)


def apply(t, levels, groups, rng):
    """Correct level-space ERA5 rows (N, 4, 44) with group ids (N,) using tables t from `fit`; RH kept in 0-100 %.
    shortcut: leftovers are resampled from the fit years only, so extremes never exceed what those balloons saw;
    add GPD tails (PLAN S4) if the tail check shows extremes too mild."""
    out = t["a"][groups] + t["b"][groups] * levels
    if t["n"].ndim == 1:  # maps written before the moisture terciles: one leftover pool per group
        n = t["n"][groups]
        draw = (rng.random(len(groups)) * n).astype(np.int64)
        left = t["pool"][groups, draw]  # gather one profile per row, never a whole pool per row
    else:
        wet, c = moisture(levels), t["cuts"][groups]
        j = (wet > c[:, 0]).astype(int) + (wet > c[:, 1])
        n = t["n"][groups, j]
        draw = (rng.random(len(groups)) * n).astype(np.int64)
        left = t["pool"][groups, j, draw]
    out += np.where((n > 0)[:, None, None], left, 0)
    rh = PROFILE.index("RH")
    out[:, rh] = np.clip(out[:, rh], 0, 100)
    return out


def group_id(station, month, hour_class):
    """station index, month 1..12, hour class (0 = 00Z, 1 = 12Z) -> group id in [0, n_stations * 8)."""
    return (np.asarray(station) * 4 + season(month)) * 2 + np.asarray(hour_class)


def load(path):
    return dict(np.load(path))


def correct(t, diff, lat, lon, month, solar_hour, rng):
    """Correct difference-view ERA5 rows (N, 4, 44) anywhere in the box: nearest station's tables, season from
    month, and the launch hour nearer in local solar time (00Z ~ 17 h, 12Z ~ 05 h in the pilot box).
    shortcut: two stations stand in for the whole box and two launch hours for the whole day; add stations
    (or blend by distance) before leaving the pilot region."""
    st = np.argmin((np.asarray(lat)[:, None] - t["lat"]) ** 2 + (np.asarray(lon)[:, None] - t["lon"]) ** 2, 1)
    sh = np.asarray(solar_hour)
    hc = ((sh >= 23) | (sh < 11)).astype(int)
    return to_diff(apply(t, from_diff(diff), group_id(st, month, hc), rng))


def check(era, obs, cor):
    """Level-space (S, 4, 44) ERA5, balloon, corrected -> per variable: distance to the balloons' distribution
    (mean |quantile gap| 5-95 %) for values and for height steps, 99th-percentile |step| (shear) ratio and spread
    ratio vs balloons (medians over heights). Gap: lower is better; ratios: 1 is balloon-like."""
    qs = np.linspace(0.05, 0.95, 19)

    def gap(x, y):
        return np.mean(np.abs(np.quantile(x, qs, 0) - np.quantile(y, qs, 0)))

    rows = []
    for i, v in enumerate(PROFILE):
        ok = np.isfinite(obs[:, i]).all(1) & np.isfinite(era[:, i]).all(1)
        ob, dob = obs[ok, i], np.diff(obs[ok, i])
        r = dict(var=v)
        for name, x in (("era5", era[ok, i]), ("corrected", cor[ok, i])):
            r[f"level_gap_{name}"], r[f"step_gap_{name}"] = gap(x, ob), gap(np.diff(x), dob)
            r[f"shear99_{name}"] = np.median(np.quantile(abs(np.diff(x)), 0.99, 0) / np.quantile(abs(dob), 0.99, 0))
            r[f"spread_{name}"] = np.median(x.std(0) / ob.std(0))
        rows.append(r)
    return pd.DataFrame(rows)


def station_pairs(ds, igra_dir, first_year, last_year):
    """Per station: (times, ERA5 profiles, balloon profiles, balloon surface) for soundings with an ERA5 match."""
    out = []
    for sid, (lat, lon) in STATIONS.items():
        t, prof, sfc = read_igra(os.path.join(igra_dir, f"{sid}-drvd.txt.zip"), first_year, last_year)
        era = era5_at(ds, nearest_point(ds, lat, lon), t)
        m = np.isfinite(era).all((1, 2))
        print(f"{sid}: {len(t):,} soundings {first_year}-{last_year}, {m.sum():,} with ERA5", flush=True)
        out.append((t[m], era[m], prof[m], sfc[m]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="data/pilot/profiles.zarr")
    ap.add_argument("--igra", default="data/raw/igra")
    ap.add_argument("--out", default="models/station_map.npz")
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--last-year", type=int, default=2020)  # validation starts 2021
    ap.add_argument("--check-to", type=int, default=2025)
    a = ap.parse_args()

    ds = xr.open_zarr(a.profiles)
    pairs = station_pairs(ds, a.igra, a.first_year, a.check_to)
    groups = [group_id(s, t.month, (t.hour == 12).astype(int)) for s, (t, *_) in enumerate(pairs)]
    fit_rows = [t.year <= a.last_year for t, *_ in pairs]
    held = [~m for m in fit_rows]

    def cat(j, sel):
        return np.concatenate([p[j][m] for p, m in zip(pairs, sel)])

    def gcat(sel):
        return np.concatenate([g[m] for g, m in zip(groups, sel)])

    t = fit(cat(1, fit_rows), cat(2, fit_rows), gcat(fit_rows), len(STATIONS) * 8)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    lat, lon = np.array(list(STATIONS.values())).T
    np.savez(a.out, **t, lat=lat, lon=lon, stations=np.array(list(STATIONS)),
             fit_years=np.array([a.first_year, a.last_year]))
    print(f"wrote {a.out}: leftover profiles per group {t['n'].tolist()}")

    era, obs = cat(1, held), cat(2, held)
    rep = check(era, obs, apply(t, era, gcat(held), np.random.default_rng(1)))
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(f"held-out {a.last_year + 1}-{a.check_to}, {len(era):,} soundings "
              "(gap: lower = closer to balloons; shear99 / spread: 1 = balloon-like):")
        print(rep.to_string(index=False))
    rep.to_csv(a.out.rsplit(".", 1)[0] + "_check.csv", index=False)


if __name__ == "__main__":
    main()
