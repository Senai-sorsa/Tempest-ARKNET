global-fixes.md

# Global extension review and fixes

This review covers `docs/plans/GLOBAL_PLAN.md`, `tempest/region.py`,
`tempest/geo/sh.py`, `tempest/ingest/fetch_global.py`,
`configs/global_holdout.toml`, and the global/L3 tests and wiring visible in the
repository. It focuses on issues that can make global results look successful
while the data, holdouts, geography, or evaluation are wrong.

The current global extension is not yet a complete end-to-end product. The plan
requires global statics, climatology, a global profile loader, pooled calibration,
spatial validation, and a global router, but the repository currently contains
only part of the planned foundation. These items should be treated as blockers or
explicitly marked as not implemented rather than assumed to work.

---

## 1. Critical global data-pipeline blockers

### 1.1 The global store has no production loader/converter

`fetch_global.py` writes one compressed NPZ per month containing encoded pressure-
level fields and point indices. The existing profile conversion and training paths
expect an xarray/Zarr profile store with named coordinates, pressure levels, surface
fields, above-ground heights, and metadata. There is no reviewed end-to-end loader
that decodes the monthly NPZ files, reconstructs physical values, merges months,
converts pressure levels to the 44 above-ground heights, applies the correct terrain
reference, and emits training rows.

**Impact:** the global data may download successfully while the global model is
trained on a different layout, wrong units, or no data at all.

**Fix:** implement and test a dedicated global dataset reader/converter before G1/G4
training. Its contract must specify array order, units, missing values, point IDs,
valid timestamps, pressure-level coordinates, surface anchors, elevation reference,
and schema/version hashes.

### 1.2 Required global static fields are not fetched or connected

The global plan requires ERA5 invariants, sub-grid orography, land-sea mask, distance
to coast, TPI, Köppen class, and eventually tropopause/terrain features. The current
global fetcher reads only `u, v, t, r, z` and seven surface fields. The planned
`tempest/geo/statics.py` does not exist in the inspected tree, and no global static
feature manifest or join is implemented.

**Fix:** create one static-field manifest with source, units, grid, validity period,
missing policy, and interpolation rule. Add a point-ID join test ensuring every
training and holdout point receives the correct static row without positional
misalignment.

### 1.3 `z_sfc` is not part of the global fetch output

The global fetcher includes `z` pressure-level geopotential but does not include a
model-surface geopotential/elevation field equivalent to `z_sfc`. The global profile
converter needs the model surface to calculate height above ground and clip
below-ground pressure levels. Inferring surface elevation from pressure is explicitly
an approximation in `terrain_weights()` and is not a substitute for the actual ERA5
model-surface geopotential.

**Fix:** fetch/store `z_sfc` or an authoritative model-surface elevation field. If
it is unavailable in the selected spatial group, define and validate a documented
surface-elevation source and retain both source and uncertainty.

### 1.4 The global fetcher does not preserve source quality/missing masks

`encode()` rejects nonfinite values, so one invalid value can abort a month, while
there is no per-value mask or missing sentinel representation. Conversely, a future
change that clips or replaces invalid values could turn missing data into valid-looking
int16 observations.

**Fix:** store validity masks and source quality flags for every variable. Fail with a
month/variable/point/time report, and make the global loader reject unsupported rows
rather than silently imputing them.

### 1.5 Monthly NPZ files lack an atomic manifest and input fingerprint

The fetcher uses `<month>.npz.part` then renames it, which protects against a partial
file, but it does not write a manifest containing source revision, coordinate hash,
requested time range, variable list, code version, compression/checksum, and validation
status. A stale monthly file is skipped solely because it exists.

**Fix:** write a transactional manifest per month and refuse reuse when the source,
point set, holdout file, variable list, quantization table, or converter version differs.

### 1.6 The point set is frozen without a point-set/version compatibility check

`points.npz` is created once and reused forever. If `global_holdout.toml`, the IGRA
station list, the seed, the point-selection algorithm, or `N_POINTS` changes, an old
point file can remain paired with newly fetched data.

**Fix:** store a point-set hash and the complete selection inputs in `points.npz`;
validate it against the current configuration before every fetch, conversion, or
training run.

---

## 2. Confirmed global sampling and geographic bugs

### 2.1 Terrain weighting is wrong in the Southern Hemisphere

In `terrain_weights()` the area factor is:

```python
np.cos(np.radians(90 - latitude))
```

Since latitude is `90 - index * 0.25`, this equals `sin(latitude)`, not the positive
area factor `cos(latitude)`. It is negative throughout the Southern Hemisphere and
near zero at the equator. The final `np.clip(w, 0, None)` therefore removes nearly
all Southern Hemisphere terrain candidates and strongly biases terrain sampling toward
the Northern Hemisphere.

**Fix:** use `cos(latitude)` in radians, validate nonnegative weights, and add tests
at 90 N, 45 N, 0, 45 S, and 90 S. Compare the selected terrain-point latitude
histogram with the intended equal-area/relief-weighted distribution.

### 2.2 Terrain selection can fail when all weights are zero

`rng.choice(..., p=w.ravel() / w.sum())` has no guard for `w.sum() == 0`. This can
occur if the source elevation/relief calculation fails, if the grid field is missing,
or if the chosen threshold produces no cells.

**Fix:** explicitly test finite positive total weight; provide a deterministic
fallback or fail with a clear diagnostic. Never pass NaN probabilities to the sampler.

### 2.3 Holdout removal changes sample count and distribution without refilling

Points are selected first, then all points within `radius_deg` of holdout sites and
stations are removed. The fetcher does not replenish removed lattice or terrain points.
The final global point count and coverage therefore depend on holdout geography, and
regions near holdouts receive fewer training points.

**Fix:** define whether the target count is before or after exclusion. If it is after,
refill deterministically from a candidate stream while applying the exclusion mask.
Report final counts and spatial density by latitude, longitude, climate class, land/ocean,
and terrain stratum.

### 2.4 Terrain points can be under-filled silently

Terrain candidates are accepted only when their coarse `(i // 2, j // 2)` cell is new and
when the final ID count is below `N_POINTS + N_TERRAIN`. Duplicates, holdout removal, and
zero-weight areas can leave substantially fewer than 1,500 terrain points without a
failure or a refill.

**Fix:** assert the requested terrain count after all exclusions, or record the shortfall
and rerun deterministic candidate generation until the target is reached.

### 2.5 The initial IGRA count can exceed `N_POINTS`

`k = np.arange(N_POINTS - len(ids)) + 0.5` assumes fewer than 6,000 unique active IGRA
grid cells. The global station list can grow, and deduplication is performed only by
grid cell. If `len(ids) >= N_POINTS`, the Fibonacci construction receives an invalid
negative count.

**Fix:** define a station-capacity policy: reserve space for all required IGRA sites,
raise a clear error when the configured capacity is insufficient, or increase the target
point count before generating lattice points.

### 2.6 WMO region assignment is not a reliable geographic region assignment

`wmo_region()` derives a region from character positions in the IGRA identifier and a
numeric block. WMO regional associations are geographic/organizational regions, not
necessarily the same as the identifier block encoding. Consequently, the supposed
"one IGRA station per WMO region" holdout set may not contain one station per actual
WMO region.

**Fix:** use an authoritative station-to-WMO-region table or determine regions from
coordinates with a versioned boundary dataset. Validate that the selected holdouts
really cover all intended regions and that the hard-coded IDs match the selection seed.

### 2.7 Hard-coded holdout IDs are not verified against the current station list

`global_holdout.toml` contains fixed IDs, while `points()` uses them directly if present.
There is no assertion that each ID exists, has valid coordinates, satisfies the required
record years, or is in the intended WMO region. A stale/typo ID can cause a crash or leave
a region without its intended holdout.

**Fix:** validate every holdout ID, coordinates, years, region, and radius at G0. Save
the resolved station metadata and selection hash in the holdout manifest.

### 2.8 Holdout exclusion is only spatial and can leak through nearby grid cells

The exclusion radius is one degree around the holdout coordinate. ERA5 grid cells,
interpolated static fields, climatology tiles, neighboring profiles, and analog candidate
selection can still include information from the holdout location or the same synoptic
station region. A one-degree point exclusion is not automatically a data-independence
boundary.

**Fix:** define holdout buffers in both geographic distance and source-grid/candidate
lineage. Exclude the holdout grid cell, neighboring cells used for interpolation, station
records, and any temporally paired profile derived from the holdout area.

### 2.9 `points()` can return fewer points without a global coverage gate

IGRA deduplication, Fibonacci collisions, terrain spacing, and holdout removal all reduce
the final count. Downstream code may assume approximately 7,500 points based on the plan.
There is no assertion or manifest describing the actual point count and stratum counts.

**Fix:** make point count, land/ocean count, climate count, terrain count, IGRA count,
holdout-distance minimum, and latitude-band density mandatory manifest fields.

---

## 3. Global time sampling and climatology risks

### 3.1 One UTC hour per day creates a strongly structured time/season design

`steps(month)` selects one hour per day with `UTC hour = day_index mod 24`. This does
cover local hours over a long sequence, but each month has only about 28–31 samples and
hour is deterministic from absolute day index. The design is not equivalent to a random
or balanced sample of all date/hour combinations, and it can interact with day-of-year,
weather regimes, leap years, and missing days.

**Fix:** quantify the joint design matrix of date, UTC hour, local solar hour, latitude,
season, and climate state. Use a deterministic balanced schedule or multiple staggered
hours per day if diurnal skill is important. Weight the training loss back to the intended
target distribution.

### 3.2 The global store cannot support all-hour verification by itself

The global plan says all hours are handled through diurnal cycling, but a given point/date
in the store has only one sampled UTC hour. A past-date lookup or exact forecast verification
needs the actual valid hour, not a different day with the same local-hour phase.

**Fix:** distinguish climatology-training samples from exact valid-time analysis data. Do
not use the diurnally cycled store for exact past-date lookup or claim hourly past accuracy.
Fetch/store a separate verification archive with actual timestamps.

### 3.3 The diurnal cycle is not independent of slow weather state

Because hour assignment is tied to absolute day index, each local hour is observed on a
specific subset of dates. If the climate state, season, or missing-data pattern is not
uniform, the model can learn a sampling artifact as a diurnal effect.

**Fix:** use balanced hour assignment within season/year blocks, or include inverse-probability
weights and verify that hour distributions are independent of target date and climate regime.

### 3.4 Leap-year and date-range coverage needs explicit assertions

`steps()` uses `np.arange` over month boundaries and a day index modulo 24. There are no
assertions for the exact number of days, unique timestamps, month membership, or complete
1991–2025 coverage.

**Fix:** test every month type, leap February, year boundaries, monotonicity, uniqueness,
UTC-hour distribution, and that no 2026 timestamp enters the store.

### 3.5 Global pressure-level samples are not directly comparable across terrain

At high terrain, many pressure levels are below ground; over low terrain, the same levels
are usable. If the converter drops missing levels and the dataset builder drops incomplete
rows, high-elevation and mountain regimes can be systematically underrepresented.

**Fix:** carry valid-height masks, support bands, and source pressure-level masks through
training and scoring. Do not compare global regions using only complete 18 km profiles.

---

## 4. Geographic representation and model risks

### 4.1 `region.py` is not a global coordinate abstraction

`Region` assumes a rectangular, regular latitude/longitude grid, computes a rectangular
point index, and uses longitude comparisons that do not support antimeridian-crossing
regions. This is incompatible with a HEALPix/Fibonacci global point set and with periodic
longitude geometry.

**Fix:** keep rectangular-region logic separate from a global point registry. Add explicit
point IDs, geodesic nearest-neighbor lookup, longitude wrapping, antimeridian tests, and
HEALPix/Fibonacci adapters. Never use `Region.point_index()` for the global store.

### 4.2 Longitude distance and interpolation are not globally safe

Many existing nearest-point and spatial calculations use ordinary longitude subtraction.
Near ±180°, points that are physically adjacent can appear 359 degrees apart. This can
select the wrong grid point and corrupt station transfer, terrain lookup, or holdout
exclusion.

**Fix:** use wrapped longitude differences or 3-D unit-sphere coordinates everywhere in
global nearest-neighbor, interpolation, station, and distance calculations.

### 4.3 Latitude/pole behavior is not fully specified

Global points include poles or near-pole locations. Regular longitude spacing collapses
at the poles, and local solar time, terrain neighborhoods, static interpolation, and
longitude-based features become ill-conditioned.

**Fix:** define pole handling, exclude the exact poles if necessary, use spherical
coordinates for neighborhoods, and test latitudes near ±90°.

### 4.4 The spherical-harmonic encoder needs a stronger numerical gate

`tempest/geo/sh.py` claims 4π normalization and supports NumPy and Torch, but the current
test checks only degree 6 on a finite equal-area ring grid with tolerance 0.01. The global
plan proposes higher degrees and possibly SIREN composition; recurrence stability and
orthogonality can degrade at high degree and near poles.

**Fix:** test L=10 and L=20, float32 and float64, poles, date-line equivalence,
Torch gradients, rotation/orthogonality on an independently generated spherical design,
and maximum absolute/relative values. Do not accept only a finite-grid matrix test.

### 4.5 Raw static features can leak location identity or create shortcuts

Terrain, Köppen, land-sea, coast distance, and invariant fields may let the model memorize
station/region identity rather than learn transferable physics. A global random point split
will then overstate generalization because nearby points share static features and weather.

**Fix:** use spatial blocks, leave-climate-out and leave-continent-out tests; add a
coordinate/static-only baseline; test whether static features alone identify the holdout.

### 4.6 Equal-area sampling does not equal equal evaluation importance

The training point set is approximately equal-area plus stratified stations/terrain, while
acceptance is reported by continents, climate groups, stations, and possibly flight-use
locations. Without explicit weights, oversampled mountains/IGRA sites can dominate the
loss and make global aggregate scores look better than ordinary locations.

**Fix:** define the target deployment distribution and use explicit training/evaluation
weights. Publish both area-weighted and application-weighted results.

### 4.7 Global calibration cannot be validated by station counts alone

Hundreds of IGRA stations still have uneven temporal coverage, launch hours, climate,
terrain, and instrument eras. A pooled calibrator can look strong because common stations
or common regimes dominate it.

**Fix:** use leave-station, leave-region, leave-climate, and time-block splits. Report
support and uncertainty per climate/terrain/height regime, not only pooled metrics.

---

## 5. Holdout and leakage controls

### 5.1 Training-data exclusion must include all derived products

Removing point coordinates within one degree is insufficient if static fields, climatology
anchors, EOFs, normalization statistics, station corrections, terrain weights, or source
fields were computed globally before holdout removal. Any operation using holdout locations
or their data can leak information even if the final point row is absent.

**Fix:** apply the holdout mask before fitting every learned or estimated object, including
climatology, standardization, EOFs, calibration, terrain selection, and DI thresholds.

### 5.2 Holdout sites must be removed from calibration as well as generator training

The plan says holdouts are never used for training, tuning, or calibration, but existing
station/calibration utilities use station lists and may independently read all available
IGRA records. Add a single holdout-aware loader used by every calibration and score path.

**Fix:** reject holdout station IDs, coordinates, and dates at calibration input time and
write the excluded IDs to the artifact manifest.

### 5.3 Static-field interpolation can cross the holdout boundary

A holdout point's static features may be computed from a neighborhood containing training
points or source-grid cells inside the exclusion radius. This is not always leakage for
static geography, but it invalidates a strict unseen-place claim if the neighborhood
contains the held-out source lineage.

**Fix:** define whether static geography may use neighboring cells; if not, mask the full
feature neighborhood. Document the choice and test both strict and practical AOA modes.

### 5.4 Final test date availability is not guaranteed by the fetch plan

The global training fetch explicitly excludes 2026, while G6 is locked to 2026-07-01
through the latest ERA5 day. No reviewed final-test fetch/loader was found in this pass
that guarantees those exact dates, variables, stations, and profiles are available.

**Fix:** create a frozen final-test acquisition manifest before G5, verify source coverage
and checksums, and prevent the model/tuning pipeline from reading it before G6.

### 5.5 The holdout lock can be bypassed by environment or alternate paths

The plan proposes a `TEMPEST_FINAL_GLOBAL=1` escape hatch. Any loader that permits this
flag without an audit log can accidentally expose final sites during tuning.

**Fix:** require an explicit signed/reviewed unlock artifact, log every access, and make
normal training processes reject the holdout regardless of environment variables.

---

## 6. Global model, calibration, and packaging risks

### 6.1 The proposed global climatology anchor has no implemented artifact contract

The plan calls for a 1-degree grid, Fourier diurnal/annual terms, and EOFs, but no reviewed
`geo/clim.py` implementation exists. There is no specification for interpolation at poles,
longitude wrap, missing ocean/land values, fitting weights, or anomaly reconstruction.

**Fix:** define a serialized climatology artifact with coordinate convention, units,
training mask, interpolation method, uncertainty floor, and schema hash. Test reconstruction
and out-of-domain behavior before training anomalies.

### 6.2 Standardized anomalies can divide by near-zero climatological spread

Global variables such as RH, upper-air components in stable regimes, or surface fields in
small strata can have very small climatological sigma. Dividing by a tiny sigma creates huge
training targets and lets a few cases dominate the loss.

**Fix:** use a documented variance floor, support-aware pooling, robust scale diagnostics,
and report the fraction of cells using a floor. Fit the floor within training folds only.

### 6.3 Climatology target leakage through future/revised data

If the global climatology is fitted from a store that includes years or holdout locations
later used for verification, the anomaly target is not independent. This remains leakage
even if the neural network never sees the raw holdout row.

**Fix:** fit climatology separately inside every temporal/spatial fold and version its exact
training support.

### 6.4 Terrain-head height semantics are not globally defined

The L3 terrain head uses an output `height` vector and `exp(-height/H)`, but the global
plan does not define whether heights are AGL, ASL, pressure-level geometric height, or
anomaly-space coordinates. A wrong convention causes terrain effects to decay at the
wrong altitude.

**Fix:** require an explicit height-reference enum in the model artifact and test the
head response at equal AGL but different terrain elevations.

### 6.5 Global pressure-level target conversion can create label seams

The plan stores pressure-level columns and converts to fixed AGL heights in the loader.
Ground clipping, interpolation choice, surface anchors, and top-level coverage vary by
location. If these choices are not identical across points, the generator learns a
conversion artifact as geography.

**Fix:** use one versioned conversion function, preserve native support masks, test seam
continuity across terrain/elevation transitions, and score interpolation error separately.

### 6.6 Quantization can damage rare tails despite small nominal error

The int16 scales are selected for ordinary values. A 0.01 K or 0.01 m/s quantization step
may be harmless for means but can affect narrow spread estimates, finite differences, and
99.9th-percentile shear after subtracting nearby levels.

**Fix:** calculate quantization error in the final target/difference/shear space, not only
per raw variable. Run FP32-versus-int16 score and tail parity tests by climate and height.

### 6.7 `sp` encoding needs a physical-range test globally

`sp` uses scale 2 Pa and offset 80,000 with int16 range. This encodes roughly 14,464–145,534
Pa, which may be adequate for Earth but must be checked against all fetched grid cells and
surface elevations. The code raises only when encoding; there is no preflight report of
where the range fails.

**Fix:** scan global min/max before the long fetch, report margin to int16 limits, and
include a decode/re-encode round-trip test.

### 6.8 Dynamic INT8/FP16 packaging can damage climate tails

The G5 gate compares aggregate CRPS and 99.9th shear, but a small aggregate change can
hide large errors in polar, mountain, ocean, or rare-convection regimes. Quantization also
may change calibration artifacts fitted to FP32 outputs.

**Fix:** calibrate and score the exact packaged model, not FP32 plus an assumed correction.
Require per-regime, per-height, worst-case limits in addition to global averages.

---

## 7. Global validation and acceptance flaws

### 7.1 `CRPSS > 0 everywhere` is statistically too strong without a defined cell size

Every location, climate group, height, month, and lead is not independently verifiable.
Requiring positive skill in every cell can select noise, while aggregate positive skill can
hide catastrophic cells.

**Fix:** define minimum support, confidence intervals, practical margins, and a finite set
of primary cells. Use a separate worst-cell guardrail and label insufficient-evidence cells.

### 7.2 Leave-continent-out and leave-climate-out tests need provenance-safe folds

A random or point-based split can leave nearby weather and static fields in both train and
test. The global plan needs folds based on geography, source lineage, climate class, and
weather episode together.

**Fix:** publish fold IDs and enforce spatial buffers, temporal embargoes, and station
exclusion in every fitted object.

### 7.3 Seed tolerance is not a statistical uncertainty interval

The plan uses seed tolerance as a gate, but seed-to-seed variation only measures one source
of model randomness. It does not quantify finite weather cases, calibration uncertainty,
station representativeness, or source revision.

**Fix:** report separate seed, block-bootstrap, station, and source uncertainties. Do not
use a seed tolerance as a substitute for confidence intervals.

### 7.4 The rotate-longitude test needs a precise invariant

Moving longitude by 180 degrees while keeping local solar hour fixed changes geography,
terrain, static fields, and possibly climate. A model should not necessarily be invariant
under this operation globally. The proposed artifact threshold is therefore ambiguous.

**Fix:** define exactly which inputs and target properties are transformed. Use symmetry
checks only where a physical symmetry exists, and do not penalize legitimate geographic
changes.

### 7.5 Reverse-latitude testing cannot simply compare raw outputs

Reversing latitude changes season, solar geometry, terrain, climate, and atmospheric
regime. A raw prediction comparison is not a valid invariance test.

**Fix:** define a season/climate-matched transformation or use this only as a diagnostic
for suspicious latitude shortcuts, not as a hard parity gate.

### 7.6 Denver G1 is not fully unseen if related western data are used

The G1 plan trains on NM/TX and uses ~15 western stations and their ERA5 columns for
calibration-transfer tests. Depending on the exact station list and static neighborhoods,
Denver may not be a clean unseen-region test.

**Fix:** freeze the Denver exclusion radius, station list, source grids, and calibration
inputs before G1. Do not use Denver or nearby Colorado data for normalization, calibration,
climatology, architecture selection, or threshold tuning.

### 7.7 `B-local` and `B-raw` need identical information budgets

The local Denver upper bound can use Denver-specific climatology, calibration, and station
information that the zero-shot model lacks. The gap is useful only if both baselines are
trained, calibrated, and scored under clearly documented and comparable budgets.

**Fix:** specify which data each baseline may use and report a data-budget table next to
skill comparisons.

### 7.8 The global final test is not independent if G6 data are sampled during development

The plan allows the latest ERA5 day available at G6. If developers inspect or use those
updates before locking G5, the final window is no longer untouched.

**Fix:** acquire and checksum the final archive at lock time, encrypt or access-control it,
and make the final script the only reader until the one-time run.

---

## 8. Operational and storage risks

### 8.1 The stated disk budget is internally inconsistent

The plan says `data/raw` is already 66–80 GB, while the global store, eight boxes, IGRA,
training artifacts, and temporary downloads must fit under a 100 GB cap. The fetcher also
writes compressed monthly NPZ files and may hold decoded arrays and `.part` files during
writes. Peak usage can exceed the steady-state estimate.

**Fix:** add a peak-storage budget including raw source, temporary files, duplicate stores,
model checkpoints, calibration artifacts, and logs. Enforce a preflight free-space check
before each month.

### 8.2 A one-month fetch failure can force an all-or-nothing rerun downstream

Monthly files are independently resumable, but no global completeness manifest tells the
converter which months are complete, valid, and compatible. A partial global store can be
mistaken for a full 1991–2025 training set.

**Fix:** require a verified manifest before training; fail if any requested month, point,
variable, level, timestamp, or holdout mask is missing.

### 8.3 File naming and coordinate metadata are insufficient for multi-region assets

`YYYY-MM.npz` plus a shared `points.npz` assumes one point set and one source configuration.
Changing region, holdout, quantization, or point selection can cause files to be reused with
incompatible metadata.

**Fix:** use region/config/content hashes in asset directories and filenames, or enforce
manifest compatibility before opening any file.

### 8.4 Global arrays may exceed memory during monthly decode

`fetch_month()` selects all points and variables for a month and calls `.compute()` before
encoding. Scaling pressure levels, variables, and 7,500 points can create large transient
arrays and multiple copies during int16 conversion and compressed NPZ writing.

**Fix:** measure peak memory for the full global point set, chunk the point dimension, and
write a streaming/chunked format rather than requiring the complete month in memory.

### 8.5 Compressed NPZ is a poor random-access training format

`np.savez_compressed` requires decompression of whole arrays and has no robust chunk/index
metadata. Global training will repeatedly decode large monthly files and may create hidden
CPU/RAM bottlenecks.

**Fix:** convert verified monthly data to Zarr or another chunked format with explicit
coordinates, masks, compression, and checksums before training.

### 8.6 Global fetch source requests have no retry/timeout policy at this layer

The global fetcher relies on the underlying store reads and Dask but has no per-month retry,
backoff, request checkpoint, or failed-variable ledger. A transient read error can abort a
long month and complicate recovery.

**Fix:** add bounded retries, structured failure logs, per-variable checkpoints, and a
resume validator that distinguishes a failed month from a valid month.

---

## 9. Priority order

### Blockers before any global training

1. Implement the NPZ-to-global-profile loader and canonical schema.
2. Fetch/store `z_sfc`, static fields, source masks, and provenance.
3. Fix Southern Hemisphere terrain weighting.
4. Validate/refill point selection after holdout exclusion.
5. Build and enforce a holdout-aware loader for all preprocessing and calibration.
6. Replace the diurnal training sample with a verified balanced design or explicitly
   restrict claims to climatology learning.
7. Create true spatial/temporal fold manifests and an untouched final archive.
8. Add global pressure-level-to-AGL conversion and support-mask tests.

### Blockers before G5 packaging

9. Validate spherical harmonics at planned degrees, poles, gradients, and precision.
10. Fit climatology/statics only inside folds and version their artifacts.
11. Evaluate area-weighted and deployment-weighted performance separately.
12. Quantization-test tails by climate, terrain, hemisphere, height, and route.
13. Run leave-station, leave-climate, leave-continent, and buffered spatial CV.

### Blockers before G6

14. Freeze the final test archive and lock access.
15. Verify every holdout ID and source lineage is excluded from every learned artifact.
16. Score the exact packaged model with route-conditional baselines and uncertainty
    intervals.
17. Report worst cells and insufficient-evidence cells, not only global averages.

No global accuracy claim should be made until the data loader, holdout enforcement,
Southern Hemisphere sampling, all-hour/time design, support masks, and independent
spatial validation are operational and tested.

---

## 10. Additional findings: pilot assumptions still in runtime and tests

A second pass shows the global extension is only partially wired in. Several runtime
modules and tests still assume the pilot region, pilot assets, or the fixed pilot
schema. Each is a place where a global build can silently fall back to pilot behavior.

### 10.1 Station/ASOS correction and scoring still use hard-coded pilot stations

`region.py` centralizes the box and station list, but `calibrate/station.py` and
`scoring/sonde.py` import `STATIONS`, `ELEV`, and the two-station ASOS flag directly.
A global run can therefore fit and score against only the two pilot balloon stations
even when the region file changes.

**Fix:** route every station, ASOS, and elevation lookup through `region.load()` (or a
global station registry), and assert at startup that the active station set matches the
active region. Fail if pilot stations are used with a non-pilot region.

### 10.2 The public API selects assets by rectangular region manifests

`api.region_assets()` chooses an asset folder from per-folder `manifest.json` rectangles.
This cannot express a single global bundle, overlapping regions, or periodic longitude,
and returns `None` outside known rectangles. A global deployment has no rectangle.

**Fix:** add an explicit global-bundle selection path with an AOA/DI applicability flag
rather than rectangular membership, and define precedence when multiple assets match.

### 10.3 `Atmosphere`/`BOX` still hard-code the pilot latitude/longitude bounds

`output/atmosphere.py` defines `BOX = dict(lat=(31.0, 34.0), lon=(-108.0, -101.0))` and
derives the trained area from the loaded profile store grid. Neither path consults the
global point registry, so the global model cannot be queried through this entry point
without code changes, and a query just outside the pilot box is rejected rather than
flagged with an applicability score.

**Fix:** replace the rectangular box gate with the planned DI/AOA flag and a global
point/grid lookup; keep a hard refusal only for truly unsupported inputs.

### 10.4 Fixed 44-height / 179-column schema is assumed across the global path

Global pressure-level data must be converted to the profile schema, but `to_physical`,
`coupled.build`, `thermo.column`, and the surface-index access all assume exactly
`4 x 44` profile columns plus three surface fields. A global schema change (added
surface wind, pressure/density targets, or different heights) breaks these silently.

**Fix:** drive every height/column access from one schema object with a version hash, and
assert the schema at each global boundary (loader, model, calibration, output).

### 10.5 Mutable global feature state is more dangerous at global scale

`features.FEATURES` and `sample.RH_TARGET` are process-global and mutated on load. A
global pipeline that loads multiple regional/global datasets or alternates models in one
process can silently build features in the wrong order or invert humidity incorrectly.

**Fix:** carry feature/target schema on explicit objects; forbid implicit global mutation
in any multi-model or multi-region process, and test alternating loads.

---

## 11. Additional findings: global coordinate and grid correctness

### 11.1 ERA5 latitude index rounding is not bounds-checked globally

`fetch_global.to_grid()` computes `round((90 - lat) / 0.25)` and `round(lon % 360 / 0.25)
% 1440`. The longitude wraps safely, but the latitude index is not clamped to `[0, 720]`.
A latitude of exactly -90 gives index 720 (valid), but any floating error slightly beyond
±90, or a bad station coordinate, yields an out-of-range row index with no check.

**Fix:** clamp and validate latitude indices to `[0, 720]`, reject coordinates outside
±90/±180 before indexing, and test the exact poles and the date line.

### 11.2 Nearest-ERA5-point selection ignores grid-cell-center offset

`to_grid()` rounds to the nearest 0.25-degree node assuming nodes at exact multiples of
0.25 starting at 90/0. If the store's coordinate convention differs (cell centers vs
edges, or a half-cell offset), every global point is shifted by up to half a cell.

**Fix:** derive indices from the store's actual coordinate arrays (searchsorted/nearest on
the real `latitude`/`longitude` values), not from an assumed analytic grid. Assert the
selected coordinate equals the requested coordinate within tolerance.

### 11.3 Great-circle distance uses `arccos`, which is unstable for small separations

`gc_deg()` uses the spherical law of cosines (`arccos`), which loses precision for small
angles — exactly the sub-degree range used for the one-degree holdout exclusion. Points
just inside the radius can be misclassified as outside.

**Fix:** use the haversine formula (or chord distance on unit vectors) for the holdout and
any near-neighbor test, and add a test at sub-degree separations.

### 11.4 Terrain relief uses a 5x5 window that is not equal-area

`terrain_weights()` takes a fixed 5x5 (1.25-degree) window in grid space. Near the poles a
1.25-degree longitude span is a tiny physical distance, so "relief" is computed over a much
smaller area at high latitude than at the equator, biasing terrain selection by latitude in
addition to the sign bug already noted in 2.1.

**Fix:** use a physical-distance neighborhood (scaled by `cos(latitude)` in longitude) or an
equal-area grid (HEALPix) for relief, and report the relief-window physical size by latitude.

### 11.5 Elevation-from-pressure proxy is biased by climate, not just noise

`terrain_weights()` estimates elevation as `8000 * ln(101325 / sp)` from a 24-field mean.
This conflates persistently low-pressure climates (storm tracks, polar lows) with high
terrain, so some ocean/storm regions can be mistaken for relief and vice versa.

**Fix:** use an actual orography/geopotential field for terrain selection; keep the pressure
proxy only as a cross-check with a documented error by climate zone.

---

## 12. Additional findings: holdout, time, and provenance (confirmed in code)

### 12.1 The holdout file has no loader-level enforcement in this tree

`global_holdout.toml` is consulted only by `fetch_global.points()`. The plan's required
"loader check that refuses these places and dates >= 2026-07-01 unless TEMPEST_FINAL_GLOBAL"
is not present in the reviewed code. Any other reader (calibration, scoring, static-field
fitting) can still touch holdout locations or 2026 dates.

**Fix:** implement a single enforced holdout/date guard used by every data entry point, with
an audit log and a test, before any global fetch or fit beyond `fetch_global`.

### 12.2 Holdout radius is applied only to final points, not to source neighborhoods

`points()` removes points within `radius_deg` of holdouts, but the ERA5 grid cell a holdout
falls in — and the cells used to interpolate its static fields or climatology — may still be
fetched for nearby training points. The one-degree point gap does not guarantee the holdout
grid cell is absent from training.

**Fix:** additionally exclude the holdout's own source grid cells and the interpolation
neighborhood from training fetch, or document that holdout independence is point-level only.

### 12.3 `held_igra` is stored but not re-validated on reuse

`points()` writes `held_igra` into `points.npz`, but reruns load the cached file and never
re-check it against the current `global_holdout.toml` or station list. If the holdout file is
edited after the first fetch, the store silently keeps the old holdouts.

**Fix:** store the holdout-file hash in `points.npz` and refuse reuse when it changes; re-run
`pick_igra_holdouts` and compare.

### 12.4 Diurnal hour schedule repeats with a fixed 24-day period

`steps()` sets `UTC hour = (days since 1991-01-01) mod 24`. Because the period is exactly 24
days, every calendar date tends to pair with the same few UTC hours across years, and the
day-of-week-like 24-day cycle can alias with the ~27-28 day lunar/synoptic and monthly
structure. Local solar hour coverage per site is therefore not uniform within a season.

**Fix:** use a schedule co-prime with the main calendar/synoptic periods (or a seeded balanced
assignment) and verify, per latitude band and season, that UTC and local-solar-hour coverage
is approximately uniform.

### 12.5 Month ordering can leave a climatologically skewed partial store usable

`month_order()` fetches 2011-2025 first, then 2001-2010, then 1991-2000. A partial store is
"already usable," but a model trained on only the recent third sees a different climate (trend,
ENSO phases, instrument era) than the full 1991-2025 target.

**Fix:** mark any partial store with its exact year/month coverage; forbid training a model
that claims 1991-2025 skill on a recent-only subset; report the covered climate distribution.

### 12.6 `--test` monkeypatches a module global, which is fragile

The global fetcher replaces `steps` via `global steps` inside `main()` for the `--test` path.
This mutates module state and is easy to leave inconsistent if the function is imported
elsewhere, and it is not covered by a reset in a long-running process.

**Fix:** pass the step function (or a `max_steps` argument) explicitly rather than reassigning
a module global.

---

## 13. Updated priority additions

- **New blocker:** route all station/ASOS/elevation lookups through the region/global
  registry (10.1) and add the enforced holdout/date guard (12.1) before any global fit.
- **New blocker:** derive ERA5 indices from the store's real coordinates (11.2) and use
  haversine for holdout distance (11.3) before trusting the point set.
- **High priority:** fix the equal-area relief window (11.4) and replace the pressure-based
  elevation proxy with real orography (11.5), together with the Section 2.1 sign fix.
- **High priority:** validate `points.npz` against the holdout and config hashes on every
  reuse (12.3, 1.6).
- **Before claims:** verify the diurnal schedule gives uniform local-hour coverage (12.4)
  and that partial stores are not used for full-period skill claims (12.5).