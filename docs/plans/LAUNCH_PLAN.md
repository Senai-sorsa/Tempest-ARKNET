# Launch plan: 80 km extension, launch-day correction, wind tails (user, 2026-11-06)

Source: the Gemini overview, fact-checked by Opus (`docs/reviews/triage/GEMINI_OVERVIEW_TRIAGE.md`).

**User decisions (2026-11-06):**
- **A1:** modified option (c). Do not retrain. Add an extension that fuses the best atmospheric models and climatology with our 0-18 km generator, up to **80 km**.
- **A2:** a flexible launch-day correction, built well.
  - Inputs are whatever is known on the day: location, time, and any readings, such as temperature, average wind speed, 2D wind direction, gusts, pressure and humidity. It is **not necessarily a balloon**.
  - Output is a corrected version of every output: the profile, the surface values, the extension, and the flight layer.
- **A3:** wanted.
- **A4:** see section 4.

Runs **after the G9 follow-up block (LOOP3 L3-28..33)**, using the same rules: one GPU job at a time, honest years, and never touching 2026 or holdout data. A1 and A2 need no GPU.

---

## A1. Extension 18-80 km (no retraining)

What exists now: `tempest_weather/flight_sim_readers.py` continues T and p above 18 km along US Standard Atmosphere 1976 lapse rates and holds the wind at its 18 km value. That is one fixed answer with no spread and no season. Above about 25 km it can be off by 10-20 K and tens of m/s, because the stratospheric jets reverse with season.

**Design: "best source per layer, copula-tied to our top".**

| Layer | Source (climatology / statistics) | Source on a forecast day (mode F) | Validation truth |
|---|---|---|---|
| 18-~48 km (to 1 hPa) | ERA5 pressure levels 1-70 hPa, per site × month × hour, 1991-2023 | GFS upper levels (check how high its level list goes; ECMWF open data stops at 50 hPa) | IGRA balloons 18-~30 km, 2024-25 |
| 48-80 km | MERRA-2 (model top 0.01 hPa ≈ 80 km; T, u, v), per site × month | none (climatology only; flagged) | Aura MLS temperature (satellite) 2024-25, if fetched |
| density/composition check | NRLMSIS 2.1 (`pymsis`) | none | MERRA-2 / MLS |

How it fuses, sample by sample:
1. **Anomaly carry-over.** Fit a Gaussian copula on ERA5 between the generator's top band (12-18 km T, u, v) and the extension heights. Each generated sample's top-band anomaly then sets the conditional mean and spread of its extension column. Correlation decays with height, so by ~35 km it is close to climatology. This is the same closed-form Schur step that `condition_on_observations` already uses, so it is code reuse, not new maths.
2. **No jump at 18 km.** The extension's first heights overlap 15-18 km. A short cosine blend over 18-20 km matches it to the sample's own values.
3. **Consistent thermodynamics.** p, ρ and speed of sound come from hydrostatic integration of the extended T, as the readers already do. Humidity is set to 0 above 18 km.
4. **Honest labels.** Every output carries `source_by_height`: generator / ERA5-copula / MERRA-2-climatology / MSIS. A simulator or user can then see which part is weather and which part is climate.

**Accept:**
- IGRA 18-30 km, 2024-25: u/v/T cov99 within 0.01 of 0.99, and CRPS better than the US76 hold.
- 30-80 km: the MERRA-2 / MLS cov99 bias is reported. It is not gated, because there are no in-situ truths up there.
- 0-18 km: unchanged, bit for bit.

**Data:**
- ERA5 1-70 hPa for the pilot box. Use the CDS API (`tempest/ingest/fetch_cds.py`, adding upper levels), which is small: ~1-3 GB. **Not** ARCO from home: that pulls ~370 GB per month.
- MERRA-2 needs a free NASA Earthdata login: **user action**. It is a few GB for the box, at monthly-diurnal resolution.
- `pip install pymsis`.

**Cost:** about 1 day of code and a few hours of fetching. No GPU.

---

## A2. Launch-day correction from whatever you have (flexible inputs)

What exists now: `condition_on_observations` (`tempest_weather/flight/engine.py`) works, but it is rigid. It only takes u/v/T/RH at exact model heights or at 2 m. It has no lag handling, no wind speed or direction input, and no held-out test (IL-33).

**Input:** one call, `launch_day(site, time, readings=[...])`. Each reading is a small record:

| field | examples |
|---|---|
| `kind` | `temperature`, `wind_speed`, `wind_dir`, `wind` (speed + direction together), `gust`, `pressure`, `humidity`/`dewpoint`, `u`/`v`, `cloud_base`, `forecast:<var>` |
| `height` | any height (m AGL), e.g. 2 m mast, 10 m anemometer, 300 m tower, a forecast level; default by kind (2 m for T, 10 m for wind) |
| `time` | when it was taken (the default is launch time). A reading from 08:00 for a 10:00 launch is allowed |
| `average_over` | e.g. 10 min, 1 h (an average is smoother than an instantaneous value) |
| `uncertainty` | optional; otherwise a preset per sensor kind (e.g. a handheld anemometer ±1 m/s, a METAR ±1 kt rounding + siting) |

Missing kinds are simply not used. One temperature reading works, and so do twenty readings.

**How the correction works:**
1. **Best prior.**
   - Within 7.5 days: mode F, the forecast-driven generator, is the prior.
   - Otherwise: the climate generator for that date and hour.
2. **Map each reading to the model.**
   - Interpolate to the nearest model heights in log-height and add a representativeness error.
   - Convert units. Dewpoint becomes RH; °F, kt and mph are accepted.
   - Discount by time lag: the earlier the reading, the larger its error. The decorrelation comes from ERA5 hourly lag correlations, as fitted for `coherence.py`.
   - An average over a window gets less "gust" noise than a spot value.
3. **Linear readings** (T, u, v, pressure, RH): use the existing closed-form copula conditioning. It is fast and exact for the Gaussian part.
4. **Nonlinear readings** (wind speed alone, direction alone, gusts, cloud base): weight the copula-conditioned pool by each reading's likelihood, then resample. The pool is the `observe_by_weights` idea, applied after step 3 so the weights don't collapse.
   - Direction uses a circular (von Mises) error, so 350° and 10° count as close.
   - Report the effective sample size. If it is below 200, widen the uncertainties and say so.
5. **Sanity check on each reading.**
   - A reading outside the prior's 99.9 % range is flagged. It is still used, with wider uncertainty, because a forecast can be wrong too.
   - A reading that is clearly a units or typo error (e.g. T 300 °C) is rejected with a message.
6. **Everything downstream follows.**
   - p, ρ and a are recomputed.
   - Dryden intensities come from the corrected profile.
   - The surface gust and pad-soak models are fed the corrected surface values.
   - The A1 extension is tied to the corrected 18 km values.
   - If a reading lies above 18 km (rare without a balloon), it conditions the extension directly.
7. **Spread inflation.** Fit it per height band on calibration years 2021-23, instead of the fixed 1.5. That keeps the corrected 99 % ranges honest.

**Output:** the same sample sets and files as today, with no vehicle inputs, so it plugs into your simulator unchanged. Plus a short report. It lists the readings used or flagged, their effect (how much each band narrowed), and the ESS.

**Test (IL-33, extended), on 2024-25 only:**
- **(a) Typical readings:** ASOS surface T, wind speed and direction, gust and pressure at the site hour, from the files already downloaded. Score 0-3 km and the surface values that were not given, against unconditioned samples.
- **(b) Lagged readings:** ASOS from 2 h before. This tests the lag handling.
- **(c) Forecast values** at a few heights as readings.
- **(d) A balloon**, when one exists, as the richest case.
- **Accept:**
  - CRPS at 0-3 km improves beyond the seed spread in (a) and (b).
  - cov99 holds within 0.01 everywhere.
  - Never worse than unconditioned when the readings are noise (a placebo run with shuffled dates).

**Cost:** about 1-1.5 days. CPU only.

---

## A3. Wind and shear tails

Builds on loop 3, without repeating it: studt was rejected for shape, and the L3-30 studt clip is in the G9 block.
1. **Export the passed shape stack** (`--post-templates --post-smap`) and re-export the assets that were not re-exported: F-27 `--wcalib`, F-12 `--modep-sfc`, F-11 `--modep-sta`. Then run the regression scores.
2. **int16 tail check:** float vs int16 99.9th-percentile shear on the global store, before G2 trains on it.
3. **u 1-5 km diagnosis:**
   - Build the stress table by season × hour against the Gaussian baseline, on ERA5 and balloons.
   - Check whether the balloon correction under-spreads it.
   - Fix whatever the table points to: a calibration fix first, a retrain only if needed.
4. **Accept:** 99.9th-percentile shear within 5 % in all bands, and u 1-5 km skill vs Gaussian ≥ 0 on 2024-25 balloons.
   - **Gate split (2026-11-07):** float vs int16 parity of the 99.9th shear within **1 %** (quantisation should cost almost nothing; same as the INT8 gate). Model vs ERA5 within 5 % per band. Model vs held-out balloons within 10 % (an extreme quantile has sampling noise, and ERA5 itself under-states balloon shear, so matching ERA5 alone is not enough).
   - Tail ideas to try: IL-103 to IL-108 in `docs/logs/AUTOPILOT.md`.

**Cost:** ~1 day. One GPU scoring pass.

---

## 4. Is A4 (downstream flight test) worth it?

**Not as written. Keep only a vehicle-free version.** (User, 2026-11-06: the system stays vehicle-agnostic, with no interaction with the vehicle. You have your own DOF simulator with a built-in Monte Carlo.)
- **Dropped:** IL-31's in-repo 3-DOF rocket and IL-32's downstream headline rows. A generic vehicle would duplicate your simulator and tie the tool to one vehicle shape.
- **Kept (about an hour, no vehicle):** the M12 passive-tracer drift check. It moves a weightless point up and down at fixed rates (e.g. 5 and 50 m/s up, 5 m/s down) through 2024-25 balloons vs our samples vs simple baselines, and compares the 95th/99th drift.
  - This is a property of the wind column alone.
  - It shows whether coupling and tails matter in a form close to landing scatter.
  - It is also a cheap way to see whether the 18-80 km extension changes drift at all.
- **Contract with your simulator:** our job ends at the interface: `sample_sobol_batch`, files, and the duck-typed readers. Your Monte Carlo drives the draws. A7 (runtime) matters more than A4 here: your MC calls us N times.

## Order
G9 block (running) → **A2** (most useful on launch day, CPU only) → **A1** (fetches run in parallel with A2) → **A3** → tracer-drift check + A7 runtime. A1/A2 fetches respect the ISP data cap; they are small.
