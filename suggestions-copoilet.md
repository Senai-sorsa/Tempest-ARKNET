# Accuracy-focused suggestions

These recommendations are based on the design and evidence recorded in
[docs/PLAN.md](docs/PLAN.md), [docs/PHASE1.md](docs/PHASE1.md),
[docs/research-notes.md](docs/research-notes.md), and the current generator code.
They address forecast and profile accuracy only; operational and infrastructure
suggestions are intentionally excluded. Items marked **Planned** are already in
the project design and are collected here as accuracy priorities. Items marked
**Additional** refine or extend that design. Treat reported research gains as
claims to test: several cited works are recent preprints or cross-domain results.

## Highest-priority accuracy work

1. **Make model selection leakage-free and account for dependence in
   verification.**
   **Planned, strengthen the protocol.** Keep the year-wise walk-forward split
   and 45-day embargo, and add held-out station/spatial blocks wherever a
   correction is intended to transfer to unseen locations. Fit normalization,
   analog weights, shift coefficients, quantile maps, tail parameters, and
   calibration factors using only each fold's training data. Tune flexible
   choices in inner folds where the limited number of years permits it; for
   very small samples, pre-specify a short candidate list rather than creating
   an underpowered nested search. Compare methods on identical cases and report
   paired uncertainty using year- and, where relevant, station-level blocks,
   not individual hourly rows.

2. **Turn acceptance into a lead-by-lead scorecard with a conservative ship
   rule.**
   **Planned, make explicit.** Report CRPS by variable and height band,
   energy score for full profiles, variogram score for shear, calibration/PIT,
   and error in extreme neighbour differences. Keep near-term forecasts,
   seasonal leads, and 1–3-year leads distinct. Pre-specify the primary score
   and an acceptable non-inferiority margin for
   the other scores and calibration checks. Require the candidate to improve
   the primary score beyond fold-to-fold uncertainty and meet those guardrails.
   Retain analogs wherever a generator, pool, or correction does not pass this
   gate.

3. **Keep analogs diverse across years, and test climate-state matching as a
   separate choice.**
   **Planned.** Cap repeated draws from a historical year where needed and
   report the effective number of contributing years (from the actual
   sampling weights).
   Do not force equal year weights unless the backtest supports that target
   distribution. Compare the baseline sampling with driver-kernel weighting,
   tuning bandwidth only on training data; avoid applying both a driver shift
   and a kernel adjustment for the same signal unless their combined value is
   demonstrated. Check held-out CRPS and profile scores as well as year
   diversity.

4. **Represent future driver uncertainty jointly and only where it has
   demonstrated skill.**
   **Planned, resolve one accuracy gap.** Keep ONI + warm water volume (WWV)
   and QBO as candidate predictors, with lead-dependent skill decay and
   climatological fallback. At each forecast issue date, only use driver
   values or forecasts that would actually have been available then. The
   documented ONI + WWV regression does not itself specify a future WWV
   forecast: validate a leakage-free WWV forecast first, or do not use future
   WWV as an input. Estimate dependence between driver forecast errors from
   out-of-fold residuals only if the archive supports it; otherwise use a
   simpler uncertainty model and disclose that limitation. Refit skill and
   uncertainty inside each fold, and remove predictors that fail to improve
   the relevant held-out lead band.

5. **Shrink climate-shift coefficients across nearby heights and sites.**
   **Planned.** Compare per-level keep/drop coefficients with partially pooled,
   smooth coefficients for trend, ENSO, and upper-level QBO effects. Test
   vertical pooling first; test spatial pooling only when multi-site data and
   spatial-block validation are available. Fit within each fold and retain the
   simpler rule unless pooling improves walk-forward CRPS without harming
   calibration. Use predictor-uncertainty draws when applying retained shifts;
   in-sample significance alone is not evidence of forecast skill.

6. **Correct ERA5 against radiosondes in shear space, while holding stations
   out.**
   **Planned.** Compare the difference-space station quantile map against
   simple spread inflation using held-out stations and years. Condition the
   correction only on strata supported by enough independent soundings (for
   example, season and height band). Use a vector-aware wind correction where
   data support it, and still report component-wise diagnostics. Check that
   the correction improves radiosonde CRPS, variogram score, and
   neighbour-difference distribution—not just marginal spread. Do not let an
   empirical quantile map silently extrapolate beyond its trained quantiles;
   evaluate its tail treatment separately. For CONUS transfer, require
   spatial-block validation before using a learned terrain/site correction.

7. **Extend shear tails without losing observed event shape.**
   **Planned, experimental.** Fit GPD tails to neighbour differences beyond a
   selected high-quantile threshold only if diagnostics support that tail
   model; check threshold and parameter stability across held-out years and
   stations. For multivariate extremes, test rescaling a real extreme
   profile's shape rather than generating each level's tail independently,
   while recognizing that a small library may not represent rare shapes.
   Evaluate 99th/99.9th-percentile shear error and coverage separately.
   Quantify uncertainty using blocks of independent weather episodes; if
   verification data cannot resolve a 99.9% claim, label it unverified rather
   than treating correlated soundings as independent evidence.

8. **Calibrate the whole sample cloud and verify cross-channel dependence.**
   **Planned, expand validation.** Use rank reordering after marginal
   calibration and test whole-cloud conformal scaling only on matured
   verifications. Do not assume conformal calibration guarantees conditional
   or joint profile coverage: formal coverage depends on its assumptions, and
   weather cases are serially dependent and non-stationary. Check marginal
   coverage by lead/season and separately assess joint vector/profile
   coverage. Measure dependence across heights, u/v, and temperature/humidity
   before and after calibration. Use reconciliation only if it improves
   held-out profile energy, variogram, shear, and physical-consistency measures.

9. **Calibrate near-term providers separately before deciding whether to
   pool.**
   **Planned.** Fit each provider's bias/spread correction independently, then
   compare the best single provider with a shrunk linear pool and post-pool
   calibration. Use only forecasts archived at issue time and matched
   verification cases. Because the IFS archive is limited and the live logger
   is short, shrink provider-specific fits strongly and avoid many
   lead/height-specific parameters until sample size supports them. Keep a
   second provider only when it improves held-out profile scores and
   calibration; member count alone is not evidence of greater accuracy.
   Recheck wind-tail performance separately from average CRPS.

10. **Do not mistake many training rows for many independent climate
    examples.**
    **Additional, generator-specific.** Nearby hours and locations are
    correlated, while the slow climate variability has few independent years.
    Compare the generator and analog sampler on identical contiguous
    held-out years and, for transfer claims, held-out spatial blocks. Report
    results by fold and lead band. Keep energy score alongside variogram,
    calibration, and tail tests. Treat architecture/loss tuning as a small,
    pre-specified experiment set; keep the generator only in bands where it
    beats analogs under the same protocol.

11. **Require upper-air verification for any seasonal-conditioned
    reweighting.**
    **Planned, tighten the gate.** The documented seasonal forecast source is
    near-surface only. If it is used to reweight analogs, verify on hindcasts
    that the change improves upper-air profile and shear scores as well as the
    near-surface quantities it conditions on. Better near-surface statistics
    alone do not establish better launch-altitude winds.

12. **Use radiosonde checks to catch vertical-grid and representativeness
    errors before fitting sophisticated corrections.**
    **Additional.** Match ERA5 to each sounding's actual launch time and
    location before comparing interpolation choices, height-above-ground
    alignment, and surface/elevation adjustments by variable and height band.
    Track station distance, launch time, and representativeness limitations;
    hold out complete stations when evaluating transfer. Fix a systematic
    height or interpolation bias before allowing a calibration layer to absorb
    it.

## Suggested order

1. Establish the paired, nested temporal-and-spatial validation and scorecard
   (suggestions 1–2).
2. Test diverse analog sampling and driver handling (3–5).
3. Verify radiosonde transfer, joint calibration, and tail behavior (6–8, 12).
4. Evaluate near-term pooling and seasonal reweighting on appropriate archives
   (9, 11).
5. Judge the generator against the validated analog baseline (10).

All suggestions are accuracy hypotheses, not claimed improvements. Keep a
change only when the specified out-of-fold test supports it.
