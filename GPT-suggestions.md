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