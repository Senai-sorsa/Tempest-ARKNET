# Colab: IFS ensemble (ifs_ens), 500/700/850 hPa, pilot + Denver box

**What it does:** pulls the ECMWF IFS 50-member ensemble forecasts from WeatherBench2, cut to the pilot box and the Denver box:
- 00 UTC starts, every 4th day, 2016-2022.
- Leads 24, 48, ..., 240 h (valid 00 UTC, about 17 solar at the site).
- Levels 500/700/850 hPa: u, v, t, q, z, plus u10, v10, t2m and msl. This store has no surface pressure.

This is item C3 in `Colab downloads.md` (the early version of item C). It is the most optional pull, so skip it if waiting 60-90 days for the logger is fine.

**Nothing in the repo is changed by this.** The cells are self-contained.

---

## Store layout (read from its metadata, 2026-11-05)

- **Store:** `gs://weatherbench2/datasets/ifs_ens/2016-2024-1440x721.zarr`, 00Z and 12Z starts, 61 leads (0-360 h every 6 h).
- **Chunk:** one chunk holds **all 50 members** for one start and one lead, over the whole globe:
  - about 620 MB uncompressed per upper-air variable (3 levels);
  - about 210 MB per surface variable.
- **What this means:**
  - You always read all 50 members, so taking fewer members saves nothing.
  - Each worker holds about 1.5-2 GB in memory, so `WORKERS` is 3. Colab has 12.7 GB.
  - Per start: 10 leads × (5 × 620 + 4 × 210 MB) = **about 40 GB read** (inside Google, free, never on your connection).

## Size and time

| | |
|---|---|
| Starts | about 640 (2016-2022) |
| Read inside Google | about 25 TB in total (uncompressed size) |
| Written to Drive | about 14 MB per start for pilot, 3 MB for Denver: **about 11 GB in total** |
| Colab time | **measured by the test month (cell 3).** Expect tens of hours. Split it with `PARTS` (below) |

**To make it faster** (cell 2):
- **`PARTS`: run several notebooks at the same time.** See "Running in parallel" below. With 3 sessions it finishes in about a third of the time.
- **`EVERY_DAYS = 8`:** half the starts, half the time.
- **`LEADS = [24, 72, 120, 168, 240]`:** half the leads, half the time.

---

## Running in parallel (the big speed-up)

The time goes into reading whole-globe chunks, so one notebook cannot go much faster. Several notebooks at once can.

1. Set `PARTS = 3` (for example) in cell 2.
2. Open the notebook 3 times (File → Save a copy, or separate tabs), each with its own `PART`: 0, 1 and 2.
3. Run them all at once. Each takes every 3rd month, and they all write to the same Drive folder without clashing.

Free Colab allows only a few sessions at once per Google account. If a second one is refused, use a second Google account: its files land on that account's Drive, so download from both. Keep `PARTS` the same in every copy.

---

## Step by step

1. Go to https://colab.research.google.com, then **New notebook**, then **Runtime → Change runtime type → CPU**.
2. Paste each cell below into its own code cell, in order.
3. Run cells 1-2. If cell 2 prints `STOP`, send the output to Claude.
4. Run cell 3 with `TEST_ONE_MONTH = True`, then cell 4. Note the `full run would take` line, and divide it by `PARTS`.
5. If cell 4 prints `OK`, set `TEST_ONE_MONTH = False` (and `PARTS` / `PART`). Rerun cell 2, then cell 3, and leave it running.
6. **After a disconnect:** rerun cells 1, 2 and 3. Finished months are skipped.
7. **If Colab says it ran out of memory:** set `WORKERS = 2` and rerun.
8. At `ALL DONE` (in every part), run cell 4 once, then follow the copy step.

### Cell 1: install and mount Drive

```python
!pip -q install gcsfs zarr xarray netCDF4 dask
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: settings and size check

```python
import os, time, glob
import numpy as np, xarray as xr, fsspec, dask, psutil

TEST_ONE_MONTH = True          # first run: only the first month, then set False
PART, PARTS = 0, 1             # parallel notebooks: same PARTS in each, PART = 0 .. PARTS-1
OUT = "/content/drive/MyDrive/tempest_wb2_ifs_ens"
FIRST, LAST = 2016, 2022       # the store runs to 2024; 2016-2022 matches the HRES set
EVERY_DAYS = 4
LEADS = list(range(24, 241, 24))
LEVELS = [500, 700, 850]
WORKERS = 3                    # each worker holds one ~620 MB chunk plus its download (~1.5-2 GB); 2 if Colab runs out of memory

URL = "gs://weatherbench2/datasets/ifs_ens/2016-2024-1440x721.zarr"
UNION = ((31.0, 40.0), (252.0, 259.0))
BOXES = {"pilot": ((31.0, 34.0), (252.0, 259.0)),        # same box as tempest/ingest/wb2_fetch.py
         "denver": ((38.0, 40.0), (254.0, 256.0))}       # configs/region_denver.toml
UPPER = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t",
         "specific_humidity": "q", "geopotential": "z"}
SURF = {"10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10",
        "2m_temperature": "t2m", "mean_sea_level_pressure": "msl"}
MEM = "number"

ds = xr.open_zarr(fsspec.get_mapper(URL, token="anon"), consolidated=True)
lead_has = (ds.prediction_timedelta.values / np.timedelta64(1, "h")).astype(int) \
           if ds.prediction_timedelta.dtype.kind == "m" else ds.prediction_timedelta.values.astype(int)
lat_up = bool(ds.latitude[1] > ds.latitude[0])
problems = [s for s, bad in [("variables missing", not set(UPPER) | set(SURF) <= set(ds.data_vars)),
                             ("no member dimension", MEM not in ds.dims),
                             ("levels missing", not set(LEVELS) <= set(ds.level.values.tolist())),
                             ("leads missing", not set(LEADS) <= set(lead_has.tolist())),
                             ("longitudes not 0-360", float(ds.longitude.max()) < 180)] if bad]
print("STOP, send this output to Claude:" if problems else "store looks usable", problems)
print("members:", ds.sizes[MEM], " lat ascending:", lat_up)

def lead_index(L):
    return [np.timedelta64(x, "h") for x in L] if ds.prediction_timedelta.dtype.kind == "m" else list(L)

def lat_slice(la):
    return slice(*la) if lat_up else slice(la[1], la[0])

T = ds.time.values
DAY = T.astype("datetime64[D]").astype(int)
MON = T.astype("datetime64[M]").astype(int)
HR = T.astype("datetime64[h]").astype(int) % 24

def starts(y, m):
    return T[(MON == (y - 1970) * 12 + m - 1) & (HR == 0) & (DAY % EVERY_DAYS == 0)]

def subset(sel):
    return ds[list(UPPER) + list(SURF)].sel(time=sel, prediction_timedelta=lead_index(LEADS), level=LEVELS,
                                            latitude=lat_slice(UNION[0]), longitude=slice(*UNION[1]))

ALL = [(y, m) for y in range(FIRST, LAST + 1) for m in range(1, 13) if len(starts(y, m))]
MINE = ALL[:1] if TEST_ONE_MONTH else ALL[PART::PARTS]
n_starts = sum(len(starts(y, m)) for (y, m) in ALL)
one = subset(T[HR == 0][:1])
read_gb = sum(np.prod(ds[k].encoding["chunks"]) * len(LEADS) * 4 for k in one.data_vars) / 1e9   # 1 chunk per lead
mb = {b: one.sel(latitude=lat_slice(la), longitude=slice(*lo)).nbytes / 2 * 1e-6 for b, (la, lo) in BOXES.items()}  # float32 out
print(f"{n_starts} starts in {len(ALL)} months; this part does {len(MINE)} months")
print(f"about {read_gb:.0f} GB read per start (inside Google)")
print("written per start (MB):", {b: round(v, 1) for b, v in mb.items()},
      " total on Drive (GB):", round(sum(mb.values()) * n_starts / 1000, 1))
for b in BOXES:
    os.makedirs(f"{OUT}/{b}", exist_ok=True)
```

### Cell 3: the download (leave running)

```python
todo = [(y, m) for (y, m) in MINE if not all(os.path.exists(f"{OUT}/{b}/{y}{m:02d}_00z.nc") for b in BOXES)]
print(len(todo), "months to do in this part")
t_start, n = time.time(), 0
for (y, m) in todo:
    sel = starts(y, m)
    t0 = time.time()
    with dask.config.set(scheduler="threads", num_workers=WORKERS):
        sub = subset(sel).load()
    sub = sub.rename({**UPPER, **SURF}).astype("float32")
    for b, (la, lo) in BOXES.items():
        p = f"{OUT}/{b}/{y}{m:02d}_00z.nc"
        sub.sel(latitude=lat_slice(la), longitude=slice(*lo)).to_netcdf(p + ".part")
        os.replace(p + ".part", p)            # only complete files get the final name
    n += 1
    per = (time.time() - t_start) / n
    print(f"{y}-{m:02d}: {len(sel)} starts in {time.time() - t0:.0f} s; about {per * (len(todo) - n) / 3600:.1f} h left; RAM use {psutil.virtual_memory().percent:.0f}%"
          + (f" (full run: about {per * len(ALL) / 3600:.0f} h in one notebook)" if TEST_ONE_MONTH else ""), flush=True)
print("ALL DONE (this part)" if not TEST_ONE_MONTH else "TEST DONE: run cell 4")
```

### Cell 4: check (checks every file in the folder, from all parts)

```python
bad = 0
for b, (la, lo) in BOXES.items():
    files = sorted(glob.glob(f"{OUT}/{b}/*_00z.nc"))
    for f in files:
        x = xr.open_dataset(f)
        ok = (set(x.data_vars) == set(UPPER.values()) | set(SURF.values())
              and x.sizes[MEM] == ds.sizes[MEM]
              and x.sizes["prediction_timedelta"] == len(LEADS)
              and list(x.level.values) == LEVELS
              and x.sizes["latitude"] == round((la[1] - la[0]) / 0.25) + 1
              and x.sizes["longitude"] == round((lo[1] - lo[0]) / 0.25) + 1
              and bool((x.time.dt.hour == 0).all())
              and all(bool(np.isfinite(x[v]).all()) for v in x.data_vars))
        if not ok:
            bad += 1; print("BAD", f, dict(x.sizes))
        x.close()
    print(b, len(files), "of", len(ALL), "files")
print("OK" if bad == 0 else f"{bad} bad files: delete them and rerun cell 3")
```

Expected shapes: pilot (latitude 13, longitude 29), Denver (9, 9), level 3, 10 leads, 50 members.

---

## Copy to this PC

1. Wait for `ALL DONE` in every part, and for cell 4 to print `OK` with all files present.
2. In Google Drive (web), right-click `tempest_wb2_ifs_ens` and choose **Download** (from each account if you used more than one).
3. Unzip into **new** folders:
   - `tempest_wb2_ifs_ens/pilot/*` → `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_ifs_ens\`
   - `tempest_wb2_ifs_ens/denver/*` → `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_ifs_ens_denver\`
4. Tell Claude it is there.

## What the code side then needs (not part of the download)

- **File format:** files are `<yyyymm>_00z.nc`, one per month, with a member dimension `number` (50). Load with `xr.open_mfdataset(sorted(glob(...)), combine="nested", concat_dim="time")`.
- **Levels:** only 3, so these cannot feed the 13-level profile builder directly. Use them for the spread and calibration checks (IL-98 C style), or interpolate in log-p between the levels.
- **Disk:** about 11 GB. `data/raw` is about 65 GB, so this fits under the 100 GB cap.
