# Colab: HRES refetch with 00Z + 12Z starts (the one Colab download to do)

**What it does:** pulls ECMWF HRES forecasts from WeatherBench2 for 2016-2022, cut to the pilot box (and the Denver box, almost free in the same pass):
- Starts at 00 UTC and 12 UTC.
- Leads out to 10 days, keeping the valid times at 12, 18 and 00 UTC (about 05, 11 and 17 solar time at the site).

**Why:** mode F has only ever seen 00 UTC, which is 17:00 solar (F-8a). This fixes the morning/midday gap, adds 8-10 day leads and gives about 10x more training cases. It is item A in `Strong improvment.md`, and items D (parts 1-2) and E need it too.

**What you need:** a Google account (free Colab plus Google Drive, with about 6 GB free on Drive). Nothing runs on this PC until the final copy.

**Nothing in the repo is changed by this.** The script below is self-contained. You paste it into Colab; you do not need to upload `wb2_fetch.py`.

---

## Expected size and time (estimated from the existing pull, not measured)

| Setting | Value |
|---|---|
| Starts | 00Z and 12Z, each every 4th day (12Z offset by 2 days), so a start every 2 days on average |
| Leads | 6-hourly up to 240 h, keeping valid 12/18/00 UTC only: 30 leads per start |
| Read inside Google | about 450 GB per year (that is free; it never touches your connection) |
| Colab time | about 5-20 h per year, about 35-140 h in total, across many sessions. It resumes per month |
| Output on Drive | about 4 GB pilot + about 1 GB Denver |

**To make it faster:**
- **Several notebooks at once (the big speed-up):** set `PARTS = 3` in cell 2. Open the notebook 3 times with `PART = 0`, `1` and `2`, and run them at the same time. Each takes every 3rd month-hour, and they write to the same Drive folder without clashing. With 3 parts it takes about a third of the time.
  - Free Colab allows only a few sessions per Google account. If one is refused, use a second account and download from both Drives.
  - Keep `PARTS` the same in every copy.
- **`WORKERS = 16`** (the default). 64 and 24 crashed the 12.7 GB runtime. Cell 3 prints the RAM use after each month: if it stays under about 40%, you can try 24.
- **`EVERY_DAYS = 8`:** half the starts, half the time.

---

## Step by step

1. Go to https://colab.research.google.com, then **New notebook**.
2. **Runtime → Change runtime type → CPU** (no GPU needed). Leave the "High-RAM" option off.
3. Paste each cell below into its own code cell, in order.
4. Run cells 1-2, then cell 3 with `TEST_ONE_MONTH = True`, then cell 4 (the check).
5. If the check prints `OK`, set `TEST_ONE_MONTH = False` in cell 2, run cell 2 again, then run cell 3 and leave it running.
6. **When Colab disconnects** (it will: free sessions end after up to about 12 h, or about 90 min idle): reconnect, then run cells 1, 2 and 3 again. Finished months are skipped automatically. Keep the browser tab open, and don't let the PC sleep.
7. When cell 3 prints `ALL DONE` (in every part), run cell 4 once more, then do the copy step at the end.

### Cell 1: install and mount Drive

```python
!pip -q install gcsfs zarr xarray netCDF4 dask
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: settings and helpers

```python
import os, time
import numpy as np, xarray as xr, fsspec, dask, psutil

TEST_ONE_MONTH = True          # first run: only 2016-01, then set False
PART, PARTS = 0, 1             # parallel notebooks: same PARTS in each, PART = 0 .. PARTS-1
OUT = "/content/drive/MyDrive/tempest_wb2_v2"
FIRST, LAST = 2016, 2022       # this store ends 2023-01; do not go past 2022
EVERY_DAYS = 4                 # 00Z and 12Z each every 4th day (12Z offset by 2 days)
HOURS = [0, 12]
MAX_LEAD = 240                 # hours
KEEP_VALID = {12, 18, 0}       # UTC valid hours kept (~05, ~11, ~17 solar); 06Z (~23 solar, night) skipped
WORKERS = 16                   # each worker holds one ~54 MB globe chunk plus its download; 64 and 24 crashed the 12.7 GB runtime

URL = "gs://weatherbench2/datasets/hres/2016-2022-0012-1440x721.zarr"
UNION = dict(latitude=slice(31.0, 40.0), longitude=slice(252.0, 259.0))   # latitudes ascend, longitudes 0-360
BOXES = {"pilot": ((31.0, 34.0), (252.0, 259.0)),        # same box as tempest/ingest/wb2_fetch.py
         "denver": ((38.0, 40.0), (254.0, 256.0))}       # configs/region_denver.toml
UPPER = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t",
         "specific_humidity": "q", "geopotential": "z"}
SURF = {"10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10",
        "2m_temperature": "t2m", "surface_pressure": "sp"}

ds = xr.open_zarr(fsspec.get_mapper(URL, token="anon"), consolidated=True)
T = ds.time.values
DAY = T.astype("datetime64[D]").astype(int)
MON = T.astype("datetime64[M]").astype(int)
HR = T.astype("datetime64[h]").astype(int) % 24

def leads_for(h):
    return [L for L in range(6, MAX_LEAD + 1, 6) if (h + L) % 24 in KEEP_VALID]

def lead_index(L):
    # the store may hold leads as timedelta or as integer hours
    return [np.timedelta64(x, "h") for x in L] if ds.prediction_timedelta.dtype.kind == "m" else list(L)

def starts(y, m, h):
    off = 0 if h == 0 else EVERY_DAYS // 2
    return T[(MON == (y - 1970) * 12 + m - 1) & (HR == h) & (DAY % EVERY_DAYS == off)]

for b in BOXES:
    os.makedirs(f"{OUT}/{b}", exist_ok=True)
print("store opened; leads 00Z:", leads_for(0))
print("leads 12Z:", leads_for(12))
```

### Cell 3: the download (leave running)

```python
import gc, ctypes
months = [(2016, 1)] if TEST_ONE_MONTH else [(y, m) for y in range(FIRST, LAST + 1) for m in range(1, 13)]
mine = [(y, m, h) for (y, m) in months for h in HOURS]
mine = mine if TEST_ONE_MONTH else mine[PART::PARTS]
todo = [(y, m, h) for (y, m, h) in mine
        if not all(os.path.exists(f"{OUT}/{b}/{y}{m:02d}_{h:02d}z.nc") for b in BOXES)]
print(len(todo), "month-hour files to do in this part")
t_start, n = time.time(), 0
for (y, m, h) in todo:
    sel = starts(y, m, h)
    if len(sel) == 0:
        continue
    t0 = time.time()
    sub = ds[list(UPPER) + list(SURF)].sel(time=sel, prediction_timedelta=lead_index(leads_for(h)), **UNION)
    with dask.config.set(scheduler="threads", num_workers=WORKERS):
        sub = sub.load()
    sub = sub.rename({**UPPER, **SURF}).astype("float32")
    for b, (la, lo) in BOXES.items():
        p = f"{OUT}/{b}/{y}{m:02d}_{h:02d}z.nc"
        sub.sel(latitude=slice(*la), longitude=slice(*lo)).to_netcdf(p + ".part")
        os.replace(p + ".part", p)            # only complete files get the final name
    del sub; gc.collect(); ctypes.CDLL("libc.so.6").malloc_trim(0)   # hand freed chunk buffers back to the OS, else RAM creeps up month by month
    n += 1
    eta_h = (time.time() - t_start) / n * (len(todo) - n) / 3600
    print(f"{y}-{m:02d} {h:02d}Z: {len(sel)} starts in {time.time() - t0:.0f} s; about {eta_h:.1f} h left; RAM use {psutil.virtual_memory().percent:.0f}%", flush=True)
print("ALL DONE (this part)" if not TEST_ONE_MONTH else "TEST DONE: run cell 4")
```

### Cell 4: check

```python
import glob
bad = 0
for b, (la, lo) in BOXES.items():
    files = sorted(glob.glob(f"{OUT}/{b}/*z.nc"))
    for f in files:
        x = xr.open_dataset(f)
        h = int(os.path.basename(f)[7:9])
        leads_h = (x.prediction_timedelta.values / np.timedelta64(1, "h")).astype(int) \
                  if x.prediction_timedelta.dtype.kind == "m" else x.prediction_timedelta.values.astype(int)
        ok = (set(x.data_vars) == set(UPPER.values()) | set(SURF.values())
              and x.sizes["level"] == 13
              and x.sizes["latitude"] == round((la[1] - la[0]) / 0.25) + 1
              and x.sizes["longitude"] == round((lo[1] - lo[0]) / 0.25) + 1
              and all((h + L) % 24 in KEEP_VALID for L in leads_h)
              and bool(np.isfinite(x["t"]).all()))
        if not ok:
            bad += 1; print("BAD", f, dict(x.sizes))
        x.close()
    print(b, len(files), "files")
print("OK" if bad == 0 else f"{bad} bad files: delete them and rerun cell 3")
```

Expected shapes: pilot (latitude 13, longitude 29), Denver (9, 9), level 13, 30 leads.

---

## Copy to this PC

1. Wait for `ALL DONE` and the check printing `OK`.
2. In Google Drive (web), right-click the folder `tempest_wb2_v2` and choose **Download**. Drive zips it, and may split it into several zip files.
3. Unzip into **new** folders (never into the existing `data/raw/wb2_hres/`):
   - `tempest_wb2_v2/pilot/*` → `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_hres_v2\`
   - `tempest_wb2_v2/denver/*` → `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_hres_v2_denver\`
4. Tell Claude it is there.

## What the code side then needs (for the session that uses it, not part of the download)

- **File format:**
  - Files are `<yyyymm>_<hh>z.nc`, one per month and start hour, not `<year>.nc`. Load with `xr.open_mfdataset(sorted(glob(...)), combine="nested", concat_dim="time")` per start hour.
  - The 00Z and 12Z files have different lead sets, so keep them as two datasets or align them on valid time.
- **Leads in hours:** `tempest/forecast/modeF.py:load_year` turns leads into whole days (`// NS_DAY`) and matches valid times to days. It must keep hours, use the solar hour as an input, and match the ERA5 truth at the hourly valid time.
- **Next steps:** retrain mode F (lead + solar hour inputs), judge with the usual rule, and widen `FORECAST_LEAD` / `FORECAST_SOLAR` in `tempest_weather/api.py` only where it wins. See item A in `Strong improvment.md`.
- **Disk:** `data/raw` is about 65 GB. This adds about 5 GB, under the 100 GB cap.
