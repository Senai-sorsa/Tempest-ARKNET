# Query tool plan: `tempest_weather/` (portable folder, two functions)

> **Modes 1-3 (past, 0-15 days, weeks 3-6) moved to Phase 4**, a separate system: `docs/plans/PHASE4_FORECAST.md`. This file still covers the tool skeleton, mode 4 and the layout.

Status: planned 2026-11-04, not built. It turns the trained model into a tool someone can copy into another repo.
The tool takes only a location, date and time, chooses the right source by itself, and fetches everything else
online. It refines the router in `PLAN.md` (*Architecture*); the analog branch there is dropped from this tool.

## What the user calls

```python
from tempest_weather import values, distribution

v = values(32.99, -106.97, "2027-03-14 09:00")             # one best-estimate profile
d = distribution(32.99, -106.97, "2027-03-14 09:00", n=1024)  # n coherent sample profiles
```

Both take `lat, lon, when`, plus these optional arguments:
- `elevation`: looked up if missing.
- `mode`: forces a mode, for testing.
- `cache_dir`: where downloads are kept.

`distribution` also takes `kind` (modes 3 and 4 only; modes 1-2 ignore it):

| `kind` | What the samples mean | 99 % range holds 99 % of outcomes? |
|---|---|---|
| `"predicted"` | **Set distribution**: the weather spread the AI predicts for those conditions. ENSO/QBO/solar are fixed at their expected values; no range calibration; mode 3 uses the central adjustment shift. | No, it is narrower. Use it for "typical spread", not for safety margins. |
| `"uncertainty"` (default) | **Uncertainty distribution**: the predicted spread plus everything we are unsure of: the 4 members' disagreement, drawn ENSO/QBO/solar values, the range calibration map, and in mode 3 the adjustment's own error (forecast-mean spread and the fitted fading error). | Yes; this is the one the tests check. |

Both kinds come from the same samples (the `uncertainty` kind adds to the `predicted` draw), so they can be compared
directly.

`when` can be:
- a timezone-aware datetime, or a string with an offset;
- a naive local clock time. The timezone is looked up from the location (`timezonefinder` if installed). If that
  package is missing, the time is treated as local solar time from the longitude and a warning says so.

Both return a plain dict of numpy arrays:

| Key | `values` | `distribution` |
|---|---|---|
| `heights` | (44,) m above ground | same |
| `u`, `v`, `T`, `RH` | (44,) | (n, 44); each row is one whole, physically consistent profile |
| `t2m`, `sp`, `rh2m` | scalars | (n,) |
| `mean`, `std`, `p005`, `p995` | - | per height and variable (p005/p995 = the 99 % range) |
| `mode`, `source`, `valid_time` | which branch answered and from which data | same |

`values` returns, for each mode:
- past: the actual profile;
- every other mode: the per-height median of `distribution(n=1024)`.

A median taken height by height is not itself one sampled profile, and the docs will say so.

## The four modes (chosen automatically from lead time = `when` - now)

| Mode | Lead time | Source | Range / spread |
|---|---|---|---|
| 1 Past | before now | ERA5 (Earthmover store, anonymous) up to the store's end, then the Open-Meteo historical-forecast API (has pressure levels) | launch-slip window (±N h the same day) + station-fitted ERA5 error (`station_map`) |
| 2 Near term | 0-15 days (raw forecasts are not tuned) | Open-Meteo ensembles: WeatherNext 2 (64 members) + ECMWF IFS ENS (51), each converted to heights above ground | per-source spread inflation, then one pooled inflation. Days 10-15 blend toward mode 3 with a linear weight. |
| 3 AI + adjustment | 15-30 days (the AI part of "the next month") | trained generator tuned by the past 7 days and the next 7 forecast days (below) | `kind` setting; calibrated per lead band |
| 4 AI only | > 30 days | trained generator; ENSO/QBO/solar as analog draws from their latest known values (`indices.analog`, K = 8; tested in `PLAN.md`, *A6 and other drivers*; soil moisture and lagged local departures were rejected for this mode) | the existing range calibration (`spread.py` map) |

The boundaries are settings (`near_days = 15`, `adjust_until = 30`), and so are the tuning windows
(`past_days = 7`, `forecast_days = 7`). **These are the starting values, not final ones**: the experiment grid below
tries other windows and keeps whichever scores best on held-out years.

**Area rule:**
- Modes 1-2 work anywhere.
- Modes 3-4 only inside the trained area: the pilot box 31-34 N, 108-101 W until the CONUS training (phase 8).
  Outside it, the call raises a clear error. It never extrapolates silently.
- Modes 3-4 are trained only for solar hours 06-21 and checked on balloons only at 00Z, at 2 stations (PLAN E5).
  Outside 06-21 solar time the call raises an error; at checked hours other than 00Z it gives a warning.

## Mode 3 tuning (set range for now: past 7 days + next 7 forecast days -> the next month)

The AI's month-ahead prediction is tuned with two windows: the **last 7 days** (what happened) and the **next 7
days of the forecast** (ensemble mean and spread). Nothing else from the 15-day forecast is used for tuning.

1. **Recent-weather inputs, trained once.** New model inputs are the departures from normal over:
   - the last 1, 3 and 7 days;
   - forecast days 1-3 and 4-7 (ensemble mean), plus the forecast spread.

   Each is given for u, v, T and RH at a few heights, plus the surface. They reuse A6's lagged-input code.
2. **Fading shift.** The day-7 forecast departure is carried forward with weight exp(-(lead - 7) / tau). tau is
   fitted per variable and height band.
3. **Running bias check.** The last 30 days of mode-3 answers are compared with what happened; a capped, shrunken
   correction is applied (cap: half the climatological std).

No online weight updates. Each part is kept only if it passes the tests below; a part that fails is turned off by a
setting, not deleted.

### Data for the tuning (the hard part) and how to get around the short forecast archive

| Source | Years | Use |
|---|---|---|
| ERA5 itself as a stand-in forecast ("perfect forecast" + lead-dependent error noise) | 1980-2026 | train the inputs and tau on the long record; the noise level is fitted from the real forecasts below |
| NOAA GEFS v12 reforecast (AWS open data, 0.25 deg, pressure levels, 16 days; to verify: years and members) | about 2000-2019 | 20 years of real forecasts: fit the error noise, tune and validate the windows |
| GEFS operational archive (AWS open data; to verify the start year) | about 2020-now | real forecasts on the 2024-25 test years |
| WeatherNext 2 archive with members (Earth Engine / BigQuery) | 2022-now | the forecast the tool actually uses: final recalibration of the tuning |
| Our own daily logger (WeatherNext 2 + IFS ENS members at the pilot sites) | from when it starts | live check of the exact Open-Meteo feed; build it first (T0), since its data only grows from the start date |

GEFS is a weaker forecast than WeatherNext 2 and IFS, so tuning fitted on it trusts the forecast a little less
than it could. That errs on the safe side, and the WeatherNext 2 archive corrects it.

### Validation (does the next-2-weeks data take part?)

Today: **no**. Every score so far uses ERA5 and balloons only (validation 2021-23, test 2024-25); no forecast data
is in any check, and the daily logger was never started. With the tool:
- **Mode 2** is checked against what happened, using the GEFS archive and our logger, per lead day.
- **Mode 3 tuning** is fitted on years up to 2020 (ERA5 stand-in + GEFS reforecast). Its windows are chosen on
  2021-23 and it is tested on 2024-25 with real forecasts, against mode 4 on the same days (walk-forward). It must
  improve CRPS and keep the 99 % range holding about 99 % (`uncertainty` kind).
- 2026 Jan-Jun stays the untouched final test.

### Experiment grid (run after the 7 + 7 baseline)

| Setting | Values tried |
|---|---|
| `past_days` | 3, 7, 14 |
| `forecast_days` | 3, 7, 10, 15 |
| `adjust_until` | 21, 30, 45, 60 |

Choose on 2021-23, report on 2024-25, and log every result in `PLAN.md`. The 7 + 7 / 30-day setting stays the
default until a different one wins clearly: better CRPS, with coverage still within 98.5-99.5 %.

## Folder layout (self-contained: no `import tempest`)

```
tempest_weather/
  __init__.py      values(), distribution(), version
  router.py        lead time -> mode; area check; blend weights
  timeplace.py     timezone, solar hour, elevation (Open-Meteo elevation API, cached)
  sources/
    era5.py        Earthmover reads (optional deps: xarray, zarr, icechunk) + Open-Meteo historical forecast
    ensemble.py    Open-Meteo ensembles -> heights above ground; retry with backoff on HTTP 429
    indices.py     ONI / QBO / WWV from NOAA, cached daily
  ai.py            numpy-only generator forward pass (no torch); members batched
  adjust.py        mode-3 add-on parts 1-3
  profiles.py      heights grid, from_diff, to_physical, to_site, clip_ranges (copied from tempest)
  calib.py         range-calibration apply + station correction apply (copied)
  assets/          weights.npz, calib.npz, station.npz, orography.npz, manifest.json
  README.md        install, the two calls, modes, limits
```

- **Required dependencies:** numpy only; HTTP uses the standard library (`urllib`).
- **Optional dependencies:** `xarray zarr icechunk` (mode 1 before the Open-Meteo coverage starts) and
  `timezonefinder`. A missing optional package gives a clear message naming what to install.

## Main-repo side (stays in `tempest/`)

- **`tempest/export_tool.py`** writes `tempest_weather/assets/` from a trained `.pt`:
  - weights as float32 `.npz` (float16 only if a fixed-seed test keeps calibration);
  - the calibration map;
  - a thinned station map: today it is 101 MB, and it would be thinned to under 20 MB by subsampling the leftover
    pools, checked against the full map;
  - grid orography;
  - `manifest.json` with the model hash, training years, calibration fit years and the trained area.

  The tool refuses assets whose hashes disagree.
- **Parity test** (`tests/test_tool_parity.py`): same inputs and the same noise give the same samples from
  `tempest.generator.sample.Sampler` and from `tempest_weather.ai`, within 1e-5. Any change to the copied functions
  must keep it passing, so the copy cannot drift from the original.
- **Assets stay out of git** (about 50-70 MB; `models/` is ignored too). The folder is copied with its `assets/`.
  An optional `fetch_assets()` can download them from a GitHub release on first use.

## Build order

| Step | Content | Check | Rough time |
|---|---|---|---|
| T0 | daily forecast logger (WeatherNext 2 + IFS ENS members at the pilot sites) | one day's file has all members and levels | 0.5 day |
| T1 | skeleton, numpy forward pass, export script, mode 4 | parity test; mode-4 coverage equals `score.py`'s on 2024-25 | 1 day |
| T2 | mode 1 (Earthmover + Open-Meteo after store end, slip window, station error) | spot-check against IGRA soundings at Santa Teresa / Midland; 99 % coverage on held-out balloons | 1-2 days |
| T3 | mode 2 (two ensembles, heights conversion, inflation, day 10-15 blend) | coverage on the logged archive since 2026-08-03 | 2-3 days |
| T4 | mode 3 tuning (after A6): GEFS fetch, 7 + 7 inputs, retrain, fading shift, bias check, both `kind`s | walk-forward 2024-25 with real forecasts: coverage ~99 % (`uncertainty`), CRPS better than mode 4 | 4-6 days + 1 retrain |
| T4b | experiment grid (windows and horizon) | best setting on 2021-23, confirmed on 2024-25 | 1-2 days of compute |
| T5 | README; copy the folder into an empty scratch repo and run both calls with only numpy installed | offline tests with recorded API responses; clear errors when there is no network | 0.5 day |

## Known limits

- Modes 3-4 cover only the pilot box until CONUS training.
- Mode 3's real-forecast check rests on a short archive (since 2026-08), plus WeatherNext 2 from 2022 via Earth
  Engine.
- Open-Meteo's free tier: about 10,000 calls a day and few at once. One query = 1-3 calls; results are cached by
  (place, valid hour).
- Mode 1 needs a network connection. Earthmover reads are chunked by year, so a first query near a new place
  downloads tens of MB; the cache keeps them.
