# Phase 4 log (forecast and past-date correction)

Started 2026-11-05 after Phases 1-3 (hold ended). Development years 2024-25 unless stated; every interval is a day-block bootstrap.

## 4.0 Probe of the forecast APIs (2026-11-05, `scripts/p4_probe.py`, raw output `data/p4/probe.json`)

| API | Finding |
|---|---|
| Historical Forecast | pressure-level fields (T 500, wind 850, RH 700) are real for **GFS from 2021-06** and **ECMWF IFS (`ecmwf_ifs025`) from about 2024**; null for IFS 2018-2023. AIFS 2025+, ICON 2024+. It is a continuous best-estimate series, not "the forecast made N days earlier" |
| Previous Runs | `_previous_dayN` works for **surface** variables only (temperature_2m tested for IFS and GFS); pressure-level variants are rejected (HTTP 400). So no true 1-7 day lead history of upper-air fields from Open-Meteo |
| Single Runs | only recent runs (IFS and GFS runs from 2026-09 worked; 2024-2025 runs "not available") |
| Seasonal (EC46) | live: 51 members, 46 days, **daily surface variables only** (no pressure levels); archive only from 2025-09-01 |
| Ensemble | live only: GEFS 31 members and IFS 51, WeatherNext 2 64, AIFS ENS 51, 384 hours; our logger archives it daily since 2026-11-05 |

**Consequence for the plan.** A first-guess correction model for leads 1-46 days cannot be trained on real lead-time upper-air history
from Open-Meteo. The route left is the NOAA GEFS reforecast on AWS (about 2000-2019, 5 members, 16-35 days) fetched with GRIB byte
ranges, plus ERA5-as-stand-in with lead-dependent noise, plus the growing logger archive. Modes P0/F/F2/M therefore wait on that
(see "Blocked" below). **Mode P (past dates) needs none of it and is the part that serves the main goal.**

## 4.4 Mode P: past dates (ERA5 as first guess, balloons as truth) — `tempest/forecast/modeP.py`, `scripts/p4_modeP.py`

First question: how good is ERA5 itself at the exact hour? 1,306 complete 00Z soundings at Santa Teresa and Midland, 2024-25:
MAE of raw ERA5 vs the balloon: u 1.5 / 1.5 / 1.8 / 2.9 m/s (0-1 / 1-5 / 5-12 / 12-18 km), v 1.5 / 1.5 / 1.8 / 3.0, T 0.82 / 0.63 / 0.54 / 1.58 K,
RH 3.7 / 7.2 / 8.5 / 5.4 %. The climate generator's median (no knowledge of the day) is 2-5 times worse (u 4.0 / 4.7 / 9.1 / 6.6, T 3.6 / 2.7 / 2.3 / 2.4, RH 12.3 / 17.3 / 17.3 / 6.5).
**For a past date the answer must start from ERA5, not from the generator.** The linear station correction (a + b ERA5, fitted
1991-2020) changes the median error by only a few percent (T 12-18 km 1.58 -> 1.28 K is the exception).

Residual network (Engression, 2 members, width 256, depth 3, trained 1991-2017 on 28,339 soundings at 00Z and 12Z; early-stopping
validation 2018-20; range map fitted on 2021-23 00Z, pooled per variable x height band): learns balloon - ERA5 from the ERA5
profile, station, season and launch hour. Test on 1,306 soundings, 2024-25 (mean over 16 variable x band cells):

| method | MAE of the median | CRPS | mean abs(cov99 - 0.99) |
|---|---|---|---|
| raw ERA5 (one value) | 2.745 | 2.745 | - |
| ERA5 + empirical error pool (same station, season) | 2.710 | 2.013 | 0.0042 |
| existing station correction (a + b ERA5 + leftover profile) | 2.667 | 1.976 | 0.0100 |
| residual network + range map | 2.657 | 1.935 | 0.0062 |
| **hybrid** (network, except RH 12-18 km where the station correction won on 2021-23) | **2.571** | **1.867** | 0.0079 |

Per cell the network is better than raw ERA5 in nearly every cell: T 0-1 km CRPS 0.43 vs 0.82, T 1-5 km 0.40 vs 0.63, wind 1.05 vs 1.5 (0-5 km),
RH 0-1 km 2.4 vs 3.7. RH 12-18 km: the network (trained on the pre-2022 humidity sensor) is worse than the 2022-23 station map (4.76 vs 3.70),
hence the hybrid, chosen on 2021-23, not the test years. Verdict: **kept as the past-date mode** (median error 6 % below raw ERA5, CRPS 5.5 %
below the old station correction). Open: the 99 % coverage (0.0079 off target) wants a per-column range map; ERA5 only (no 21-level CDS data yet,
step 4.6).

## Blocked / waiting
- 4.2 history fetch for F/F2/M: see 4.0 consequence; the GEFS reforecast route needs `eccodes`/`cfgrib` byte-range reads (not started).
- 4.6 21-level data: the CDS download is at about 8 % (33 of 420 months).
- 4.7-4.9 (modes P0, F, F2, M and the lead blending) depend on the above.

## 4.0 addendum: GEFS reforecast feasibility (2026-11-05)
`s3://noaa-gefs-retrospective/GEFSv12/reforecast/<year>/<yyyymmdd00>/c00|p01..p04/Days:1-10|10-16/<var>_<level group>_...grib2` is readable anonymously
over HTTPS and has `.idx` files (byte ranges per field). Fields are **global** (no server-side cropping), roughly 1 MB per (variable, level, step). A
10-day run for u, v, T, RH, height on 11 levels at 6-hourly steps is about 2,000 fields = ~2 GB per initialisation and member; even keeping only
leads 1, 3, 5, 7 days it is ~180 MB per initialisation. The 50 GB cap allows ~270 initialisations, which is not enough to train a correction
model that beats the live ensembles. **Decision: the GEFS-reforecast route is not taken now** (candidate for the improvement loop if disk allows). Modes P0/F/F2/M
are built from the live ensembles (tool side) and calibrated on the daily logger archive as it grows; until then they are flagged uncalibrated.

## Built so far (code and tests, 2026-11-05)
- 4.3 `tempest/ops/logger_p4.py` (EC46 daily ensemble at both sites, 51 members x 46 days x 8 surface variables; loop running; GEFS 35-day members are not
  served by the Ensemble API: non-null only to 10 days).
- 4.5 `tempest/forecast/scenarios.py`: `scenarios(samples, outcome_fn, pcts, weights)` returns whole real profiles at percentiles of an outcome (2 tests).
- 4.7 (conversion only) `tempest/nearterm/ensemble.py`: Open-Meteo ensemble response (the logger's files) -> u, v, T, RH on the 44 heights, members kept apart.
  Check on the real logger files: IFS and WeatherNext mean temperature agree (Midland 6.5 km: 253.0 K both; 10 m 290.9 vs 291.5 K), 8 % of
  points NaN (levels above the 50 hPa top or below ground). No correction or calibration is applied: that needs verification data the logger has not yet
  collected (one day so far).
- 4.9 `tempest/forecast/router.py`: modes by lead (P <= -6 d, P0 to 0, F to 7, F2 to 15, M to 46, C beyond), cosine weights for the 10-15 day hand-over and the
  35-46 day fade to climate, sample-level mixing so every sample stays a whole profile (3 tests).
- 4.1 `tempest/ingest/openmeteo.py`: cached, rate-limit-aware client for the forecast, ensemble, historical-forecast, previous-runs, single-runs, seasonal and elevation APIs; stale-cache fallback flagged `_stale`; API errors are never cached (4 offline tests).

## Phase 4 end-of-phase checklist (2026-11-05)
| Step | State |
|---|---|
| 4.0 probe | done; findings above and in `data/p4/probe.json` |
| 4.1 client | done, tested |
| 4.2 history fetch | **not started, by decision**: no source for true lead-time upper-air history (probe), GEFS reforecast too large for the 50 GB cap |
| 4.3 extra logger | done, running (EC46 daily) |
| 4.4 mode P | done (hybrid residual network; coverage 0.0079 off target); 21-level retrain (4.6) waits on the CDS download |
| 4.5 scenarios | done, tested |
| 4.6 21 levels | waiting on `fetch_cds` (33 of 420 months) |
| 4.7 modes P0/F/F2 | conversion of the live ensembles to our heights done and tested; calibration waits on logger history (days of data) |
| 4.8 mode M | waits on EC46 archive history (surface variables only) |
| 4.9 router | done, tested (seam-free weights) |
| 4.10 tool hook | part of Phase 5 |
| 4.11 double-check, 4.12 final test | at the very end |
