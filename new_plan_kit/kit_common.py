"""Shared helpers for every script in new_plan_kit/. Nothing here edits the repository: it only reads data and the installed tool.
Self-check (no data needed for the maths part):  PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/kit_common.py
"""
import ctypes
import os
import sys
import time

import numpy as np
import pandas as pd

KIT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(KIT)
for _p in (REPO, os.path.join(REPO, "scripts"), KIT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tempest_weather import _core   # noqa: E402

H = np.asarray(_core.HEIGHTS, float)          # 44 model heights, m above ground
NH = len(H)
BANDS = [("0-1 km", 0, 1000), ("1-5 km", 1000, 5000), ("5-12 km", 5000, 12000), ("12-18 km", 12000, 18001)]
EPZ, MAF = "USM00072364", "USM00072265"       # IGRA balloon stations (Santa Teresa / El Paso, Midland)
NOISE, PAIRED_TOL = 0.0006, 0.0009            # CRPS change below NOISE is noise; paired tolerance for "not worse"
OUT = os.path.join(REPO, "data", "kit")       # every kit output file goes here (never committed: data/ is ignored)
LOGS = os.path.join(REPO, "docs", "results", "logs")


def free_ram_gb():
    class M(ctypes.Structure):
        _fields_ = [("n", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(k, ctypes.c_ulonglong) for k in ("tot", "avail", "a", "b", "c", "d", "e")]
    m = M()
    m.n = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def ram_gate(min_gb=6.0, poll_s=60):
    """Wait (never kill) until at least min_gb RAM is free. Call before any heavy step."""
    while free_ram_gb() < min_gb:
        print(f"[kit] free RAM {free_ram_gb():.1f} GB < {min_gb} GB, waiting", flush=True)
        time.sleep(poll_s)


def report(name, lines):
    """Print the lines and append them to docs/results/logs/kit_<name>.log (the file a later reader looks at for the verdict)."""
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    text = "\n".join(lines)
    print(text, flush=True)
    if os.environ.get("KIT_SMOKE"):          # smoke tests (KIT_SMOKE=1) print only: a tiny run must never look like a verdict in the log
        return
    with open(os.path.join(LOGS, f"kit_{name}.log"), "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M ") + text + "\n\n")


def crps1(ens, y):
    """CRPS of one number y against a 1-D ensemble."""
    e = np.sort(np.asarray(ens, float))
    m = len(e)
    return float(np.abs(e - y).mean() - ((2 * np.arange(1, m + 1) - m - 1) * e).sum() / (m * m))


def block_boot(values, days, draws=2000, seed=0):
    """Mean of `values` with a 95 % interval from resampling whole days. values (n,), days (n,) any labels -> (mean, lo, hi)."""
    values = np.asarray(values, float)
    _, inv = np.unique(np.asarray(days), return_inverse=True)
    s, c = np.bincount(inv, values), np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(s), (draws, len(s)))
    b = s[pick].sum(1) / c[pick].sum(1)
    return float(values.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def band_idx(lo, hi):
    return np.flatnonzero((H >= lo) & (H < hi))


def balloon(sid):
    """-> (DatetimeIndex, dict u, v [m/s], T [K], RH [%], p [Pa], each (n, 44) on the model heights, NaN where missing)."""
    d = np.load(os.path.join(REPO, "data", "igra_heights", sid + ".npz"))
    sel = np.array([int(np.argmin(np.abs(d["heights"] - h))) for h in H])
    assert np.abs(d["heights"][sel] - H).max() < 1.0, "balloon heights do not hold the 44 model heights"
    out = {}
    for k in ("u", "v", "T", "RH", "lnp"):
        raw = d[k][:, sel]
        x = raw.astype(float) * (0.0005 if k == "lnp" else 0.1)
        x[raw == -32768] = np.nan
        out["p" if k == "lnp" else k] = np.exp(x) if k == "lnp" else x
    return pd.DatetimeIndex(d["time"].astype("datetime64[ns]")), out


def station_pos(sid):
    from tempest.calibrate import station
    lat, lon = station.STATIONS[sid]
    return float(lat), float(lon), float(station.ELEV[sid])


STAGES = {"range map only": ("lmap", "smap", "rank", "rank_extra", "tpl"), "+ shuffle": ("lmap", "smap"), "+ shear map": ("lmap",), "+ lapse map (shipped)": ()}


def tool(lat, lon, t, seed, n=199, elevation=None, stage=None):
    """The installed tool's climate-mode samples -> atm dict (u, v, T, RH, p ... each (n, 44)). stage = a key of STAGES switches later post-processing off, in memory only."""
    from tempest_weather import api
    when = pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:00+00:00")
    if stage is None:
        return api.atmosphere_set(lat, lon, when, n=n, seed=seed, mode="ai", elevation=elevation)[0]
    A = api._assets()
    full = A["post"]
    A["post"] = {k: v for k, v in full.items() if k not in STAGES[stage]}
    try:
        return api.atmosphere_set(lat, lon, when, n=n, seed=seed, mode="ai", elevation=elevation)[0]
    finally:
        A["post"] = full


def era5_at(lat, lon, times, store="data/pilot/profiles.zarr", names=("u", "v", "T")):
    """ERA5 profile store at the nearest point -> (times found, dict name -> (n, 44)). Only hours the store holds come back."""
    import xarray as xr
    z = xr.open_zarr(os.path.join(REPO, store))
    i = int(np.argmin((z.lat.values - lat) ** 2 + (z.lon.values - lon) ** 2))
    common = np.intersect1d(np.asarray(times, "datetime64[ns]"), z["time"].values)
    return pd.DatetimeIndex(common), {k: z[k].isel(point=i).sel(time=common).values.astype(float) for k in names}


def shear_mag(u, v):
    """Vector shear between neighbouring model heights, m/s per km, (..., 43)."""
    return np.hypot(np.diff(u, axis=-1), np.diff(v, axis=-1)) / (np.diff(H) / 1000.0)


def n2(T, p):
    """Brunt-Vaisala frequency squared between neighbouring heights, 1/s^2, (..., 43). T in K, p in Pa."""
    th = T * (1e5 / p) ** 0.286
    return 9.81 / (0.5 * (th[..., 1:] + th[..., :-1])) * np.diff(th, axis=-1) / np.diff(H)


def asos_speed(st, years):
    """{hour (UTC, tz-aware): (speed m/s, direction deg)} from data/raw/asos/<ST>/<year>.csv (the loader of scripts/a1_paired_persistence.py; missing years are skipped)."""
    import a1_paired_persistence as a1
    out = {}
    for y in years:
        if os.path.exists(os.path.join(REPO, "data", "raw", "asos", st, f"{y}.csv")):
            out.update(a1.load(st, [y]))
    return out


def radar_files(site):
    """Cached radar wind-profile files of one site (EPZ, MAF, HDX, FTG) -> (DatetimeIndex sorted, list of paths). Never downloads."""
    import glob
    fs = sorted(glob.glob(os.path.join(REPO, "data", "raw", "nexrad_nvw", site + "_NVW_*")))
    return pd.to_datetime([os.path.basename(f)[len(site) + 5:] for f in fs], format="%Y_%m_%d_%H_%M_%S"), fs


def radar_uv(site, t, ground_m, max_age_min=65, index=None):
    """Newest cached volume at most max_age_min before t -> (u, v), each (44,) on the model heights above ground_m (NaN where the radar has no value), or None.
    65 min, not 45: the cached files are the FIRST volume of hour 23 / 11 (51-60 min before the balloon hour), about half of them hold no wind (clear air)."""
    from p3_vad_vs_balloon import parse
    times, fs = index or radar_files(site)
    t = pd.Timestamp(t)
    k = int(np.searchsorted(times.values, np.datetime64(t), side="right")) - 1
    if k < 0 or (t - times[k]) > pd.Timedelta(minutes=max_age_min):
        return None
    try:
        return parse(fs[k], ground_m)
    except Exception:   # noqa: BLE001  (a broken file is a missing volume)
        return None


def day_ok(t):
    """True for a test time this plan may use: never 2026 data."""
    return pd.Timestamp(t).year <= 2025


def _selfcheck():
    rng = np.random.default_rng(0)
    e = rng.standard_normal(4000)
    assert abs(crps1(e, 0.0) - 0.2337) < 0.02            # CRPS of N(0,1) at 0 = 0.2337
    m, lo, hi = block_boot(rng.standard_normal(600) + 0.5, np.repeat(np.arange(200), 3))
    assert lo < 0.5 < hi and lo < m < hi
    T = 288.0 - 0.0065 * H
    p = 1e5 * (T / 288.0) ** 5.256
    assert (n2(T, p) > 0).all() and abs(float(n2(T, p)[0]) - 1.2e-4) < 0.5e-4   # standard atmosphere N^2 about 1.2e-4
    assert shear_mag(H / 1000.0, 0 * H).round(6).tolist() == [1.0] * (NH - 1)
    assert free_ram_gb() > 0.5
    if os.path.exists(os.path.join(REPO, "data", "igra_heights", EPZ + ".npz")):
        t, b = balloon(EPZ)
        ok = np.isfinite(b["p"][:, 0])
        assert 7e4 < np.nanmedian(b["p"][ok, 0]) < 9.5e4 and 250 < np.nanmedian(b["T"][:, 0]) < 310, "balloon units are not Pa / K"
    print("kit_common selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
