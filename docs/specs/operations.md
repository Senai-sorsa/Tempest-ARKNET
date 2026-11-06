# Operations: running Tempest as a long-term tool

Spec, 2026-11-04, against commit `ba2e2df`. Extends `docs/plans/TOOL_PLAN.md`. The tool as planned fetches everything
live at query time. That works for a demo, but over years it breaks for these reasons:
- sources change or disappear;
- forecast models are upgraded silently;
- the climate drifts away from the training years;
- answers cannot be reproduced;
- the forecast logger has gaps;
- each machine caches on its own;
- the people who know the system leave.

This spec changes the design to **precompute centrally, read locally**, and gives every failure a detection rule, an
automatic response and a manual fix.

## 1. Architecture

```
                     ┌──────────── scheduled snapshot job (after each forecast cycle) ────────────┐
 Open-Meteo ensembles│  fetch → validate → convert to heights → calibrate → write snapshot        │
 NOAA indices        │  + keep raw responses (verification archive) + health report               │
 IGRA / ERA5T        └───────────────────────────────┬────────────────────────────────────────────┘
                                                     ▼
                          shared store (primary + mirror): snapshots/, extracts/, releases/
                                                     ▼
 tempest_weather tool:  local cache → shared snapshot → live fetch → degraded fallback → clear error
                                                     ▼
                          campaign bundle (everything a result used) → EDITH / flight_sim
```

### 1a. Site registry

`sites.toml` lists the places the team launches or tests:
- name, lat, lon, elevation, time zone;
- launch hours;
- an `active` flag.

Starting entries: Spaceport America and Midland. Add test sites as needed. The snapshot job and the past-date extracts
cover only registered sites. Any other place still works through live fetch.

### 1b. Snapshot job (replaces and extends TOOL_PLAN step T0, the forecast logger)

- **When:** four times a day, at a fixed offset after the 00/06/12/18 UTC forecast cycles become available. Each run
  is idempotent: a cycle already stored is skipped, so extra runs are harmless.
- **What, per active site:**
  - WeatherNext 2 and IFS ENS members on pressure levels;
  - surface variables (2 m temperature, 10 m wind and gusts, radiation, boundary-layer height where served);
  - the latest climate indices (once a day).
- **Steps:**
  1. Fetch, with retry and backoff.
  2. Validate (section 2b).
  3. Save the raw response, gzipped. This is the verification archive.
  4. Convert to the 44 heights.
  5. Derive p, rho and a.
  6. Calibrate each source, then the pool.
  7. Write `snapshots/<site>/<cycle>.npz` and update `snapshots/<site>/latest.json`.
- **Size:** about 7 MB per site per cycle uncompressed (115 members × 60 time steps × 44 heights × 6 variables,
  float32); about 2-3 MB compressed. Keep every cycle for 90 days. After that, keep only the launch-hour slices
  needed for verification: a few hundred MB per site per year.

### 1c. Past-date extracts

Past dates for registered sites are prebuilt, so no on-demand Earthmover reads:
- `extracts/<site>.zarr` holds ERA5 columns at the 4 grid points around each site, 1940 to now, on the 44 heights;
- it also holds hourly surface variables (all 24 hours) for soak temperature;
- a few hundred MB per site.

A monthly job appends the newest ERA5 data. Recent days use ERA5T, ERA5's preliminary near-real-time stream, which
runs about 5 days behind. Mark those days `preliminary` and replace them when final ERA5 arrives.

### 1d. Tool read order

For each query, the tool tries these in order and records which one answered:
1. **Local cache** (same site, same cycle).
2. **Shared snapshot**, if fresh enough (section 3).
3. **Live fetch** from the sources, through the same validation and calibration code as the job.
4. **Degraded fallback** (section 3), with flags.
5. **Clear error** naming what failed and what the user can do. The tool never returns an unflagged guess.

### 1e. Campaign bundles (reproducibility)

Every Monte Carlo campaign saves `bundle_<campaign-id>/`, containing:
- the samples file and the coupling file (`coupled-atmosphere.md`);
- a copy of the snapshot or extract slice used;
- `manifest.json`: the query, mode, `quality` flags, source cycle times, model release, calibration version, tool
  version, and sha256 of every file.

Re-running a bundle reproduces the campaign exactly, years later. A flight readiness review cites the bundle id.

### 1f. Model releases

Models are versioned as `tempest-model-YYYY.N`. Each release holds:
- the assets (weights, calibration maps, station map, orography) with their hashes;
- a **model card**: training years, calibration fit years, test scores with intervals, known weaknesses;
- a changelog.

The tool pins one release and refuses mismatched or corrupted assets (TOOL_PLAN already checks hashes). Old releases
stay available so old bundles still run.

### 1g. Where it runs

- **Primary:** a GitHub Actions scheduled workflow in the repo.
  - Scheduled workflows are disabled after 60 days without repository activity. The health report commits a small
    status file, which keeps the repo active and leaves a public record.
  - Check the free minutes if the repo is private.
- **Backup:** a second scheduler, such as an always-on lab machine or a team-owned small server, running the same job.
  The two never conflict, because writes are idempotent.
- **Storage:** primary bucket or drive plus a mirror. Check the size limits of whatever is chosen; GitHub release
  assets have a per-file cap. Everything in `snapshots/` and `extracts/` can be rebuilt from the sources except the
  verification archive, so the archive is the one thing that **must** be mirrored.

### 1h. Monitoring and the daily health report

One report per day, posted where the team will see it (a GitHub issue or the team channel):
- per source: last good cycle, member counts, schema status, failures in the last 24 h;
- snapshot freshness per site;
- rolling verification against the 00Z balloons at Santa Teresa and Midland and against ERA5T:
  - 99 % and 90 % coverage, bias, and spread/skill per variable and height band;
  - over 30 and 90 days, with bootstrap intervals;
- drift alarms (section 2).

## 2. Failure handling

### 2a. Degradation ladder and quality flags

Every answer carries a `quality` list. EDITH records it and prints it on every report.

| Flag | Meaning |
|---|---|
| `nominal` | everything current and validated |
| `stale-snapshot` | snapshot older than the freshness limit; lead time shifted accordingly |
| `single-source` | one forecast model missing; the other used alone with its own calibration |
| `calibration-suspect` | a source changed or drift was detected; ranges widened (2c) |
| `fallback-mode` | the right mode could not answer; the next one did (for example mode 3 for a 10-day lead) |
| `driver-missing` | a climate index unavailable; the model's "driver missing" path used (PLAN *A6* option 4) |
| `preliminary-past` | past date answered from preliminary ERA5T |

A campaign config can set `require = "nominal"`. Flight readiness campaigns should, so a degraded answer stops the
campaign instead of slipping into a report.

### 2b. Validation (runs on every fetch, in the job and in the tool)

Fail closed: data that fails validation is never used or stored as good.
- **Schema:** expected variables, units, pressure levels, member counts, time steps.
- **Ranges:** T 150-330 K, |u|, |v| < 120 m/s, RH 0-100 %, surface pressure plausible for the site elevation.
- **Physics:** heights increase with falling pressure; the hydrostatic check holds within tolerance.
- **Members:** drop individual bad members if they are under 10 % of a source; otherwise reject the whole cycle for
  that source.

### 2c. Failure table

| # | Failure | Detection | Automatic response | Manual fix |
|---|---|---|---|---|
| 1 | Source down, timeout, HTTP 5xx | request fails after 3 retries with backoff | use latest snapshot if within freshness; else other source (`single-source`); else `fallback-mode` | none if temporary; health report shows duration |
| 2 | Rate limit (HTTP 429) | status code | honour Retry-After, never loop; job spreads calls; tool prefers cache and snapshot | reduce live-fetch use; consider paid tier |
| 3 | Model removed or renamed | schema check: model missing | pool continues with the other source (`single-source`) | update the source adapter; recalibrate if a replacement model is added |
| 4 | Model silently upgraded | provider changelog check in the job, plus a drift test: a jump in rolling bias or spread/skill (CUSUM on daily verification) | `calibration-suspect`: widen that source's ranges by a fixed factor fitted from past upgrades (start 1.2, then tune); online conformal adjustment takes over within its bounds | refit the source's calibration once ~4-8 weeks of post-upgrade verification exist |
| 5 | Units, names or format changed | schema validation fails | reject cycle, fall back as in 1 | update the adapter; add the new format to the recorded-response tests |
| 6 | Bad values in good-looking data | range and physics checks | drop bad members or reject cycle | report upstream if persistent |
| 7 | Snapshot job missed cycles | freshness check (tool) and health report ("no new cycle in 18 h") | tool live-fetches; backup scheduler runs | backfill missed cycles from the source's own archive where it exists (Open-Meteo keeps past ensemble members since 2026-08) |
| 8 | Verification archive gap | daily count check | alert on first missed day | backfill as in 7; WeatherNext 2's own archive (Earth Engine / BigQuery) covers 2022+ |
| 9 | Storage lost or corrupted | hash check on read; mirror comparison weekly | read from mirror | restore; rebuild snapshots and extracts from sources |
| 10 | Earthmover ERA5 store unavailable or moved | extract job fails | past mode keeps working from extracts; new sites use Open-Meteo historical API (has pressure levels), flagged | point the adapter at the new location or at CDS |
| 11 | Copernicus CDS API change or key expiry | training-data job fails | none needed at query time (CDS is only used for rebuilds) | renew key (never committed); update client |
| 12 | NOAA index feed changed or late | parser validation; age of latest value | lagged drivers use the last known value with the longer lag (they are trained for this); past a limit, `driver-missing` | update parser |
| 13 | IGRA host down | verification job fails | verification for those days deferred, not lost | backfill when back (happened once already) |
| 14 | Climate drift (cold bias grows) | rolling bias vs balloons and ERA5T beyond a threshold (e.g. 0.3 K over 90 days in any band) | online bias correction within bounds; alert | yearly retrain (section 4); the warming input (recommendation A4) reduces this |
| 15 | Coverage drift | rolling 90-day 99 % coverage outside 0.97-0.997 for any variable band | online conformal adjustment within bounds; `calibration-suspect` if out of bounds | refit range calibration; investigate cause |
| 16 | Query outside trained area or hours | router check | modes 3-4 refuse with a clear message; modes 1-2 still answer | register the site; extend training (phase 8) |
| 17 | Python dependency breaks | weekly CI run of the full test suite with recorded responses | pinned lockfile (`uv.lock`) protects existing installs; the portable tool needs only numpy | update pins after tests pass |
| 18 | Model assets missing, wrong or corrupted | hash check against the release manifest | refuse to run, name the expected release | re-download the pinned release |
| 19 | Source terms or licence change (e.g. Open-Meteo free tier) | provider notices; health report warns on new errors | none | switch adapter: Open-Meteo paid API or a self-hosted Open-Meteo (check its licence first); ECMWF's own open data for IFS ENS; Earth Engine / BigQuery for WeatherNext 2 |
| 20 | Time-zone or daylight-saving error | unit tests on DST change days and solar-hour edges | everything internal in UTC; local time only at input and output | fix and add the case to tests |
| 21 | Grace allocation expired | renewal reminder 60 days ahead | pilot retraining still fits on a laptop (~13 min) | renew; CONUS work waits |
| 22 | Team turnover, knowledge loss | named owner and backup in `OPERATIONS.md`; yearly handover checklist | health reports keep going to the team, not one person | hand-over session; runbook walk-through |
| 23 | A result is disputed later | bundle exists for every campaign | re-run the bundle | none |

## 3. Freshness rules

| Snapshot age | Use |
|---|---|
| ≤ 12 h | nominal |
| 12-36 h | usable; lead time computed from the snapshot's cycle (a 3-day lead from yesterday's cycle is treated as a 4-day lead); `stale-snapshot` |
| > 36 h | live fetch; if that fails, `fallback-mode` |

Past-date extracts: preliminary ERA5T is used for the last few days and flagged; final ERA5 replaces it.

## 4. Routine maintenance

| When | Task | Owner checks |
|---|---|---|
| Daily | health report | read alarms |
| Weekly | CI with recorded responses; mirror comparison | failures |
| Monthly | extract update; storage usage; verification summary | drift trends |
| After a source upgrade | refit that source's calibration once 4-8 weeks of data exist | coverage back in range |
| Yearly (January) | retrain with the newest full year, refit calibrations, rescore on held-out years, publish a new model release with its model card | scores not worse than the previous release beyond intervals; otherwise keep the old release |
| Yearly (handover) | update `OPERATIONS.md` runbook; owner and backup confirmed | a new member can run the yearly retrain from the runbook alone |

## 5. Tests for the failure handling

- **Recorded responses:** saved real API responses from each source (good, rate-limited, missing model, changed
  format, NaN-filled). Every failure row in 2c that can be simulated gets a test that injects it and checks the
  automatic response and the flag.
- **Fallback chain:** with the snapshot store, the network and each source switched off in turn, the tool still
  answers (or errors clearly) and the flags are right.
- **Bundle round trip:** a bundle re-run gives bit-identical samples.
- **Freshness:** snapshots aged 6, 20 and 40 h give nominal, stale and live-fetch paths.

## 6. Build order

| Step | Content | Replaces / extends |
|---|---|---|
| O1 | site registry; snapshot job writing raw responses (the logger) with validation | TOOL_PLAN T0 |
| O2 | snapshot processing (heights, p/rho/a, calibration) and `latest.json` | TOOL_PLAN T3 |
| O3 | tool read order, quality flags, freshness rules | TOOL_PLAN T1-T3 |
| O4 | past-date extracts and monthly update | TOOL_PLAN T2 |
| O5 | campaign bundles; EDITH records flags and bundle id | `coupled-atmosphere.md` steps 3-4 |
| O6 | health report and drift tests; backup scheduler | new |
| O7 | recorded-response and fault-injection tests; weekly CI | TOOL_PLAN T5 |
| O8 | model release process, model card, `OPERATIONS.md` runbook | new |

**Start O1 first.** Every day the logger is not running is verification data lost for good.
