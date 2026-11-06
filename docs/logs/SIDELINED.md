# Sidelined and skipped (everything NOT done in the capped improvement loop)

Written 2026-11-05 at the user's request ("sideline and make a file of everything you skip"). Nothing here is deleted: the rows stay in `AUTOPILOT.md`, code stays, flags stay off. Revisit after the final test, or when the stated trigger arrives.

The capped loop (user, 2026-11-05) keeps the 6 best items: IL-86 generator PIT recalibration, IL-101 station-scale wind widening, IL-77 mode F overfitting, IL-72 recent-years balloon offset shift (with IL-19), IL-80 ridge + network average for mode F, IL-16 stack check. Then group E.


## A. Chosen for the capped loop (6)  (6)

- **IL-101** Station-scale widening of the 10 m wind: the tool's grid-cell wind spread is ~40 % narrower than the spread of forecast-minus-ASOS at the sites; test 
- **IL-16** Stack check: all kept S-items together vs p2f
- **IL-72** Recent-years balloon offset: median shift per variable x band fitted on balloons 2022-23 only (after the sensor change) and applied on balloon scoring
- **IL-80** Ridge and network disagree at 7 days (ridge better coverage, same skill): average the two predictive distributions (mixture) and test; also use the en
- **IL-86** Same full PIT recalibration for the climate generator (IL-46 proper): PIT distance mean 0.033 (worst T 5-12 km 0.059); `score --pit-recal` and `diagno
- **IL-77** Mode F overfits within 250 steps (validation CRPS 0.53 at step 250, 0.64 at 2750; train 0.27): regularise. Variants: width 128 / depth 2, weight decay

## B. Needs the flight simulator (stage 6 or later)  (11)

- **IL-31** The only honest proof that coupling and tails matter for the thing the user does; replaces the missing landing-scatter test C6
- **IL-32** Optimises what is used, not only per-column CRPS
- **IL-33** The most useful day-of-launch capability: Monte Carlo around what is known, with honest spread
- **IL-34** Rare dangerous cases are exactly what a Monte Carlo is run for
- **IL-35** A launch slips by hours; the same atmosphere must evolve realistically, not be redrawn
- **IL-36** A rocket flies 10-30 km downrange; today every point is a separate draw or one shared profile
- **IL-37** Decision-relevant quantities, not just raw columns
- **IL-38** The tails and joint behaviour are what the Monte Carlo depends on
- **IL-39** Removes friction: any simulator can read it without custom code
- **IL-40** Prevents misreading Monte Carlo noise as real differences
- **IL-41** The user always sees what to rely on

## C. Blocked on data or on you  (5)

- **F-17** KNOWN (IL-64, depends on the user's Colab run; CDS download at about 60 of 420 months)
- **IL-6** Calibrate modes F/F2 on WeatherBench2 HRES
- **IL-30** Mode P with the 21 levels (4.6) and the ARCO fill: retrain residual network and compare MAE vs balloons 2.571
- **IL-64** the strongest shear is near the ground
- **IL-75** More HRES starts/leads: only 92 starts a year at leads 1/3/5/7; a second Colab pull with 00 and 12 UTC, every 2nd day, leads 12 h ... 10 days would tr

## D. Already done or superseded (row not updated)  (8)

- **IL-59** real shear is what a rocket sees
- **IL-60** the gap may sit in a few layers or in winter only; then a targeted fix beats a global one
- **IL-68** Vertical correlation error is 0.056-0.099 (goal 0.05; worst T 0.099, u 0.094): profiles have slightly wrong vertical coherence
- **IL-76** **Validation and calibration windows overlap** (found by pitfall check 1c): the generators are early-stopped on 2021-23 and every range map / table is
- **IL-73** **DONE first version 12:35 (CRPS skill vs climatology 0.69 / 0.54 / 0.34 / 0.18 at 1/3/5/7 days, test 2022; table in PLAN)** Mode F (forecast-conditio
- **IL-84** Noise floor for every shape number on a small test set: the same metric for a perfectly calibrated forecast (a member as pseudo-truth) is printed next
- **IL-83** The same vertical-coherence weakness probably exists in the climate generator at a smaller scale (vertical correlation error 0.056-0.099, goal 0.05; I
- **R-2** todo

## E. Group R (other places / hours / far future)  (5)

- **R-3** todo (with F-20)
- **R-4** todo
- **R-7** todo (after R-5)
- **R-8** todo (GPU, after BLOCK 0)
- **R-9** todo

## F. Skipped on purpose: generator shape, loss and noise ideas  (24)

- **IL-46** repairs the interior shape directly (S1, S2); the present map mainly fixes the 99 % ends
- **IL-47** the loss decides the shape; CRPS with 4 samples is a weak signal for skew and kurtosis
- **IL-48** cleaner gradient for the distribution shape; costs about 2x time
- **IL-49** targets marginal shape without needing a pointwise truth
- **IL-50** the network's output shape inherits the noise shape; skewed variables (RH, wind speed, shear) may need it
- **IL-51** conditional shape
- **IL-52** the clipped RH ends are a shape feature the Gaussian-noise network handles crudely
- **IL-53** keeps marginals and puts the real joint shape back
- **IL-100** Dynamic balloon leftover in the training loop (the unfinished half of F-24): store a + b ERA5 as the target and draw the leftover profile per step fro
- **IL-9** Mask tokens with random input dropout + arcsinh scaling for shear/gust targets
- **IL-24** Worst measured cells (stress table): DJF evening t2m skill15 -0.046, T 0-1 km -0.038, JJA evening T 5-12 km cov99 0.955: cell-specific blend toward th
- **IL-25** Shear patch rate p and size per band were fixed (p = 0.05, 0.01): fit p jointly with sigma on the calibration years (grid over p) instead of picking
- **IL-43** todo
- **IL-44** todo (after IL-43)
- **IL-45** todo (after IL-44)
- **IL-61** the network can only make tails as heavy as its noise allows; shear tails are heavy
- **IL-62** the present tail term uses the magnitude only
- **IL-63** users compare against raw soundings
- **IL-65** losses fix the model, the map fixes what is left
- **IL-69** Worst PIT cells T 5-12 km (0.059), T 1-5 km (0.052): full PIT recalibration (IL-46) first
- **IL-70** Monthly median bias normalised by climate sd reaches 0.46 at T 12-18 km (mean over cells 0.27): month x band shift (IL-20) fitted on 2011-2023
- **IL-71** Event-conditional coverage gap 0.18 at RH 5-12 km: extreme RH outcomes are missed more often than a perfect forecast would miss them; bounded-variable
- **IL-81** Shape metrics for mode F (PIT distance, vertical correlation, tails) with `metrics_ext` on the 2022 test rows, per lead; compare with the climate gene
- **IL-87** Date-block bootstrap for the shape numbers of mode F (resample whole forecast dates, as the day-block intervals do elsewhere) so the PIT distance carr

## G. Skipped on purpose: mode F ideas  (3)

- **IL-78** Mode F on live forecasts: the network learned from archived HRES (IFS deterministic). The logger stores IFS ENS and WeatherNext, Open-Meteo serves IFS
- **IL-79** Mode F at any lead (it was trained on 1/3/5/7 days): add lead as continuous input and check 2 / 4 / 6 day interpolation (needs the IL-75 notebook reru
- **IL-74** Lead blending: between 0 and about 7 days use mode F, beyond about 10-15 days the climate generator, with a smooth weight by lead fitted on the skill 

## H. Skipped on purpose: shift, index-forecast, tokens, probes and the rest  (12)

- **IL-14** Chronos + ridge average for ONI/WWV
- **IL-15** Mode P tendency inputs for wind columns only
- **IL-17** Analog-driver K tuning (A6), block validation (row 20)
- **IL-18** 2C shear codebook / 2B spectral generator probes
- **IL-19** IL-13's shift is a 2021-23 average, so it cannot follow a warming trend. Fit the shift per year over a longer window (2015-23, using only years not us
- **IL-20** Shift per calendar month (smoothed 3 months) and per hour bin: the cold bias is probably seasonal/diurnal like the T 5-12 km summer miss
- **IL-21** IL-2/IL-11 and IL-13 share one idea (a table over month x band): fit them jointly (shift then width) so the width is measured around the shifted media
- **IL-22** Stack IL-10 (trust), IL-11, IL-12, IL-13 in the best order and re-fit each on the output of the previous one (they were fitted separately)
- **IL-23** Pool the members of the token model (IL-8) with the MLP members (p2f) into one ensemble: different architectures make different errors
- **IL-26** QBO forecast: ridge beat Chronos and analog, but a phase-aware model (QBO is nearly periodic, ~28 months) should do better still: regression on sin/co
- **IL-27** WWV is in raw m3 (1e13): standardising/log before ridge and analog may change which method wins (the covariance fix in the numpy tool already needed i
- **IL-29** After IL-8/IL-9: if tokens help the shear tail, try depth/width of the token model (d = 192, 6 layers) and a second pass with the shear-tail loss weig

## I. Skipped from the other session's plan (Strong improvment.md)  (0)


## I. From the other session's plan (`Strong improvment.md`, tracked as IL-98 / IL-101 etc.)

- **G** `observe()`: importance-weight samples on an observation (builds on IL-33, flight-simulator side too)
- **H** sample-derived lapse rate in `to_site` (small, testable on balloons)
- **I** spread-conditioned width (needs the ensemble path, C)
- **K** Haar/DCT vertical CRPS term (GPU test only)
- **M** evaluation hygiene (partly done with the shape verdict and the seed spread)
- **C (full)** live-ensemble EMOS: needs the daily logger to reach 60-90 days (started 2026-11-05)
- **A, D, E, F** (HRES refetch consequences, richer mode F inputs, per-lead ridge cascade, multi-model first guess): need the Colab pulls
- **J, L** ConvToken generator, lagged-run ensemble: later

## Also not done (from earlier lists)

- A4 GFS-on-AWS download (about 160 GB): not planned; the Colab HRES pull replaces it.
- Real Earth-GRAM: needs NASA; the Gaussian proxy is scored instead.
- North America build (R-6), second HRES diurnal pull (ASK_LATER 8), ARCO/CDS 21-level retrain (blocked on data).
- Stage 6 flight-simulator tools: only after the final model and your approval (tools only, no model changes).

## User decisions 2026-11-06 ("what would make it innovative")

- **Tempest stays a standalone weather tool, fully separate from the rocket.** Nothing vehicle-specific gets trained into the model.
- **Stage 6 gets IL-33 + G (`observe()`)**: condition samples on day-of observations (partial sounding, surface obs, forecast values) by weighting and resampling a large pool. It works at sampling time, with no retrain, so it fits the "no model changes" rule.
- **IL-35 + IL-36 scheduled before stage 6** (AUTOPILOT group C, after group E): time and downrange coherence via a fitted copula, regime check, learned version only as a fallback. Not a balloon-drift correction (F-10 tested that).
- **Future climate (year/warming-conditioned climatology)**: to be tested for accuracy. Note: PLAN.md already keeps a learned year trend and dropped CMIP6 (scenarios don't diverge within 3 years, LOCA2 has no upper-air winds).
- **Discarded**: vehicle-sensitivity training loss (IL-32), tail-directed importance sampling (IL-34), above-18 km extension, launch-window query layer (IL-37).
- Pushing to GitHub after the push at 86baaf0: waits for your approval or the end.

## Loop 2 sidelined
- H5 shear map per season: shear distance already inside noise.
- IL-74 lead blending: forecast mode still skilful at 7 d; no data beyond.
- IL-79 continuous lead: needs notebook rerun with more leads (data).
- IL-14 Chronos+regression: tied in earlier bake-off, no effect on profile shape.


## Loop 3 cut (2026-11-06)

User: "reduce it so only a couple things overall are tried (only the very important things or what would take almost no time) + what gemini gave (the ideas)". Kept: Denver fill-top rescore, w768 (already trained), terrain (L3-5), Gemini fixes ctxsep/sirenw15, Gemini ideas studt/jump (`scripts/ap_l3_lean.sh`). Sidelined (rows stay in `LOOP3.md`, configs stay):
- L3-6 clocks, L3-7 clim inputs, L3-10 ctxall (ctxsep covers it), L3-11 terrain head, sh10ctx retry
- L3-8/9 SAMOS target space, L3-13 variogram loss, L3-14 coordinate-only baseline
- L3-15..19 calibration transfer, spread-conditional calibrator, pooled balloon correction, pooled EGPD tail, DI test
- L3-20/21 stacks (run by hand only if a kept row wins), L3-22 ONNX
- D1-D7 data-need runs (`scripts/ap_l3_data.sh`)
- Gemini idea 2 (Pairformer trunk): removed (user, 2026-11-06)
- Gemini idea 3 (jump head, L3-27): waits for the IGRA balloon targets (`configs/generator_l3_jump_igra.toml`)
