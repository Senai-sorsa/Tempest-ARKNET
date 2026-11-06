# Downloads to do (automatic: no Colab, no login)

Only downloads that a script on this PC can do unattended. The WB2 pulls that need Colab are in `Colab downloads.md`.

**Nothing here has been started.** The user's current rule is no downloads beyond what is already running.

**Ground rules (same as `Strong improvment.md` section 6):**
- `era5_cds` is still downloading: leave it alone.
- Another Claude session may be training, so don't compete with it. Run downloads at low priority, one at a time.
- Write to new folders; never overwrite existing `data/raw/` folders.
- `data/raw` is at about 65 GB (2026-11-05), under the 100 GB cap (raised from 50 GB on 2026-11-05). Everything below except A4 is tiny.

---

## A1. Open-Meteo Previous Runs: surface lead history at the sites — best value, tiny

- **What:** the forecast made 1-7 days earlier (`_previous_day1` … `_previous_day7`) for **surface** variables at each site, for the models the tool uses live (`ecmwf_ifs025`, `gfs_seamless`). Variables: `temperature_2m`, `dew_point_2m`, `wind_speed_10m`, `wind_direction_10m`, `surface_pressure`.
- **Limit:** surface only. Pressure-level variants return HTTP 400 (PHASE4_LOG).
- **Why:** real lead-time history of the **live** models at the site. It is used for:
  - B: back-testing the EWMA bias tracker on the actual feed.
  - G: setting the surface kernel widths.
  - C/I: EMOS for surface variables now, without waiting for the logger.
- **How:** the client already exists: `tempest.ingest.openmeteo.previous_runs(lat, lon, models, hourly, start, end)`. It caches, and an archive request never expires.
  1. New script `scripts/fetch_previous_runs.py`. For each site in `tempest/ops/sites`, request one month at a time from the earliest available date (probe first; Open-Meteo states about 2024) to the present.
  2. Save to `data/raw/om_previous_runs/<site>/<model>/<yyyymm>.json`, skipping existing months. Sleep between calls.
- **Size / limits:** a few MB in total. Well under the free limit of about 10,000 calls a day. Long spans count as several calls, so stay with one month per call.
- **Self-check:** on one month, assert that `previous_day1` at valid time t is not equal to `previous_day3` (that is, real leads, not a copy of the analysis).

## A2. ASOS refresh to the present — tiny

- **Why:** verification for A1 (2024-2026) and for the bias tracker.
- **How:** the existing script, into a new folder:
  `python -m tempest.ingest.fetch_asos --out data/raw/asos_2026 --first 2024 --last 2026`
  It rate-limits and retries on its own.
- **Size:** a few MB.

## A3. IGRA refresh to the present — small

- **Why:** upper-air verification for 2024-2026 (the logger era, and A1 at the launch sites). It is also the backtest truth for G (`observe()`).
- **How:** the existing script, into a new folder (period-of-record files would otherwise replace the current ones):
  `python -m tempest.ingest.fetch_igra --out data/raw/igra_2026`
  For Denver, add its station ID as an argument, into `data/raw/igra_denver_2026`.
- **Size:** about 400 MB, like the current folders.

## A4. NOAA GFS forecasts on AWS: optional, heavy transfer

- **What:** GFS forecasts, all starts and leads, 2021 onward, from the public `noaa-gfs-bdp-pds` bucket (no login). Byte-range reads using the `.idx` files fetch only the needed GRIB fields.
- **Why:** the only automatic route to **upper-air** lead-time history with 00/12Z starts (the same goal as Colab C1, but a different model). Mode F would need its own fit on it.
- **Cost:** each field is still a whole-globe grid. This is my estimate, not measured:
  - At 0.5°, about 0.25 MB per field and about 70 fields per forecast (5 variables x 13 levels + surface), so about 17 MB per forecast.
  - 00+12Z every 4th day, 10 leads (24-240 h), 2021-2025: about 9,000 forecasts, so **about 160 GB transfer** for about 1 GB kept.
  - Every 2nd day with 20 leads would be about 640 GB.
- **How:** new `tempest/ingest/fetch_gfs.py`:
  1. For each start, read the `.idx` file and pick the byte ranges for the needed fields.
  2. Fetch them, decode with `cfgrib` (check it is installed), crop to the 13x29 box, and save monthly netCDF to `data/raw/gfs_aws/`.
- **Recommendation:** do it only if Colab C1 is not possible. It costs days of bandwidth.

---

## Already automatic (no action)

| What | Used by | Note |
|---|---|---|
| Daily ensemble logger | C, I, L | Running since 2026-11-05. It only needs about 60-90 days. |
| Live observations at run time (pad sensor, IGRA morning sounding, ASOS) | G, B | Small reads made by the tool when it runs. |

## Order

1. A1, A2 and A3 (all tiny; they unlock the B/G/C surface work).
2. A4 only if Colab is ruled out.
