# Colab: global HRES at the 7,483 global points (for global Mode F, ASK_LATER 9) — notebook 1 of 3

**What it does:** pulls ECMWF HRES forecasts from WeatherBench2 (2016-2022) at the same 7,483 points as the ERA5 global store (`data/raw/era5_global/points.npz`).

**Which cases:** the ERA5 global store keeps one hour per day (hour = days since 1991-01-01, mod 24). The notebook keeps every HRES forecast (00Z or 12Z start, lead 6-240 h) whose valid time is exactly one of those stored hours. So every case already has its ERA5 truth on this PC, and no truth download is needed. That is about 1,200 cases a year with 20 leads per valid time, spread evenly over 6 h to 10 days and over all four UTC hours. Since the points cover every longitude, this also covers all solar hours.

**Not the same as `Colab HRES refetch.md`:** that one (pilot + Denver boxes) is already done (`data/raw/wb2_hres_v2*`).

**What you need:** a Google account (free Colab plus Google Drive, with about 8 GB free on Drive).

**Tested on 2026-11-07:** cells 2-4 were run from this PC on 3 cases. The grid matched all 7,483 points, and the spot check matched the store to 0.01 K.

---

## Expected size and time (estimated)

| Setting | Value |
|---|---|
| Cases | about 100 a month, 84 months (2016-2022) |
| Read inside Google | one global field per case and variable, about 100 GB a year (free; it never touches your connection) |
| Colab time | roughly 1-5 h a year, about 8-35 h in total. It resumes per month |
| Output on Drive | about 0.8 MB per case, about 7 GB in total (int16, compressed) |

**To make it faster:** set `PARTS = 3` in cell 2, then open the notebook 3 times with `PART = 0`, `1` and `2`, and run them at the same time. Keep `PARTS` the same in every copy. If Colab refuses a session, use a second Google account and download from both Drives. `MAX_LEAD = 168` cuts the work by 30 %.

---

## Step by step

1. In Google Drive, make the folder `MyDrive/tempest_wb2_global` and upload `C:\Users\Senai\Tempest-ARKNET\data\raw\era5_global\points.npz` into it (0.6 MB).
2. Go to https://colab.research.google.com, then **New notebook**. **Runtime → Change runtime type → CPU**.
3. Paste each cell below into its own code cell, in order.
4. Run cells 1-2, then cell 3 with `TEST_ONE_MONTH = True` (one month, a few minutes), then cell 4. It must print `OK`.
5. Set `TEST_ONE_MONTH = False` in cell 2, run cell 2 again, then run cell 3 and leave it running.
6. **When Colab disconnects:** reconnect, then run cells 1, 2 and 3 again. Finished months are skipped. Keep the tab open and don't let the PC sleep.
7. When cell 3 prints `ALL DONE` (in every part), run cell 4 once more, then do the copy step.

### Cell 1: install and mount Drive

```python
!pip -q install -U gcsfs "zarr>=3" xarray dask
import zarr, xarray   # if this line fails, or cell 2 says "unrecognized engine 'zarr'": Runtime -> Restart session, then run cells 1-2 again
print("zarr", zarr.__version__, "xarray", xarray.__version__)
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: settings and helpers

```python
import os, time
import numpy as np, xarray as xr, fsspec, dask, psutil

TEST_ONE_MONTH = True          # only notebook 1 runs the test
PART, PARTS = 0, 3             # notebook 1 of 3
OUT = "/content/drive/MyDrive/tempest_wb2_global"   # points.npz must be in this folder
FIRST, LAST = 2016, 2022       # this store ends 2023-01; do not go past 2022
MAX_LEAD = 240                 # hours; 168 (7 days) cuts the output by 30 %
WORKERS = 16                   # 64 and 24 crashed the 12.7 GB runtime in the box notebook

URL = "gs://weatherbench2/datasets/hres/2016-2022-0012-1440x721.zarr"
UPPER = {"u_component_of_wind": "u", "v_component_of_wind": "v", "temperature": "t",
         "specific_humidity": "q", "geopotential": "z"}
SURF = {"10m_u_component_of_wind": "u10", "10m_v_component_of_wind": "v10",
        "2m_temperature": "t2m", "surface_pressure": "sp"}
# int16 coding as in tempest/ingest/fetch_global.py: value = code * scale + offset (q is specific humidity, kg/kg)
CODE = {"u": (0.01, 0), "v": (0.01, 0), "t": (0.01, 200), "q": (1e-6, 0), "z": (10.0, 0),
        "u10": (0.01, 0), "v10": (0.01, 0), "t2m": (0.01, 200), "sp": (2.0, 80000)}
DAY0 = np.datetime64("1991-01-01")   # the ERA5 global store keeps one hour per day: (days since DAY0) mod 24

pts = np.load(f"{OUT}/points.npz")
ds = xr.open_zarr(fsspec.get_mapper(URL, token="anon"), consolidated=True)
IL = np.round((pts["lat"] - float(ds.latitude[0])) / 0.25).astype(int)
JL = np.round((np.mod(pts["lon"], 360) - float(ds.longitude[0])) / 0.25).astype(int) % ds.sizes["longitude"]
assert np.allclose(ds.latitude.values[IL], pts["lat"]) and np.allclose(ds.longitude.values[JL], np.mod(pts["lon"], 360))
IL, JL = xr.DataArray(IL, dims="point"), xr.DataArray(JL, dims="point")
T = ds.time.values.astype("datetime64[h]")
assert ds.prediction_timedelta.dtype.kind == "i"   # leads stored as integer hours

def cases(y, m):
    """(start, lead h, valid) with valid = the ERA5 global store's hour that day, at 00/06/12/18 UTC, start 00Z or 12Z."""
    month = f"{y}-{m:02d}"
    days = np.arange(np.datetime64(month, "D"), np.datetime64(month, "M") + np.timedelta64(1, "M"))
    V = days.astype("datetime64[h]") + ((days - DAY0).astype(int) % 24).astype("timedelta64[h]")
    out = []
    for v in V[V.astype(int) % 6 == 0]:
        for L in range(6, MAX_LEAD + 1, 6):
            s = v - np.timedelta64(L, "h")
            if s.astype(int) % 12 == 0 and np.isin(s, T):
                out.append((s, L, v))
    return out

def encode(name, x):
    s, o = CODE[name]
    q = np.round((np.asarray(x, np.float64) - o) / s)
    nan = ~np.isfinite(q)
    if (np.abs(q[~nan]) > 32767).any():   # never clip silently
        raise ValueError(f"{name}: values outside the int16 range")
    q[nan] = -32768                       # missing values (if any) are stored as -32768
    return q.astype(np.int16), int(nan.sum())

os.makedirs(OUT, exist_ok=True)
c = cases(2016, 1)
print(len(pts["lat"]), "points; 2016-01 has", len(c), "cases, leads", sorted({L for _, L, _ in c}))
```

### Cell 3: the download (leave running)

```python
import gc, ctypes
months = [(2016, 1)] if TEST_ONE_MONTH else [(y, m) for y in range(FIRST, LAST + 1) for m in range(1, 13)]
todo = [(y, m) for (y, m) in months[PART::PARTS] if not os.path.exists(f"{OUT}/{y}{m:02d}.npz")]
print(len(todo), "months to do in this part")
names = list(UPPER) + list(SURF)
t_start, n = time.time(), 0
for (y, m) in todo:
    cs = cases(y, m)
    t0 = time.time()
    sub = xr.concat([ds[names].sel(time=s, prediction_timedelta=L).isel(latitude=IL, longitude=JL)
                     for s, L, _ in cs], "case", coords="minimal", compat="override")
    with dask.config.set(scheduler="threads", num_workers=WORKERS):
        sub = sub.load()
    out, nans = {}, 0
    for k, v in {**UPPER, **SURF}.items():
        out[v], bad = encode(v, sub[k].transpose("case", "level", "point") if k in UPPER else sub[k].transpose("case", "point"))
        nans += bad
    p = f"{OUT}/{y}{m:02d}.npz"
    with open(p + ".part", "wb") as f:
        np.savez_compressed(f, **out, start=np.array([s for s, _, _ in cs]), lead_h=np.array([L for _, L, _ in cs]),
                            valid=np.array([v for _, _, v in cs]), level=sub.level.values,
                            code=np.array([f"{k} {s} {o}" for k, (s, o) in CODE.items()]))
    os.replace(p + ".part", p)            # only complete files get the final name
    del sub, out; gc.collect(); ctypes.CDLL("libc.so.6").malloc_trim(0)
    n += 1
    eta_h = (time.time() - t_start) / n * (len(todo) - n) / 3600
    print(f"{y}-{m:02d}: {len(cs)} cases in {time.time() - t0:.0f} s; {nans} missing values; about {eta_h:.1f} h left; RAM {psutil.virtual_memory().percent:.0f}%", flush=True)
print("ALL DONE (this part)" if not TEST_ONE_MONTH else "TEST DONE: run cell 4")
```

### Cell 4: check

```python
import glob
bad = 0
files = sorted(glob.glob(f"{OUT}/[12]*.npz"))
for f in files:
    x = np.load(f)
    st, L, v = x["start"], x["lead_h"], x["valid"]
    vd = v.astype("datetime64[D]")
    t = x["t"] * 0.01 + 200
    ok = ((st + L.astype("timedelta64[h]")) == v).all() \
         and ((vd - DAY0).astype(int) % 24 == v.astype(int) % 24).all() \
         and x["t"].shape == (len(v), 13, len(pts["lat"])) and x["sp"].shape == (len(v), len(pts["lat"])) \
         and 150 < t.min() and t.max() < 340 and (x["t"] != -32768).all()
    if not ok:
        bad += 1; print("BAD", f, x["t"].shape)
print(len(files), "files")
# spot check: first file, first case, 500 hPa, point 0 against the store
x = np.load(files[0]); k = list(x["level"]).index(500)
ref = float(ds["temperature"].sel(time=x["start"][0], prediction_timedelta=int(x["lead_h"][0]), level=500)
            .isel(latitude=int(IL[0]), longitude=int(JL[0])).values)
got = x["t"][0, k, 0] * 0.01 + 200
print(f"spot check t500: file {got:.2f} K, store {ref:.2f} K")
bad += abs(got - ref) > 0.006
print("OK" if bad == 0 else f"{bad} bad: delete the BAD files and rerun cell 3")
```

Each file `<yyyymm>.npz` holds: `u v t q z` as (case, level 13, point), `u10 v10 t2m sp` as (case, point), all int16 (value = code × scale + offset, see `code`; -32768 = missing), plus `start`, `lead_h`, `valid` (case) and `level`.

---

## Copy to this PC

1. Wait for `ALL DONE` and `OK`.
2. In Google Drive (web), right-click `tempest_wb2_global` → **Download** (it may come as several zips).
3. Unzip into the **new** folder `C:\Users\Senai\Tempest-ARKNET\data\raw\wb2_hres_global\` (about 7 GB).
4. Tell Claude it is there.

## What the code side then needs (not part of the download)

- Truth: ERA5 at `valid` from `data/raw/era5_global/<yyyy-mm>.npz`, same point order. Note that the ERA5 store has `r` (relative humidity) while HRES has `q`: convert one into the other with `rh_from_q` in `tempest/ingest/arco_fill.py`.
- Mode F with a continuous lead-hour input and solar hour (from `valid` and the point longitude). The 2026 test and the global holdouts are already excluded from the points.
