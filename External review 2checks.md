# External review 2checks

## Scope and review standard

This is an independent review of the current Tempest-ARKNET implementation,
including the expanded generator, feature modes, calibration, scoring, routing,
past/near-term forecast modules, profile conversion, and output-related paths.

Items are classified as:

- **Confirmed defect:** directly observable from current code and likely to produce
  incorrect results, crashes, or misleading evaluation.
- **High-risk flaw:** may be valid by design, but can make results look better than
  they are unless explicitly tested.
- **Structural safeguard:** not necessarily a current bug, but needed to prevent
  future silent regressions.

No finite review can guarantee zero defects. Every scientific result should still
be reproduced from a clean environment and an untouched verification set.

---

## 1. Confirmed or near-certain implementation defects

### 1.1 GPU training silently changes the training data precision

`train.py` stores normalized training features and targets in `float16` when the
device is CUDA:

```text
dt = torch.float16 if gpu else torch.float32
Xc = ...
Xt = ...
```

Each batch is later converted back to float32 before the forward pass. This does
not restore the lost precision: normalized inputs and targets were already rounded
to float16. Validation remains float32, so the optimizer trains on one numerical
distribution and is selected on another.

**Impact:** small target differences, pressure departures, humidity coordinates, and
standardized tail values can be distorted. This is especially dangerous for
difference-space shear channels and rare-event losses.

**Required check:** compare GPU float16-storage training against float32-storage
training on identical rows, seeds, checkpoints, CRPS, variogram score, coverage,
and tail metrics. If the goal is speed rather than memory, use float32 storage
first or document and gate the precision change.

### 1.2 The advertised “lossless” training speedups are not necessarily lossless

The active training path already uses bfloat16 autocast on GPU:

```text
with torch.autocast("cuda" if gpu else "cpu", torch.bfloat16, enabled=gpu):
    s = model(c, cfg["m"])
```

It also stores inputs in float16. Therefore, any claim that training changes preserve
the exact original float32 objective is false unless the baseline is explicitly
defined as this mixed-precision path.

**Required check:** retain a float32 reference mode and compare the complete training
trajectory, not only one loss evaluation. A matching first batch does not prove
matching optimizer updates or final calibration.

### 1.3 Checkpoint creation can save an unusable model after NaN validation

`best_state` begins as `None` and is only assigned when `v < M["best"]`. If the
validation loss is NaN or infinite for every evaluation, the code still constructs
a checkpoint with `state=None`. `Sampler` then attempts to load the state and fails
later, far from the actual training error.

**Required fix/check:** reject nonfinite losses immediately, require every member
to have a finite `best_state`, and validate all tensors and normalization arrays
before saving.

### 1.4 The validation split can become invalid with block validation

`split()` indexes:

```text
val = vb[day // 14]
```

The size of `vb` is estimated from `day.max()`, but there is no explicit assertion
that all computed block IDs are nonnegative and within bounds. More importantly,
the block split operates on a synthetic integer day (`year * 366 + doy`) rather
than a true calendar date. Leap-year gaps and the missing day 366 can distort
14-day block boundaries and the intended three-day embargo.

**Required check:** generate block IDs from actual normalized timestamps, assert
the embargo in calendar days, and test January, February 29, December, and
cross-year blocks.

### 1.5 `val_block_frac` can produce unstable validation populations

Validation blocks are selected with a fixed RNG seed independent of the model seed,
but no minimum validation count, minimum training count, or per-year coverage is
enforced. A random draw can leave some years absent from validation or training,
especially on small pilot datasets.

**Impact:** model selection can depend on an accidental block draw, and comparisons
between configurations may use different effective climate populations.

**Required check:** persist validation block IDs, report counts by year/station/month,
and reject splits that fail minimum support requirements.

### 1.6 The active feature configuration is mutable global process state

`features.FEATURES` and `sample.RH_TARGET` are changed by `load_npz()` and
`Sampler._activate()`. This means importing or loading one dataset/model changes
the behavior of all subsequently imported functions in the same Python process.

**Failure example:** load a `p2`/`dpd` model, then load a base/RH model. Any code
that constructs features or physical profiles between those operations can use the
wrong feature order or humidity inverse.

**Required fix:** store feature and target modes on explicit model/dataset objects;
pass them into feature construction and physical conversion. At minimum, add tests
that alternate two incompatible models repeatedly in one process and verify exact
outputs.

### 1.7 Feature activation is checked by set inclusion rather than exact schema

`Sampler._activate()` activates the global feature list when:

```text
set(self.cond_names) <= set(features.BASE_FEATURES) | set(features.P2_FEATURES)
```

This accepts arbitrary ordering and duplicate names. The model's normalization vectors
depend on positional order, so an order mismatch can produce plausible but incorrect
predictions without a shape error.

**Required fix:** compare the exact ordered feature list and reject duplicates,
missing names, or unexpected names. Store a feature-schema hash in the checkpoint.

### 1.8 Humidity mode is global, but the raw target schema is not validated

`Sampler` sets `RH_TARGET` from checkpoint metadata, but `to_physical()` still
assumes the target has exactly four 44-level variables followed by exactly three
surface fields. A checkpoint can declare `rh_target="dpd"` while its target layout
or physical columns do not match that assumption.

**Required fix:** validate target names, count, units, humidity transform, and schema
version together before sampling.

### 1.9 `build_dataset.py` can apply station correction to unsupported rows without
a support mask

Station correction returns corrected values, but the training artifact stores only
`cond`, `target`, and `year`. It does not carry which station group, height levels,
source fields, or residual support were used. Rows corrected by an identity fallback,
rows with different source coverage, and rows corrected with different station
groups become indistinguishable.

**Impact:** later scorecards can attribute station-specific calibration behavior to
the generator and cannot stratify by correction support.

**Required fix:** persist group IDs, source/support masks, correction version, and
support counts into the training artifact.

### 1.10 The raw-data provenance is lost before model training

The training artifact does not retain timestamps, point IDs, station IDs, source month,
input data revision, or row IDs. Once a model score changes, it is difficult to
determine whether the model changed or the selected data population changed.

**Required fix:** include stable row IDs and provenance arrays, or maintain a
sidecar immutable row index with hashes.

---

## 2. Silent evaluation inflation risks

### 2.1 Known-driver results are easier than the operational problem

The score and sonde paths construct both known-driver and unknown-driver samples,
but diagnostics and reports prominently use `known`. Known-driver samples use
observed target-month ONI, WWV, and QBO values. A future query cannot use these
observations.

**Required reporting rule:** make unknown-driver results primary for future forecasts
and label known-driver results as an unreachable upper bound.

### 2.2 ERA5 truth is not independent atmospheric truth

`score.py` evaluates against ERA5 profiles, while the generator is trained on ERA5
targets and ERA5 is smoother than radiosonde observations. This can make the model
look well calibrated while it remains under-dispersed against the atmosphere.

**Required reporting rule:** treat ERA5 scoring as development diagnostics. Make
held-out radiosonde verification primary for claims about physical atmospheric
accuracy, with representativeness limitations reported separately.

### 2.3 “Held-out” years become development data once they select changes

The improvement log uses 2024–2025 results to accept or reject calibration and
station-correction choices. Those years are no longer untouched final test years.

**Required reporting rule:** reserve an untouched final year, station, or episode set,
or relabel 2024–2025 as development verification and weaken the final claim.

### 2.4 Calibration can be selected on the same data used for the headline result

Range calibration, station calibration, model choice, quantile levels, clipping,
and scorecard settings are all capable of changing coverage. If any of these are
chosen after examining the final years, those years are part of development.

**Required fix:** use a split manifest with mutually exclusive model-fit,
calibration-fit, development, and final-release sets. Store selected row IDs and
reject overlap automatically.

### 2.5 Dropped cases can make skill look better

`score.py` drops held-out rows without a climatology group, and `sonde.py` keeps
only soundings with finite values in every physical column. Difficult high-altitude,
rare-season, and incomplete-profile cases may be removed before scoring.

**Required reporting rule:** publish kept and dropped counts, distributions by month,
height support, station, and weather regime. Score every method on the same cases
and provide a declared fallback baseline for empty groups.

### 2.6 The Gaussian baseline is unstable in 179 dimensions

The Gaussian reference baseline estimates a full covariance from each group and
uses a small diagonal jitter. When group size is not large relative to 179
dimensions, the covariance can be noisy, nearly singular, or accidentally favorable.

**Required fix:** use a documented shrinkage or low-rank covariance, minimum group
support, positive-definiteness checks, and diagonal/low-rank comparison baselines.

### 2.7 Finite-member coverage is mislabeled by nominal probability

The coverage routine uses a discrete order-statistic interval. At `m=199` and
`p=0.99`, its `k=1` rule selects the minimum and maximum members, which is
approximately a 100% interval for a continuous exchangeable truth, not an exact 99%
central interval.

**Required fix:** define finite-member interval conventions explicitly, test analytical
coverage with synthetic exchangeable data, and record attainable coverage next to
nominal coverage.

### 2.8 Calibration changes tails but the scorecard may not show latent clipping

`spread.apply()` and physical conversion clip RH to [0, 100]. This can create point
masses and make final RH coverage look acceptable even if the raw generator produces
physically invalid humidity.

**Required diagnostic:** report the pre-clip fraction of samples hitting each bound
by variable, height, season, route, and calibration version.

### 2.9 Marginal calibration is not joint profile calibration

Per-column monotone range maps can improve marginal coverage while leaving wind
vectors, shear, T/RH coupling, and whole-profile regions miscalibrated. Rank
preservation is not a guarantee of physical joint coverage, especially after clipping
and site transfer.

**Required metric:** add vector, shear, thermodynamic-column, and whole-profile joint
coverage. Do not call marginal 99% bands joint 99% bands.

### 2.10 The scorecard can hide the worst launch-critical band

Summary metrics average across columns and height bands. A good upper-air temperature
score can hide a poor 10 m–1 km wind/shear result that matters more to dispersion.

**Required reporting rule:** make the worst variable-height band, miss direction,
station, month, and uncertainty prominent. Require each launch-critical band to pass
independently.

---

## 3. Generator and loss pitfalls

### 3.1 GPU float16 storage and bfloat16 forward need an explicit reference mode

The current GPU path is faster but not equivalent to float32. Compare:

- float32 storage + float32 forward
- float16 storage + bfloat16 forward
- float32 storage + bfloat16 forward

Use identical rows, seeds, optimizer settings, and validation noise. Compare final
CRPS, energy score, variogram score, calibration, and shear tails.

### 3.2 Training loss and final score use different targets unless explicitly aligned

Training scores reconstructed profiles with per-channel standardization, optional
step losses, optional shear-tail losses, and optional physical penalties. The final
scorecard reports physical-unit CRPS, energy/variogram behavior, and coverage. A
lower training loss is not evidence that the acceptance metrics improved.

**Required reporting rule:** log each loss component separately and require final
selection on the same physical metrics used by the ship gate.

### 3.3 Step and shear losses can dominate through unit/scale mistakes

`step_loss` and `shear_tail_loss` use different reconstructed coordinates and
scales. `shear_scale` can be near zero in calm layers despite the `safe()` floor,
which can produce very large gradients. Step-window scales can also differ greatly
between variables and height spacings.

**Required check:** log per-term magnitude, gradient norm, and contribution by
variable/layer. Add finite-value and maximum-gradient guards.

### 3.4 Almost-fair CRPS depends on `alpha` and member count

The configuration uses `crps_alpha=0.99` in the A99 model and `m=4`. Changing alpha
changes the spread incentive and the optimum; it is not merely a numerical setting.
Compare alpha and member count under the same downstream metrics and record them in
the checkpoint and report.

### 3.5 Ensemble members may not be independent

Members differ mainly by seed while using the same rows, split, architecture,
normalization, and optimizer. Four members can therefore have much lower effective
ensemble size than four independent forecasts.

**Required check:** calculate inter-member correlations by variable and height and
report effective ensemble size before interpreting pooled coverage.

### 3.6 Fresh validation noise can choose a lucky checkpoint

Even though validation uses a forked RNG, each evaluation can still generate only
`m=4` samples per row. The fixed seed makes evaluations repeatable, but it does not
remove Monte Carlo estimation noise.

**Required fix:** use common random numbers plus a larger evaluation member count or
repeated fixed-noise batches. Select checkpoints using the same evaluation protocol
as the final report.

### 3.7 EMA changes the evaluated model and can be inconsistent with training history

When `ema_decay` is enabled, validation evaluates the EMA model and saves its state,
but training loss and optimizer history describe the raw model. The report can
therefore show a validation improvement that is not attributable to the logged
training trajectory.

**Required fix:** log raw and EMA validation scores separately and record which
state was selected and calibrated.

---

## 4. Forecast-route and past/near-term risks

### 4.1 Router boundaries need explicit timezone and timestamp semantics

`router.mode()` uses `lead_days = valid time - now` and floating thresholds. A query
near midnight, a daylight-saving transition, or a timezone conversion boundary can
switch routes unexpectedly.

**Required fix:** calculate lead from timezone-aware UTC instants, define inclusive
boundaries, and test every threshold at sub-hour resolution.

### 4.2 Mixture sampling assumes equal member counts and aligned sample semantics

`router.mix()` requires both arrays to have the same member count and replaces row
`j` with row `j` from the other source. This is a valid mixture only if rows are
exchangeable draws and both arrays have identical variable order, support masks,
units, and site reference. The function performs no checks.

**Required fix:** validate schema, shape, units, support, and route metadata before
mixing. Record the realized source count and mixture weight.

### 4.3 Cosine ramp parameters are not validated

`ramp(x, start, end)` divides by `end-start` without checking `end > start`.
Bad settings produce NaNs or inverted behavior.

**Required fix:** validate settings at load time and add tests for scalar, vector,
boundary, reversed, and equal endpoints.

### 4.4 Past-mode residuals are trained on nearest-grid/nominal-hour comparisons

Mode P pairs balloons with the nearest ERA5 grid point and nominal 00Z/12Z time.
It does not model release-time drift or station representativeness in the residual
definition, so the residual network may learn a site-specific comparison artifact.

**Required check:** compare nearest, bilinear, release-time, and drift-aware pairing
where metadata permit; hold out complete stations or periods when evaluating transfer.

### 4.5 Mode P tendency arrays can be misaligned at store boundaries

`load_pairs()` computes `nxt = station.era5_at(ds, pt, t + 1 hour)` and then uses
`ok2 = ok & finite(nxt)`. This is valid only if `era5_at` returns an array aligned
exactly to the original `t` order and the dataset has unique timestamps. Add explicit
timestamp assertions and a test around the final available hour.

### 4.6 Mode F uses several unverified boundary-layer approximations

Mode F derives 100 m wind, 2 m dew point, RH, and surface quantities from
approximations. These approximations can dominate residual errors, but the residual
network may hide them in aggregate metrics.

**Required check:** report boundary-layer approximation error before residual correction,
by lapse bin, wind speed, humidity, terrain, and lead. Compare against simple neutral
and persistence baselines.

### 4.7 Mode F spatial longitude matching is brittle

The longitude mapping assumes one specific convention:

```text
h.longitude - 360 - store_longitude == 0
```

This fails if either dataset uses a different convention, if coordinates are rounded
differently, or if the point is not represented exactly.

**Required fix:** normalize both longitudes to one convention and use nearest matching
with a tolerance, logging the distance and rejecting unmatched points.

### 4.8 Mode F truth indexing needs a direct invariant

`load_year()` builds a unique valid-time array, maps it to profile-store time indices,
then uses `searchsorted` to recover truth positions. This relies on `vt` being sorted
and unique and on every `valid[case, lead]` being present. Assert all three conditions
and test missing valid times, duplicate forecast times, and unsorted source files.

---

## 5. Feature and humidity-mode pitfalls

### 5.1 P2 features can silently differ between dataset creation and inference

`build_dataset.py` mutates the active feature list with `set_active(P2_FEATURES)`,
while `load_npz()` and `Sampler._activate()` mutate it again based on metadata.
A process that builds P2 and then loads a base dataset can produce valid-shaped but
semantically wrong feature arrays if callers retain stale references or use
previously constructed conditions.

**Required fix:** eliminate mutable active feature state or make feature objects
immutable and explicit.

### 5.2 ONI hinge and lag features need availability-vintage checks

The P2 feature path adds `oni_pos`, `oni_neg`, and `oni_lag3`, but the review must
verify whether lagged ONI and GMST values are available at the historical forecast
issue time. A target-month index accidentally used in these derived features creates
leakage while preserving plausible values.

### 5.3 DPD humidity inverse needs numerical and physical tests

`dpd_from_rh()` floors RH and `rh_from_dpd()` clips depression. Check round-trip error
over the full temperature/RH domain, especially near RH=0.5%, RH=100%, cold
temperatures, and negative/large generated DPD values. Log saturation and clipping
rates; otherwise the model can appear calibrated because invalid humidity is repaired.

### 5.4 The DPD transform changes the loss geometry

DPD is nonlinear and bounded differently from RH. A model can improve DPD-space CRPS
while worsening RH-space CRPS or density error. Select and report models in both
target and physical spaces, with density and saturation checks.

### 5.5 Feature order must be checked by names, not shape

P2 and base feature vectors can have the same general numeric shape while differing in
semantic order. Every model input must be validated against the checkpoint's exact
ordered feature names and a schema hash.

---

## 6. Common AI review traps

### 6.1 Do not use loss curves as evidence of forecast accuracy

A decreasing loss can reflect memorization, unconditional climatology learning,
or leakage. Require driver ablations, spatial/year holdouts, calibration, physical
checks, and comparison against the analog baseline.

### 6.2 Do not tune on the final scorecard repeatedly

Every threshold, calibration window, model architecture, loss weight, route boundary,
and clipping rule inspected after seeing final scores consumes test independence.
Track experiments and freeze the release configuration before final scoring.

### 6.3 Do not trust a single random seed

Seed-specific improvements are especially likely with small independent-year samples,
rare tails, and stochastic generators. Report multiple seeds and uncertainty over
folds, not only the best run.

### 6.4 Do not count correlated rows as independent evidence

Hourly weather rows, nearby grid points, repeated soundings, and ensemble members are
correlated. Use episode/year/station blocks for confidence intervals and effective
sample sizes.

### 6.5 Do not let repair layers hide invalid predictions

RH clipping, pressure restoration, site transfer, and residual correction can make
outputs look physically plausible after a broken generator. Report raw outputs,
repair rates, and post-repair scores separately.

### 6.6 Do not compare routes without route-conditional baselines

A model can appear strong if it is compared against a weak baseline in one lead band
and a stronger baseline in another. Define baselines separately for past, near-term,
sub-seasonal, and climate routes, and compare each route on identical cases.

---

## 7. Immediate review gate

Before accepting any new result, require:

1. Clean environment and complete test suite.
2. Float32 reference run versus the active mixed-precision run.
3. Exact feature and target schema validation.
4. Explicit train/validation/calibration/test manifests.
5. Unknown-driver results as the operational primary output.
6. ERA5 and radiosonde scorecards shown separately.
7. Pre-clip and post-clip diagnostics.
8. Finite-member interval convention and synthetic coverage test.
9. Per-band and joint-profile calibration.
10. Support/dropout counts by source, month, height, station, and route.
11. Multiple seeds and blocked confidence intervals.
12. Frozen final configuration before release scoring.

This review file is a checklist for preventing attractive but invalid results. It does
not replace independent scientific verification, untouched test data, or domain-expert
review.