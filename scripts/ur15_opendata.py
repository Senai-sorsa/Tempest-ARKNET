"""UR15 + UR13 (New_Plan 17.2): a clean third test period, 2023-24, from ECMWF open data (the operational IFS forecast, free, on AWS:
https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com, no account). Why this source (checked 2026-11-13): the WeatherBench 2 HRES archive that the
Mode F rows come from ends 2022-12, and Open-Meteo's archive of past runs refuses every pressure-level variable (surface only).
What the open data has: 00Z / 12Z runs from 2023-01-18, steps to 240 h; u, v, t, q, gh on 9 pressure levels (1000, 925, 850, 700, 500, 300, 250,
200, 50 hPa) and 10 m wind, 2 m temperature; 0.4 deg ('0p4-beta', through early 2024 and beyond) and 0.25 deg (from 2024-02). Each field is fetched
alone by an HTTP byte range from the file's .index; only the box is kept.
LIMITS (stated before any result; they go into every verdict that uses these rows):
  - 9 levels instead of the WB2 store's 13 (no 600 / 400 / 150 / 100 hPa): the forecast profile between levels is coarser;
  - 0.4 deg grid (default, the same resolution for both years; --prefer 0p25 switches) vs the WB2 grid; store points take the nearest grid point;
  - 00Z starts every --every days (default 4), steps --steps (default 24 / 72 / 120 / 168 / 216 h = lead bins 1 / 3 / 5 / 7 and one day beyond 7.5 d).
  The sanity gate of new_plan_kit/b37_ur15_third_period.py --gate must pass before any verdict is read.
Commands (run from the repo root, PYTHONPATH=.):
  fetch <box> [--every 4] [--steps 24,72,120,168,216] [--with-older] [--first 2023-01-20] [--last 2024-12-31] [--smoke]
        -> data/raw/opendata_hres_<box>/<YYYYMM>_00z.nc (and _12z.nc with --with-older: the 12Z run 36 h before each start, at step + 36 h, for UR13's
           older-run mix as CHORUS stage 1 built it). Resumable: finished (date, step) pieces are kept in .../parts/. Size about 28 MB downloaded per
           (run, step); the defaults are ~26 GB for 2023-24, --with-older adds ~20 GB (inside the 50 GB download budget). --smoke: one run, one step,
           three fields, nothing kept but a printed check.
  rows <box> [--points 16]  -> data/ur15_<box>_od/2023.npz, 2024.npz and 2324.npz (the file il6_modeF.py --test-file reads); hres_old added when
           the 12Z files exist. Truth = the ERA5 box store at the point and valid hour (data/pilot/profiles80.zarr, profiles_denver_full.zarr).
  mix <box>  -> data/ur15_<box>_od_mix/2324.npz: hres = w new + (1 - w) old with the CHORUS stage 1 weights (models/chorus_<box>_weights.npz)
           (UR13). Rows without the older run keep the newest run.
Downloads go to data/raw/opendata_hres_<box>/tmp/ (own folder) and are decoded by eccodes / cfgrib only. Never 2026.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd
import xarray as xr

from tempest.forecast import modeF

BASE = "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/"
LAYOUTS = {"0p4": ("0p4-beta/oper", "ifs/0p4-beta/oper", "0p25/oper", "ifs/0p25/oper"), "0p25": ("ifs/0p25/oper", "0p25/oper", "0p4-beta/oper", "ifs/0p4-beta/oper")}
PL = ("t", "u", "v", "q", "gh")
SFC = {"10u": "u10", "10v": "v10", "2t": "t2m"}
LEVELS = (1000, 925, 850, 700, 500, 300, 250, 200, 50)
G = 9.80665
STORE = {"nmtx": "data/pilot/profiles80.zarr", "denver": "data/pilot/profiles_denver_full.zarr"}


def get(url, rng=None, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(10 * (k + 1))
        except Exception:   # noqa: BLE001 (network hiccup: retry)
            time.sleep(10 * (k + 1))
    raise RuntimeError(f"download failed after {tries} tries: {url}")


def find_index(date, hour, step, prefer):
    for lay in LAYOUTS[prefer]:
        key = f"{date:%Y%m%d}/{hour:02d}z/{lay}/{date:%Y%m%d}{hour:02d}0000-{step}h-oper-fc"
        raw = get(BASE + key + ".index")
        if raw:
            return key, [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
    return None, None


def wanted(recs, smoke=False):
    out = [r for r in recs if (r.get("levtype") == "pl" and r["param"] in PL and int(r.get("levelist", 0)) in LEVELS) or (r.get("levtype") == "sfc" and r["param"] in SFC)]
    if smoke:
        out = [r for r in out if (r["param"] == "t" and int(r.get("levelist", 0)) in (850, 500)) or r["param"] == "2t"]
    return sorted(out, key=lambda r: r["_offset"])


def ranges(recs):
    """merge byte ranges that touch -> [(start, end inclusive)]."""
    out = []
    for r in recs:
        a, b = r["_offset"], r["_offset"] + r["_length"] - 1
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def box_of(box):
    ds = xr.open_zarr(STORE[box])
    return float(ds.lat.min()) - 1, float(ds.lat.max()) + 1, float(ds.lon.min()) - 1, float(ds.lon.max()) + 1


def decode(path, bounds):
    """GRIB file -> dict of box arrays: pl vars (level, lat, lon) in LEVELS order, sfc vars (lat, lon); and the lat / lon axes."""
    la0, la1, lo0, lo1 = bounds
    out = {}
    with xr.open_dataset(path, engine="cfgrib", backend_kwargs={"filter_by_keys": {"typeOfLevel": "isobaricInhPa"}, "indexpath": ""}) as d:
        lon = ((d.longitude.values + 180) % 360) - 180
        ki, kj = (d.latitude.values >= la0) & (d.latitude.values <= la1), (lon >= lo0) & (lon <= lo1)
        lev = list(np.atleast_1d(d.isobaricInhPa.values).astype(int))
        for v in PL:
            if v in d:
                arr = d[v].values if "isobaricInhPa" in d[v].dims else d[v].values[None]          # a file with one level has no level dimension
                out[v] = np.stack([arr[lev.index(L)][np.ix_(ki, kj)] if L in lev else np.full((ki.sum(), kj.sum()), np.nan) for L in LEVELS]).astype(np.float32)
        lat_ax, lon_ax = d.latitude.values[ki], lon[kj]
    for p, name in SFC.items():
        try:
            with xr.open_dataset(path, engine="cfgrib", backend_kwargs={"filter_by_keys": {"shortName": p}, "indexpath": ""}) as d:
                v = list(d.data_vars)[0]
                out[name] = d[v].values[np.ix_(ki, kj)].astype(np.float32)
        except Exception:   # noqa: BLE001 (a field missing in the file is left out; the assembler fills NaN)
            pass
    return out, lat_ax, lon_ax


def piece(box, date, hour, step, prefer, root, bounds, smoke=False):
    """one (run, step) -> saved npz in parts/ (or the dict for smoke). Returns the path, or None if the run is not in the archive."""
    p = f"{root}/parts/{date:%Y%m%d}{hour:02d}_{step:03d}.npz"
    if os.path.exists(p) and not smoke:
        return p
    key, recs = find_index(date, hour, step, prefer)
    if key is None:
        return None
    sel = wanted(recs, smoke)
    os.makedirs(f"{root}/tmp", exist_ok=True)
    tmp = f"{root}/tmp/{date:%Y%m%d}{hour:02d}_{step:03d}.grib2"
    with open(tmp, "wb") as f:
        for a, b in ranges(sel):
            raw = get(BASE + key + ".grib2", (a, b))
            assert raw is not None and len(raw) == b - a + 1, f"short read {key} {a}-{b}"
            f.write(raw)
    arr, la, lo = decode(tmp, bounds)
    os.remove(tmp)
    if smoke:
        return dict(key=key, fields=len(sel), mb=sum(r["_length"] for r in sel) / 1e6, arrays={k: v.shape for k, v in arr.items()}, lat=la, lon=lo, arr=arr)
    os.makedirs(f"{root}/parts", exist_ok=True)
    np.savez(p + ".part.npz", lat=la, lon=lo, layout=key.split("/", 2)[2].rsplit("/", 1)[0], **arr)
    os.replace(p + ".part.npz", p)
    return p


def assemble(root, month, hour, steps):
    """parts of one month -> <root>/<YYYYMM>_<hh>z.nc in the WB2 layout (time, prediction_timedelta, level, latitude, longitude); z = gh x g."""
    files = sorted(f for f in os.listdir(f"{root}/parts") if f.startswith(month) and f[8:10] == f"{hour:02d}")
    if not files:
        return None
    times = sorted({pd.Timestamp(f[:8]) + pd.Timedelta(hours=hour) for f in files})
    first = np.load(f"{root}/parts/{files[0]}")
    la, lo = first["lat"], first["lon"]
    shp5 = (len(times), len(steps), len(LEVELS), len(la), len(lo))
    data = {v: np.full(shp5, np.nan, np.float32) for v in ("t", "u", "v", "q", "z")}
    data.update({v: np.full(shp5[:2] + shp5[3:], np.nan, np.float32) for v in SFC.values()})
    for f in files:
        z = np.load(f"{root}/parts/{f}")
        if z["lat"].shape != la.shape or z["lon"].shape != lo.shape:
            continue                                                       # a resolution change inside the month: the other grid is skipped (counted below)
        i, j = times.index(pd.Timestamp(f[:8]) + pd.Timedelta(hours=hour)), steps.index(int(f[11:14]))
        for v in PL:
            if v in z.files:
                data["z" if v == "gh" else v][i, j] = z[v] * (G if v == "gh" else 1.0)
        for v in SFC.values():
            if v in z.files:
                data[v][i, j] = z[v]
    dims5, dims4 = ("time", "prediction_timedelta", "level", "latitude", "longitude"), ("time", "prediction_timedelta", "latitude", "longitude")
    ds = xr.Dataset({v: (dims5 if a.ndim == 5 else dims4, a) for v, a in data.items()},
                    coords=dict(time=np.array(times, "datetime64[ns]"), prediction_timedelta=np.array(steps, "timedelta64[h]").astype("timedelta64[ns]"),
                                level=np.array(LEVELS), latitude=la, longitude=lo + 360.0))   # longitude stored 0-360 as the WB2 files
    out = f"{root}/{month}_{hour:02d}z.nc"
    ds.to_netcdf(out + ".part")
    os.replace(out + ".part", out)
    return out


def fetch(a):
    root = a.root or f"data/raw/opendata_hres_{a.box}"
    os.makedirs(root, exist_ok=True)
    bounds = box_of(a.box)
    steps = [int(s) for s in a.steps.split(",")]
    if a.smoke:
        r = piece(a.box, pd.Timestamp("2023-06-01"), 0, 72, a.prefer, root, bounds, smoke=True)
        t850 = r["arr"]["t"][LEVELS.index(850)]
        print(f"smoke: {r['key']}: {r['fields']} fields, {r['mb']:.1f} MB; arrays {r['arrays']}; box lat {r['lat'].min():.1f}-{r['lat'].max():.1f}, "
              f"lon {r['lon'].min():.1f}-{r['lon'].max():.1f}; T850 {np.nanmin(t850):.1f}-{np.nanmax(t850):.1f} K, 2 m T {np.nanmean(r['arr']['t2m']):.1f} K", flush=True)
        assert 250 < np.nanmean(t850) < 310 and 250 < np.nanmean(r["arr"]["t2m"]) < 320, "decoded values are not temperatures in K"
        return
    dates = pd.date_range(a.first, a.last, freq=f"{a.every}D")
    assert dates.max() < pd.Timestamp("2026-01-01"), "never 2026"
    done, missing = 0, 0
    for d in dates:
        jobs = [(d, 0, s) for s in steps] + ([(d - pd.Timedelta(hours=36), 12, s + 36) for s in steps if s + 36 <= 240] if a.with_older else [])
        for dd, hh, s in jobs:
            if piece(a.box, dd.normalize(), hh, s, a.prefer, root, bounds) is None:
                missing += 1
            else:
                done += 1
        print(f"{d:%Y-%m-%d}: {done} pieces on disk, {missing} not in the archive", flush=True)
    months = sorted({f"{d:%Y%m}" for d in dates} | ({f"{(d - pd.Timedelta(hours=36)):%Y%m}" for d in dates} if a.with_older else set()))
    for m in months:
        for hh, st in ((0, steps), (12, [s + 36 for s in steps if s + 36 <= 240])):
            if hh == 12 and not a.with_older:
                continue
            out = assemble(root, m, hh, st)
            if out:
                print("wrote", out, flush=True)


def rows(a):
    root, store = a.root or f"data/raw/opendata_hres_{a.box}", xr.open_zarr(STORE[a.box])
    od = a.rows_out or f"data/ur15_{a.box}_od"
    bl = dict(np.load("models/modeF_bl.npz"))
    pl, pn, zs = store.lat.values, store.lon.values, store.z_sfc.values.astype(float)
    tidx_all = store.get_index("time")
    out = {2023: [], 2024: []}
    for f in sorted(x for x in os.listdir(root) if x.endswith("_00z.nc")):
        h = xr.open_dataset(f"{root}/{f}").load()
        prev = f"{(pd.Timestamp(f[:6] + '01') - pd.Timedelta(days=1)):%Y%m}"
        olds = [xr.open_dataset(f"{root}/{m}_12z.nc").load() for m in (prev, f[:6]) if os.path.exists(f"{root}/{m}_12z.nc")]   # a run 36 h before an early start sits in the month before
        olds = [o for o in olds if o.latitude.shape == h.latitude.shape and o.longitude.shape == h.longitude.shape]
        old = xr.concat(olds, "time") if olds else None
        steps_h = (h.prediction_timedelta.values // np.timedelta64(1, "h")).astype(int)
        la_i = np.abs(h.latitude.values[None, :] - pl[:, None]).argmin(1)
        lo_i = np.abs((h.longitude.values - 360.0)[None, :] - pn[:, None]).argmin(1)
        rng = np.random.default_rng(int(f[:6]))
        case, lead, pt = [], [], []
        for c, t0 in enumerate(pd.DatetimeIndex(h.time.values)):
            for j, s in enumerate(steps_h):
                if not np.isfinite(h["t"].values[c, j]).any():
                    continue
                p = rng.choice(len(pl), min(a.points, len(pl)), replace=False)
                case += [c] * len(p)
                lead += [j] * len(p)
                pt += list(p)
        if not case:
            continue
        case, lead, pt = np.array(case), np.array(lead), np.array(pt)
        init = pd.DatetimeIndex(h.time.values)[case]
        valid = init + pd.to_timedelta(steps_h[lead], unit="h")
        ti = tidx_all.get_indexer(valid)
        ok = ti >= 0
        case, lead, pt, init, valid, ti = case[ok], lead[ok], pt[ok], init[ok], valid[ok], ti[ok]
        hp = modeF.forecast_profiles(h, case, lead, la_i[pt], lo_i[pt], zs[pt] * G, bl)
        hres = np.stack([hp[v] for v in modeF.PROFILE], 1).astype(np.float32)
        lapse, dpd, _ = modeF.boundary_inputs(h, case, lead, la_i[pt], lo_i[pt], zs[pt] * G)
        obs = np.stack([store[v].isel(time=xr.DataArray(ti), point=xr.DataArray(pt)).values for v in modeF.PROFILE], 1).astype(np.float32)
        hold = np.full(hres.shape, np.nan, np.float32)
        if old is not None:                                                  # the 12Z run 36 h before, at step + 36 h
            oi = pd.DatetimeIndex(old.time.values).get_indexer(init - pd.Timedelta(hours=36))
            os_h = (old.prediction_timedelta.values // np.timedelta64(1, "h")).astype(int)
            oj = np.array([np.flatnonzero(os_h == s + 36)[0] if (os_h == s + 36).any() else -1 for s in steps_h[lead]])
            k = (oi >= 0) & (oj >= 0)
            if k.any():
                op = modeF.forecast_profiles(old, oi[k], oj[k], la_i[pt[k]], lo_i[pt[k]], zs[pt[k]] * G, bl)
                hold[k] = np.stack([op[v] for v in modeF.PROFILE], 1)
        good = np.isfinite(hres).all((1, 2)) & np.isfinite(obs).all((1, 2))
        for y in (2023, 2024):
            s = good & (valid.year == y)
            if not s.any():
                continue
            n = int(s.sum())
            out[y].append(dict(year=np.full(n, y), valid=valid[s].values, lead_days=(steps_h[lead][s] / 24.0).astype(np.float32), lead_hours=steps_h[lead][s],
                               start_hour=np.zeros(n, int), valid_utc_hour=valid[s].hour.to_numpy(), lat=pl[pt][s].astype(float), lon=pn[pt][s].astype(float), z_sfc=zs[pt][s],
                               doy=valid[s].dayofyear.to_numpy().astype(np.int32), hres=hres[s], obs=obs[s], hres_old=hold[s],
                               init_day=init[s].dayofyear.to_numpy().astype(np.int32), lapse_low=lapse[s].astype(np.float32), dpd_low=dpd[s].astype(np.float32)))
        print(f"{f}: {int(good.sum()):,} rows", flush=True)
    os.makedirs(od, exist_ok=True)
    allp = []
    for y, parts in out.items():
        if not parts:
            continue
        d = {k: np.concatenate([x[k] for x in parts]) for k in parts[0]}
        allp.append(d)
        for L in (1, 3, 5, 7, 0):
            k = modeF.lead_bin(d["lead_days"]) == L
            print(f"{y} lead bin {L if L else '9 (beyond 7.5 d)'}: {k.sum():,} rows, mean |forecast - ERA5| {np.abs(d['hres'][k] - d['obs'][k]).mean():.3f}", flush=True)
        save(f"{od}/{y}.npz", d)
    if allp:
        save(f"{od}/2324.npz", {k: np.concatenate([x[k] for x in allp]) for k in allp[0]})


def mix(a):
    d = dict(np.load(f"data/ur15_{a.box}_od/2324.npz"))
    wf = np.load(f"models/chorus_{a.box}_weights.npz")
    lb = modeF.lead_bin(d["lead_days"])
    have = np.isfinite(d["hres_old"]).all((1, 2)) & (lb > 0)
    w = np.stack([wf[f"w{L}"] if L > 0 else np.ones_like(wf["w1"]) for L in lb])
    d["hres"] = np.where(have[:, None, None], w * d["hres"] + (1 - w) * np.nan_to_num(d["hres_old"]), d["hres"]).astype(np.float32)
    os.makedirs(f"data/ur15_{a.box}_od_mix", exist_ok=True)
    save(f"data/ur15_{a.box}_od_mix/2324.npz", d)
    print(f"mixed {have.sum():,} of {len(have):,} rows", flush=True)


def save(path, d):
    np.savez(path.replace(".npz", ".part.npz"), **d)
    os.replace(path.replace(".npz", ".part.npz"), path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fetch", "rows", "mix"))
    ap.add_argument("box", choices=("nmtx", "denver"))
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--steps", default="24,72,120,168,216")
    ap.add_argument("--with-older", action="store_true")
    ap.add_argument("--first", default="2023-01-20")
    ap.add_argument("--last", default="2024-12-31")
    ap.add_argument("--prefer", choices=("0p4", "0p25"), default="0p4")
    ap.add_argument("--points", type=int, default=16)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--root", default="", help="download folder (default data/raw/opendata_hres_<box>); for tests")
    ap.add_argument("--rows-out", default="", help="rows folder (default data/ur15_<box>_od); for tests")
    a = ap.parse_args()
    {"fetch": fetch, "rows": rows, "mix": mix}[a.cmd](a)


def _unit():
    recs = [dict(_offset=0, _length=10), dict(_offset=10, _length=5), dict(_offset=40, _length=5)]
    assert ranges(recs) == [(0, 14), (40, 44)]
    r = [dict(levtype="pl", param="t", levelist="850", _offset=5, _length=1), dict(levtype="pl", param="vo", levelist="850", _offset=0, _length=1),
         dict(levtype="pl", param="u", levelist="600", _offset=1, _length=1), dict(levtype="sfc", param="2t", _offset=2, _length=1)]
    assert [x["param"] for x in wanted(r)] == ["2t", "t"]


_unit()
if __name__ == "__main__":
    sys.exit(main())
