# Colab: IFS extended range (weeks 1-6), upper-air weekly means, forecasts + 20-year reforecasts

**What it does:** pulls the ECMWF IFS extended-range forecasts from WeatherBench2 as **weekly-mean upper-air fields (ensemble mean)**, cut to the pilot box and the Denver box (optionally also the six G2 boxes):
- **Forecasts:** 730 starts, 2016-01-04 to 2022-12-29 (about twice a week), leads 0-40 days.
- **Reforecasts (hindcasts):** the same 730 start dates, each re-run for the previous 20 years (about 1996-2021). This is the long upper-air history that weeks 3-6 had been missing (IL-118).
- **Levels:** 100, 200, 300, 500, 700, 850, 925, 1000 hPa (the store also has 10 and 50 hPa; add them in cell 2 if you want the stratosphere).
- **Variables:** u, v, temperature, specific humidity, geopotential. (Specific humidity is empty in the store at 10, 50 and 100 hPa, so it is read from 200 hPa down and is NaN at 100 hPa in the output files by design.)
- **Grid:** the store is 1.5 degrees, so a box holds only a handful of points. Each box is cut with a one-cell margin so interpolation to the site is possible.

This is backlog item **IL-118** (`docs/logs/AUTOPILOT.md`). Its downloads are covered by the **5 GB budget** the user approved on 2026-11-07 for IL-118 to IL-127.

**Nothing in the repo is changed by this.** The cells are self-contained.

---

## Store layout (read from the store's metadata, 2026-11-07)

- **Forecast store:** `gs://weatherbench2/datasets/ifs_extended_range/weekly/ifs-ext-pressure-levels-weekly_avg_ens_mean.zarr`
  - Dimensions: `time` 730, `prediction_timedelta` 41, `level` 10, `latitude` 121, `longitude` 240. Variables `u_component_of_wind`, `v_component_of_wind`, `temperature`, `specific_humidity`, `geopotential`, all `float32`.
  - Chunk: 1 start, 14 leads, 1 level, the whole globe = **about 1.6 MB**. One variable, start and level needs 3 chunks to cover all 41 leads.
- **Reforecast store:** `gs://weatherbench2/datasets/ifs_extended_range/weekly/ifs-ext-reforecast-pressure-levels-weekly_avg_ens_mean.zarr`
  - Dimensions: `forecast_time` 730 (the real start dates, 2016-2022), `hindcast_year` 20 (values -20 to -1), then the same as above. The coordinate `time` (730 x 20) holds the actual date of each hindcast.
  - Chunk: 1 start, 1 hindcast year, 14 leads, 1 level, whole globe = about 1.6 MB.
- **Specific humidity is empty (NaN) at 10, 50 and 100 hPa** in both stores (measured on three starts); the other four variables are complete at all 10 levels.
- **Ensemble mean only.** These stores hold the mean of the ensemble, so there is no spread. The all-member version (`..._weekly_avg.zarr`) would give the spread but is far larger; ask Claude before pulling it.
- **What a weekly average covers (tested 2026-11-07 against ERA5 at the pilot box):** lead k is the mean of the 7 daily values for days k, k+1, ..., k+6, each daily value being a 24 h mean **centred on 00 UTC of that day**. In hours: the 168 h window **[start + k days - 12 h, start + (k+7) days - 12 h)**. Three readings were compared: forward from k (best, anomaly correlation 0.94 at lead 0 for 500 hPa temperature), centred on k (0.78) and trailing to k (0.34). A timing test on lead-to-lead increments peaked sharply at -12 h for temperature, geopotential and wind (forecasts and reforecasts, 6 h resolution). Pair each lead with the ERA5 hourly mean over that window.
- **What this means:** chunks are small, but each one is a whole-globe field, so reading is the cost (inside Google, free, never on your connection).

## Size and time

| | |
|---|---|
| Starts used | `START_EVERY = 2`: 365 of the 730 (about one a week) |
| Hindcast years used | `HINDCAST_STEP = 2`: 10 of the 20 (-1, -3, ... -19) |
| Read inside Google | about 770 GB in total (**estimate**: 11 fields per start x 5 variables x 8 levels x 3 chunks of 1.6 MB, over 365 starts) |
| Written to Drive | about 0.25 MB per start-year for pilot + Denver: **about 1 GB in total** (estimate; the test month prints the real number) |
| Colab time | **measured by the test month (cell 3).** Rough estimate from the HRES pulls: 3-11 h in one notebook, **about 1-4 h per part with 3 parts** |

**Budget check:** the 5 GB budget is for all of IL-118 to IL-127 together. With the defaults this pull is about 1 GB. With the six G2 boxes on, the defaults are about 3 GB. The most it can reach (all 730 starts, all 20 years) is about 4 GB for pilot + Denver and about 12 GB with the G2 boxes, with about 3 TB read, so do not turn everything on at once.

**To make it faster** (cell 2):
- **`PARTS`:** run several notebooks at the same time (see below).
- **`START_EVERY = 4`:** half the starts, half the time. **`HINDCAST_STEP = 4`:** half the hindcast years.
- **Fewer levels:** the cost scales with the number of levels.

**To get more** (only if the budget allows; ask first): `START_EVERY = 1`, `HINDCAST_STEP = 1`. Use a new `OUT` folder, because finished months in the old one would be skipped.

---

## Running in parallel (the big speed-up)

1. Set `PARTS = 3` (for example) in cell 2.
2. Open the notebook 3 times (File -> Save a copy, or separate tabs), each with its own `PART`: 0, 1 and 2.
3. Run them all at once. Each takes every 3rd month and they all write to the same Drive folder without clashing.

Free Colab allows only a few sessions at once per Google account. If a second one is refused, use a second Google account: its files land on that account's Drive, so download from both. Keep `PARTS` the same in every copy.

---

## Step by step

1. Go to https://colab.research.google.com, then **New notebook**, then **Runtime -> Change runtime type -> CPU**.
2. Paste each cell below into its own code cell, in order.
3. Run cells 1-2. If cell 2 prints `STOP`, send the output to Claude.
4. Run cell 3 with `TEST_ONE_MONTH = True`, then cell 4. Note the `full run: about X h in one notebook` line, and divide it by `PARTS`.
5. If cell 4 prints `OK`, set `TEST_ONE_MONTH = False` (and `PARTS` / `PART`). Rerun cell 2, then cell 3, and leave it running.
6. **After a disconnect:** rerun cells 1, 2 and 3. Finished months are skipped.
7. **If Colab says it ran out of memory:** set `WORKERS = 4` and rerun cells 2 and 3.
8. At `ALL DONE` (in every part), run cell 4 once, then follow the copy step.

### Cell 1: install and mount Drive

```python
!pip -q install -U gcsfs "zarr>=3" xarray netCDF4 dask
import zarr, xarray   # if this line fails, or cell 2 says "unrecognized engine 'zarr'": Runtime -> Restart session, then run cells 1-2 again
print("zarr", zarr.__version__, "xarray", xarray.__version__)
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: settings and size check

```python
import os, time, glob, gc
import numpy as np, xarray as xr, fsspec
from concurrent.futures import ThreadPoolExecutor

TEST_ONE_MONTH = True          # first run: only the first month, then set False
PART, PARTS = 0, 3             # 3 notebooks: PART = 0 in the first copy, 1 in the second, 2 in the third
OUT = "/content/drive/MyDrive/tempest_wb2_ifs_extended"
START_EVERY = 2                # 1 = all 730 starts; 2 = every 2nd start (about one a week)
HINDCAST_STEP = 2              # 1 = all 20 hindcast years; 2 = every 2nd (-1, -3, ... -19)
LEVELS = [100, 200, 300, 500, 700, 850, 925, 1000]    # the store also has 10 and 50 hPa
WORKERS = 8                    # reads at once; each holds one ~1.6 MB chunk, so memory is no problem. Use 4 if Colab complains
INCLUDE_G2 = False             # True adds the six G2 boxes (about 3x more output, about 3 GB in total; the 5 GB budget is shared)
PAD = 1.5                      # one grid cell (1.5 degrees) of margin around every box
Q_MIN_LEVEL = 200              # specific humidity is empty (NaN) at 10, 50 and 100 hPa in this store, so it is read only from 200 hPa down

BASE = "gs://weatherbench2/datasets/ifs_extended_range/weekly/"
URL_F = BASE + "ifs-ext-pressure-levels-weekly_avg_ens_mean.zarr"
URL_R = BASE + "ifs-ext-reforecast-pressure-levels-weekly_avg_ens_mean.zarr"
VARS = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t",
        "specific_humidity": "q", "geopotential": "z"}
BOXES = {"pilot": ((31.0, 34.0), (252.0, 259.0)),        # same box as tempest/ingest/wb2_fetch.py
         "denver": ((38.0, 40.0), (254.0, 256.0))}       # configs/region_denver.toml
if INCLUDE_G2:                                           # configs/region_g2_*.toml (longitudes as 0-360)
    BOXES.update({"g2_canaveral": ((27.5, 29.5), (278.5, 280.5)), "g2_fairbanks": ((64.0, 66.0), (211.0, 213.0)),
                  "g2_hilo": ((18.5, 20.5), (204.0, 206.0)), "g2_lamont": ((35.5, 37.5), (261.5, 263.5)),
                  "g2_saltlake": ((40.0, 42.0), (247.0, 249.0)), "g2_vandenberg": ((33.5, 35.5), (239.0, 241.0))})

dsF = xr.open_zarr(fsspec.get_mapper(URL_F, token="anon"), consolidated=True, chunks=None)   # no dask: each read touches only the chunks it needs
dsR = xr.open_zarr(fsspec.get_mapper(URL_R, token="anon"), consolidated=True, chunks=None)
lat_up = bool(dsF.latitude[1] > dsF.latitude[0])
T = dsF.time.values
problems = [s for s, bad in [
    ("variables missing", not set(VARS) <= set(dsF.data_vars) & set(dsR.data_vars)),
    ("levels missing", not set(LEVELS) <= set(dsF.level.values.tolist()) & set(dsR.level.values.tolist())),
    ("time not decoded to dates", not np.issubdtype(T.dtype, np.datetime64)),
    ("longitudes not 0-360", float(dsF.longitude.max()) < 180),
    ("reforecast start dates differ from the forecast ones", not np.array_equal(dsR.forecast_time.values, T)),
    ("hindcast_year is not 20 values", dsR.sizes["hindcast_year"] != 20),
    ("grid is not 1.5 degrees", abs(float(dsF.latitude[1] - dsF.latitude[0])) != 1.5)] if bad]
print("STOP, send this output to Claude:" if problems else "stores look usable", problems)
print("starts:", len(T), T[0], "to", T[-1], " leads:", dsF.sizes["prediction_timedelta"], " hindcast years:", dsR.hindcast_year.values[[0, -1]])

def lat_slice(la):
    a, b = la[0] - PAD, la[1] + PAD
    return slice(a, b) if lat_up else slice(b, a)

def lon_slice(lo):
    return slice(lo[0] - PAD, lo[1] + PAD)

UNION_LAT = (min(la[0] for la, _ in BOXES.values()), max(la[1] for la, _ in BOXES.values()))
UNION_LON = (min(lo[0] for _, lo in BOXES.values()), max(lo[1] for _, lo in BOXES.values()))

STARTS = np.arange(len(T))[::START_EVERY]                        # indices of the starts used
HY_IDX = sorted(range(19, -1, -HINDCAST_STEP))                   # indices of the hindcast years used
MON = T.astype("datetime64[M]")
ALL = sorted(set(MON[STARTS].tolist()))                           # months that have at least one start
MINE = ALL[:1] if TEST_ONE_MONTH else ALL[PART::PARTS]
def month_starts(mo):
    return [i for i in STARTS if MON[i] == mo]

n_starts = len(STARTS)
per_box = {b: dsF.latitude.sel(latitude=lat_slice(la)).size * dsF.longitude.sel(longitude=lon_slice(lo)).size for b, (la, lo) in BOXES.items()}
mb = {b: n * len(VARS) * len(LEVELS) * dsF.sizes["prediction_timedelta"] * 4 / 1e6 for b, n in per_box.items()}   # MB per start-year, float32
total_gb = sum(mb.values()) * n_starts * (1 + len(HY_IDX)) / 1000
read_gb = n_starts * (1 + len(HY_IDX)) * len(VARS) * len(LEVELS) * 3 * 1.6 / 1000
print(f"{n_starts} starts x (1 forecast + {len(HY_IDX)} hindcast years) in {len(ALL)} months; this part does {len(MINE)} months")
print("grid points per box (with margin):", per_box)
print(f"about {read_gb:.0f} GB read inside Google; about {total_gb:.1f} GB written to Drive (the 5 GB budget covers all long-range pulls)")
if total_gb > 3:
    print("WARNING: more than 3 GB; the shared 5 GB budget is at risk. Raise START_EVERY / HINDCAST_STEP or ask Claude")
for b in BOXES:
    for kind in ("fc", "rf"):
        os.makedirs(f"{OUT}/{b}/{kind}", exist_ok=True)
```

### Cell 3: the download (leave running)

```python
GAPS = []                                  # (store, variable, start, hindcast year): fields that are NaN in the store itself

def read(ds, var, idx, hy=None):
    """One variable, one start (and one hindcast year): all leads, the chosen levels, the union of the boxes."""
    key = dict(time=idx) if hy is None else dict(forecast_time=idx, hindcast_year=hy)
    lv = [l for l in LEVELS if var != "specific_humidity" or l >= Q_MIN_LEVEL]
    sel = dict(level=lv, latitude=lat_slice(UNION_LAT), longitude=lon_slice(UNION_LON))
    for k in range(6):
        a = ds[var].isel(**key).sel(**sel).load()
        if np.isfinite(a.values).all():
            return a.reset_coords(drop=True).astype("float32")
        time.sleep(10 * (k + 1))           # a failed chunk read comes back as NaN instead of an error, so retry
    if bool(ds[var].isel(**key).sel(level=lv).isnull().all()):     # the whole globe is NaN: a real gap in the store
        GAPS.append((("rf" if hy is not None else "fc"), var, int(idx), None if hy is None else int(hy)))
        tpl = ds[var].isel(**key).sel(**sel)                            # lazy: gives shape and coordinates, reads nothing
        return xr.DataArray(np.full(tpl.shape, np.nan, "float32"), dims=tpl.dims, coords={d: tpl[d] for d in tpl.dims})
    raise RuntimeError(f"still NaN after 6 tries: {var}, start {idx}, hindcast {hy}. Send this to Claude")

def build(kind, idxs):
    """All starts of one month -> Dataset on the union region."""
    ds = dsF if kind == "fc" else dsR
    hys = [None] if kind == "fc" else HY_IDX
    jobs = [(v, i, h) for i in idxs for h in hys for v in VARS]
    with ThreadPoolExecutor(WORKERS) as pool:
        got = list(pool.map(lambda j: read(ds, *j), jobs))
    it = iter(got)
    per_start = []
    for i in idxs:
        per_h = []
        for h in hys:
            per_h.append(xr.Dataset({VARS[v]: next(it) for v in VARS}))
        if kind == "rf":
            per_h = xr.concat(per_h, dim=xr.DataArray(dsR.hindcast_year.values[hys], dims="hindcast_year", name="hindcast_year"))
        else:
            per_h = per_h[0]
        per_start.append(per_h)
    dim = "time" if kind == "fc" else "forecast_time"
    out = xr.concat(per_start, dim=xr.DataArray(T[idxs], dims=dim, name=dim))
    if kind == "fc":
        out = out.assign_coords(valid_time=(("time", "prediction_timedelta"), dsF.valid_time.isel(time=idxs).values))
    else:
        out = out.assign_coords(time=(("forecast_time", "hindcast_year"), dsR.time.isel(forecast_time=idxs, hindcast_year=hys).values),
                                valid_time=(("forecast_time", "hindcast_year", "prediction_timedelta"),
                                            dsR.valid_time.isel(forecast_time=idxs, hindcast_year=hys).values))
    return out

def done(mo):
    ym = str(mo)[:7].replace("-", "")
    return all(os.path.exists(f"{OUT}/{b}/{k}/{ym}.nc") for b in BOXES for k in ("fc", "rf"))

todo = [mo for mo in MINE if not done(mo)]
print(len(todo), "months to do in this part")
t_start, n = time.time(), 0
for mo in todo:
    t0 = time.time()
    idxs = month_starts(mo)
    ym = str(mo)[:7].replace("-", "")
    for kind in ("fc", "rf"):
        sub = build(kind, idxs)
        for b, (la, lo) in BOXES.items():
            p = f"{OUT}/{b}/{kind}/{ym}.nc"
            piece = sub.sel(latitude=lat_slice(la), longitude=lon_slice(lo))
            piece.to_netcdf(p + ".part", encoding={v: {"zlib": True, "complevel": 4} for v in piece.data_vars})
            os.replace(p + ".part", p)            # only complete files get the final name
        del sub
    gc.collect()
    n += 1
    per = (time.time() - t_start) / n
    print(f"{ym}: {len(idxs)} starts in {time.time() - t0:.0f} s; about {per * (len(todo) - n) / 3600:.1f} h left"
          + (f" (full run: about {per * len(ALL) / 3600:.1f} h in one notebook)" if TEST_ONE_MONTH else ""), flush=True)
if GAPS:
    with open(f"{OUT}/store_gaps_part{PART}.txt", "a") as g:
        g.writelines(f"{x}\n" for x in GAPS)
    print(len(GAPS), "fields are empty in the store itself (written to store_gaps_part*.txt)")
print("ALL DONE (this part)" if not TEST_ONE_MONTH else "TEST DONE: run cell 4")
```

### Cell 4: check (checks every file in the folder, from all parts)

```python
bad, size = 0, 0
n_lead = dsF.sizes["prediction_timedelta"]
for b, (la, lo) in BOXES.items():
    exp_lat = dsF.latitude.sel(latitude=lat_slice(la)).size
    exp_lon = dsF.longitude.sel(longitude=lon_slice(lo)).size
    for kind in ("fc", "rf"):
        files = sorted(glob.glob(f"{OUT}/{b}/{kind}/*.nc"))
        for f in files:
            size += os.path.getsize(f)
            x = xr.open_dataset(f)
            sdim = "time" if kind == "fc" else "forecast_time"
            def valid(v):                       # specific humidity exists only from Q_MIN_LEVEL down; elsewhere it is NaN by design
                return x[v].sel(level=[l for l in LEVELS if v != "q" or l >= Q_MIN_LEVEL])
            def whole_ok(v):                    # NaN is allowed only as a whole field (a real store gap, listed in store_gaps_part*.txt)
                a = valid(v); w = [d for d in a.dims if d not in (sdim, "hindcast_year")]
                return bool((a.isnull().all(w) | a.notnull().all(w)).all())
            q_low = [l for l in LEVELS if l < Q_MIN_LEVEL]
            ok = (set(x.data_vars) == set(VARS.values())
                  and list(x.level.values) == LEVELS
                  and x.sizes["prediction_timedelta"] == n_lead
                  and x.sizes["latitude"] == exp_lat and x.sizes["longitude"] == exp_lon
                  and (kind == "fc" or x.sizes["hindcast_year"] == len(HY_IDX))
                  and all(whole_ok(v) for v in x.data_vars)
                  and (not q_low or bool(x.q.sel(level=q_low).isnull().all()))
                  and float(x.t.min()) > 150 and float(x.t.max()) < 340
                  and float(x.q.min()) > -1e-5 and float(x.z.min()) > -5000)   # q may dip a hair below 0 in spectral fields; z at 1000 hPa can be negative in deep lows
            if not ok:
                bad += 1; print("BAD", f, dict(x.sizes))
            x.close()
        print(b, kind, len(files), "of", len(ALL), "files")
print(f"total on Drive: {size / 1e9:.2f} GB")
print("OK" if bad == 0 else f"{bad} bad files: delete them and rerun cell 3")
```

Expected shapes: forecast files `(time, 41 leads, 8 levels, lat, lon)`, reforecast files `(forecast_time, 10 hindcast years, 41, 8, lat, lon)`. With the margin the pilot box has 4 x 7 points and Denver 3 x 3.

---

## Copy to this PC

1. Wait for `ALL DONE` in every part, and for cell 4 to print `OK` with all files present.
2. In Google Drive (web), right-click `tempest_wb2_ifs_extended` and choose **Download** (from each account if you used more than one). Include any `store_gaps_part*.txt`.
3. Unzip into a **new** folder `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_ifs_extended\`, keeping the `pilot\fc`, `pilot\rf`, `denver\fc`, `denver\rf` subfolders.
4. Tell Claude it is there.

## What the code side then needs (not part of the download)

- **File format:** one NetCDF per month, `fc/<yyyymm>.nc` (forecasts) and `rf/<yyyymm>.nc` (reforecasts), float32, zlib-compressed. Load with `xr.open_mfdataset(sorted(glob(...)), combine="nested", concat_dim="time")` (or `"forecast_time"` for `rf`).
- **Pairing with ERA5:** `valid_time` gives the date of each lead; the reforecast also carries `time` (the hindcast's own start date). Weekly means of ERA5 are formed on the same windows (the 168 h window in Store layout).
- **Use:** weekly-mean anomalies (forecast minus the model's own reforecast climate) as `linear_cols` for Mode M (`docs/plans/PHASE4_FORECAST.md`). Years 2016-2022 only; no spread (ensemble mean).
- **Disk:** about 1 GB with the defaults. `data/raw` stays well under the 200 GB cap.
