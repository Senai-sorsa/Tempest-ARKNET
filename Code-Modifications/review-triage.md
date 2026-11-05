# Triage of the outside architecture review (2026-11-04)

The review proposed 10 alternative architectures and 10 add-ons for the generator. This file sorts them against the
repo at commit `ba2e2df`, the PLAN.md experiment log, and the earlier specs (`claude-recommendations-v2.md`,
`atmosphere-outputs.md`, `coupled-atmosphere.md`). Every adopted item still goes through the usual gate: one change at
a time, train <= 2020, fit 2021-23, test 2024-25, keep only if it wins beyond the bootstrap intervals.

## Corrections to the review before using it

- **Its projected gains are guesses.** No source or test supports "whole-profile coverage 0.85 → 0.98+", "RH skill
  → > 0", "EMA +0.5-1.5 % CRPS", or the per-item latencies and effort days. Treat each one as a hypothesis.
- **`site_elev - grid_elev` is zero in every training row** (design review item 13). It cannot be "the single best
  predictor" of anything until the training data contain real site elevations (phase 8 / station-corrected targets).
- **Static place features cannot beat climatology on their own.** Skill is measured against recent climatology *for
  the same place*, which already knows the place. Extra terrain inputs can help the model learn each place's climate
  more accurately, but they add no information about *which* weather will happen, and that is what the input-limited
  plateau is about. New time-varying drivers (lagged soil moisture, recent anomalies, forecasts) are what move it.
- **The bottom-up running sum is not unchecked.** The loss already scores the *rebuilt* profiles (afCRPS on all 44
  heights + energy score), so drift with height is penalised directly. The "random-walk drift" concern is weaker than
  stated, though a test is still cheap.
- **"Guarantees CRPS skill >= 0"** for the trust layer holds only on the years the blend weights are fitted on. On new
  years it should be near that, not guaranteed.
- **The low-rank Gaussian covariance head** was already reviewed and discarded in PLAN.md (*Blueprint review*).

## Part 1: very beneficial or low cost (adopt now, each through the gate)

| # | Item (review ref) | Why adopt | Notes for Claude Code | Test |
|---|---|---|---|---|
| 1.1 | **RH as transformed dewpoint depression** (add-on 1) | RH is the only variable worse than climatology; clipping at 0/100 piles samples at the bounds and kills gradients; RH is very skewed and often near-bimodal | Predict `ln(T - Td + 1 K)` as the 4th profile variable; rebuild with softplus so depression >= 0; derive RH inside the forward pass using the **same saturation formula as `to_heights.liquid_rh`** (over liquid water), not a different approximation; score both the transformed value and RH. One retrain. | RH skill per band (balloons and ERA5), rank histograms, July / monsoon months separately; no other variable worse |
| 1.2 | **Trust layer as a rank-preserving quantile blend** (add-on 10) | Removes every negative-skill column; this formulation **keeps each sample's rank at every height**, so coupling survives. It replaces the sample-mixture version in `claude-recommendations-v2.md` A2, which would mix heights from different sources | Per variable × height band (and later lead band): `x = w·x_model + (1 - w)·Q_clim15(rank(x_model))`, `w` in [0, 1] fitted on 2021-23 by CRPS. Apply after range calibration | per column no worse than its best part on 2024-25; whole-profile coverage and variogram score not worse |
| 1.3 | **Global mean temperature instead of calendar year** (add-on 3) | Same as recommendation A4; fixes the cold bias where warming accelerated | 5-year smoothed GMST anomaly on the existing straight-line path; at query time drawn from a published annual forecast with its uncertainty; then retry 1980-90 (log item 22) | T bias and skill 2024-25; coverage holds |
| 1.4 | **El Niño / La Niña hinges** (part of add-on 5) | Lets El Niño and La Niña act differently, which is well documented, at almost no overfitting risk | Replace ONI with `max(0, ONI)` and `min(0, ONI)` on the straight-line path, lagged as in PLAN *A6* | skill at 1-12 month leads with unknown drivers |
| 1.5 | **Multi-lag step CRPS** (add-on 2a) | Today the step loss only sees neighbouring heights; mid-scale waves (3-10 km) are unconstrained, which fits the low whole-profile coverage | Step CRPS at strides 1, 2, 4, 8, 16 heights; start with equal weights summing to the current 0.5; training-only change | whole-profile coverage, variogram score at several lags, per-height CRPS not worse |
| 1.6 | **Simultaneous 99 % band as an extra output** (add-on 2b) | Gives a true "all heights at once" envelope for safety margins without changing the samples | One multiplier per variable fitted on 2021-23 so the max standardised exceedance over the 44 heights stays inside 99 % of the time. Output as `band99_joint_lo/hi`; **do not** use it to stretch the samples (per-height coverage would overshoot and CRPS would worsen; PLAN's blueprint review rejected it as a replacement) | joint coverage of the band on 2024-25 ≈ 0.99 with intervals |
| 1.7 | **EMA of weights** (add-on 9b) | Standard, cheap, often slightly better and steadier scores | Exponential moving average (decay ~0.999) of each member's weights over the last part of training; evaluate and export the EMA weights | CRPS and coverage vs the same run without EMA |
| 1.8 | **Super-adiabatic hinge above 2 km** (add-on 8, part) | Layers cooling faster than 9.8 K/km do not persist in the free troposphere; a penalty only above 2 km avoids fighting the ERA5 boundary-layer artifact (design review item 11) | Small fixed-weight squared hinge on rebuilt T steps above 2 km. Pressure and density come from the derivation already specified in `atmosphere-outputs.md` (the review's hypsometric step is the same thing) | share of super-adiabatic layers above 2 km falls; scores not worse |
| 1.9 | **Smooth line fits across heights in the balloon correction** (add-on 6b) | `a(z)` and `b(z)` are fitted height by height, so they can jump between neighbours and create fake steps | Ridge penalty on differences of `a` and `b` between adjacent heights (strength chosen on 2021-22, checked on 2023-25) | held-out level and step gaps vs balloons (the item 19 table) |
| 1.10 | **Gumbel gust output** (add-on 10b) | Already recommendation A3 | Keep it as the separate gust module, not a head inside the generator, so the working model is untouched | as in A3 |

## Part 2: future add-ons and extensions (worth testing later, gated)

| # | Item (review ref) | When | Why wait | Test that decides |
|---|---|---|---|---|
| 2.1 | **Vertical backbone: attention across heights or 1D convolutions** (alternatives 1, 2) | after 1.1-1.5 and the new drivers | The audit says the model is input-limited, so a new backbone mainly helps joint shape. Attention over 45 tokens is the same idea as the height transformer in the seamless core | whole-profile coverage and variogram score improve beyond intervals; per-height skill not worse; numpy forward pass still fast |
| 2.2 | **Seamless context encoder** (alternative 10) | with the seamless core (recommendation B2) | Needs the reforecast training data first. It is the same design as B2, written as a neural-process encoder with an availability mask, which is a good way to build B2 | walk-forward vs modes 2-4 on the same days, per lead band |
| 2.3 | **Split noise by scale** (alternative 5, first two parts only) | after 2.1 | Plausible: large-scale noise early, smaller-scale later. Leave out the fixed AR(1) "turbulence" noise at the end: the balloon-correction leftovers already put real fine structure into the targets, and a fixed parametric shear could look unrealistic | 99th and 99.9th percentile shear vs balloons; whole-profile coverage |
| 2.4 | **Anchored reconstruction** (add-on 7) | any time, as an A/B test | The loss already scores rebuilt profiles, so gains may be small; fixed anchors at 2 km and 12 km also assume a fixed boundary-layer top and jet height, which vary | jet-level (9-14 km) and 2 km scores, whole-profile coverage |
| 2.5 | **Synoptic nearest-neighbour leftovers in the balloon correction** (add-on 6a) | CONUS scale, with many more soundings | The same idea lost at pilot scale (log items 7 and 11): splitting the leftover pool by moisture thinned it and added noise. k = 30 neighbours from ~2,700 soundings per group may thin it again | balloon step and level gaps; no variable worse |
| 2.6 | **Terrain descriptors at grid scale** (add-on 4) | phase 8 (CONUS) with option 3C | Only 336 grid points in the pilot box and site = grid elevation in training. At CONUS scale with station-corrected targets, terrain slope and roughness can help the correction carry to unsampled sites | spatial-block cross-validation on held-out stations |
| 2.7 | **Fourier features of coordinates** (add-on 9a) | phase 8 | Helps networks learn sharp spatial changes, but over a small box it mostly invites memorising grid points | same as 2.6 |
| 2.8 | **Continuous-height model / training on raw balloon levels** (alternative 8) | phase 8 data foundation (recommendation B3) | Large rebuild; most useful when many stations are used directly | balloon scores on held-out stations |
| 2.9 | **Flow matching, 2-4 step sampling** (alternative 7) | last resort (recommendation B6) | Its argument for two-peaked variables (dry vs cloud-saturated RH) is reasonable; try it only if 1.1 does not fix RH and tails still fall short | the generator falsification test in PLAN.md |
| 2.10 | **Schaake shuffle with balloon rank patterns** (add-on 2 alternative) | as a diagnostic only | It replaces the model's own height-to-height coupling with historical patterns, which throws away coupling that depends on the day. Useful as a baseline: if it beats the model on joint scores, the model's coupling needs work | energy and variogram score, model vs shuffled |

## Part 3: risky or not worth it

| Item (review ref) | Why not |
|---|---|
| **Low-rank Gaussian copula + spline marginals as the generator** (alternative 6) | Already discarded in PLAN.md's blueprint review. Spline marginals fix skew, but the joint dependence stays Gaussian with a fixed rank: no tail dependence, which is exactly where extreme shear lives. It would replace a working model with an untested one for speed the tool does not need (one query per campaign) |
| **Latent autoencoder + generator** (alternative 4) | "Samples cannot escape the envelope" also means samples cannot reach the extremes: a compressed decoder smooths away rare fine-scale shear. PLAN's option 2B falsification (12 modes losing > 5 % of the 99.9th percentile step) and FUTURE_OPTIONS already flag this. Consider only for storage at CONUS scale, not for generation |
| **Bidirectional state-space / Mamba column scanner** (alternative 3) | Built for very long sequences; a column has 44 heights. Attention or convolution (2.1) covers the same coupling with less machinery |
| **Mixture of regime experts** (alternative 9) | Hand-named regimes and six heads trained on ~30 years at two stations is thin data; the experiment log already shows that splitting by regime (season, spread, moisture) loses because each part gets too few cases (items 8, 11) |
| **PNA, PDO, AMO and ONI × QBO interaction inputs** (rest of add-on 5) | PNA is a weather pattern that cannot be known months ahead, so at query time it would always be "missing" (ground rule 4). PDO was dropped in PLAN.md because it mostly carries ENSO. AMO is decadal and weak over the Southwest. Interaction terms on ~30 years invite fitting noise. Revisit only after the hinges (1.4) and lagged drivers are in |
| **The review's numeric promises and latency table** | Unsourced. Use the gate's results instead |

## Order

1.1, 1.2 → 1.3, 1.4 → 1.5, 1.7, 1.8 (one retrain can carry several training-only changes only if each is also
tested alone first) → 1.6, 1.9 → 1.10 (with A3). Part 2 items wait for their stated stage. Part 3 items stay out
unless a later test result changes the reason given.
