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
device is CUDA (`dt = torch.float16 if gpu else torch.float32`). Each batch is later
cast back to float32, which does not restore the precision already lost. Validation
stays float32, so the model trains on one numerical distribution and is selected on
another.

**Impact:** small differences in difference-space shear channels, pressure departures,
humidity coordinates, and standardized tail values can be distorted.

**Required check:** compare float16-storage against float32-storage training on identical
rows, seeds, and metrics (CRPS, variogram, coverage, tails). If the intent is memory
savings, document and gate the change.

### 1.2 The advertised "lossless" training speedups are not necessarily lossless

The active path already uses bfloat16 autocast on GPU and float16 storage. Any claim
that a change preserves the exact float32 objective is false unless the baseline is
explicitly defined as this mixed-precision path.

**Required check:** keep a float32 reference mode and compare the whole training
trajectory, not one loss value.

### 1.3 Checkpoint creation can save an unusable model after NaN validation

`best_state` starts as `None` and is only set when `v < M["best"]`. If every validation
loss is NaN or infinite, a checkpoint with `state=None` is still built; `Sampler` then
fails later, far from the real cause.

**Required fix:** reject nonfinite losses immediately and require a finite `best_state`
and finite normalization arrays before saving.

### 1.4 Block validation operates on a synthetic calendar

`split()` builds `day = year*366 + doy` and 14-day blocks from it. Leap years and the
missing day 366 distort block boundaries and the 3-day embargo.

**Required check:** build blocks from true timestamps; assert the embargo in calendar
days; test January, Feb 29, December, and cross-year blocks.

### 1.5 `val_block_frac` can produce unstable validation populations

Blocks are drawn with a fixed RNG seed independent of the model seed, with no minimum
train/val counts or per-year coverage. A draw can leave years absent from one side.

**Required check:** persist block IDs, report counts by year/station/month, reject splits
below minimum support.

### 1.6 The active feature configuration is mutable global process state

`features.FEATURES` and `sample.RH_TARGET` are mutated by `load_npz()` and
`Sampler._activate()`. Loading one dataset/model changes behavior for everything imported
afterward in the same process.

**Failure example:** load a p2/dpd model, then a base/rh model; feature order or the
humidity inverse used between them can be wrong.

**Required fix:** store feature/target modes on explicit objects and pass them in; at
minimum, test alternating two incompatible models in one process.

### 1.7 Feature activation is checked by set inclusion, not exact schema

`Sampler._activate()` activates when `set(cond_names) <= BASE | P2`. This accepts wrong
ordering and duplicates; normalization is positional, so an order mismatch gives plausible
but wrong predictions with no shape error.

**Required fix:** compare the exact ordered list, reject duplicates/missing/unexpected
names, and store a feature-schema hash.

### 1.8 Humidity mode is global, but raw target schema is not validated

`Sampler` sets `RH_TARGET` from metadata, but `to_physical()` still assumes exactly four
44-level variables plus three surface fields. A checkpoint can declare `dpd` while its
layout differs.

**Required fix:** validate target names, count, units, humidity transform, and schema
version together before sampling.

### 1.9 `build_dataset.py` applies station correction without a support mask

The training artifact stores only `cond`, `target`, `year` — not station group, source/
support masks, or correction version. Identity-fallback rows and rows with different
source coverage become indistinguishable.

**Required fix:** persist group IDs, source/support masks, correction version, and counts.

### 1.10 Raw-data provenance is lost before training

No timestamps, point/station IDs, source month, data revision, or row IDs are retained,
so a score change cannot be attributed to the model versus the data population.

**Required fix:** include stable row IDs and provenance, or a sidecar immutable index.

---

## 2. Silent evaluation inflation risks

### 2.1 Known-driver results are easier than the operational problem
Diagnostics/reports prominently use `known` (observed target-month ONI/WWV/QBO), which no
future query can use. Make unknown-driver results primary; label known as an upper bound.

### 2.2 ERA5 truth is not independent atmospheric truth
`score.py` scores against the smooth ERA5 field the model trained on. Treat ERA5 scoring
as development only; make held-out radiosonde verification primary.

### 2.3 "Held-out" years become development data once they select changes
2024–2025 were used to accept/reject calibration choices. Reserve an untouched final set
or relabel those years as development verification.

### 2.4 Calibration can be chosen on the same data as the headline result
Range/station calibration, model choice, quantile levels, and clipping all change coverage.
Use a split manifest with mutually exclusive fit/calibration/development/release sets and
reject overlap by row ID.

### 2.5 Dropped cases can make skill look better
`score.py` drops empty-climatology-group rows; `sonde.py` keeps only all-finite soundings.
Publish kept/dropped counts and distributions; score all methods on the identical surviving
set.

### 2.6 The Gaussian baseline is unstable in 179 dimensions
Full covariance from a small group with fixed jitter can be noisy or accidentally favorable.
Use documented shrinkage/low-rank covariance, minimum support, and comparison baselines.

### 2.7 Finite-member coverage is mislabeled by nominal probability
The order-statistic interval at m=199, p=0.99 uses k=1 (min–max), which is ~100% for a
continuous truth, not an exact 99% central interval. Define the convention, test analytical
coverage, and record attainable vs nominal.

### 2.8 Calibration changes tails but latent clipping is hidden
RH clipping after the quantile transform can make final RH coverage look acceptable even if
the raw generator is invalid. Report pre-clip bound-hit rates by variable/height/season/route.

### 2.9 Marginal calibration is not joint profile calibration
Per-column monotone maps can leave vectors, shear, and T/RH coupling miscalibrated. Add
vector/shear/thermodynamic/whole-profile joint coverage.

### 2.10 The scorecard can hide the worst launch-critical band
Averages can mask a poor low-level wind/shear band. Surface the worst band, miss direction,
station, month, and uncertainty; require each launch-critical band to pass on its own.

---

## 3. Generator and loss pitfalls

### 3.1 Precision modes need an explicit reference comparison
Compare float32/float32, float16/bfloat16, and float32/bfloat16 on identical rows/seeds for
final CRPS, energy, variogram, calibration, and shear tails.

### 3.2 Training loss and final score use different targets unless aligned
Lower training loss is not evidence that acceptance metrics improved. Log each loss component
and select on the same physical metrics the ship gate uses.

### 3.3 Step and shear losses can dominate through unit/scale mistakes
`shear_scale` can be tiny in calm layers despite the `safe()` floor, producing large
gradients. Log per-term magnitude, gradient norm, and per-variable/layer contribution; add
finite/max-gradient guards.

### 3.4 Almost-fair CRPS depends on alpha and member count
`crps_alpha=0.99` and `m=4` change the spread incentive and optimum. Compare under downstream
metrics and record alpha and m in the checkpoint and report.

### 3.5 Ensemble members may not be independent
Members differ mainly by seed while sharing rows, split, architecture, normalization, and
optimizer. Compute inter-member correlation and effective ensemble size before interpreting
pooled coverage.

### 3.6 Fresh validation noise can choose a lucky checkpoint
Forked RNG makes evaluations repeatable but does not remove Monte Carlo noise at m=4. Use
common random numbers plus a larger evaluation m or repeated fixed-noise batches.

### 3.7 EMA changes the evaluated model inconsistently with training history
With `ema_decay`, validation evaluates and saves the EMA model while loss/history describe
the raw model. Log raw and EMA validation separately and record which state was selected.

---

## 4. Forecast-route and past/near-term risks

### 4.1 Router boundaries need explicit timezone/timestamp semantics
`router.mode()` uses float thresholds on `lead_days`; a query near midnight, a DST change, or
a timezone conversion can switch routes. Compute lead from timezone-aware UTC and test every
threshold at sub-hour resolution.

### 4.2 Mixture sampling assumes equal member counts and aligned semantics
`router.mix()` requires equal m and performs no schema/units/support checks. Validate before
mixing and record realized source count and weight.

### 4.3 Cosine ramp parameters are not validated
`ramp()` divides by `end-start` without checking `end>start`. Validate at load; test scalar,
vector, boundary, reversed, and equal endpoints.

### 4.4 Past-mode residuals use nominal-hour/nearest-grid pairing
Mode P pairs balloons with the nearest grid point and nominal 00Z/12Z, ignoring drift and
representativeness in the residual definition. Compare nearest/bilinear/drift-aware pairing
and hold out whole stations or periods.

### 4.5 Mode P tendency arrays can be misaligned at store boundaries
`nxt = era5_at(ds, pt, t + 1h)` must be aligned exactly to `t` with unique timestamps. Assert
this and test the final available hour.

### 4.6 Mode F uses several unverified boundary-layer approximations
100 m wind, 2 m dew point, RH, and surface fields are approximated; the residual net can hide
their error. Report approximation error before correction by lapse bin, wind, humidity,
terrain, and lead.

### 4.7 Mode F longitude matching is brittle
It assumes `h.longitude - 360 - store_longitude == 0`. Normalize both to one convention and use
nearest matching with a tolerance, logging distance and rejecting unmatched points.

### 4.8 Mode F truth indexing needs direct invariants
Assert `vt` is sorted and unique and every `valid[case, lead]` is present; test missing valid
times, duplicate forecast times, and unsorted files.

---

## 5. Feature and humidity-mode pitfalls

### 5.1 P2 features can silently differ between build and inference
`build_dataset.py` and `load_npz`/`Sampler` all mutate the active feature list. Eliminate the
mutable global or make feature objects immutable and explicit.

### 5.2 ONI hinge and lag features need availability-vintage checks
Verify `oni_lag3`/`gmst` are available at the historical issue time; a target-month value used
here leaks while staying plausible.

### 5.3 DPD humidity inverse needs numerical and physical tests
Check `dpd_from_rh`/`rh_from_dpd` round-trip over the full domain, especially RH=0.5%, RH=100%,
cold T, and large/negative generated DPD. Log saturation/clipping rates.

### 5.4 The DPD transform changes the loss geometry
A model can improve DPD-space CRPS while worsening RH-space CRPS or density error. Report both
spaces plus density and saturation checks.

### 5.5 Feature order must be checked by names, not shape
P2 and base vectors can share shape but differ in order. Validate against the checkpoint's exact
ordered names and a schema hash.

---

## 6. Common AI review traps

- **6.1** Do not use loss curves as evidence of accuracy; require ablations, holdouts,
  calibration, and physical checks.
- **6.2** Do not tune repeatedly on the final scorecard; freeze the release config first.
- **6.3** Do not trust a single seed; report multiple seeds and fold uncertainty.
- **6.4** Do not count correlated rows as independent; use episode/year/station blocks.
- **6.5** Do not let repair layers (RH clip, site transfer, residual correction) hide invalid
  predictions; report raw outputs and repair rates.
- **6.6** Do not compare routes without route-conditional baselines.

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

---

## 8. Second pass: end-to-end output path (`tempest/output`, `tempest/forecast`)

This pass reviews the assembled query-to-atmosphere path: `output/atmosphere.py`,
`output/coupled.py`, `forecast/router.py`, `forecast/scenarios.py`, and
`profiles/thermo.py`. `thermo.column` was checked and appears internally consistent
(hypsometric integration with virtual temperature and a fixed-point humidity pass). The
findings below are additional to Sections 1–7.

### 8.1 Confirmed defect: the w-head and site transfer use inconsistent elevations

In `Atmosphere.sample()` the vertical-wind head runs on grid-elevation profiles, then the
profiles are shifted to the site:

```text
extras["w"] = self.head(head_inputs(cond, phys)).astype(np.float32)
phys = sample_mod.to_site(phys, elev_row[:n], elev)
```

The `w` samples are stored alongside the site-transferred `phys` in `coupled.build`, so the
coupling file computes w-to-profile correlations from mismatched references.

**Required check:** confirm the w-head's training elevation and either transfer its inputs
consistently or compute `w` after the site transfer; test that the w-head reference equals the
reference of the profiles stored with it.

### 8.2 Confirmed fragility: surface fields are read by hard-coded index 176

```text
u10, v10 = phys[:, 0], phys[:, len(HEIGHTS)]
hist = self.lib.draw(p, t_utc.round("h"), phys[:, 176], rng)
```

These assume exactly 4x44 profile columns then `t2m` at 176. Under P2/DPD, extra surface
fields, or future pressure/density targets, index 176 can silently become the wrong variable.
There is no schema assertion.

**Required fix:** resolve surface indices by name from the active schema and assert the column
count.

### 8.3 Confirmed risk: range calibration is applied before site transfer

```text
phys = spread.apply(self.cal, self.sampler.profiles(cond).reshape(groups, M_CAL, -1))...
phys = sample_mod.to_site(phys, elev_row[:n], elev)
```

Calibration was fit on grid-elevation profiles but shipped after `to_site`. If the fit and
ship stages differ in elevation reference, the 99% guarantee does not hold for written values.

**Required fix:** fit and apply calibration at the same pipeline stage, or verify `to_site`
preserves the calibrated distribution per band.

### 8.4 Confirmed defect: driver-forecast horizon is silently clamped to 12 months

```text
horizon = int(min(12, ...))
d = index_forecast.draw(known, known.index[-1], horizon, n, rng)
```

Any target more than 12 months past the last known index gets a 12-month spread while the note
still reports "{horizon} months ahead," understating uncertainty where it is largest.

**Required fix:** extend the driver-forecast model or mark long-lead draws as climatological
with widened spread, and make the note state the clamp.

### 8.5 High-risk: solar-time handling for naive vs aware timestamps differs

`solar_time()` computes the 06–21 h window check differently for naive (`t.hour+min/60`) and
aware (longitude-shifted) inputs, so the same query can be accepted in one form and rejected in
the other.

**Required fix:** compute solar hour through one shared path; test the 06:00/21:00 edges and the
longitude sign.

### 8.6 High-risk: `coupling()` silently drops variables containing any NaN

`coupled.coupling()` keeps only variables where `isfinite(...).all()`. A single NaN removes a
variable from every correlation/EOF/shear summary without warning.

**Required fix:** report included/excluded variables and fail if a variable expected to be
finite contains NaNs.

### 8.7 High-risk: EOF/correlation summaries can mislead on skewed, clipped data

Pearson/Spearman correlations and SVD-based EOFs are reported on standardized samples. After RH
clipping and nonlinear humidity transforms, these can imply more linear coupling than exists.

**Required rule:** keep the diagnostic-only label and add a nonlinear-dependence check so near-
zero correlation is not read as independence.

### 8.8 Confirmed risk: `scenarios()` returns the nearest sample, not the percentile

For each percentile it returns the single sample whose outcome is nearest. In sparse tails (e.g.
99th with few extremes) the realized `outcome` can differ materially from the target.

**Required rule:** display both target and realized outcome (both already in the dict) and warn
when the gap exceeds a tolerance, especially for 1st/99th and small tail counts.

### 8.9 Confirmed risk: weighted-percentile path assumes positive, normalizable weights

The weighted branch divides by `cw[-1]` with no check for zero/negative/non-finite weights.

**Required fix:** validate weights (finite, nonnegative, positive sum) and test the weighted path
against the unweighted path under uniform weights.

### 8.10 High-risk: router thresholds and mixture lack validation (confirmed in code)

`router.mode()` does not assert ordered thresholds; `ramp()` divides by `end-start` unchecked;
`mix()` requires equal member counts and aligned semantics but checks none.

**Required fix:** validate settings at load (strictly increasing boundaries, positive ramp
widths) and validate shape/schema/units in `mix()`.

### 8.11 High-risk: bilinear point/elevation blend must not smooth profile shear

`atmosphere.sample()` blends the four points' elevations and allocates range-map blocks by
weight. This is fine for scalars, but any profile-level blending introduced the same way would
reduce shear variance (the Part 1 B6 concern).

**Required check:** confirm only whole-sample point selection (no profile averaging) is used and
document the elevation-blend effect on the site transfer.

---

## 9. Environment and verification status

- `python -m compileall` succeeds for `tempest` and `tests`.
- `python -m pytest` cannot run: `pytest` is not installed in the active interpreter, so no test
  provided evidence for any claim here. Every finding is from static inspection and must be
  confirmed by execution.
- Highest-priority confirmed items: 1.1 (float16 training storage), 1.3 (NaN checkpoint),
  8.1 (w-head elevation mismatch), 8.2 (hard-coded surface index 176), 8.3 (calibration before
  site transfer), and 8.4 (silent 12-month driver-horizon clamp). Each can make the product look
  correct while being physically or statistically wrong.