# Claude recommendations v2 (2026-11-04)

Replaces `claude-recommendations.md`. Based on the repo at commit `ba2e2df` ("Honest evaluation, faster
training, experiment log") and a review session the same day. **Every item must be tested, not assumed.** Each goes
through the gate in [docs/PLAN.md](docs/PLAN.md): it ships only if it beats what it replaces on held-out years, and
every result, including failures, goes in the PLAN.md improvement log.

Two phases. **Phase A** is lower risk: cheap, reversible, mostly outside the trained network. **Phase B** is higher
risk: new training setups, new data plumbing, weeks of work.

## Where things stand (what this plan builds on)

- The generator (3A, Engression, 4 members, ~2.8 M parameters) is trained and scored. The 99 % range holds ~98-99.7 %
  per height after range calibration, on ERA5 and on balloons.
- Honest skill is small: ~1-4 % better than recent climatology for T and upper wind. RH aloft, surface pressure and
  rh2m are **worse** than climatology. Whole-profile 99 % coverage is 0.83-0.87 (climatology 0.79-0.83).
- Cold T bias: the learned year slope under-extrapolates warming. Adding 1980-1990 made it worse (log item 22).
- Audit (log item 18): no overfitting; validation is flat after ~1,500 steps. **The model is input-limited.** Bigger
  gains need new information, not a bigger network.
- The user-facing tool (`values()`, `distribution(kind="predicted" | "uncertainty")`, four modes) is planned in
  `docs/TOOL_PLAN.md`, not built.

## Ground rules (every item)

1. **Keep Engression (3A) as the engine.** Architecture changes are last (B6).
2. **Honest protocol** (log item 18): train <= 2020, validate and fit calibrations on 2021-23, development test
   2024-25, final untouched test 2026 Jan-Jun. Report June on its own; say plainly that 2026 H1 has no monsoon.
3. **One change at a time**, same seeds and splits before and after, with the day-block bootstrap 95 % intervals
   (`diag.headline`). A gain inside the interval is not a gain.
4. **Query-time inputs must exist at query time.** Any driver is trained the lagged way it will be used
   (PLAN.md, *A6 and other drivers*).
5. **Laptop for the pilot, Grace for scale.** ~6,000 units on TAMU HPRC Grace: use them for the reforecast
   processing, CONUS data and multi-fold backtests, not the pilot.

## Phase A: lower risk

### A1. Check the shape of the distribution, not just its edges

The scorers test 90 % and 99 % coverage and the extreme tails. Nothing checks the middle, so "shaped like the real
distribution" is unproven.

- Rank (PIT) histogram per variable x height band, on ERA5 and balloons. Flat = right shape; U = too narrow;
  hump = too wide; slope = biased.
- Coverage at 50, 80, 90 and 99 %, not only 90 and 99.
- **`predicted` kind**: give it its own test, or state in TOOL_PLAN and the tool README that it is uncalibrated and
  narrower than reality (raw cov90 was 0.83-0.88), for "typical spread" only, never for safety margins.
- **`values()`**: document that a per-height median is not one real profile; score wind speed and direction
  (PLAN E6), since u and v medians understate speed.
- Finish E10 (score each height on the soundings that have it) and the worst-month / worst-column print (E7).

### A2. Trust layer: never worse than climatology

- **Stacking.** Blend generator, analogs (when built) and recent climatology with weights per lead band x variable x
  height band, fitted on 2021-23 by CRPS, weights non-negative and summing to 1 (mixture of sample sets). Columns
  where the generator loses (RH aloft, sp, rh2m) automatically lean on climatology. Test: no column worse than its
  best part on 2024-25; whole-profile coverage does not drop.
- **Stress test.** Search for the input combinations where coverage fails (season x ENSO phase x hour x height
  band), instead of averaging them away. Report the worst 10 cells with intervals.
- **Online recalibration** (later, with the tool): update the range map from the daily forecast logger using only
  verifications whose target time has passed.

### A3. Gust output, near the ground (new, priority)

**Goal:** an additional output: for each sample profile, the distribution of the **largest gust** in a chosen
window, as a **Gumbel distribution** (location mu, scale beta) per height near the ground. Gumbel is the standard
model for the maximum of many turbulent fluctuations (Davenport's peak-factor theory). Also test a GEV (Gumbel plus a
shape term xi) and keep Gumbel unless xi is clearly non-zero on held-out data.

Definitions (settings, defaults to agree with the team):
- gust = peak 3-second wind (WMO / ASOS convention);
- window = the launch window at the pad (default 10 min) and, separately, the first ~10 s of flight;
- heights: 10 m first, then the lowest profile heights (50-500 m) as data allows.

Build it as a **separate gust module** that runs on each generated profile, so the working generator is untouched:
- inputs: that sample's 10 m and low-level mean wind, boundary-layer height (`blh`, already in the store), surface
  heating / stability proxy (t2m minus low-level T), solar hour, season, terrain;
- outputs: mu, beta (and xi if kept) of the max gust; samples of the gust drawn from it;
- fitted by CRPS or maximum likelihood on observed gusts.

Data:
- **Truth:** ASOS gust and 1-minute wind observations at the airports nearest the pilot sites (NCEI), 2000 onward;
  respect the honest split by year.
- **ERA5 `i10fg`** (10 m gust, hourly maximum): use as an input feature, not truth; model gusts are known to be biased.
- **0-15 days:** Open-Meteo forecast gusts (`wind_gusts_10m`) where the chosen models provide them, calibrated
  against ASOS like the other near-term variables.

Outputs added to the tool: `gust_mu`, `gust_beta` per near-ground height, gust samples (n,), P(gust > threshold)
for a user threshold, and gust quantiles; a `[gust]` table in the `dynamics` TOML.

Tests (2024-25 held out): rank histogram of observed max gusts against the predicted Gumbel is flat; 50/90/99 %
coverage within intervals; better CRPS than (a) a constant gust factor x mean wind and (b) ERA5 `i10fg` with a
linear correction; Gumbel vs GEV decided by held-out score.

### A4. Physical warming input instead of calendar year

Fix the cold T bias with pattern scaling: replace `year` with the observed global mean surface temperature anomaly
(annual, lagged as at query time), kept on the straight-line path. For future dates, draw it from a published
annual global temperature forecast (e.g. the UK Met Office annual forecast) with its stated uncertainty.
Then retry the 1980-1990 training years (log item 22 failed through the year slope, which this removes).
Test: T bias and T skill on 2024-25; coverage holds.

### A5. Index forecast bake-off (ONI, QBO)

Lagged regression vs **Chronos-2** zero-shot (WWV as covariate) vs official ENSO forecasts (CPC/IRI plume, NMME) up
to ~9 months. Keep the best per lead. Leakage warning: Chronos-2's pretraining may contain ONI's history, so treat a
small Chronos win as no win. Expect small effects.

### A6. Hydrostatic check, then penalty

Check hydrostatic consistency of samples in the scorecard now; add a small fixed-weight penalty once
pressure-at-height is a target (design review item 12). Keep only if no proper score worsens.

### A7. More real data and drivers

- More IGRA stations near the pilot box, for the station correction and the balloon scorecard.
- The lagged drivers already planned in PLAN.md (*A6 and other drivers*): recent local departures and soil moisture
  first, then regional SST. No change to that plan.

### A8. Launch-commit conditioning (sampling time only)

Configurable go/no-go rules (surface wind limit from the team's or competition's rules; do not invent one) and a
launch window. For each sample path take the first hour that passes; report P(scrub). Output conditioned and
unconditioned sets. Once A3 exists, the rule can use the gust as well as the mean wind. Test: conditioned samples
match historical days that pass the same rule; P(scrub) calibrated.

## Phase B: higher risk

### B1. Gusts and fine structure aloft (follows A3)

For the rocket, small-scale changes of wind with height are gusts: at flight speed it crosses a 100 m layer in a
fraction of a second. ERA5 and the 44-level grid smooth these out.

- **Data:** NWS high-resolution (1-second) radiosonde data at Santa Teresa and Midland, which resolve wind every few
  metres in height.
- **Model:** a stochastic fine-structure layer added to each sample: perturbations along height with a fitted
  vertical spectrum (von Karman / Dryden-type shape, as used in flight-sim turbulence models), amplitude conditioned
  on the sample's shear, stability and height band. Plus a Gumbel for the largest sub-grid gust per height band.
- **Test:** on held-out high-res soundings, the perturbation spectra and the 99th-percentile small-scale shear match;
  the Gumbel rank histograms are flat; the 44-level scores are unchanged (the layer must not hurt them).

### B2. Seamless forecast-aware core (the biggest accuracy gain)

One model that knows its lead time, replacing hand-set mode boundaries and blend weights:
- **Lead time as an input**; trained on past forecasts (GEFS reforecast from TOOL_PLAN, WeatherNext 2 archive 2022+,
  ECMWF reforecasts) so it learns how fast each source loses skill, sliding to climate + trend at long leads.
- **Forecast inputs:** ensemble statistics for days 0-15, **bias-corrected weeks 3-6 forecasts** (probabilistic bias
  correction, arXiv 2604.16238, which roughly doubled AIFS's weeks 2-6 skill and won ECMWF's 2025 competition), and
  seasonal monthly means.
- **Recent observations in context:** the last 7-30 days of real profiles at the site.
- **Teacher-student:** large ensembles as teachers for what lead L could know; short leads trained first (curriculum).
- Expect most of the gain at 2-8 weeks. At 1-3 years, climatology + a good trend (A4) is near the ceiling.
- Test: walk-forward, against today's modes 2-4 on the same days, per lead band; coverage holds.

### B3. CONUS scale-up on Grace, with a better data foundation

Phase 8 of PLAN.md, plus: train all CONUS IGRA stations jointly (data-rich sites help data-poor ones); represent
the profile as a function of height so raw balloon levels train it directly with no interpolation (also removes
the lapse-rate artifact, design review item 11); masked pretraining (hide heights and variables, predict them) on
ERA5 and balloons before fine-tuning. Option 3C as planned. Streaming data loading (design review item 9).

### B4. Real-column memory (only if whole-profile coverage stays short)

Retrieve the K most similar real historical profiles as extra input, with similarity learned from outcomes
(contrastive) rather than by date; optionally sample a weather regime first (monsoon, jet, dryline), then the
profile. Leakage rule: analogs only from years outside the held-out block.

### B5. ACE2 synthetic pretraining (deprioritised)

The audit found no overfitting, so this is unlikely to help now. ACE2 is also coarse (1 deg, 8 layers): it cannot
teach shear or the boundary layer. Revisit only if a later model overfits.

### B6. Different generator head (last resort)

Flow-matching head and hydrostatic-by-construction outputs, only if tails or whole-profile coverage still fail after
everything above. Same falsification test as the generator.

## Deferred (later, not now)

- **Decision layer:** trajectory-weighted loss, landing-point fine-tuning, importance sampling of dangerous tails.
  Needs a layered wind model in `flight_sim` first.
- **Launch-day update** from same-day measurements.
- Dropped: wind recovery from flight telemetry.

## Novelty note

The architecture pieces are all published (Engression, AIFS-CRPS/FGN conditioning, CRPS + energy loss, quantile
calibration, ERA5-to-balloon correction; launch-site Monte Carlo wind models go back to NASA in the 1990s). What is
less common is the combination: a CRPS-trained generator of whole, balloon-corrected above-ground profiles for launch
Monte Carlo, with gust distributions and honest evaluation. B2 (one lead-aware generator across 0 days to years) is
the part most likely to be genuinely new.

## Order

A1, A2 -> **A3 (gusts)** -> A4 -> A5, A6, A7 -> A8 -> B1 -> B2 -> B3 -> B4, B5, B6 only if needed.
