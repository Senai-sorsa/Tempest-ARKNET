"""MERRA-2 model-level subset for A1 (18-80 km layer; docs/plans/LAUNCH_PLAN.md, Limitations 5.2.8).

    python -m tempest.ingest.fetch_merra2 --dry-run                 # one day into a temp folder: check variables, top height, size
    python -m tempest.ingest.fetch_merra2 [--out data/raw/merra2] [--first-year 1991] [--last-year 2025]

Collection M2I3NVASM (inst3_3d_asm_Nv: 72 model levels up to 0.01 hPa, about 80 km; 3-hourly; 0.5 x 0.625 deg).
Server-side Earthdata Cloud OPeNDAP (DAP4) subset of the box (default 31-40 N, 108-101 W), variables T, U, V, H (mid-layer height), PL,
00Z and 12Z only, days 1, 11 and 21 of each month: A1 needs a per-site x month climatology above 18 km, not every day.
One file per day, data/raw/merra2/YYYYMMDD.nc4 (skipped if present: re-running resumes).
Token: NASA Earthdata, ~/.earthdata_token (never in the repo, never printed), sent as Authorization: Bearer.
Years after 2025 are refused (2026 is the final test).
shortcut: 3 days a month x 2 hours samples the climatology, not the day-to-day spread; fetch more days if A1's
spread above 48 km turns out to matter.
"""
import argparse
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

# GES DISC on-prem OPeNDAP (goldsmr5) answers 410 since its retirement; Cloud OPeNDAP, collection concept id from CMR
BASE = "https://opendap.earthdata.nasa.gov/collections/C1276812900-GES_DISC/granules/M2I3NVASM.5.12.4:"
VARS = ("T", "U", "V", "H", "PL")
DAYS = (1, 11, 21)
TIMES = (0, 4)                     # 3-hourly file: index 0 = 00Z, 4 = 12Z


def stream(year, month):
    """MERRA-2 production stream in the file name (a few months were reprocessed as 401)."""
    return 100 if year <= 1991 else 200 if year <= 2000 else 300 if year <= 2010 else 400


def box_index(lat0, lat1, lon0, lon1):
    """Degrees -> inclusive index ranges on the MERRA-2 grid (lat -90 + 0.5 j, lon -180 + 0.625 i)."""
    import math
    return (math.floor((lat0 + 90) / 0.5), math.ceil((lat1 + 90) / 0.5),
            math.floor((lon0 + 180) / 0.625), math.ceil((lon1 + 180) / 0.625))


def url(year, month, day, idx, s=None):
    j0, j1, i0, i1 = idx
    s = s or stream(year, month)
    f = f"MERRA2_{s}.inst3_3d_asm_Nv.{year:04d}{month:02d}{day:02d}.nc4"
    sub = f"[{TIMES[0]}:{TIMES[1] - TIMES[0]}:{TIMES[1]}]"
    c = ";".join([f"/{v}{sub}[0:1:71][{j0}:1:{j1}][{i0}:1:{i1}]" for v in VARS] + [f"/lat[{j0}:1:{j1}]", f"/lon[{i0}:1:{i1}]", "/lev", f"/time{sub}"])
    return f"{BASE}{f}.dap.nc4?dap4.ce=" + urllib.parse.quote(c, safe="/:;")   # ';' must stay literal: encoded, Hyrax answers 500


def get(u, token, dest, tries=3):
    req = urllib.request.Request(u, headers={"Authorization": f"Bearer {token}"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
                f.write(r.read())
            os.replace(dest + ".part", dest)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if k == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if k == tries - 1:
                raise
        time.sleep(10 * (k + 1))
    return False


def fetch_day(year, month, day, idx, token, out):
    dest = os.path.join(out, f"{year:04d}{month:02d}{day:02d}.nc4")
    if os.path.exists(dest):
        return dest
    for s in (stream(year, month), 401):                  # reprocessed months live under stream 401
        if get(url(year, month, day, idx, s), token, dest):
            return dest
    raise FileNotFoundError(f"MERRA-2 {year}-{month:02d}-{day:02d}: not found under stream {stream(year, month)} or 401")


def _selfcheck():
    assert box_index(31, 40, -108, -101) == (242, 260, 115, 127)
    assert stream(1991, 1) == 100 and stream(1995, 6) == 200 and stream(2005, 1) == 300 and stream(2024, 1) == 400
    u = url(2024, 1, 1, (242, 260, 115, 127))
    assert "M2I3NVASM.5.12.4:MERRA2_400.inst3_3d_asm_Nv.20240101.nc4.dap.nc4?dap4.ce=" in u
    assert "/T%5B0:4:4%5D%5B0:1:71%5D%5B242:1:260%5D%5B115:1:127%5D;" in u and "%3B" not in u


def main():
    _selfcheck()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw/merra2")
    ap.add_argument("--first-year", type=int, default=1991)
    ap.add_argument("--last-year", type=int, default=2025)
    ap.add_argument("--box", type=float, nargs=4, default=(31, 40, -108, -101), metavar=("LAT0", "LAT1", "LON0", "LON1"))
    ap.add_argument("--dry-run", action="store_true", help="fetch 2024-01-01 into a temp folder, report variables, top height and the full-run size, write nothing under --out")
    a = ap.parse_args()
    if a.last_year > 2025:
        sys.exit("years after 2025 are the final test: refused")
    token = open(os.path.expanduser("~/.earthdata_token"), encoding="utf-8").read().strip()
    idx = box_index(*a.box)
    if a.dry_run:
        import numpy as np
        import xarray as xr
        tmp = tempfile.mkdtemp(prefix="merra2_dry_")
        t0 = time.time()
        p = fetch_day(2024, 1, 1, idx, token, tmp)
        dt, size = time.time() - t0, os.path.getsize(p)
        with xr.open_dataset(p) as ds:
            print(ds)
            h = ds["H"].values
            print(f"top mid-layer height {np.nanmax(h) / 1000:.1f} km, lowest {np.nanmin(h) / 1000:.2f} km; "
                  f"levels {ds.sizes.get('lev')}, times {ds.sizes.get('time')}, grid {ds.sizes.get('lat')} x {ds.sizes.get('lon')}")
        n = (a.last_year - a.first_year + 1) * 12 * len(DAYS)
        print(f"one day: {size / 1e6:.2f} MB in {dt:.1f} s; full run {n} days: about {n * size / 1e9:.2f} GB, {n * dt / 3600:.1f} h at this speed")
        print(f"dry-run file: {p} (temp folder, not under {a.out})")
        return
    os.makedirs(a.out, exist_ok=True)
    for y in range(a.first_year, a.last_year + 1):
        for m in range(1, 13):
            for d in DAYS:
                fetch_day(y, m, d, idx, token, a.out)
        print(f"{y} done", flush=True)


if __name__ == "__main__":
    main()
