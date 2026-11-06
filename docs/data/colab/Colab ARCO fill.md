# Colab: ERA5 boundary-layer fill from ARCO, the missing months in 6 fixed portions

**What it does:** the same job as the CDS download (`tempest/ingest/fetch_cds.py`): the 8 pressure levels 975-750 hPa (u, v, t, r, z), every hour, over the pilot box. It reads them from Google's ARCO-ERA5 copy, which has no queue. Each month becomes one `<yyyymm>.nc` file, written exactly as `tempest/ingest/arco_fill.py` writes it, and `to_heights` reads it the same way as a CDS `.grib` file.

**Why:** CDS does about one month every 40-45 min, one at a time per account. Here 6 notebooks each work on their own months at the same time.

**Same data?** It was checked against a CDS file (`notebooks/arco_fill_colab.md`):
- u, v and t agree to 0.001, and z to 0.07 m2/s2.
- ARCO has no RH, so RH is computed from specific humidity with the ERA5 formula. It is within 1% RH above 825 hPa. At 975-900 hPa it differs by 2-8% RH, but those levels are below the ground over most of the box, and `to_heights` does not use them.

## What is already done, and what is left (2026-11-06)

- **Already done:**
  - **CDS on the PC:** 1991-01 to 1997-12.
  - **ARCO on your Drive (`tempest_fill`):** 2025-12 to 2025-07, 2023-12 to 2022-07.
- **Left, 312 months:**
  - 2025-01 to 2025-06;
  - all of 2024;
  - 2022-06 down to 1998-01.

These 312 months are split into **6 fixed portions of 52 months**. Each notebook only works on its own portion: it checks only those months, downloads only the missing ones, and cell 4 checks only those files. The other portions are never touched.

| `PART` | Account | Portion (newest → oldest) |
|---|---|---|
| 0 | yours | 2025-06 to 2025-01, all of 2024, 2022-06 to 2019-09 |
| 1 | yours | 2019-08 to 2015-05 |
| 2 | yours | 2015-04 to 2011-01 |
| 3 | other person | 2010-12 to 2006-09 |
| 4 | other person | 2006-08 to 2002-05 |
| 5 | other person | 2002-04 to 1998-01 |

Cell 2 prints the portion when you run it, so you can check it against this table.

## Size and time (estimated, not measured)

| | |
|---|---|
| Read inside Google | about 370 GB per month (free, never on your connection) |
| Written to Drive | about 25 MB per month: about 1.3 GB per portion |
| Colab time | about 20-60 min per month, so about 17-52 h per portion, over several sessions (it resumes per month) |

## Step by step (the same in all 6 notebooks; only `PART` differs)

1. Go to https://colab.research.google.com, then **New notebook**, then **Runtime → Change runtime type → CPU**.
2. Paste the 4 cells below, each into its own code cell. In cell 2, set `PART` from the table.
3. Run cells 1-2. Check that the printed portion matches the table.
4. Run cell 3 with `TEST_ONE_MONTH = True` (one month of the portion), then cell 4. It should print the minutes for one month, and cell 4 should say 0 bad.
5. Set `TEST_ONE_MONTH = False`, rerun cell 2, then run cell 3 and leave it running. The test month is kept and skipped.
6. **After a disconnect:** rerun cells 1, 2 and 3. Finished months in the portion are skipped.
7. **If it runs out of memory:** set `WORKERS = 8`. If RAM stays under about 40%, you can try 24.
8. At `ALL DONE`, run cell 4. It should print `52 of 52 months present, OK`.

### Cell 1: install and mount Drive

```python
!pip -q install gcsfs zarr xarray netCDF4 dask
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: settings, your portion, helpers

```python
import os, time, glob, calendar
import numpy as np, xarray as xr, fsspec, dask, psutil

TEST_ONE_MONTH = True          # first run: one month only, then set False
PART = 0                       # yours: 0, 1, 2. The other account: 3, 4, 5. See the table
OUT = "/content/drive/MyDrive/tempest_fill"   # the folder the earlier ARCO run wrote to
WORKERS = 16                   # hours read at once; each holds about 0.2 GB per variable. 8 if it runs out of memory

def months(a, b):              # a..b inclusive, as yyyymm strings
    out, y, m = [], int(a[:4]), int(a[4:])
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out

# only the months still missing (2026-11-06), newest first, cut into 6 fixed portions of 52
MISSING = sorted(months("202501", "202506") + months("202401", "202412") + months("199801", "202206"), reverse=True)
assert len(MISSING) == 312
MINE = MISSING[PART * 52:(PART + 1) * 52]
MINE_RUN = MINE[:1] if TEST_ONE_MONTH else MINE
print(f"PART {PART}: portion {MINE[0]} down to {MINE[-1]}, {len(MINE)} months")
if PART == 0:
    print("  (that is 2025-06..2025-01, all of 2024, then 2022-06 downward)")

URL = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
LEVELS = [975, 950, 900, 875, 825, 800, 775, 750]
LAT, LON = (34.0, 31.0), (252.0, 259.0)    # configs/region.toml; N to S as in the CDS files, longitudes 0-360
VARS = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t", "geopotential": "z", "specific_humidity": "q"}
T0, TICE = 273.16, 250.16
EPS = 287.0597 / 461.5250

def _es(t, a3, a4):
    return 611.21 * np.exp(a3 * (t - T0) / (t - a4))

def rh_from_q(q, t, p_pa):
    # copy of tempest/ingest/arco_fill.py: ERA5/IFS mixed-phase saturation (water above 0 C, ice below -23 C)
    e = p_pa * q / (EPS + (1 - EPS) * q)
    alpha = np.clip(((t - TICE) / (T0 - TICE)) ** 2, 0, 1)
    alpha = np.where(t >= T0, 1.0, np.where(t <= TICE, 0.0, alpha))
    es = alpha * _es(t, 17.502, 32.19) + (1 - alpha) * _es(t, 22.587, -0.7)
    return np.clip(100 * e / es, 0, 100)

def month(ds, yyyymm):
    t0 = np.datetime64(f"{yyyymm[:4]}-{yyyymm[4:]}-01")
    t1 = (t0.astype("datetime64[M]") + 1).astype("datetime64[h]")
    sub = ds[list(VARS)].sel(time=slice(t0, t1 - np.timedelta64(1, "h")), level=LEVELS,
                             latitude=slice(*LAT), longitude=slice(*LON)).chunk({"time": 1})
    with dask.config.set(scheduler="threads", num_workers=WORKERS):
        sub = sub.load()
    sub = sub.rename(VARS).rename(level="isobaricInhPa")
    p = sub.isobaricInhPa.astype(float) * 100.0
    out = xr.Dataset({"u": sub.u, "v": sub.v, "t": sub.t, "z": sub.z, "r": xr.apply_ufunc(rh_from_q, sub.q, sub.t, p)})
    return out.transpose("time", "isobaricInhPa", "latitude", "longitude").astype("float32")

ds = xr.open_zarr(fsspec.get_mapper(URL, token="anon"), consolidated=True, chunks=None)   # no dask over all 273 variables
os.makedirs(OUT, exist_ok=True)
print("store opened;", sum(os.path.exists(f"{OUT}/{ym}.nc") for ym in MINE), "of this portion already on this Drive")
```

### Cell 3: the download (leave running)

```python
import gc, ctypes
todo = [ym for ym in MINE_RUN if not os.path.exists(f"{OUT}/{ym}.nc")]   # only this portion
print(len(todo), "months to do in this portion")
t_start, n = time.time(), 0
for ym in todo:
    t0 = time.time()
    p = f"{OUT}/{ym}.nc"
    month(ds, ym).to_netcdf(p + ".part")
    os.replace(p + ".part", p)                # only complete files get the final name
    gc.collect(); ctypes.CDLL("libc.so.6").malloc_trim(0)   # hand freed buffers back to the OS
    n += 1
    per = (time.time() - t_start) / n
    print(f"{ym}: {(time.time() - t0) / 60:.0f} min; about {per * (len(todo) - n) / 3600:.1f} h left; RAM use {psutil.virtual_memory().percent:.0f}%", flush=True)
print("ALL DONE (this portion)" if not TEST_ONE_MONTH else "TEST DONE: run cell 4")
```

### Cell 4: check (this portion only)

```python
bad, have = 0, 0
for ym in MINE:
    f = f"{OUT}/{ym}.nc"
    if not os.path.exists(f):
        continue
    have += 1
    x = xr.open_dataset(f)
    hours = calendar.monthrange(int(ym[:4]), int(ym[4:]))[1] * 24
    ok = (set(x.data_vars) == {"u", "v", "t", "z", "r"}
          and dict(x.sizes) == {"time": hours, "isobaricInhPa": 8, "latitude": 13, "longitude": 29}
          and bool(np.isfinite(x["t"]).all()) and float(x["r"].max()) <= 100)
    if not ok:
        bad += 1; print("BAD", f, dict(x.sizes))
    x.close()
print(f"PART {PART}: {have} of {len(MINE)} months present,", "OK" if bad == 0 else f"{bad} bad files: delete them and rerun cell 3")
```

---

## Copy to this PC

1. Wait for `ALL DONE` and `52 of 52 months present, OK` in every portion.
2. On each account, in Google Drive (web), right-click `tempest_fill` and choose **Download**. Your folder also holds the months the earlier run finished, so copy those too.
3. Unzip the `.nc` files into `C:\Users\Senai\Tempest-ARKNET\data\raw\era5_cds\`, next to the `.grib` files. Do not overwrite anything there. If a month already has a `.grib`, the grib is used.
4. Tell Claude. The CDS downloader (`fetch_cds`) only looks for `.grib` files, so it keeps asking CDS for months from 1998 onward that ARCO will cover. Stop it once the ARCO portions are done (or restart it with `--last 1997`).

**Disk:** `data/raw` is about 65 GB. All ARCO months together add about 10 GB; with the HRES and ENS pulls the total is about 85 GB, under the 100 GB cap.
