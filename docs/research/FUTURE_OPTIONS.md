# Future options (the "mediocre" list)

Ideas that are sound but not worth doing yet: small or unproven accuracy gain, a lot of code, or they need data we
do not have. Try them if coverage or skill needs more. Sources: the two Argon "99 % past-weather" blueprints
(reviewed 2026-11-04) and GPT-suggestions.md parts 2-4 (reviewed 2026-11-04). Adopted and rejected items are logged
in `docs/plans/PLAN.md` (improvement log and blueprint review); discarded ideas are at the end of this file.

## Accuracy: data and physics

- Balloon drift along a slanted path (40-150 km by 20 km) when comparing with ERA5; compare nearest-grid, bilinear
  and drift-aware matching (GPT 109). Needs the 4-D store around each station; may cut upper-level wind error in
  the balloon scorecard.
- Radiosonde sun-heating / ascent-rate de-trending. IGRA derived files carry neither, so little to fit on.
- Terrain warping of heights near the ground (ERA5 grid elevation vs real elevation); the sp offset already
  handles the pressure part.
- Moisture-consistent (virtual temperature) heights; theta / dewpoint interpolation.
- Measure liquid-water RH's effect on density and hypsometric pressure, not just RH bias (GPT 105; continuity and
  monotonicity are now tested).
- Keep a source mask (Earthmover-only / CDS-filled / partly filled months) through training and scoring and report
  them separately (GPT 106, 135).
- u10/v10 targets; pressure at each height.

## Accuracy: model and loss

- Quasi-random (Sobol / antithetic) noise when sampling: smoother tails at the same m. → LOOP3 L3-37 (Sobol at inference, queued 2026-11-06).
- Smooth vertical basis (EOF / B-spline) or a jet / inversion shape head (step loss already fixed shear).
- Sobolev / hydrostatic penalty in the loss; vertical conv / Fourier layer; FiLM conditioning.
- afCRPS alpha 0.99 instead of 0.95: tried as item 13, no skill gain.
- Tune `step_weight` against physical shear and variogram scores, not the normalised loss (GPT 104).
- Measure how independent the 4 trained members really are (inter-member correlation, GPT 116).

## Accuracy: calibration and station correction

- Range calibration split by weather regime. Season and spread tercile tested as item 8 and lost to one global
  map; revisit only with far more fit rows (or a different regime variable such as wind speed).
- SetConv / neural-process station correction: only worth it with many stations (2 in the pilot box).
- Use soundings with missing upper levels for the station leftovers (by highest common height) instead of
  requiring all 44 heights (GPT 108): would add data where balloons burst early.
- Minimum-support rules everywhere: report pair counts per station group and mark thin tails "unresolved"
  (GPT 100, 107). Station groups already need 50 complete leftovers.

## Honest verification

- **Untouched final test block** (GPT 118, 142): 2024-25 have now been used to pick changes, so they are
  development years. Before claiming a final number, score once on data never used for a decision (e.g. 2026 once
  available, or the CDS years 1991-2000 held back from all choices).
- Confidence intervals on coverage from block bootstrap by month / station / weather episode, with a tolerance
  declared up front (GPT 94, 122). Two years of hourly rows are far fewer independent cases than rows.
- Joint coverage: wind vector, selected shear layers, whole profile, next to the per-column numbers (GPT 99).
- One split manifest saved with each calibration file (fit years / rows) and checked against the test years
  (GPT 95, 96, 110, 131). Today `--first-test-year` does this by hand.
- Calibration files carry more provenance (model hash, schema) and refuse to apply on mismatch (GPT 123, 132).
  The member-count check is already in.
- Climatology groups: test `group_keys` against real timestamps at year/leap-day/bin edges (GPT 112); report or
  fill the rows dropped for lacking a climatology group (GPT 113, count is printed).
- Shrinkage covariance for the Gaussian reference-atmosphere baseline (GPT 114): fairer baseline in 179 dimensions.
- Machine-readable ship gate: thresholds on worst band, bias, spread/skill, support (GPT 124, 141).
- Property and integration tests: row-order / batch-size invariance, identity calibration is a no-op, a tiny
  end-to-end fixture (GPT 119, 147-151).

## Speed (same result, faster training)

- Train the 4 members in parallel on the GPU (GPT 163): biggest wall-clock win, the pilot uses ~0.4 GB of 12 GB.
- Pinned memory + `non_blocking` copies, normalisation on the GPU, one-batch prefetch (GPT 156-158).
- `torch.compile` with eager fallback (GPT 160); bfloat16 autocast only if a fixed-seed run keeps calibration
  (GPT 159).
- Gradient norm only on evaluation steps (GPT 162); smaller fixed validation subset if it picks the same
  checkpoints (GPT 161).
- Sort-identity afCRPS and vectorised energy score (GPT 152-155): exact, but with m = 4 the tensors are tiny, so
  only worth it if training m grows.
- Assert the training .npz is uncompressed so `load_npz` never falls back to reading 6 GB into RAM (GPT 164).

## Discarded

- GPT 93 "k = 1 of m = 199 gives ~100 % coverage, not 99 %": wrong. The truth is equally likely to be any of the
  200 ranks, so it lands outside [min, max] with probability 2/200 and inside with exactly 0.99 (tested).
- GPT 98 "check RH coverage after clipping": already done; scores are computed on the clipped output.
- GPT 103 "score physical pressure, not the departure": already the case (`to_physical` restores it before every
  score and calibration).
- GPT 120 "separate past-weather from future skill": already the product design (past dates use the actual ERA5
  profile).
- GPT Part 3 rebuild (schema module, typed forecast/query objects, transform graph, router, Zarr training store,
  transactional manifests, provider interface, layered uncertainty, 126-130, 133-140, 143-146): a large rewrite
  of working code with no accuracy gain; the useful cores are listed above in small form.
- Argon: "50 samples cap coverage at 96 %" (solved with order statistics, m = 199); two-number / sup-norm conformal
  scaling (our per-column map is a superset); low-rank Gaussian head (Gaussian tails, loses skew); the unsourced
  percentages; the drop-in code (different variables and grid, breaks every saved model).
