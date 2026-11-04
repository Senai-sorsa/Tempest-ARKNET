# GPT accuracy suggestions

These are suggestions to raise the **accuracy and honesty** of the Tempest-ARKNET
system, grounded in the current [docs/PLAN.md](docs/PLAN.md),
[docs/PHASE1.md](docs/PHASE1.md), [docs/research-notes.md](docs/research-notes.md),
and the code in `tempest/generator/`. They are meant to complement, not repeat,
[suggestions-copoilet.md](suggestions-copoilet.md): where that file covers the
validation protocol and the ship-gate philosophy well, this file focuses on
concrete method, data-pipeline, and code-level issues that most directly move the
numbers in the acceptance table.

Every item is a hypothesis to test under the plan's walk-forward / spatial-block
protocol, not a claimed improvement. Keep a change only when its named
out-of-fold check supports it.

---

## A. Data and vertical-grid accuracy (fix before any model learns)

A systematic grid/interpolation/units error is the single most dangerous source
of silent inaccuracy, because every downstream calibration layer will quietly
absorb it and then transfer the bias to new sites. Address these in phase 1.

1. **Interpolate wind in height but keep shear-preserving endpoints.**
   PHASE1.md §3 uses "linear in ln(height) below 100 m, linear above". Linear
   interpolation onto 44 fixed heights smooths the very shear the product is
   supposed to preserve. Before locking this in, measure (against IGRA at native
   resolution) how much shear the 44-level reprojection loses versus the raw
   sounding, per height band. If the loss is material near the boundary layer and
   jet, prefer a shape-preserving scheme (monotone PCHIP in height for T/RH; keep
   the log-law only inside the surface layer). Record the reprojection loss as a
   known error budget so phase 6 does not try to "correct" it with inflation.

2. **Validate the CDS/Earthmover seam per variable and per season, not just once.**
   The §6 seam check compares one mean T difference between 950 and 925 hPa. Seam
   artifacts in **wind** (u, v) and in RH are more likely to matter for shear and
   density than the T step, and they can be seasonal (boundary-layer height
   varies). Add seam diagnostics for u, v, and RH across the 950/925 boundary, by
   month, and fail the phase if any component shows a step beyond a pre-set
   threshold.

3. **Match ERA5 to the IGRA launch time and drift, not just the nominal hour.**
   A radiosonde drifts tens of km and takes ~1–2 h to reach the stratosphere, so a
   12Z "sounding" at 15 km is not a 12Z point sample. Before using IGRA to fit the
   ERA5-smoothness correction (phase 6), interpolate ERA5 to the sounding's actual
   release time and, where the derived file provides it, approximate the balloon's
   horizontal drift. Otherwise the fitted "ERA5 error" will contain a
   representativeness term that is really a sampling mismatch, and it will be wrong
   at the heights (upper levels) where drift is largest.

4. **Treat RH near saturation and at low T carefully.**
   RH from `t2m`/`d2m` via Magnus, and ERA5 `r`, both behave badly near 100 % and
   at cold upper levels. Clipping RH to 0–105 % (the §6 physics check) can bias the
   mean upward near saturation. Consider carrying specific humidity `q` (already in
   the store) as the primary moisture variable for the hypsometric/density
   calculation, and derive RH only for reporting. This also removes a nonlinear
   T-dependence from the variable the density depends on.

5. **Verify the geometric-height and above-ground conversion end to end.**
   The `h = R·Z/(R−Z)` step and the `agl = h(z) − h(z_sfc)` subtraction are exactly
   where a sign or reference-surface error hides. Add a unit test that, for a known
   profile, recovers hydrostatic consistency: integrating the hypsometric equation
   from the surface p and T profile should reproduce the stored geopotential
   heights to within a tight tolerance. A failure here is a height-reference bug,
   not an ERA5 limitation.

---

## B. Analog sampler accuracy

6. **Blend the four neighbours in the right space, per variable.**
   PLAN.md step 2 bilinearly blends the four grid neighbours' profiles "same-time".
   Averaging four columns **reduces variance and smooths shear** — the opposite of
   the design goal. Two safer options to test: (a) pick the single nearest grid
   point and apply only the elevation correction (no spatial smoothing of the
   profile shape), keeping the blend for surface scalars only; or (b) blend in a
   way that preserves second moments (e.g. blend the mean but draw the deviation
   from one chosen neighbour). Compare variogram score of each against the current
   four-point average on held-out years.

7. **Make the ±7-day / ±1-h window seasonally adaptive.**
   A fixed ±7-day window mixes early-June and late-June regimes that can differ
   (monsoon onset near the pilot box). Test a window that is narrower in the fast-
   changing shoulder seasons and the monsoon transition, chosen by CRPS on
   training folds, rather than one global ±7 days. Report the effective sample
   size so the window is not shrunk below what the tails need.

8. **Report and enforce effective sample size for the 99.9th percentile.**
   The plan itself flags that ~1,500 analogs are "thin for 99.9th". Make this
   quantitative: for every query, compute the effective number of independent
   analog years (from the actual draw weights after the per-year cap and any
   kernel), and refuse or down-label a 99.9 % band when that number is below a
   pre-set floor. This turns the known tail limitation into an explicit,
   per-query honesty flag instead of a silent over-confident band.

---

## C. Driver shift and long-range honesty

9. **Guard the WWV forecast against leakage before using ONI + WWV.**
   The measured ONI + WWV skill gain (PHASE1.md §5) is computed from *observed* WWV
   aligned to the ENSO target — but at a future issue date WWV itself must be
   forecast. As suggestions-copoilet.md §4 notes, the regression does not specify a
   future WWV. Concretely: build and validate a leakage-free WWV forecast (or use
   only the WWV value known at issue time with its own persistence decay), and
   re-measure the 9–18-month skill with *that* forecast substituted in. If the gain
   collapses once WWV must itself be predicted, drop future WWV and keep only ONI.
   Do this measurement before phase 4 relies on the headline numbers.

10. **Propagate driver-forecast error into the shift as a distribution, not a point.**
    Step 4 already draws ONI_Y and QBO_Y from their forecast distributions, which is
    right. Add the regression's **parameter** uncertainty (coefficient covariance),
    not only the residual spread, because with ~35 years the slope itself is poorly
    determined and that uncertainty widens with lead. Also draw the trend
    extrapolation error from the fitted slope's standard error, not a fixed value.
    This keeps long-lead bands honestly wide rather than falsely sharp.

11. **Cross-check the linear driver shift against a "no-shift" null at every lead.**
    Make plain resampled climatology (no shift) a permanent reference in every fold
    and lead band, printed next to the shifted sampler. Beyond the measured skill
    horizon (ONI ~12–18 mo, QBO ~2 yr) the shift must *not* degrade CRPS or
    calibration relative to the null. If it does in a band, that band falls back to
    the null automatically. This operationalizes the "CRPSS ≥ 0 at every lead"
    acceptance row.

---

## D. Near-term pool accuracy

12. **Calibrate against ERA5-as-truth and IGRA-as-truth separately for days 0–15.**
    The near-term members are verified against reanalysis in early phases and
    radiosondes later. Because ERA5 is smoother than IGRA, a pool tuned to match
    ERA5 will look under-dispersed against balloons. Fit and report near-term
    calibration against both truths, and use the IGRA-referenced spread for the
    shipped bands so the days-0–15 product is not quietly under-dispersed at launch
    altitude.

13. **Account for the WeatherNext-2 6-hourly / 00Z-12Z sampling when verifying.**
    WN2 is 6-hourly and built from 00Z/12Z runs; the launch window is 08–20 local.
    Interpolating members to an off-synoptic local hour adds error that is easy to
    mis-attribute to the model. When computing pool weights, verify at the member's
    native valid times and interpolate only at query time, so the weights reflect
    model skill, not interpolation artifacts.

14. **Keep the day 10–15 ensemble→analog blend weight data-driven, not linear.**
    PLAN.md uses a weight "moving linearly from ensemble to analogs" over days
    10–15. Fit the crossover from the backtest (the lead where analog CRPS first
    matches ensemble CRPS, per variable and height band) rather than assuming a
    straight line. The crossover is almost certainly different for low-level wind
    (ensemble loses skill fast) than for jet-level wind.

---

## E. Calibration and joint-shape accuracy

15. **Verify that whole-cloud conformal scaling does not break calibration per height.**
    S7 scales each draw's deviation from the sample mean by one conformal factor per
    (variable, height band, lead band), to preserve joint shape. A single scalar
    cannot fix a cloud that is simultaneously too narrow at one height and too wide
    at another. Measure per-height PIT **after** the whole-cloud scaling, not only
    the aggregate coverage, and if per-height calibration regresses, prefer the
    rank-reorder-after-marginal-calibration path (which the plan already has) over
    the single scaling factor in that band.

16. **Check conformal coverage under serial dependence explicitly.**
    Online conformal's guarantee assumes exchangeability; weather cases are serially
    correlated and non-stationary. Report coverage on **blocks of independent
    weather episodes** (e.g. separated by several days) and over rolling windows, so
    a nominal 99.9 % band that only holds within-episode is caught. Label any band
    whose block-coverage cannot be resolved by the available independent cases as
    "unverified" rather than reporting a point estimate.

17. **Fit GPD tail threshold and shape with stability diagnostics, per variable.**
    The plan bounds ξ to [−0.1, 0.25] and shares it per variable. Add the standard
    EVT diagnostics inside each fold (mean-residual-life and parameter-stability
    plots across candidate thresholds) and require the chosen threshold to be stable
    across held-out years before the GPD tail ships in a band. A mis-chosen
    threshold is worse than no tail extension.

---

## F. Generator (`tempest/generator/`) accuracy

18. **Train on more than m = 4 samples per row, or quantify the estimator noise.**
    `DEFAULTS["m"] = 4`. The energy-score estimator is unbiased in expectation, but
    its pairwise-spread estimate is noisy with only four samples. Do not assume the
    resulting error must be under-dispersion: measure the direction and magnitude
    across repeated seeds. Test larger m (for example 8–16) at pilot scale and
    compare validation calibration, tail behavior, and profile scores—not just ES.
    If m must remain small, use an independently validated spread diagnostic rather
    than adding an unverified variance penalty.

19. **Standardize the energy-score target channels by climatological sd, consistently.**
    The phase 2 harness standardizes each variable by its climatological sd before
    the energy score (PHASE1.md §7). The training loss in `train.py` standardizes the
    *target* by its training mean/std per element (`tm`, `ts`), which is a different
    weighting (per-element, not per-variable). Make the loss weighting match the
    evaluation metric's weighting, or the generator will optimize a different
    objective than the one it is scored on, and will look worse than it should on the
    harness.

20. **Score the generator in difference space on shear directly.**
    The outputs are surface value + 43 neighbour differences, which is good. Ensure
    the **evaluation** (not just the loss) uses the variogram score on the
    reconstructed shear layers (as the harness intends) and reports the
    99.9th-percentile neighbour-difference error, because the energy score on the
    full standardized vector can be dominated by the many mid-profile channels and
    hide a bad boundary-layer or jet shear.

21. **Make the walk-forward fold boundary leak-proof in the data builder.**
    `train.py` selects validation as `year > year.max() - val_years` and normalizes
    from training rows only — correct. But the **target** is "station-corrected
    profiles", and the station correction (S4 quantile map) is itself fitted on data.
    When building `pilot.npz` per fold, refit the station correction inside the fold's
    training years only, so the generator's targets do not carry information from the
    validation years. Document this in the phase-6A data-builder spec.

22. **Add a hard fallback to analogs when generator inputs are out of training range.**
    Engression extrapolates "a little" beyond the training range by design, but 2027–
    2029 drivers (trend, ONI, QBO) can sit well outside 1991–2025 combinations. Detect
    when a driver draw falls outside the convex hull (or a per-input quantile band) of
    the training set and route that draw to the analog sampler instead of trusting the
    extrapolation. Log the fraction of draws that fell back, per query, as an honesty
    diagnostic.

---

## G. Cross-cutting

23. **Carry a single, explicit error budget per variable and height band.**
    Many separate corrections (reprojection loss, ERA5 analysis error, ERA5-smoothness
    inflation, GPD tails, conformal scaling) each touch spread. Maintain one ledger of
    what each layer is responsible for, so two layers do not both try to fix the same
    under-dispersion (double-counting) or both assume the other handles the tails
    (gap). This is a bookkeeping discipline, but it directly prevents the most common
    calibration drift.

24. **Add a physical-consistency acceptance check, not just statistical scores.**
    Beyond CRPS/ES/VS, add a thermal-wind-balance residual and a hydrostatic residual
    as diagnostics on the generated/sampled clouds. Analogs pass by construction;
    the generator and any correction layer can violate these. A draw that scores well
    but is not in approximate thermal-wind balance is physically wrong and should be
    flagged before it reaches a dispersion study.

---

## H. Additional implementation findings

25. **Do not silently discard high-altitude rows with missing upper levels.**
    `build_dataset.py` drops every row containing any NaN, while `to_heights.py`
    produces NaNs whenever 18 km lies above the highest usable pressure level.
    Missingness is correlated with site elevation, pressure and weather regime, so
    this can bias the training distribution toward profiles with complete upper-air
    coverage. Add a per-row valid-height mask and train/evaluate each supported
    height band with its own eligibility rule, or fill only where a physically
    justified source exists. Never turn missing upper-air observations into a
    climatological value without scoring the resulting bias.

26. **Store and use the actual grid elevation as a separate feature.**
    In `build_dataset.py`, both `elev_site` and `elev_grid` are currently populated
    with `elev[p]`; the profile store does not appear to retain the ERA5 grid-point
    elevation separately. This prevents the generator from learning the site-to-grid
    transfer that the feature schema claims to provide and makes the terrain-transfer
    experiment impossible to evaluate. Persist `z_sfc` for both the site and each
    source grid point, pass them separately, and test whether the elevation
    difference improves spatial-block performance.

27. **Use pseudo-real-time predictor histories in every long-lead backtest.**
    Training rows currently receive the observed ONI, WWV and QBO values for their
    target timestamps. A future query receives forecasts or draws available at the
    issue date. If the model is scored using observed target-time drivers, its
    apparent skill is overstated. Construct hindcast features using only information
    available at each historical issue date, including driver forecast error and
    publication lag, then compare them with the idealized-observed-driver upper
    bound.

28. **Encode the forecast issue time explicitly and avoid target-time conditioning.**
    The feature vector contains target day, solar hour, year and climate indices, but
    not the issue date or lead. The same target profile can therefore be represented
    identically at 1 day and 36 months lead even though the uncertainty and available
    predictors differ. Either train separate lead-band models or include lead and
    issue-time features, with calibration and validation still performed separately
    by lead band. Confirm that no target-time index is accidentally used for a
    historical query.

29. **Make generator validation deterministic and ensemble-based.**
    `train.py` evaluates a fresh random set of only `m=4` samples at each validation
    checkpoint. Validation ES therefore contains Monte Carlo noise, which can select
    the wrong checkpoint or trigger early stopping. Use fixed validation noise seeds,
    several independent noise batches, and a larger evaluation sample count. Save
    the checkpoint selected by the same multi-sample scoring procedure used in the
    falsification report.

30. **Constrain or transform generator outputs before reconstruction.**
    The MLP emits unconstrained surface values and differences; after cumulative
    summation it can produce negative pressure, RH outside physical bounds, or
    implausible temperature inversions. Test bounded/positive parameterizations for
    RH, pressure and density, or apply a physically checked repair layer whose effect
    is measured out of fold. Re-score after repair in profile, shear, calibration and
    thermal-wind metrics; a repair that improves marginal RMSE but damages joint
    structure should be rejected.

31. **Test whether cumulative differencing amplifies small low-level errors.**
    `from_diff()` reconstructs every level by cumulative summation. A small systematic
    bias in each neighbour difference can therefore grow with height, while the
    energy score in normalized target space may not expose it. Report error and
    calibration both in difference space and reconstructed level space, including
    cumulative drift versus height. Compare this representation with anchored
    differences, DCT coefficients, or a zero-sum correction as a gated experiment.

32. **Separate random row sampling from event-level sampling.**
    The training builder samples point-hour rows uniformly. This overrepresents
    persistent weather regimes and gives the generator many nearly duplicate rows,
    while rare severe shear episodes remain underrepresented. Stratify or reweight
    by season, independent weather episode, shear magnitude and site, then undo the
    sampling weights in the proper scoring objective. Keep an unweighted test set so
    improvements in rare-event metrics do not hide degraded climatological skill.

33. **Add an issue-time data/version audit to every forecast record.**
    ERA5 and index feeds are revised, and the current pipeline can be rerun with
    newer files. Store source versions, retrieval timestamps, valid-time cutoffs,
    interpolation method, calibration-fit interval and model commit with each
    backtest and output. Reproducible hindcasts are necessary to distinguish a real
    accuracy gain from revised observations or accidental future data.

34. **Test spatial interpolation against nearest-grid retrieval with a fair baseline.**
    The plan's four-point bilinear profile blend may reduce variance and smooth
    boundary-layer shear, while nearest-grid retrieval can add representativeness
    noise. The existing recommendation flags this, but make the comparison include
    elevation correction, station distance, and the same calibration budget. Evaluate
    both marginal scores and cross-height dependence on held-out stations; do not
    choose solely from pointwise RMSE.

35. **Use an explicit model for analysis-time uncertainty in past-date products.**
    The past-date path adds fixed starting errors and a launch-slip window, but these
    components can overlap and may not be independent. Estimate their covariance by
    comparing ERA5 analyses with IGRA at matched times, condition it on height and
    weather regime, and test whether adding both double-counts uncertainty. The
    uncertainty product should distinguish uncertainty about the analysis from
    uncertainty caused by the requested launch time.

36. **Add cross-variable physical checks to every calibration stage.**
    Existing checks mainly constrain individual variables and profile scores. After
    station transfer, tail expansion, rank reorder, reconciliation and generator
    sampling, test RH/T consistency, pressure-density consistency, nonnegative
    absolute humidity, and wind/T vertical relationships. Run these checks before
    and after each stage so the first stage that creates an implausible relationship
    can be identified rather than hidden by later calibration.

## I. Ingestion, scoring, and evaluation foundations

37. **Implement the scoring harness before fitting candidate models.**
    `tempest/scoring/` currently contains only `__init__.py`, while the plan depends on CRPS, energy score, variogram score, PIT and coverage for model selection. Implement these metrics first with analytical fixtures, including perfect ensembles and known normal forecasts. Freeze the score definitions, standardization, member axis and missing-value policy in a versioned report schema.

38. **Validate downloaded files and record immutable source metadata.**
    Treating a completed HTTP response or Zarr write as sufficient can admit truncated or revised data. Validate byte counts or checksums where available, verify IGRA archives, inspect Zarr dimensions and record URL, retrieval time, source revision, byte count and date range beside every artifact.

39. **Make index parsing calendar-aware and fail closed.**
    `read_qbo()` relies on a fixed line offset and `read_oni()` assumes every row has four valid fields. Add tests for header changes, duplicate months, missing months, malformed values, sentinels, leap/year boundaries and ONI seasons crossing New Year. A one-month timestamp shift contaminates every driver evaluation.

40. **Separate observed target-time indices from issue-time-available indices.**
    `indices.at()` returns values for the target month and `build_dataset.py` uses them directly. Store observation availability dates and construct historical features by truncating data at each issue time. Missing or unreleased values must trigger a documented fallback or exclusion, never silent forward filling.

41. **Trim and assert the actual profile date range after chunk-aligned reads.**
    The Earthmover fetch intentionally starts before 1991 at a chunk boundary, but the profile conversion does not explicitly trim to 1991–2025 before writing. Select the exact date range and assert first/last timestamps, hourly cadence, uniqueness and expected calendar coverage.

42. **Test coordinate orientation and longitude conventions with real-store fixtures.**
    Assert latitude/longitude monotonicity, expected point ordering, correct 0–360 to −180..180 conversion, no duplicate longitudes and correct inclusion of box edges. A reversed or empty slice should fail loudly rather than produce geographically wrong training data.

43. **Test solar-window boundaries numerically, including fractional times and leap days.**
    `solar_hour()` uses only integer UTC hours and discards minutes. Compute solar time from the full timestamp, define boundary inclusivity, and test 06:00/21:00 edges, longitude sign changes, leap day and fractional-hour queries.

44. **Use independent frozen benchmark cases for every comparison.**
    Existing generator tests use toy data and do not verify real-profile calibration or tails. Create a small versioned benchmark of held-out profiles and soundings with fixed forecast samples. Every analog, calibration and generator change should report against it.

45. **Quantify uncertainty in score differences with blocked resampling.**
    Adjacent hourly rows and soundings are dependent. Report paired confidence intervals by weather episode, year and station, and require gains to exceed a predeclared practical margin and uncertainty before routing away from the analog baseline.

46. **Define missing-data handling centrally for all competitors.**
    The builder drops nonfinite rows, while later scorers may use different masks or imputations. Define masks, valid height bands, imputation rules and case eligibility centrally. Score all methods on identical cases and report coverage of difficult profiles.

47. **Add station-distance and representativeness baselines.**
    Compare nearest-grid, bilinear-grid and station-climatology baselines stratified by distance, terrain and launch time before fitting station corrections. This distinguishes transferable correction skill from effects specific to the two pilot sites.

48. **Freeze fold definitions and preprocessing manifests.**
    Save each fold’s timestamps, stations, candidate IDs, preprocessing statistics and random seeds. Refitting inside folds remains required, but the exact fitted inputs must be auditable and reproducible.

## J. CDS and profile-assembly safeguards

49. **Generate valid calendar days for each CDS request.**
    `fetch_cds.py` requests days 01–31 for every month, including invalid dates. Generate actual month lengths, including leap years, and test February and 30-day months. A rejected month can remove precisely the seasonal cases needed for calibration.

50. **Count every nonterminal CDS status against the in-flight limit.**
    The fetcher counts only `accepted` and `running`; queued or service-specific states may permit excessive submissions. Normalize remote statuses and count every submitted request that still occupies capacity.

51. **Validate each downloaded GRIB before marking a month complete.**
    Inspect variables, eight pressure levels, valid calendar days, 24 hourly times, spatial bounds, units and record count with eccodes/cfgrib. Record a checksum and validation result before renaming the `.part` file.

52. **Check ordering and duplicate timestamps when merging sources.**
    Normalize dimension names, units and coordinate order explicitly; sort pressure and time once; assert one value per point/time/level. Duplicate or mismatched timestamps can create artificial vertical steps.

53. **Make the boundary-layer fallback explicit.**
    `open_raw()` raises `NotImplementedError` whenever a CDS GRIB exists, so the planned 21-level product cannot currently be produced. Until implemented, fail before writing a complete-looking profile store and mark the 13-level path as provisional.

54. **Validate surface pressure against the interpolated profile.**
    Compare surface pressure with pressure implied by the lowest valid level and hypsometric integration. Flag impossible ordering or large discontinuities to catch wrong geopotential units, level order and ground clipping.

55. **Preserve provenance for every profile source and transformation.**
    Store whether each level came from Earthmover, CDS, an anchor or interpolation, along with source time and grid elevation. Stratify errors by source to identify seam, anchor or extrapolation problems.

56. **Do not use the same sounding to tune and validate a station correction.**
    Split IGRA by complete sounding episodes and hold out time blocks or stations when selecting quantile maps, GPD parameters and inflation. Level-wise random splits will overstate transfer accuracy.

## K. Product-definition and fail-closed issues

57. **Implement and independently test the CDS merge before claiming the planned vertical resolution.**
    `to_heights.open_raw()` deliberately raises `NotImplementedError` whenever a CDS GRIB exists. The current profile path therefore cannot use the eight boundary-layer levels specified by the plan; it either fails once the fill is present or runs provisionally on the coarse 13-level source. Implement the merge with a small known GRIB fixture, compare the merged profile against a direct CDS read, and make the output metadata state clearly whether the profile is provisional or complete.

58. **Produce the pressure and density fields promised by the product contract.**
    The plan says pressure and density at height follow from temperature and humidity using the hypsometric equation, but `to_heights.py` currently stores only `u`, `v`, `T`, `RH` and surface pressure. Add pressure/density derivation—or explicitly defer it—and test hydrostatic and moist-air consistency against ERA5 pressure/geopotential. Do not let downstream consumers infer these fields differently from the forecast engine.

59. **Define civil-local time, solar time and DST as separate concepts.**
    The query contract uses local time, while storage and training use solar hour (`UTC + longitude/15`). These are not interchangeable, especially across time zones and daylight-saving transitions. Use an IANA timezone lookup for civil-local queries, convert to UTC with an explicit date-aware offset, then derive solar time separately for analog matching. Add tests around DST changes, time-zone boundaries and sites near the box edges.

60. **Use exact timestamps, not integer UTC hours, for query matching and verification.**
    The current solar-hour helper uses only `DatetimeIndex.hour`, discarding minutes and seconds. This can place a 05:59/06:01 solar-time case on the wrong side of the launch-window boundary and introduces avoidable timing error in radiosonde comparisons. Preserve timezone-aware timestamps through ingestion, define the interpolation policy for off-hour queries, and test it at the window edges.

61. **Fail closed on incomplete or invalid profile blocks.**
    `to_heights.py` records a block as done after writing it, but there is no post-write readback or finite-value/coordinate assertion before the marker is appended. Validate the written region, expected dimensions, time coordinates, source coverage and NaN mask first; write `done.txt` only after those checks pass. A partial Zarr write must be resumable, never silently treated as complete.

62. **Reject invalid generator checkpoints instead of silently routing with them.**
    In `train.py`, a NaN validation score can prevent `best_state` from being populated, and the sampler has no explicit check for that condition or for nonfinite normalization statistics. Require a finite best score, finite state tensors and finite `cm/cs/tm/ts` before saving or loading a checkpoint. Record the fold, data hash and validation score in the checkpoint metadata.

63. **Separate model uncertainty from observation and analysis uncertainty in evaluation.**
    The generator is trained on one realized ERA5 profile per row, while the shipped product also adds ERA5 analysis error and radiosonde-derived corrections. Score these layers separately and together. Otherwise a model can appear better simply because uncertainty was added after scoring, or appear worse because observation error was counted twice.

64. **Define a common vertical support and top-of-profile policy.**
    The product extends to 18 km, but pressure-level coverage depends on terrain and the available top level. Establish a per-query maximum supported height and make the output explicitly indicate clipped levels. Do not compare an 18-km score for one site with a 14-km score for another as if they were the same target; stratify acceptance metrics by supported height.

65. **Test the requested-height interpolation against native-level verification.**
    A model can score well after both forecast and sounding are projected onto the same 44 levels even if the interpolation method erases errors. Retain native IGRA levels and compare interpolation residuals separately. Report scores both on the common grid and on height bands where observations provide direct support.

66. **Add a density/ballistic sensitivity metric to model selection.**
    Component-wise T/RH scores do not directly measure the quantity that affects dispersion. Propagate each sampled thermodynamic profile through the same hypsometric/density calculation used by the eventual flight model and score density, scale height and integrated density-column error. Use this as a guardrail, not as a replacement for proper probabilistic profile scores.

## L. Sampling, contract, and release safeguards

67. **Refill sampled training rows after finite-value filtering.**
    `build_dataset.py` samples from all solar-window rows and only later drops rows with nonfinite targets or features. The retained distribution can therefore vary with missingness; if upper-level coverage correlates with season, elevation or weather, generator training is biased. Build the finite-value mask before sampling, or refill until the requested count is reached, and report selection rates by site, month, height support and regime.

68. **Separate deterministic past-date lookup accuracy from uncertainty calibration.**
    Define whether the deterministic target is the ERA5 analysis at the requested valid time, the nearest stored profile, or a launch-slip distribution. Score exact lookup and uncertainty around lookup separately so a wider band cannot hide a timestamp-selection error.

69. **Version the output contract and validate TOML/sample consistency.**
    Verify that the sample array's variable order, height order, units and count agree with TOML means and standard deviations recomputed from the samples. Include schema version, supported maximum height, timezone interpretation, source route and calibration version.

70. **Add deterministic replay tests for the complete query path.**
    Freeze local fixtures for a past-date, near-term and long-range query. With a fixed seed and frozen inputs, require identical candidate IDs, driver draws, dimensions and summary statistics across runs. Changing only the seed should change samples but not the fitted mean, route or metadata.

71. **Make README status and acceptance claims machine-verifiable.**
    The README currently describes a complete workflow while the scoring harness and CDS merge remain unfinished. Add readiness flags for each phase and link claims to tests or report artifacts. Do not advertise radiosonde calibration, pooled near-term members or 44-level completeness until their stated gates pass.

72. **Download every raw field required by the profile converter.**
    `to_heights.open_raw()` opens `z_sfc`, but `fetch_earthmover.py` does not include `z_sfc` in its `SINGLE` download list. A fresh pipeline therefore fails before profile construction with a missing raw store. Add `z_sfc` to the fetch list and assert that every required raw variable exists before processing. Keep a fixture that runs the fetch manifest against the converter's required-variable list.

73. **Handle latitude and longitude coordinate direction explicitly.**
    `fetch_earthmover.py` uses fixed `.sel()` slices whose behavior depends on coordinate ordering, while `to_heights.py` assumes a particular point ordering when flattening latitude and longitude. Detect whether each coordinate is ascending or descending, construct the appropriate slice, and assert the selected bounds and point count. A valid but empty or reversed selection can silently produce wrong spatial training data.

74. **Invalidate stale completion markers when inputs or code change.**
    `to_heights.py` trusts `done.txt` by block index only. If raw data, interpolation code, height grid or source date range changes, old markers can cause blocks from an earlier product to be skipped. Store a manifest containing input fingerprints, code/config version, coordinate hash and height-grid hash; refuse resume when the manifest does not match.

75. **Verify Zarr regions after interrupted writes and before reuse.**
    A process can finish a region write but fail before the marker, or write a marker after an incomplete/incorrect region. On startup, validate every marked block by reading its coordinates, dimensions, finite-value mask and a checksum/sample of values. Recompute invalid blocks rather than trusting marker count alone.

76. **Assert that the downloaded Earthmover subset contains the intended time range.**
    Chunk-aligned reads intentionally start before 1991, but the fetcher also limits by chunk count when `--years` is used and does not write a manifest of the actual selected range. Record and validate the first and last raw timestamps, cadence, duplicate count and requested end boundary before downstream conversion.

77. **Check vertical monotonicity after every source merge, not only before interpolation.**
    Pressure levels from Earthmover and CDS can have different coordinate order or duplicate metadata. Assert that pressure decreases with geometric height, geopotential is finite and strictly ordered above ground, and no duplicate level/time coordinate survives the merge. Reject the block before interpolation if these checks fail.

78. **Preserve source quality flags and missing-value semantics.**
    Raw reanalysis fields may contain fill values, masked values or source-specific validity metadata. Convert them to explicit NaNs only after checking units and valid ranges, and retain a per-field quality mask. Do not let a fill value become a plausible temperature, wind or humidity observation that is later learned as atmospheric structure.

79. **Reconcile the generator output dimension and surface-variable contract.**
    The documented generator output is described as 181 values, but `build_dataset.py` currently creates `4 * 44 + 3 = 179` targets: four profile variables plus `t2m`, `sp` and `rh2m`. The plan separately promises surface 10 m wind, while the implementation relies on the first profile wind value and does not store `u10/v10` as target surface fields. Define one canonical schema, generate names from that schema, assert the expected dimension at dataset creation and checkpoint load, and add a round-trip test from target vector to output TOML/profile arrays.

80. **Do not treat the 10 m profile anchor as equivalent to a 2 m surface field.**
    The first wind profile level is 10 m, while temperature and RH are anchored at 2 m and then interpolated to 10 m. The generator's surface fields therefore have mixed reference heights. Label every target with its physical height and test that reconstruction does not accidentally interpret `u_sfc` as 2 m or `t2m` as the 10 m profile value. This is especially important when comparing with the existing dynamics input format.

81. **Add a raw-variable manifest test before any expensive download.**
    Build one authoritative required-variable manifest from the profile converter, including `z_sfc`, and compare it with the Earthmover fetch manifest and the CDS merge manifest. Fail immediately on missing or extra fields, rather than discovering the mismatch after hours of downloading. Include expected units and dimensions in the manifest.

82. **Make random sampling reproducible without allocating a full boolean cube.**
    `build_dataset.py` creates a random array with the full `(point, time)` shape and then filters it after loading the profile store. For larger CONUS stores this can consume substantial memory and make the selected rows sensitive to chunking and available RAM. Sample deterministic row IDs from a precomputed eligible index, save those IDs, and use the same IDs for every model comparison.

83. **Make GPU training reproducible enough for model-selection decisions.**
    `torch.manual_seed()` does not by itself guarantee deterministic CUDA kernels, and the sampler uses fresh random noise for every call. Set and record Python, NumPy, CPU and CUDA seeds, document deterministic-operation tradeoffs, and use fixed evaluation noise for checkpoint selection. Report variation over multiple seeds before promoting a generator over the analog baseline.

84. **Test normalization and target statistics for degenerate or masked channels.**
    Adding `1e-6` to each standard deviation prevents division by zero but can turn a constant or nearly missing channel into an artificially high-weight loss dimension. Compute channel support counts and robust scale diagnostics, exclude unsupported channels or use a defined minimum scale, and ensure the same policy is used during training, evaluation and sampling.

85. **Ensure metadata arrays are decoded consistently when saving checkpoints.**
    `build_dataset.py` writes `cond_names` and `target_names` as NumPy string arrays, while `train.py` converts metadata entries with `str(x)`. Depending on NumPy scalar/string types this can create inconsistent names across folds. Normalize names to plain UTF-8 strings, assert uniqueness and order, and include a schema hash in every checkpoint.

86. **Test all stated output summaries against the actual sample axis.**
    The plan requires means, standard deviations, quantiles and exceedance probabilities from joint samples. Add tests that recompute every summary from the saved `N × height × variable` array and compare it with TOML values, including NaN masks, degrees of freedom and wind-vector quantities. Never calculate a summary from independently reconstructed marginal arrays if the shipped samples are the source of truth.

87. **Correct the target-schema test instead of encoding the current mismatch.**
    `tests/test_data_pipeline.py` currently asserts `4 * len(HEIGHTS) + 3`, which locks in the present 179-target layout even though the plan and generator documentation describe additional surface fields. Define the canonical schema first, then make the test assert its names, order, count and physical reference heights. A passing test must prove the contract, not merely reproduce the current implementation.

88. **Preserve provenance and support masks into `build_dataset.py`.**
    The profile store contains source and validity information only implicitly, while the training file stores `cond`, `target` and `year`. Add source IDs, supported maximum height, valid masks and profile-store version to each training artifact. This prevents a model from being trained on mixed provisional/complete profiles without the fold or evaluator knowing it.

89. **Do not infer chunk completeness from a chunk tuple alone.**
    `build_dataset.py` reads `ds["u"].data.chunks[1]` and assumes the second dimension is time and has a usable chunk tuple. This is fragile across Zarr/xarray versions and after rechunking. Read dimension names and chunk sizes by name, validate that all profile variables share the same point/time coordinates, and fail with a clear error when the store is unchunked or inconsistently chunked.

90. **Replace the `done.txt` count check with coordinate-based completeness.**
    Counting marker lines does not prove that markers correspond to unique, valid, non-overlapping time regions. Validate marker offsets against the expected block partition, reject duplicates and out-of-range offsets, and verify every block’s time coordinate and required variables before dataset construction.

91. **Add a full round-trip test for surface anchors and differences.**
    Test `profiles_from_levels → to_diff → from_diff` for u, v, T and RH, and separately verify that the 10 m wind, 2 m temperature/RH and surface pressure fields retain their units, ordering and reference heights. A component-level diff test cannot detect a surface-field permutation or an output-schema shift.

92. **Make unsupported upper levels visible in every downstream artifact.**
    A row with a valid low and mid-level profile but no 18 km value must not look equivalent to a complete row. Store `max_supported_height` and a height mask, propagate them through sampling and scoring, and report skill separately for each support band. Do not let `np.isfinite(...).all(1)` silently turn this into undocumented sample-selection bias.

## Suggested order

1. **Phase 1:** A1–A5 (grid, seam, launch-time matching, humidity, height check) —
   fix representation errors before fitting anything.
2. **Phase 3–4:** B6–B8 (blend/window/effective-N), C9–C11 (WWV leakage, driver
   uncertainty, no-shift null).
3. **Phase 5:** D12–D14 (dual-truth near-term calibration, native-time verification,
   data-driven blend).
4. **Phase 6:** E15–E17 (per-height calibration after whole-cloud scaling, block
   conformal coverage, GPD stability), G23–G24 (error budget, physical consistency).
5. **Phase 6A:** F18–F22 (m, loss/metric alignment, shear scoring, fold-safe
   targets, out-of-range fallback).

All items are out-of-fold hypotheses. Keep a change only when its named check
passes beyond fold-to-fold noise, and retain analogs wherever a change does not
pass.

---

# Part 2 — Secondary review of the 2026-11-04 implementation changes

These structural changes should reduce silent scientific errors more than another
round of model tuning. The most urgent are the canonical schema, centralized
splits, explicit finite-ensemble interval API, versioned calibration artifacts,
and source/support masks.

---

# Part 4 — Training speedups that do not change the result

These target training wall-clock in `tempest/generator/train.py` and
`tempest/generator/model.py`. Items in Part 4A are numerically lossless (same
objective, same gradients up to floating-point reassociation, so the trained
model is effectively identical). Items in Part 4B are safe engineering changes
with negligible or no effect on the optimum. Each should be confirmed by a
before/after test: identical (or within tight tolerance) loss on a fixed seed
and batch, then equal or better steps-per-second.

With `members = 4`, every one of these savings is multiplied by four, because
the four seeds are trained sequentially in `main()`.

## Part 4A — Lossless loss-function rewrites

152. **Replace the `afcrps` pairwise outer product with the sort identity.**
     `afcrps()` builds `(samples.unsqueeze(1) - samples.unsqueeze(2)).abs()`, an
     `(B, m, m, D)` tensor, every step and again inside the step loss. The spread
     term `sum_{i,j}|x_i - x_j|` equals, per value, `2 * sum_k (2k - m - 1) *
     sort(x)_k` with `k = 1..m`. Sorting along the member axis and taking that
     weighted sum gives the identical number in `O(B m log m D)` time and `O(B m D)`
     memory, removing the `m*m*D` allocation (~47 MB per call at B=4096, m=4,
     D=179). This is exact, not an approximation; assert equality to the current
     implementation in a test before switching.

153. **Vectorize `energy_score` instead of the Python pair loop.**
     `energy_score()` sums over a Python generator of `m*(m-1)/2` member pairs,
     launching many small kernels. Compute all pairwise norms with one batched
     operation over the member axis (for example, a single `cdist` per row-block,
     or the upper-triangular indices gathered once), keeping the same unbiased
     formula. With `m=4` the arithmetic is tiny, so the gain is purely from fewer
     kernel launches and Python overhead; keep the result bit-comparable on CPU.

154. **Reuse the fit term shared by `afcrps` and `energy_score`.**
     Both losses recompute `samples - y.unsqueeze(1)`. When `es_weight > 0`, form
     that residual once per call site and pass it to both terms. This removes one
     full `(B, m, D)` subtraction and its broadcast each step without changing any
     value.

155. **Compute the step loss from the already-reconstructed profiles.**
     `score()` calls `afcrps` on `samples[..., :n_prof]` (the raw differences) in
     addition to the main `afcrps`/`energy_score` on reconstructed profiles. The
     difference-space values are already the per-step increments used to build the
     profile, so the step loss can reuse intermediate tensors from the physical
     reconstruction rather than re-slicing and re-standardizing. Confirm the
     numbers match the current `step_weight` term exactly before relying on it.

## Part 4B — Safe engineering speedups (no objective change)

156. **Overlap host-to-device copies with pinned memory and `non_blocking`.**
     `batch()` builds a normalized float32 array on the CPU and copies it to the
     GPU synchronously every step. Allocate pinned (page-locked) host buffers for
     the batch and validation tensors and copy with `non_blocking=True`, so the
     transfer overlaps the previous step's compute. This changes only timing, not
     values.

157. **Move per-batch normalization to the device.**
     `batch()` computes `(cond[idx] - cm) / cs` and the target transform in NumPy
     on the CPU for every step. Copy the raw gathered rows once and apply the fixed
     `cm/cs/tm/ts` (and the `sp_offset` subtraction) on the GPU. The CPU then only
     does the memmap gather; the arithmetic runs where the model already is. Keep
     the statistics in the same float precision to preserve values.

158. **Prefetch the next batch while the current step runs.**
     Row indices come from `rng.integers(...)` and a memmap gather. A one-batch
     look-ahead (a small background thread or a CUDA stream for the copy) hides the
     disk/gather latency behind GPU compute. Draw indices from the same seeded RNG
     in the same order so the training trajectory is unchanged.

159. **Enable TF32 / mixed precision explicitly and measure it.**
     The code already sets `torch.set_float32_matmul_precision("high")` (TF32
     matmuls). On this RTX 50-series GPU, also test autocast to bfloat16 for the
     forward/backward with float32 master weights. bfloat16 is not bit-identical,
     so treat it as Part 4B-conditional: keep it only if a fixed-seed run matches
     the float32 validation curve within noise and does not worsen calibration or
     tail scores. Keep the loss reductions and the standardization in float32.

160. **`torch.compile` the model and loss once per process.**
     Wrap the generator (and ideally the loss) in `torch.compile` so the residual
     blocks, FiLM, and the sort-based loss fuse into fewer kernels. This does not
     change the math. Guard it so a compile failure falls back to eager, and make
     sure the first-step compile cost is excluded from throughput measurements.

161. **Cut validation cost with fixed noise and a right-sized `val_rows`.**
     Validation runs every 500 steps over up to 50,000 rows plus a `diagnose()`
     pass. Use fixed (seeded) evaluation noise so the early-stop signal is not
     noisy (this also improves selection, Part 2 item 117), and check whether a
     smaller, fixed validation subset gives the same stopping decisions. Fewer
     validation rows is a straight time saving once the subset is shown to pick the
     same checkpoints.

162. **Avoid the full-gradient-norm reduction if it is only a diagnostic.**
     `clip_grad_norm_(..., float("inf"))` computes the global gradient norm every
     step purely to log it ("measure only, no clipping"). Computing it only on
     evaluation steps (every `eval_every`) removes a full parameter-wide reduction
     from most steps with no effect on the optimizer.

163. **Train the `members` seeds in parallel where the GPU has headroom.**
     The four members are independent and currently trained one after another
     (4× wall-clock). Measured pilot training used ~0.4 GB of a 12 GB GPU, so
     several members can share the device via separate CUDA streams or a batched
     "ensemble-of-MLPs" layout (a leading model axis on every `nn.Linear`). This is
     the single largest wall-clock win and does not change any member's result as
     long as each keeps its own seed, data order, and initialization.

164. **Keep `load_npz` memory-mapped and gather contiguously.**
     The custom reader already memory-maps uncompressed `.npz`. Ensure training
     never triggers the `np.load` fallback (which reads the whole ~6 GB into RAM):
     assert the file is `ZIP_STORED` at start, and, where possible, sort the sampled
     row indices within a step so the memmap gather touches pages more
     sequentially. Row order within a batch does not affect the loss.

Part 4A items should be adopted first and locked behind an exact-equality test.
Part 4B items 156–158 and 160, 162, 163 are the biggest wall-clock wins and carry
no accuracy risk; item 159 (bfloat16) is the only one that must be gated on a
calibration check before it ships.

This section reviews the new improvement log and changes in `docs/PLAN.md`,
`tempest/calibrate/`, `tempest/generator/`, `tempest/profiles/`,
`tempest/scoring/`, and the associated tests. These findings are separate from
Part 1 and focus on risks introduced by pressure-offset learning, liquid-water
RH, step loss, ensemble members, range calibration, and the 99% past-weather
coverage objective.

The 99% objective is a calibration target for the stated verification population;
it is not evidence that future weather is predictable. All findings below must
be checked on untouched years, stations, and weather episodes.

## Part 2A — Calibration and coverage correctness

93. **Correct the finite-ensemble 99% coverage convention.**
    `coverage90()` computes `k = round((1-p)(m+1)/2)` and then indexes the
    `k-1` and `m-k` order statistics. For `m=199` and `p=0.99`, `k=1`, so the
    interval is the sample minimum through maximum. For a continuous exchangeable
    truth and 199 forecast members, that interval contains the truth essentially
    100% of the time, not 99%. To obtain an approximately 99% central interval,
    the endpoint convention must exclude appropriate extreme members (for example,
    use the second and second-to-last members for this ensemble size), or use a
    clearly defined randomized/interpolated quantile rule. Derive the finite-sample
    coverage mathematically, test it with a large synthetic exchangeable ensemble,
    and do not describe the current `k=1` result as exact 99% coverage.

94. **Quantify uncertainty in the 99% coverage results.**
    Two years of hourly rows are not two years of independent evidence. Report
    confidence intervals using independent weather episodes, year, month and
    station blocks, together with effective sample size. If the interval is too
    wide to distinguish 99% from nearby values, label the band unresolved.

95. **Make fit, calibration and test splits mutually exclusive by construction.**
    The new commands combine `--year`, `--from-year`, `--first-test-year`, and
    validation-year defaults. Create one split manifest containing exact years,
    row IDs, soundings and episode IDs; reject overlap and save the manifest in
    every calibration artifact consumed by `score` or `sonde`.

96. **Prevent row and episode reuse during range calibration.**
    `spread.fit()` pools model members and truth values from selected rows. Store
    the selected IDs and verify that no row, timestamp, sounding or weather episode
    appears in both calibration and final evaluation.

97. **Use one finite-sample convention in fitting, applying and scoring.**
    `spread.apply()` interpolates quantile knots and extrapolates beyond them,
    whereas `coverage90()` uses discrete order statistics. Test the complete
    production chain on synthetic exchangeable data and record the convention in
    the calibration artifact.

98. **Recheck RH calibration after clipping.**
    `spread.apply()` calls `clip_ranges()` after the quantile transform. Clipping
    creates point masses at 0 and 100%, changes ranks, and can alter tail coverage
    and RH/T dependence. Prefer a bounded transform or measure PIT, tail coverage,
    and physical consistency after the final clipping step.

99. **Do not claim joint 99% profile coverage from marginal bands.**
    Separate monotone maps preserve the raw rank copula across columns before any
    clipping or ties, but they do not guarantee calibrated physical joint regions,
    covariance, wind-vector magnitudes, or shear events. Report marginal, vector,
    selected shear, thermodynamic, and whole-profile joint coverage separately,
    including the effect of RH clipping.

100. **Require minimum support for every calibrated tail.**
     Range and station calibration can have too few rows after finite-value,
     year, station, month and height filtering. Enforce minimum counts per column,
     group and tail; otherwise mark that band unresolved instead of extrapolating
     a 99% map from insufficient data.

## Part 2B — Schema and physical-transform correctness

101. **Make physical reconstruction schema-driven rather than 179-column-specific.**
     `train.py` enables profile reconstruction only when metadata has exactly
     `N_PROF + 3` targets, while `sample.py` assumes 179 columns and three surface
     fields. Adding u10/v10, pressure levels or density could silently change the
     loss into a raw-vector loss. Define a schema with names, units, dimensions,
     transforms and a hash; reject mismatched datasets and checkpoints.

102. **Test pressure-offset round trips at training and inference.**
     Training subtracts standard pressure using `elev_grid`, and `Sampler` adds it
     back using the condition index. Test multiple elevations, old checkpoints
     without `sp_offset`, extreme synthetic values, units and finite outputs. A
     missing or mismatched offset must fail loudly rather than produce plausible but
     mis-scaled pressure.

103. **Ensure every score receives physical pressure, not pressure departure.**
     Confirm that calibration, Gaussian baselines, diagnostics, reports and output
     writers all receive pressure in pascals after the offset is restored. Add an
     invariant at the scoring boundary that rejects pressure departures outside
     the expected physical range.

104. **Evaluate step-loss weighting in physical units.**
     Step loss is applied to normalized difference coordinates while the primary
     loss uses reconstructed, per-channel standardized profiles. Measure each
     component's actual loss and gradient contribution, and tune `step_weight`
     inside training folds against physical shear and variogram scores.

105. **Test the liquid-water RH conversion at all phase boundaries.**
     Validate `liquid_rh()` above 0 C, below -23 C, and through the transition for
     continuity, monotonicity, finite output and saturation behavior. Also measure
     its effect on density and hypsometric pressure, not just RH bias.

106. **Do not silently mix complete and partial CDS profiles.**
     `to_heights.py` permits missing CDS months and partially filled months. Persist
     source/support masks and report Earthmover-only, fully filled and partially
     filled cases separately in training, calibration and scoring.

## Part 2C — Station and radiosonde verification

107. **Report support for every station-correction group.**
     Station correction groups combine station, season and launch hour. Report pair
     counts per group and height, reject unsupported groups, and explicitly identify
     identity fallbacks instead of treating them as calibrated output.

108. **Do not require complete 44-level soundings for all residual learning.**
     `station.fit()` retains leftovers only when all variables and all 44 heights are
     finite. This preferentially removes soundings with missing upper levels. Use
     support masks or stratified corrections by maximum common height, and publish
     the retained-versus-discarded distribution.

109. **Align radiosonde truth with observation geometry.**
     Nominal 00Z/12Z and nearest-grid comparisons omit release-time and ascent-path
     representativeness. Compare nearest-grid, bilinear and—where metadata permit—
     drift-aware matching before interpreting residuals as model error.

110. **Keep station calibration and final sonde testing independent.**
     The optional station calibration must use complete sounding episodes outside
     the final test set. Save fit IDs and reject any overlap by sounding, day,
     station or weather episode.

## Part 2D — Scorecard and model-selection safeguards

111. **Use one canonical schema across all scorecard baselines.**
     Climatology, Gaussian, generator, sonde and reporting code must consume the
     same ordered physical columns and support mask. A baseline that omits or
     reorders a surface field can produce misleading aggregate skill.

112. **Audit climatology grouping against direct timestamps.**
     `group_keys()` reconstructs month and hour bins from sine/cosine features and
     truncates them. Test year boundaries, leap day, negative longitude, fractional
     solar time and bin edges against a timestamp-based implementation.

113. **Do not drop held-out rows solely because a climatology group is empty.**
     Such rows may be systematically rare. Use a declared fallback or report all
     methods on the same eligible set together with the excluded-case distribution.

114. **Use shrinkage covariance for the high-dimensional Gaussian baseline.**
     Full covariance from a small group in 179 dimensions is unstable. Require a
     minimum sample count, use documented shrinkage or low-rank covariance, check
     positive definiteness, and compare against diagonal and low-rank baselines.

115. **Separate training-member count from evaluation-member count.**
     The current paths use m values of 4, 50, 100 and 199. CRPS and finite-ensemble
     coverage depend on m. Define fixed training/evaluation conventions, use common
     random numbers, and report sensitivity rather than comparing unlike ensembles.

116. **Measure effective ensemble size across trained members.**
     Members may differ only by seed while sharing rows, normalization and optimizer
     settings. Measure inter-member correlation; do not count correlated members as
     independent spread when evaluating coverage.

117. **Use common random numbers for checkpoint selection.**
     Fresh noise at every validation checkpoint adds Monte Carlo noise to early
     stopping. Fix validation noise or average repeated common-noise evaluations,
     using the same member count and physical metrics as the final report.

118. **Keep model selection separate from final calibration selection.**
     The improvement log uses 2024–2025 results to accept or reject calibration
     choices. If those years are used for decisions, call them development years
     and reserve an untouched final year/station block for the final accuracy claim.

119. **Add invariance tests for batching and row order.**
     Permuting rows or changing batch size should not change score definitions,
     calibration tables or diagnostics except for documented random sampling.
     This is especially important with sorted group arrays and chunked generation.

## Part 2E — Acceptance and reproducibility

120. **Separate past-weather coverage from future-forecast skill.**
     Exact ERA5 lookup, radiosonde correction, near-term forecast calibration and
     multi-month probabilistic skill are different products. Publish separate
     acceptance tables and do not transfer a past-weather 99% result to future
     dates.

121. **Require every declared band to pass, not only an aggregate range.**
     The improvement log already shows RH and T bands with different behavior.
     Publish the worst band, miss direction, station/month breakdown and uncertainty;
     aggregate summaries cannot hide a failed launch-critical band.

122. **Predeclare nominal-coverage tolerances and multiplicity handling.**
     Define tolerance intervals and block-bootstrap uncertainty before inspecting
     results. Distinguish practical tolerance, statistical confidence and the fact
     that many variable/height bands are tested.

123. **Version every calibration artifact against the model and schema.**
     Store model and member hashes, target-schema hash, transform version, source
     hash, fit IDs, fit years, member count, random seed, quantile levels and
     clipping policy. Refuse application when these do not match production.

124. **Make diagnostics part of the automated ship gate.**
     Bias, spread/skill, miss direction, worst columns, monthly/station coverage,
     joint coverage and support counts should be machine-readable and thresholded.
     Charts alone are insufficient for a 99% claim.

125. **Run the complete changed suite in a clean pinned environment.**
     The repository now changes scoring, calibration, profile and training paths.
     Run all tests with the lockfile's Python/package/CUDA versions, including
     synthetic score/calibration fixtures and real-data smoke tests, before treating
     the improvement log as validated.

Part 2 is complete only when the finite-ensemble convention, split manifest,
schema hash, source-support mask, scorecard baselines and joint-coverage
diagnostics are explicit and reproducible.

---

# Part 3 — Structural recommendations

The largest remaining risk is not primarily the neural-network architecture. It
is that schemas, transformations, data splits, calibration rules, routing, and
verification logic are distributed across scripts and represented by anonymous
arrays and dictionaries. The following structural changes are intended to make
silent scientific errors difficult or impossible.

## Part 3A — Canonical data and physical-domain contracts

126. **Create one canonical profile schema.**
     Add a central module such as `tempest/schema.py` containing the ordered
     profile and surface variables, heights and reference heights, units,
     difference-space and physical-space slices, bounds, transformations, and a
     schema version/hash. Dataset builders, checkpoints, calibration artifacts,
     scorecards, sample files, and TOML outputs must all carry and validate that
     hash. This should eliminate the current 179/181 ambiguity and prevent field
     permutations from remaining numerically plausible.

127. **Separate physical transformations from generator sampling.**
     Move difference-to-level reconstruction, standard-pressure handling,
     pressure/density derivation, RH conventions, site-elevation transfer, and
     physical constraints out of `generator/sample.py`. Suggested boundaries are
     `tempest/physics/profile.py`, `tempest/physics/site.py`, and
     `tempest/physics/constraints.py`. The sampler should load a model and produce
     stochastic model outputs, not define atmospheric physics. Training should not
     need to import physical transforms from the inference sampler.

128. **Introduce a typed forecast-sample object.**
     Replace anonymous arrays with an explicit container holding values, member
     axis, variables, heights, units, issue and valid times, site/grid elevation,
     route, source/support masks, calibration history, schema hash, and random-seed
     provenance. Distinguish raw difference-space targets, pressure departures,
     physical profiles, and site-adjusted profiles with separate types or explicit
     states so they cannot be passed interchangeably.

129. **Represent forecast queries explicitly.**
     Create a query object containing issue time, target time, lead, location,
     civil timezone, solar time, requested heights, predictor vintage, and the
     predictors available at issue time. This structurally prevents target-time
     climate indices or revised observations from being mistaken for predictors
     available when the forecast was issued.

130. **Define one authoritative physical-transform pipeline.**
     Express the production order explicitly: model output, pressure-offset
     restoration, level reconstruction, range calibration, physical constraints,
     site transfer, derived pressure/density, and output serialization. Every
     training, calibration, scoring, and production path should invoke the same
     versioned transform graph rather than recreating parts of it independently.

## Part 3B — Splits, artifacts, and scientific provenance

131. **Centralize all temporal and spatial splits.**
     Replace independently calculated training, validation, calibration, and test
     years with a split registry. Each immutable split manifest should identify
     row IDs, timestamps, years, stations, weather episodes, regions, data hashes,
     and preprocessing versions for training, checkpoint validation, calibration,
     development testing, and untouched release testing. Consumers must reject
     overlapping roles automatically.

132. **Replace loose calibration dictionaries with versioned artifacts.**
     Define a common calibration artifact containing type/version, model and member
     hashes, schema hash, transform version, source hash, split hash, fit IDs,
     member count, quantile convention, clipping policy, support counts,
     applicability domain, and fit diagnostics. It should expose a common interface
     for fitting, application, compatibility validation, and diagnostics, and
     refuse incompatible forecasts.

133. **Make every model checkpoint self-describing and verifiable.**
     Store schema and transform hashes, feature names and units, target names and
     units, training split hash, data hash, configuration, software versions,
     random seeds, normalization support counts, and validation report. Loading a
     checkpoint should validate these fields before allocating the model or
     producing samples.

134. **Replace `done.txt` with transactional processing manifests.**
     For every profile block, record input hashes, source availability, time range,
     coordinates, height grid, transformation version, output checksum, and
     validation status. Write and validate output atomically before committing the
     manifest entry. Changes to raw inputs, interpolation, RH convention, grid, or
     code must invalidate affected blocks automatically.

135. **Carry source and support masks as first-class data.**
     Each output value should identify whether it came from Earthmover ERA5, CDS,
     a surface anchor, vertical interpolation, station correction, extrapolation,
     or fallback. Preserve these masks through the profile store, training data,
     forecast samples, and scorecards. Mixed 13-level, 21-level, corrected, and
     provisional products must remain distinguishable.

136. **Move beyond monolithic NPZ training artifacts.**
     The custom memory-mapped NPZ reader is useful but fragile and cannot naturally
     carry row-level masks and provenance. For larger stores, use a chunked,
     schema-aware format such as Zarr for features, targets, masks, row IDs,
     timestamps, split assignments, and provenance. Keep a small immutable index
     for sampled row IDs and fold definitions.

## Part 3C — Evaluation and scorecard architecture

137. **Create a single pure metrics library.**
     Put CRPS, energy score, variogram score, PIT, marginal coverage, joint
     coverage, confidence intervals, and skill calculations in
     `tempest/scoring/metrics.py` as side-effect-free functions. Freeze their axis,
     masking, weighting, and finite-ensemble conventions with analytical tests and
     a metric-version identifier.

138. **Replace `coverage90()` with an explicit interval API.**
     The function name and optional `p` argument obscure the interval convention.
     Require callers to select order-statistic, interpolated-quantile, or randomized
     finite-ensemble intervals, together with inclusive/exclusive endpoint rules.
     Return the nominal probability, attainable finite-sample probability, observed
     coverage, case count, and uncertainty rather than a bare Boolean array alone.

139. **Separate case building, forecasting, evaluation, gating, and rendering.**
     Current score scripts perform selection, baseline construction, sampling,
     calibration, metrics, CSV writing, diagnostics, and charting in one path.
     Split these into a case builder, forecast runner, metric evaluator, ship-gate
     evaluator, and report renderer. Numerical tests should not need plotting,
     command-line parsing, or live data access.

140. **Define one forecast-provider interface for every baseline and model.**
     Climatology, Gaussian reference atmosphere, analogs, generator, near-term
     providers, and fallback routes should consume the same case table and return
     the canonical forecast-sample object. This enforces identical cases, variables,
     support masks, member counts, physical transforms, and scoring rules.

141. **Create an automated, versioned ship gate.**
     The gate should evaluate skill versus required baselines, marginal and joint
     coverage, bias, spread/skill, worst variable-height band, source/support rate,
     physical-consistency failures, out-of-domain rate, and block-bootstrap
     uncertainty. Produce machine-readable pass, fail, or insufficient-evidence
     decisions. Charts should explain decisions, not make them manually.

142. **Keep a frozen, untouched release benchmark.**
     Maintain benchmark cases that are never used to choose model architecture,
     calibration method, thresholds, interval conventions, or routing. Clearly
     separate exploratory, development-verification, and release-gate reports.
     Require a new benchmark version when observations are revised or the product
     schema changes.

## Part 3D — Forecast routing and uncertainty layers

143. **Make forecast routing a first-class component.**
     Implement an explicit router with named routes for past analysis, near-term
     ensembles, transition/blended leads, long-range generation, analog fallback,
     and out-of-domain fallback. Each route should declare its valid lead range,
     required inputs, supported region/heights, calibration artifact, verification
     report, and fallback route.

144. **Separate target-state conditioning from issue-time knowledge.**
     Forecast providers should receive predictors through the query object and data
     vintage rather than reading target-time indices directly. Historical backtests
     must reconstruct only the information available at each issue time. An
     idealized known-driver run may remain as a labeled upper bound, never as the
     operational score.

145. **Represent uncertainty sources as distinct composable layers.**
     Keep atmospheric predictive uncertainty, analysis uncertainty,
     site-representativeness uncertainty, launch-time uncertainty, measurement
     uncertainty, and parameter/calibration uncertainty separate. Combine them only
     in named product stages with recorded covariance assumptions. This prevents
     station correction, range calibration, and analysis inflation from counting
     the same error twice.

146. **Add explicit out-of-domain detection and routing.**
     Detect spatial, elevation, seasonal, driver, source-support, and physical-state
     departures from training/calibration support. Return an applicability report
     and route unsupported cases to an approved fallback. Do not rely on the neural
     network or calibration map to extrapolate silently.

## Part 3E — Testing architecture

147. **Organize tests into four distinct levels.**
     Maintain unit tests for transforms, parsers, and metrics; contract tests for
     schema/artifact compatibility; integration tests for raw data through output;
     and scientific regression tests for frozen cases and accepted score ranges.
     Failures should identify whether code correctness, interface compatibility,
     integration, or scientific performance regressed.

148. **Add property-based and randomized invariants.**
     Verify difference conversion invertibility, row-order and batch-size
     invariance, calibration monotonicity, identity-calibration neutrality, schema
     round trips, positive density, pressure decreasing with height, physical RH
     bounds, and analytical finite-ensemble coverage. These tests can initially use
     deterministic randomized loops without requiring another dependency.

149. **Add a complete small-pipeline integration fixture.**
     Include at least one synthetic month and one small immutable real-data fixture
     covering raw-source merge, profile interpolation, dataset construction,
     training or checkpoint loading, sampling, calibration, site transfer, scoring,
     routing, and output serialization. Validate units, dimensions, hashes, masks,
     and summaries at every boundary.

150. **Add deterministic replay tests for every route.**
     With frozen inputs and seed, require identical case IDs, route selection,
     member assignment, driver draws, physical samples, calibration metadata, and
     summaries. Changing only the seed may change samples but must not change route,
     schema, source support, or fitted metadata.

151. **Run scientific regression tests with uncertainty-aware thresholds.**
     Do not require bit-identical GPU scores when nondeterministic kernels are
     allowed. Instead, predeclare score intervals and seed-to-seed tolerances derived
     from repeated runs. Keep exact deterministic tests for transforms, metrics,
     manifests, schemas, and CPU fixtures.

## Part 3F — Recommended implementation order

1. Canonical schema, transform graph, and typed forecast/query objects.
2. Central split manifests and artifact compatibility checks.
3. Pure metrics library and corrected finite-ensemble interval API.
4. Versioned calibration artifacts and checkpoint manifests.
5. Transactional profile manifests and source/support masks.
6. Common forecast-provider interface and explicit router.
7. Automated ship gate and frozen release benchmark.
8. Layered uncertainty composition.
9. Contract, integration, property, replay, and scientific regression tests.
10. Only then resume architecture tuning or broader deployment.

These structural changes should reduce silent scientific errors more than another
round of model tuning. The most urgent are the canonical schema, centralized
splits, explicit finite-ensemble interval API, versioned calibration artifacts,
and source/support masks.