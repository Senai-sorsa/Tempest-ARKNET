"""IGRA2 plain sounding files (data-por, *-data.txt.zip) -> one small npz per station on the extended height grid.

    python -m tempest.ingest.igra_to_heights [--raw data/raw/igra2_data] [--out data/igra_heights]
                                             [--first-year 1991] [--last-year 2025] [--workers 4] [--delete-raw]

Done once, for both uses: the 44 model heights (0-18 km, today's training/calibration) and the A1 extension
(19-30 km every 1 km, 32-80 km every 2 km = EXT_HEIGHTS, 81 heights). Balloons burst at ~30-35 km, so the columns above
are NaN here; ERA5 pressure/model levels fill them later. Every launch hour is kept (time holds the UTC hour).

Plain files report geopotential height only on some levels (mandatory levels in older records). Heights for the
other pressure levels come from the hypsometric equation (virtual temperature, T interpolated in ln p), shifted to
match the reported heights (offset interpolated in ln p). Wind-only levels without pressure use their reported
height. Heights are geometric metres above the launch surface, as in tempest.calibrate.station.read_igra.

Output <ID>.npz: time (S,) datetime64[h]; lat, lon (S,) float32; elev (S,) launch height m; heights (H,);
u, v (m/s), T (K), RH (%) as int16 x10 and lnp = round(2000 ln(p/Pa)) as int16, all with MISSING (load() decodes);
sfc (S,3) T K, p Pa, RH %.
Never reads 2026 (last year is capped at 2025) or a holdout station (re-checked against points.npz held_igra).
"""
import argparse
import glob
import io
import os
import zipfile
from multiprocessing import Pool

import numpy as np

from tempest.calibrate.station import to_grid
from tempest.profiles.to_heights import G0, HEIGHTS, geometric_height, magnus_rh

EXT_HEIGHTS = np.concatenate([HEIGHTS, np.arange(19000, 30001, 1000), np.arange(32000, 80001, 2000)]).astype(HEIGHTS.dtype)
MISSING = np.int16(-32768)
RD, EPS = 287.05, 0.622
# plain-file data columns: LVLTYP1 0, LVLTYP2 1, PRESS Pa, GPH m, TEMP C*10, RH %*10, DPDP C*10, WDIR deg, WSPD m/s*10
COLS = [(9, 15), (16, 21), (22, 27), (28, 33), (34, 39), (40, 45), (46, 51)]


def parse(text):
    """Whole file -> list of (header line, int array (n, 9): lt1, lt2, p, gph, t, rh, dpd, wdir, wspd; NaN missing)."""
    lines = text.splitlines()
    head = [i for i, l in enumerate(lines) if l.startswith("#")]
    data = np.array([l.ljust(52)[:52] for l in lines], "S52")
    raw = data.view(np.uint8).reshape(-1, 52)
    f = lambda a, b: raw[:, a:b].copy().view(f"S{b - a}").ravel()  # noqa: E731
    out = np.empty((len(lines), 9))
    out[:, 0] = raw[:, 0].astype(int) - 48
    out[:, 1] = raw[:, 1].astype(int) - 48  # digits; anything else is not 1 or 2
    body = np.ones(len(lines), bool)
    body[head] = False
    for k, (a, b) in enumerate(COLS):
        col = np.full(len(lines), np.nan)
        col[body] = f(a, b)[body].astype(float)
        out[:, 2 + k] = col
    out[out <= -8888] = np.nan
    return [(lines[i], out[i + 1:j]) for i, j in zip(head, head[1:] + [len(lines)])]


def heights_gph(lt2, p, gph, tk, rh):
    """Geopotential height (m) on every level: reported where given, else hypsometric between reported ones."""
    z = gph.copy()
    pl = np.flatnonzero(np.isfinite(p) & (p > 0))
    if len(pl) < 2:
        return z
    lp = np.log(p[pl])
    okt = np.isfinite(tk[pl])
    if okt.sum() < 2:
        return z
    t = np.interp(-lp, -lp[okt], tk[pl][okt], left=np.nan, right=np.nan)  # T on all pressure levels (ln p)
    tc = t - 273.15
    e = np.nan_to_num(rh[pl] / 100) * 611.2 * np.exp(17.67 * tc / (tc + 243.5))
    tv = t * (1 + 0.61 * EPS * e / p[pl])
    dz = RD / G0 * 0.5 * (tv[1:] + tv[:-1]) * (lp[:-1] - lp[1:])
    zh = np.concatenate([[0.0], np.cumsum(dz)])  # NaN after the first level without T
    anc = np.isfinite(zh) & np.isfinite(gph[pl])
    if not anc.any():
        return z
    off = np.interp(-lp, -lp[anc], (gph[pl] - zh)[anc])  # offset to the reported heights, constant beyond the ends
    fill = np.isnan(z[pl])
    z[pl[fill]] = (zh + off)[fill]
    return z


def sounding(a, grid):
    """(n, 9) levels -> (u, v, T, RH, p on grid, surface T/p/RH, launch gph) or None."""
    lt1, lt2, p, gph, t, rh, dpd, wdir, wspd = a.T
    tk = t / 10 + 273.15
    rh = np.where(np.isfinite(rh), rh / 10, magnus_rh(tk, tk - dpd / 10))
    z = heights_gph(lt2, p, gph, tk, rh)
    sfc = np.flatnonzero(lt2 == 1)
    i0 = sfc[0] if len(sfc) and np.isfinite(z[sfc[0]]) else None
    if i0 is None:
        return None
    h = geometric_height(z * G0) - geometric_height(z[i0] * G0)
    spd, d = wspd / 10, np.deg2rad(wdir)
    out = [to_grid(h, -spd * np.sin(d), grid), to_grid(h, -spd * np.cos(d), grid), to_grid(h, tk, grid),
           to_grid(h, np.clip(rh, 0, 100), grid)]
    return out, to_grid(h, np.log(p), grid), [tk[i0], p[i0], rh[i0]], z[i0]


def enc(x, scale):
    return np.where(np.isfinite(x), np.round(x * scale), MISSING).astype(np.int16)


def convert(path, out_dir, first_year, last_year, grid=EXT_HEIGHTS):
    sid = os.path.basename(path).split("-")[0]
    dst = os.path.join(out_dir, f"{sid}.npz")
    if os.path.exists(dst):
        return sid, -1
    with zipfile.ZipFile(path) as zf, zf.open(zf.namelist()[0]) as f:
        text = io.TextIOWrapper(f, "ascii", errors="replace").read()
    times, lat, lon, elev, prof, pp, sfc = [], [], [], [], [], [], []
    for hd, a in parse(text):
        year, hour, rel = int(hd[13:17]), int(hd[24:26]), int(hd[27:31])
        if not first_year <= year <= last_year or len(a) < 3:
            continue
        if hour == 99:
            if rel == 9999 or rel // 100 > 23:
                continue
            hour = rel // 100
        r = sounding(a, grid)
        if r is None:
            continue
        times.append(f"{hd[13:17]}-{hd[18:20]}-{hd[21:23]}T{hour:02d}")
        lat.append(int(hd[55:62]) / 1e4)
        lon.append(int(hd[63:71]) / 1e4)
        elev.append(geometric_height(r[3] * G0))
        prof.append(r[0])
        pp.append(r[1])
        sfc.append(r[2])
    prof = np.array(prof, np.float32).reshape(-1, 4, len(grid))
    q = enc(prof, 10)
    tmp = dst + ".part.npz"
    np.savez_compressed(tmp, time=np.array(times, "datetime64[h]"), lat=np.float32(lat), lon=np.float32(lon),
                        elev=np.float32(elev), heights=grid, u=q[:, 0], v=q[:, 1], T=q[:, 2], RH=q[:, 3],
                        lnp=enc(np.array(pp, np.float32).reshape(-1, len(grid)), 2000), sfc=np.array(sfc, np.float32).reshape(-1, 3))
    os.replace(tmp, dst)
    return sid, len(times)


def load(path):
    """npz -> dict with u, v, T, RH and p (Pa) back as float32 (NaN missing)."""
    with np.load(path) as d:
        out = {k: d[k] for k in d.files}
    for k in ("u", "v", "T", "RH"):
        x = out[k]
        out[k] = np.where(x == MISSING, np.nan, x / np.float32(10)).astype(np.float32)
    lnp = out.pop("lnp")
    out["p"] = np.where(lnp == MISSING, np.nan, np.exp(lnp / 2000.0)).astype(np.float32)
    return out


def _job(args):
    path, out, fy, ly, delete = args
    try:
        sid, n = convert(path, out, fy, ly)
    except Exception as e:  # one bad file must not stop the rest; it is reported and its raw zip kept
        return os.path.basename(path), f"FAILED {e!r}"
    if delete and n >= 0:
        os.remove(path)
    return sid, "exists" if n < 0 else f"{n} soundings"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw/igra2_data")
    ap.add_argument("--out", default="data/igra_heights")
    ap.add_argument("--points", default="data/raw/era5_global/points.npz")
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delete-raw", action="store_true", help="remove each raw zip once its npz is written")
    a = ap.parse_args()
    assert a.last_year <= 2025, "2026 is never used"
    os.makedirs(a.out, exist_ok=True)
    held = set(np.load(a.points)["held_igra"]) if os.path.exists(a.points) else set()
    files = sorted(glob.glob(os.path.join(a.raw, "*-data.txt.zip")))
    files = [f for f in files if os.path.basename(f).split("-")[0] not in held]
    print(f"{len(files)} station files -> {a.out} ({len(EXT_HEIGHTS)} heights)", flush=True)
    with Pool(a.workers) as pool:
        for i, (sid, msg) in enumerate(pool.imap_unordered(_job, [(f, a.out, a.first_year, a.last_year, a.delete_raw)
                                                                  for f in files]), 1):
            print(f"{i}/{len(files)} {sid}: {msg}", flush=True)
    print("igra_to_heights done", flush=True)


if __name__ == "__main__":
    main()
