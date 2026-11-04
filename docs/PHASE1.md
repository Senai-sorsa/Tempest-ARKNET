# Phases 1–2: build spec

What to build first, in order, with the exact sources, requests and checks. Facts checked 2026-11-04.
The plan this implements is [PLAN.md](PLAN.md).

## Day-one checklist

1. **CDS account (user, ~10 min, start first because the queue is slow).**
   Register at https://cds.climate.copernicus.eu, open the *ERA5 hourly data on pressure levels* dataset page
   and accept its licence (CC-BY-4.0), then copy your API key from your profile page into
   `%USERPROFILE%\.ecmwfdatastoresrc`:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: <your key>
   ```
   Never commit it (`.gitignore` covers it). Check: `python -c "from ecmwf.datastores import Client; Client().check_authentication()"`.
2. `uv init` the project, Python **≥ 3.12** (icechunk and scoringrules both need it; 3.14 tested OK), and add the
   dependencies below.
3. Start `fetch_cds.py` (pilot box) in the background. It runs for hours to days.
4. Run `fetch_earthmover.py` (about 40 min measured), then `fetch_igra.py`, `fetch_indices.py`.
5. Write `to_heights.py`, then run the phase 1 checks. Phase 2 can start on the 13 Earthmover levels before
   the CDS fill lands.

## Dependencies

| Package | Version checked | Use |
|---|---|---|
| icechunk | 2.3.1 (has a Windows wheel) | read the Earthmover ERA5 store |
| xarray, zarr (v3), dask | current | arrays, local stores |
| numcodecs[pcodec] | current | the store's codec, without it reads fail with `UnknownCodecError` |
| ecmwf-datastores-client | 0.5.3 | CDS API (replaces cdsapi) |
| cfgrib + eccodes | 0.9.15.1 / 2.50.0 (eccodes ships Windows wheels) | read CDS GRIB |
| numpy, scipy, pandas | current | everything else |
| scoringrules | 0.11.0 | CRPS, energy score, variogram score (phase 2) |
| pytest | current | the checks below |
| torch | 2.11.0 + CUDA 12.8 (`pyproject.toml` pins the PyTorch index) | phase 6A generator; already set up and tested |

## Layout

```
tempest/
  ingest/      fetch_earthmover.py  # ERA5 13 levels + surface, pilot box → data/raw/era5_em/<var>.zarr
               fetch_cds.py         # ERA5 8 boundary-layer levels → data/raw/era5_cds/<yyyymm>.grib + ledger
               fetch_igra.py        # IGRA v2.2 derived files → data/raw/igra/<id>-drvd.txt.zip
               fetch_indices.py     # ONI, QBO u30/u50, PMEL WWV → data/raw/indices/*.txt
               igra.py, indices.py  # parsers
  profiles/    to_heights.py        # raw → data/pilot/profiles.zarr on the 44-level above-ground grid
  scoring/     score.py, splits.py  # phase 2 harness
               baseline.py          # v1-style independent mean/std climatology
  generator/   build_dataset.py     # profiles.zarr + indices → data/train/pilot.npz (179 targets, 13 features)
               model.py, train.py, sample.py
  drivers/ analogs/ nearterm/ past/ calibrate/ output/   # later phases, see each __init__.py
configs/  scripts/  tests/
data/  models/                      # git-ignored
```
Raw data is kept unchanged so `to_heights.py` can be rerun when the method changes.

## 1. Earthmover ERA5 (13 levels + surface)

```python
import icechunk as ic, xarray as xr
storage = ic.s3_storage(bucket="earthmover-icechunk-era5", prefix="icechunkV2",
                        region="us-east-1", anonymous=True)
repo = ic.Repository.open(storage=storage, config=ic.RepositoryConfig(max_concurrent_requests=16))
store = repo.readonly_session("main").store
pl = xr.open_zarr(store, group="pressure/temporal", zarr_format=3, chunks={})
sf = xr.open_zarr(store, group="single/temporal", zarr_format=3, chunks={})
```
- **Box:** 31–34 N, 108–101 W, selected by coordinate (check whether the store's longitude is 0–360 first).
  That is **6 storage tiles** of 3° × 3°: Spaceport America's 4 neighbours sit in one tile, but Midland's
  straddle the tile edge at 102 W, and phase 7 needs random points across the box anyway.
- **Time:** 1991-01-01 to 2025-12-31, all 24 hours. The raw store keeps 00Z and 12Z for radiosonde checks;
  the solar-hour cut happens in `to_heights.py`.
- **Variables:** pressure `u, v, t, r, z`; single `u10, v10, u100, v100, t2m, d2m, sp, z_sfc` (geopotential
  of the model surface; confirm the name in the store).
- **Reads:** one variable at a time, `.load()` with dask threads, then write `data/raw/era5_em/<var>.zarr`
  (float32). Resume: skip variables whose output already exists. About 2,600 chunks per tile and ~16k in
  total. At the measured 3–5 s per chunk and 16 concurrent requests, that is about 1–2 h.

## 2. CDS boundary-layer fill

One request per month, keyed `yyyymm`:
```python
request = {
    "product_type": ["reanalysis"],
    "variable": ["u_component_of_wind", "v_component_of_wind", "temperature",
                 "relative_humidity", "geopotential"],
    "pressure_level": ["975", "950", "900", "875", "825", "800", "775", "750"],
    "year": ["1991"], "month": ["06"],
    "day": [f"{d:02d}" for d in range(1, 32)],
    "time": [f"{h:02d}:00" for h in range(24)],
    "area": [34, -108, 31, -101],          # N, W, S, E
    "data_format": "grib",
}
remote = client.submit("reanalysis-era5-pressure-levels", request)
```
- 31 × 24 × 8 × 5 = 29,760 items per request, under the 60k cap. That makes 420 requests for 1991–2025.
  Before the first submit, check one request with `client.estimate_costs(...)`.
- **Ledger** `data/raw/era5_cds/ledger.csv` (`yyyymm, request_id, status`). Submit about 20 at a time.
  Then loop: poll `client.get_remote(request_id).status`, download when it reads `successful`, and resubmit
  on `failed` or `rejected`. Because the ledger is the state, a crash or reboot only reruns the loop and
  never pays for a request twice. Write each download to a `.part` file and rename it when complete.
- **CONUS:** the same script with the CONUS area runs right after, in the background (PLAN.md, phase 1).

## 3. To the above-ground grid (`to_heights.py`)

For each grid point and hour:
1. Merge the 13 + 8 levels into 21 levels, sorted by pressure.
2. Height above the model surface. Use g0 = 9.80665 and R = 6,371,000 m.
   - Geopotential height: `Z = z / g0`.
   - Geometric height: `h = R·Z / (R − Z)`. This adds about 50 m at 18 km.
   - Height above ground: `agl = h(z) − h(z_sfc)`.
3. Drop levels with `agl ≤ 0` (1000 hPa and often 925 hPa are underground here).
4. Add the surface anchors:
   - wind at 10 m (`u10, v10`) and 100 m (`u100, v100`)
   - T at 2 m (`t2m`)
   - RH at 2 m from `t2m` and `d2m` with the Magnus formula
5. Interpolate onto the 44 heights (PLAN.md):
   - wind: linear in ln(height) below 100 m, linear in height above
   - T and RH: linear in height
   - targets above the 50 hPa level become NaN
6. Keep hours whose solar time `UTC + lon/15` falls in 06–21. Also keep 00Z and 12Z for the IGRA checks.
7. Write `data/pilot/profiles.zarr` with dims (point, time, height), variables u, v, T, RH, chunked
   one point × full time. Also store the surface values, point lat/lon and `z_sfc`.

Use float32 for the pilot. It is about 59 GB (377 points × ~222k hours × 44 heights × 4 variables), and float16 is a
phase 8 decision. RH is clipped to 0–100 after interpolation.

## 4. IGRA v2.2 (truth)

- Download `https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/derived-por/<ID>-drvd.txt.zip`.
- Stations:
  - Santa Teresa NM `USM00072364` (143 MB)
  - Midland TX `USM00072265` (148 MB)
  - later: Albuquerque `USM00072365`, Amarillo `USM00072363`
- Header lines start with `#`. The fields are fixed-width. Columns below are 1-based and inclusive, so
  Python slices are `[a-1:b]`.

  | Field | Columns |
  |---|---|
  | ID | 2–12 |
  | YEAR | 14–17 |
  | MONTH | 19–20 |
  | DAY | 22–23 |
  | HOUR | 25–26 |
  | RELTIME | 28–31 |
  | NUMLEV | 32–36 |

- Data lines (NUMLEV per sounding; the first is the surface):

  | Field | Columns | Units |
  |---|---|---|
  | PRESS | 1–7 | Pa |
  | REPGPH | 9–15 | m |
  | CALCGPH | 17–23 | m |
  | TEMP | 25–31 | K×10 |
  | REPRH | 89–95 | %×10 |
  | CALCRH | 97–103 | %×10 |
  | UWND | 113–119 | m/s×10 |
  | VWND | 129–135 | m/s×10 |

  The missing value is −99999.
- Height above ground is GPH minus the surface level's GPH. Use REPGPH, falling back to CALCGPH. Interpolate
  onto the 44 heights the same way as ERA5. 00Z is about 17 h solar, inside the launch window; 12Z is about
  05 h solar, so it is used only to check ERA5.
- Test: parse a 2-sounding fixture cut from the real file. Assert the surface pressure, NUMLEV, and one
  wind value.

## 5. ENSO and QBO

- **ONI:** `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`. Columns are `SEAS YR TOTAL ANOM`,
  monthly from DJF 1950. The latest, ASO 2026, is +2.46 (strong El Niño).
- **QBO:** `https://www.cpc.ncep.noaa.gov/data/indices/qbo.u30.index` and `qbo.u50.index`. Use the first
  (`ORIGINAL DATA`) block of 12 monthly columns, from 1979; −999.9 means missing. FU Berlin's file stopped
  in 2021, so do not use it.
- **Forecast method (decided by measurement, 2026-11-04).** No machine-readable ENSO plume was found, and
  none is needed. A lagged linear regression, fitted on the first 70 % of the record and tested on the last
  30 %, gives:

  | Predictor | Lead | Test correlation | Residual sd / climatological sd |
  |---|---|---|---|
  | ONI | 3 months | 0.78 | 0.52 / 0.83 |
  | ONI | ≥ 8 months | ~0 | ~0 |
  | QBO u30 (from u30, u50) | 8 months | 0.74 | 10.1 / 15.0 m/s |
  | QBO u30 (from u30, u50) | 12 months | 0.66 | 11.4 / 15.0 m/s |
  | QBO u30 (from u30, u50) | 20 months | 0.53 | 12.9 / 15.0 m/s |
  | QBO u30 (from u30, u50) | 32 months | ~0 | ~0 |

  So the forecast for ONI_Y and QBO_Y is a lead-specific regression mean plus a normal draw with the
  residual sd. Once the regression no longer beats climatology, draw from the target month's climatological
  values instead. Phase 4 refits this by calendar month, inside each fold.
- **Warm water volume (added 2026-11-04):** `https://www.pmel.noaa.gov/tao/wwv/data/wwv.dat` (PMEL TAO,
  monthly from 1980-01, columns `date volume anomaly`). This is the recharge-oscillator precursor of ENSO.
  Adding the WWV anomaly to the ONI regression, with the same 70/30 split over 1980–2026, gives:

  | Lead | ONI only: r / MSSS | ONI + WWV: r / MSSS |
  |---|---|---|
  | 3 months | 0.78 / +0.63 | 0.88 / +0.77 |
  | 6 months | 0.38 / +0.17 | 0.61 / +0.38 |
  | 9 months | 0.07 / +0.01 | 0.37 / +0.16 |
  | 12 months | 0.04 / −0.01 | 0.27 / +0.08 |
  | 18 months | 0.17 / +0.01 | 0.31 / +0.09 |

  ENSO skill now runs to about 12–18 months instead of about 6, so the ONI forecast uses ONI + WWV.
  `fetch_indices.py` also fetches `wwv.dat`. This is one split; phase 4 confirms it walk-forward.
  QBO stays useful out to about 2 years.

## 6. Phase 1 done when

Automated in `tests/test_pilot.py`:
- [ ] **Completeness.** Every pilot point has every year 1991–2025 and every kept hour. There are no NaNs
  at heights that lie between the surface and the 50 hPa level.
- [ ] **Physics.** After the merge, z rises as pressure falls in every profile. RH is in 0–105 %. T is in
  180–330 K.
- [ ] **Seam.** The CDS levels join the Earthmover levels without a step. The mean T difference between
  950 and 925 hPa matches the lapse rate within 1 K.
- [ ] **vs IGRA (Midland 72265, Santa Teresa 72364, 2015–2025, 00Z and 12Z).** Per height band:

  | Quantity | Height band | Target |
  |---|---|---|
  | Wind bias | below 1 km | ≤ 1 m/s |
  | Wind bias | above 1 km | ≤ 0.5 m/s |
  | Wind RMSD | all | 1.5–4 m/s |
  | T bias | above 500 m | ≤ 1 K |

  Outside these, look for a units or height-reference bug before blaming ERA5.
- [ ] **vs `dynamics`.** For Spaceport America, June 2016–2025, 09:00 local, compare the 10 m wind and
  2 m T means with the mean and std from `tools/weather/Weather_to_JARVIS_inputs.py monte-carlo`. Both are
  ERA5, so they should agree within 0.5 m/s and 0.5 K.

## 7. Phase 2: scoring harness

- **Scores** (scoringrules, numpy backend):
  - `crps_ensemble(obs, fct, m_axis=-1)` per variable and height
  - `es_ensemble(obs, fct, m_axis=-2, v_axis=-1)` on whole profiles, with each variable standardised by
    its climatological sd first
  - `vs_ensemble(..., p=0.5)` on the wind components, with weights only for pairs closer than 1 km
    (shear layers)
  - PIT and coverage of ±1/2/3σ and 5–95 %
- **Splits** (`splits.py`):
  - Walk-forward: for target year Y, train on years < Y, with a 45-day embargo before 1 January Y.
  - Test years: 2011–2025, which gives at least 20 training years.
  - Lead: issue time = target − lead, for leads of 1, 3, 6, 12, 24 and 36 months.
- **Truth:** ERA5 profiles at the pilot points (phase 2–5) and IGRA soundings (phase 6).
- **Baseline** (`baseline.py`): v1-style. For each variable and height, take the mean and sd of the
  ±7-day, ±1 h window over the training years, then sample each height *independently* from a normal
  distribution. Also score plain resampled climatology (the analogs with no shift) so phase 3 has two
  references.
- **Done when:**
  - `score.py` reproduces scoringrules' documented example values.
  - CRPS of a normal forecast matches the closed form (`sr.crps_normal`) to within 1 % with 10k members.
  - The baseline's coverage on held-out years is within ±3 points for T. Independent sampling should
    already be calibrated per height; its weakness should show only in the energy and variogram scores.
  - One report table prints CRPS / ES / VS per lead for the baseline.
