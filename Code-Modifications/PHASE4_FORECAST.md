# Phase 4: Forecast and past-date correction system

Written 2026-11-04. Status: **STARTED 2026-11-05** (Phases 1-3 finished; hold ended). Progress in docs/PHASE4_LOG.md. Original note: ON HOLD until Phases 1-3 are finished (user's decision, 2026-11-04).

Phase 4 is a **separate system** from Phases 1-3 (`PHASED_PLAN.md`). Another session is already working on Phases 1-3. Phase 4 has its own session, its own files and its own experiment log. It shares the machine, the data and the rules, and it must never break the Phases 1-3 work (section 3).

What Phase 4 covers:
- **Past dates:** the best estimate of what the atmosphere actually was, with honest error ranges.
- **Recent past (0-5 days ago),** before ERA5 has that day.
- **Next 1-15 days:** a corrected forecast.
- **Weeks 3-6 (days 16-46):** a corrected sub-seasonal forecast.

Beyond 46 days the Phases 1-3 climate model is used unchanged (today that is E12).

It **replaces** steps T2, T3 and T4/T4b in `PHASED_PLAN.md` §4 and modes 1-3 in `docs/TOOL_PLAN.md`. The Phases 1-3 session builds T1 (the tool skeleton), T5 and mode 4. Phase 4 plugs its modes into that skeleton (4.9).

---

## Contents
0. How to start a Phase 4 session (ready-to-paste prompt)
1. The idea in plain language
2. Goals and what "done" means
3. Separation rules: how to run alongside the Phases 1-3 session
4. Modes and lead-time map
5. Data sources (verified facts, to-verify items, budgets)
6. Model design (reuse the existing generator)
7. Training, calibration and the honest test protocol
8. Metrics, baselines and pass rules
9. Work plan: steps 4.0-4.12 with files, flags, tests and cost
10. Operations: live use, caching, failures, refresh
11. Honest expectations
12. Risks and the ASK_LATER list
13. Open questions answered by the 4.0 probe

---

## 0. How to start a Phase 4 session

Paste this into a new session, in a different Claude account or window from the Phases 1-3 session:

```
You are running Phase 4 of Tempest-ARKNET (C:\Users\Senai\Tempest-ARKNET): the forecast and past-date
correction system. Another session is running Phases 1-3 on the same machine at the same time. You have no
memory of earlier sessions; the files are your context.

STEP 0
1. Read Code-Modifications/PHASE4_FORECAST.md in full. It is your plan.
2. Read Code-Modifications/HANDOVER.md sections 2-4 and 6: the user, hard rules, machine limits and metrics.
3. Read docs/TOOL_PLAN.md, which you are taking modes 1-3 over from.
4. Save the hard rules and PHASE4_FORECAST.md section 3 (separation rules) as memory notes.

PHASE A: planning (the only time you talk to me first)
Turn section 9 into a concrete schedule. Give one message with every question you truly need answered.
Then wait for my approval.

PHASE B: after approval, work on your own to the very end.
- Never stop to ask again. If something breaks, diagnose it, fix it and keep going.
- Follow section 3 strictly. The other session's work must never break.
- Log every experiment in docs/PHASE4_LOG.md.
- Risky items go to Code-Modifications/ASK_LATER.md under a "Phase 4" heading. Then carry on with the rest.
- At the end:
  - run the full double-check (step 4.11);
  - run the single 2026 H1 final test;
  - report in plain language.
- Then keep improving until several honest attempts in a row give no gain.
```

---

## 1. The idea in plain language

The current model (E12) knows only the place, the date and the climate indices, so its "most likely" value is close to normal weather for that day. Its ranges are honest, but it cannot say what the weather actually was or will be.

Phase 4 gives the **same model** one more input: a **first guess** for that exact day.

| When | First guess |
|---|---|
| past dates | ERA5 for that hour |
| last 0-5 days | the newest forecast run |
| next 1-15 days | weather-model forecasts |
| weeks 3-6 | ECMWF's 46-day forecast (EC46) |

The model then learns two things:
1. how wrong that first guess usually is: its bias by height, season, hour and lead time;
2. how wide the range around it should be.

The output keeps today's format: a corrected most-likely profile plus calibrated Monte Carlo samples. When a guess carries no information (very long leads), training teaches the model to fall back to climate-like ranges, so nothing gets worse than E12.

Data roles:
- **ERA5:** the "truth" for training the forecast corrections, and the first guess for past dates.
- **Balloons (IGRA):** independent truth, used for the honest test.
- **Forecasts:** fetched from APIs, mostly Open-Meteo. Only a few hundred MB on disk, as a cache.

---

## 2. Goals and what "done" means

| ID | Goal | Measured by | Target |
|---|---|---|---|
| G4.1 | Past dates more accurate than raw ERA5 | median MAE and CRPS against balloons, 2024-25 dev, then 2026 H1 | better than raw ERA5 in most variable × height bands; never worse than E12 |
| G4.2 | Forecast days 1-15 more accurate than the raw forecast | median MAE and CRPS against ERA5 and balloons, per lead day | better than the raw forecast (deterministic and ensemble) at every lead |
| G4.3 | Weeks 3-6 at least as good as E12 | CRPS skill against E12 and against 15-year climatology, per week | at least E12 at every lead, and better where the forecast has signal |
| G4.4 | Honest ranges everywhere | 99 % range coverage per variable, height band and lead bucket | mean \|cov99 − 0.99\| ≤ 0.003, no band below 0.98 |
| G4.5 | No jumps between modes | median and spread against lead, 0-46 days | smooth; no step larger than the noise between neighbouring leads |
| G4.6 | Usable in the tool | `values()` / `distribution()` choose the mode by date | mode, source and its tested error reported with every answer; falls back to E12 if the APIs are down |
| G4.7 | Scenario picker | `scenarios(samples, outcome_fn, pcts)` | returns real whole profiles at the 1/25/50/75/99 percentiles of an outcome; tested |
| G4.8 | Honest reporting | every number | bootstrap interval (resampling whole days), test years stated, "development" until the final test |

---

## 3. Separation rules: running alongside the Phases 1-3 session

These rules exist because two sessions share one laptop, one GPU and one repo.

### 3.1 Files Phase 4 owns (may create or edit)

| What | Where |
|---|---|
| shared Phase 4 code | `tempest/forecast/` (new package) |
| past and recent-past modes | `tempest/past/` (currently a stub) |
| forecast modes | `tempest/nearterm/` (currently a stub) |
| Open-Meteo client | `tempest/ingest/openmeteo.py` (new) |
| scripts | `scripts/p4_*.py`, `scripts/p4_*.sh` |
| tests | `tests/test_p4_*.py` |
| models | `models/p4/` |
| data | `data/p4/`, `data/openmeteo/` (API cache) |
| experiment log | `docs/PHASE4_LOG.md`, **not** `docs/PLAN.md`, so the two sessions never edit the same log |
| plan | this file |

### 3.2 Files Phase 4 must NOT edit

- Everything else in `tempest/`: `generator/`, `calibrate/`, `scoring/`, `profiles/`, `ingest/` other than `openmeteo.py`, `ops/`.
  - Import and reuse them; never change them.
  - If Phase 4 needs a change there, subclass or wrap the code inside `tempest/forecast/`.
  - Example: `GuessGenerator(Generator)` adds the residual skip without touching `model.py`.
- `docs/PLAN.md`, `Code-Modifications/PHASED_PLAN.md`, `HANDOVER.md`, `START_PROMPT.md`: these belong to the other session. Exception: the one-line pointers already there.
- `configs/sites.toml` and the running logger (`tempest.ops.logger --loop 12`): read only.
  - If Phase 4 needs more logged sites or models (step 4.3), write a separate logger config or script under `scripts/p4_*`.
- The running CDS download (`tempest.ingest.fetch_cds`) and `pipeline4.sh`: never stop or edit them.

### 3.3 GPU and CPU sharing

- **One GPU job on the whole machine at a time.**
- Before starting any training or sampling job, check that no other session's job is running:
  1. `Get-CimInstance Win32_Process` for python command lines containing `tempest.generator`, `train`, `score`, `sample` or `p4_`;
  2. `nvidia-smi --query-compute-apps=pid --format=csv`.
- If busy, do CPU work (data building, fetching, tests) and check again later.
- The Phases 1-3 session has priority on the GPU.
- Training runs stay at about 15 minutes or less unless a verified gain justifies more.
- Heat (HANDOVER §4): CPU affinity 4095, BelowNormal priority, `OMP_NUM_THREADS=12`. Never stop a running job because of heat.
- API fetchers are network-only. They may run alongside training, at low priority, one fetcher at a time.

### 3.4 Shared rules (same as HANDOVER §3)

- "Dont break anything". New behaviour sits behind a flag, off by default. Failed items are switched off, not deleted.
- Never print the CDS key.
- Never commit `data/` or `models/`.
- Commit only when the user says yes, with no Claude attribution line.
- 2026 Jan-Jun is touched once, at the very end.
- Run pytest only for `tests/test_p4_*`, so you never collide with the other session's scoring runs.
- Run the full suite only in step 4.11, when the other session is not scoring.

---

## 4. Modes and lead-time map

| Mode | Lead (valid time − now) | First guess | Extra inputs | Fallback |
|---|---|---|---|---|
| **P** past | ≤ −6 days (ERA5 exists) | ERA5 at that hour: 13-level Earthmover store, or 21-level CDS data where available | — | none needed |
| **P0** recent past | −5 to 0 days | Open-Meteo Previous Runs `_previous_day0` (IFS, GFS) or the Historical Forecast API | source id | P from the ERA5T preliminary data if available, else F at lead 0 |
| **F** short range | +0 to +7 days | Previous Runs `_previous_dayN` deterministic, live from the Forecast API | ensemble spread (Ensemble API), lead, source id | E12 |
| **F2** medium range | +8 to +15 days | Single Runs (IFS HRES full run) live; ECMWF IFS ENS mean | ensemble spread, lead | E12 |
| **M** weeks 3-6 | +16 to +46 days | EC46 ensemble mean as weekly-mean anomalies (Seasonal API); GEFS 35-day ensemble as a second source | weekly ensemble spread, lead | E12 |
| **C** climate | > +46 days, or no guess | none: Phases 1-3 model (E12 or its successor) | indices | — |

All boundaries are settings (`p0_days = 5`, `f_days = 7`, `f2_days = 15`, `m_days = 46`) and tuned in step 4.8.

---

## 5. Data sources

### 5.1 Already local (no fetching)

| Source | Years | Levels | Use |
|---|---|---|---|
| ERA5 Earthmover store | 1980-2026 | 13 pressure levels → 44 heights | P first guess; truth for F, F2, M |
| ERA5 CDS, extra boundary-layer levels | 1991-2025, **downloading: 27 of 420 months on 2026-11-04, about 40 min per month** | 21 levels | better P near the ground (step 4.6) |
| IGRA balloons | 1980-2025 | soundings | P truth; final check for every mode |
| Daily logger archive (`data/ops/raw/`) | from 2026-11-05 | 13 levels, WeatherNext 2 (64 members) and IFS ENS (51) at Spaceport America and Midland | live check of the real feed (it grows daily) |

### 5.2 Open-Meteo APIs (verified from the docs via Context7, 2026-11-04)

| API | Content | History | Notes |
|---|---|---|---|
| Previous Runs | value forecast N days before valid time, `_previous_day0..7` | GFS from 2021-03, JMA from 2018, most others from 2024-01 | same models and variables as the Forecast API; pressure levels **to verify (4.0)** |
| Single Runs | full output of one run (`&run=`) | ECMWF IFS HRES from 2024-03; others from 2026-04 | needed for leads 8-15 |
| Historical Forecast | continuous best-run series | about 2021 on | P0 and fallback |
| Ensemble | members live; GEFS up to 35 days, IFS ENS 15 days, WeatherNext 2 | live only; past members are not served | spread inputs; our logger keeps them |
| Seasonal | EC46 (46 days, daily runs, 51 members, 6-hourly, 36 km) and SEAS5 (7 months) | members kept 1 month; **ensemble mean and spread stored longer** (how long: to verify) | M first guess; data is not bias-corrected |
| Pressure levels | 1000-10 hPa (31 levels) for deterministic models | — | the logger found that 975/950/900/800 hPa are null in the Ensemble API |

Licence and limits:
- Free tier is **non-commercial**, under 10,000 calls a day.
- Calls with more than 10 variables, or more than 2 weeks of data, count as several calls.
- Commercial use needs the paid plan (ASK_LATER).

### 5.3 Long training history for forecast modes (optional, makes the honest ≤2020 protocol possible)

| Source | Years (to verify) | Content | Size if fetched only at our points |
|---|---|---|---|
| NOAA GEFS v12 reforecast (AWS open data, no account) | about 2000-2019 | daily 00Z, 5 members, 16 days; weekly 11 members to **35 days** | a few GB using GRIB `.idx` byte ranges, if it can be done per point; else larger, so check first (4.0) |
| GEFS operational archive (AWS) | about 2020 on | 31 members, 16-35 days | same approach |
| WeatherNext 2 archive (Earth Engine / BigQuery) | 2022 on | the model the tool uses | needs a Google account and terms acceptance: **ASK_LATER** |

Stay within a **100 GB total disk cap** (raised from 50 GB on 2026-11-05) for all Phase 4 data. Check sizes before any bulk fetch.

### 5.4 Points

Start with:
- the balloon stations in or near the box (the ones `station_map_mix` already uses);
- the 2 logger sites;
- about 6 grid points spread across the box.

Add more points only if a test shows a gain.

### 5.5 Fetch budget (rough, verify in 4.0)

| Fetch | Size | Days at the free limit |
|---|---|---|
| F history: 12 points × 5 years × leads 1, 2, 3, 5, 7 × 13 levels × 5 variables | ~40k weighted calls | ~4 |
| F2 history: 00Z runs only, 6 points, 2.5 years | ~27k | ~3 |
| EC46 ensemble-mean history | depends on 4.0 | small if it exists |
| Daily live use by the tool | < 100 calls a day | — |

---

## 6. Model design: reuse the existing generator

- **Engine:** the same engression `Generator` (`tempest/generator/model.py`) and the same loss (afCRPS α 0.95 + energy score 0.1 + step CRPS 0.5). Same 4-member training, `Sampler`, quantile-map calibration (m = 199) and scoring code.
- **New wrapper `tempest/forecast/model.py: GuessGenerator(Generator)`:**
  - extra input `guess`: the first-guess profile, converted to our 44 heights plus surface (179 values) with `tempest/profiles/to_heights.py` and normalised with the target scaler;
    - variant A: all 179 values;
    - variant B: 32 PCA modes of the guess, if A overfits.
  - extra inputs `lead_days`, `guess_spread` (ensemble standard deviation per height and variable, compressed like the guess; 0 if unknown), and `source_id` (one-hot: ERA5, IFS, GFS, WeatherNext 2, EC46, GEFS);
  - **residual output:** `out = guess_norm × g + net(...)`, where `g` is a learned per-output gate that starts at 1.
    - The last layer starts at zero, so an untrained model returns the guess itself. Training only learns corrections, which suits the short forecast history.
    - At long leads training can push `g` toward 0, which means "ignore the guess, use climate".
  - existing inputs kept: lat, lon, elevation, day-of-year, hour, year and the indices (as `linear_cols`, exactly as E12 does).
- **Mode M:** weekly-mean anomalies (forecast minus the model's own climate) enter as `linear_cols` too, the same mechanism the ENSO and QBO indices use. It stops the network memorising individual days.
- **One model per mode family:**
  - `models/p4/gen_P.pt`;
  - `models/p4/gen_F.pt`, covering P0, F and F2 with lead as an input (split them only if validation says so);
  - `models/p4/gen_M.pt`.
- **Calibration:** a quantile map per mode and lead bucket (0, 1-2, 3-5, 6-7, 8-11, 12-15, 16-22, 23-29, 30-36, 37-46). Plus the Phases 1-3 joint and whole-profile width fix (`joint.py`) if the scenario tests need coherent profiles.
- **Ideas carried over from TOOL_PLAN mode 3**, now experiments inside M:
  - lagged departures over the last 1, 3 and 7 days;
  - the fading shift `exp(−(lead − 7)/τ)`;
  - a running 30-day bias check, capped at half the climate standard deviation.

  Each is kept only if it wins on validation.

---

## 7. Training, calibration and the honest protocol

Splits use whole days only. Forecast errors are shared across heights and points on the same day, so a day must never be split between train and test.

| Mode / source | Train | Calibrate + choose | Dev test | Final test (once) |
|---|---|---|---|---|
| P (ERA5 → balloons) | ≤2020 | 2021-23 | 2024-25 | 2026 H1 |
| F/F2 pre-training on GEFS reforecast (if fetched) | 2000-2019 | — | — | — |
| F (GFS deterministic, Previous Runs) | 2021-03 to 2023 | 2024 | 2025 | 2026 H1 |
| F/F2/P0 (ECMWF; WeatherNext 2 if granted) | 2024 | 2025 H1 | 2025 H2 | 2026 H1 |
| M (EC46 history, GEFS reforecast weekly 35-day runs) | oldest 60 % (≤2019 for the reforecast) | next 20 % | last 20 % / 2024-25 | 2026 H1 |

- **Two-stage training for short-history sources:**
  1. pre-train on the long sources (ERA5 plus GEFS reforecast);
  2. fine-tune or recalibrate on the live source's short history.

  Keep stage 2 only if it beats stage 1 alone on that source's validation slice.
- **ERA5 as a stand-in forecast** (from TOOL_PLAN): ERA5 plus lead-dependent error noise fitted from real forecasts gives 1980-2020 of extra pre-training data. Try it as an experiment, and keep it only if it helps.
- **Model choices on very short histories:** use rolling-origin time-series cross-validation (whole months). Fit the final model once on train plus calibration, then dev-test.
- **Leak checks:**
  - no valid date in both train and test;
  - no forecast run initialised after its test valid date's split boundary;
  - no 2026 H1 data opened before 4.11.

---

## 8. Metrics, baselines and pass rules

Metrics are reported per variable (u, v, T, RH, t2m, sp, rh2m), per height band (0-1, 1-5, 5-12, 12+ km) and per lead bucket:

| Metric | What it tells |
|---|---|
| MAE and RMSE of the median | how close the most likely value is |
| CRPS, plus skill against each baseline | quality of the whole distribution |
| cov99 and cov90 | range honesty |
| whole-profile coverage (`joint.py`) and shear and lapse-rate percentiles (`scripts/physics.py`) | whether the samples are realistic whole profiles |

Baselines per mode:

| Mode | Baselines |
|---|---|
| P | raw ERA5 (CRPS using the station-fitted ERA5 error spread, as TOOL_PLAN mode 1 planned); E12 |
| P0, F, F2 | raw deterministic forecast; raw ensemble (members as samples); ensemble with simple spread inflation (TOOL_PLAN mode 2); E12 |
| M | raw EC46 ensemble; E12; 15-year climatology |

**Pass rule (per mode, on the dev test):**
1. CRPS better than every baseline in most bands, and not worse than the best baseline by more than its bootstrap interval in any band.
2. MAE of the median better than the raw first guess in most bands.
3. Coverage meets G4.4.

A mode that fails stays off (flag), and the tool uses the best baseline for those leads instead.

---

## 9. Work plan

Order: highest value first, and work that needs only local data before work that waits on fetching.

| Step | What | Files (all Phase 4-owned) | Flag | Test | Cost |
|---|---|---|---|---|---|
| **4.0** | **Probe** (results written into section 13):<br>• pressure levels in Previous Runs / Single Runs (IFS, GFS);<br>• real history start of each API;<br>• EC46 ensemble-mean history length and its upper-air variables;<br>• call weights;<br>• GEFS reforecast years, members, 35-day runs, `.idx` per-point fetch size | `scripts/p4_probe.py` | — | output saved to `data/p4/probe.json` | ½ day, no GPU |
| **4.1** | Open-Meteo client: one function per API, parquet cache, retry with backoff, rate limit, resume | `tempest/ingest/openmeteo.py` | — | `tests/test_p4_openmeteo.py` using recorded JSON fixtures (no network in tests) | ½-1 day |
| **4.2** | Start background fetches: F history, then F2, then EC46 mean | `scripts/p4_fetch.py` | — | resume test; size check under 100 GB | runs about 4-7 days unattended |
| **4.3** | Extra logger (separate from the running one): EC46 ensemble mean and spread daily + GEFS 35-day members at the same sites, so the M archive grows | `scripts/p4_logger.py`, `configs/p4_sites.toml` | — | validation like `tempest.ops.logger` | ½ day |
| **4.4** | **Mode P:** pair each balloon launch with ERA5 at that hour and grid point. Train `gen_P`, calibrate, score on balloons 2024-25 | `tempest/forecast/{model,build,train}.py`, `tempest/past/` | `--guess` | `tests/test_p4_model.py`: untrained model returns the guess; feature shapes | 1-2 days, about 15 min GPU per run |
| **4.5** | Scenario picker `scenarios(samples, outcome_fn, pcts)` | `tempest/forecast/scenarios.py` | — | `tests/test_p4_scenarios.py`: picked outcomes equal `np.percentile` | 2 h |
| **4.6** | P on the 21-level CDS data, when the download finishes | same | `--levels 21` | compare with 4.4 | 1 day, waits on the download |
| **4.7** | **Modes P0, F, F2** from the fetched history; optional GEFS-reforecast pre-training; source-specific stage 2 | `tempest/nearterm/`, `tempest/forecast/build.py` | `--guess --lead` | leak test: no run after the split boundary | 2-3 days once data is in |
| **4.8** | **Mode M** (if 4.0 allows): weekly anomalies, GEFS 35-day and EC46; then the carried-over experiments (fading shift, lagged departures, running bias) one at a time | `tempest/forecast/` | `--weekly` | lead-curve plot | 2-3 days |
| **4.9** | Lead blending and tuning of the mode boundaries. Plot MAE, CRPS and coverage against lead, −30 to +46 days. If a seam is bad, add a mixture weight w(lead) learned on validation | `tempest/forecast/router.py` | — | seam test (G4.5) | 1 day |
| **4.10** | Tool hook: plug P, P0, F, F2 and M into the T1 skeleton from the Phases 1-3 session (`tempest_weather/`) as numpy-exported models. Live fetch with cache; fall back to C if the API fails; report mode, source and tested error | `tempest_weather/modes_p4/` (new subfolder only) | per-mode switch | parity test 1e-5; fault-injection test (API down) | 1-2 days; needs T1 done first |
| **4.11** | **Double-check:**<br>• full pytest (when the other session is idle);<br>• rescore every kept model;<br>• check that the calibration and model hashes match;<br>• leak audit;<br>• confirm E12 and the Phases 1-3 outputs are unchanged.<br>Fix anything found, even if that means retraining | — | — | — | ½ day |
| **4.12** | **Final test on 2026 H1, once per mode.** Plain-language report: a table per mode with intervals. Then the improvement loop | `docs/PHASE4_LOG.md` | — | — | ½ day |

Critical path: 4.0 → 4.1 → 4.2 (fetching runs in the background while 4.4 and 4.5 run) → 4.7 → 4.9 → 4.10 → 4.11 → 4.12.

Rough total: 2-3 weeks of wall time, mostly waiting on fetches.

---

## 10. Operations

- **Cache:** `data/openmeteo/` as parquet, keyed by API, model, run, point and variable.
  - Live answers are reused for 6 hours, the global model update cycle.
  - Past data is cached forever.
- **API down or slow:**
  - retry 3× with backoff;
  - then the newest cached run if under 36 hours old (flagged "stale");
  - then mode C, with a warning.
  - Never fail silently.
- **Model upgrades at the forecast centres** shift their bias.
  - `source_id` plus recent-weighted fine-tuning handle this.
  - A monthly drift check compares the last 30 days of the logger archive with ERA5 and balloons. A refit is triggered when CRPS degrades beyond its interval.
  - The refit schedule itself is an ASK_LATER item.
- **ERA5 lag:** ERA5T is about 5 days behind. The P/P0 boundary moves with the store's actual last date, not a fixed number.

---

## 11. Honest expectations (published typical errors, not promises)

| Mode | Raw first-guess error (mid-troposphere T) | What correction can add |
|---|---|---|
| P: ERA5 vs balloons | 0.5-1 °C | small; mostly near-ground bias and RH |
| F: days 1-3 | 1-2 °C | 5-20 % lower error, and honest ranges |
| F: day 7 | 2-3 °C | 5-20 % |
| F2: days 10-15 | near climatology | mostly better-shaped ranges |
| M: weeks 3-6 | climatology | a little; warm/cold or wet/dry tilts in some weeks |

Tell the user plainly that weeks 3-6 will be close to E12. The gain there is a slight shift in the odds, not a day-specific forecast.

---

## 12. Risks (to `ASK_LATER.md` under "Phase 4"; never block on them)

| Risk | Handling |
|---|---|
| Open-Meteo licence is non-commercial | note in the README; paid plan only with user approval |
| APIs may change or disappear | cache, fallback to C, recorded fixtures in tests |
| Short ECMWF history (from 2024) | wide intervals, stated; GEFS-reforecast pre-training |
| WeatherNext 2 archive needs an account and accepted terms | ASK_LATER; never create accounts or accept terms |
| Collision with the Phases 1-3 session | section 3 rules; GPU check before every job |
| Disk | 100 GB cap for Phase 4 data; check before every bulk fetch |
| Heat | HANDOVER §4 limits; fetchers at low priority |

---

## 13. Open questions answered by the 4.0 probe (filled in 2026-11-05; details in docs/PHASE4_LOG.md)

- Pressure-level history of past forecasts at a lead: **not available from Open-Meteo** (Previous Runs is surface-only; Historical Forecast is a stitched best-estimate series, GFS from 2021-06, IFS from ~2024; Single Runs only the newest runs).
- EC46: surface daily variables only, 51 members, archive from 2025-09-01.
- Still to verify: GEFS reforecast years/members/35-day runs and the size of per-point byte-range fetches.

- [ ] Previous Runs: pressure levels for IFS and GFS? Which levels? True start dates?
- [ ] Single Runs: pressure levels for IFS HRES? Weight of one full-run call?
- [ ] Seasonal API: how far back are the EC46 ensemble mean and spread kept? Upper-air variables?
- [ ] GEFS v12 reforecast: years, members, 35-day weekly runs, per-point fetch possible and its size?
- [ ] Actual call weights: compare the 5.5 budget with reality.
