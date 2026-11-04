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

18. **Train on more than m = 4 samples per row, or document the bias.**
    `DEFAULTS["m"] = 4`. The energy-score estimator in `model.energy_score` is
    unbiased in expectation, but with only 4 samples per row the spread term has
    high variance, which tends to make the fitted model **under-dispersed** (it is
    cheaper to shrink spread than to get it exactly right under a noisy estimate).
    Test larger m (e.g. 8–16) at the pilot scale where it fits in memory, and
    compare validation calibration (not just validation ES) across m. If m must stay
    small for CONUS, add a spread-penalty or an explicit variance-matching term.

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