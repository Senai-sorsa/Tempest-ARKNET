# Improvements tried (concise) — as of 2026-11-08

One line per item. IDs point to the full logs: `IL-n` / `F-n` / `L3-n` in `docs/logs/AUTOPILOT.md` and `docs/logs/LOOP3.md`, `P-n` = numbered pilot-phase items in `docs/plans/PLAN.md` (the 1-22 table), `P3-n` / `P5-n` = PLAN phase 3 / phase 5 rows. Numbers are from those logs. Bug fixes are in `Fixes-Concise.md`. Next steps are in `To-do-Concise.md`.
Compiled from AUTOPILOT, LOOP3, PLAN, FINAL_REPORT, APPLIED_STATUS, SIDELINED and the review triage files; a few old rows have no recorded verdict and are marked "no verdict recorded".

Tags: **[KEPT]** in the shipped system or an opt-in flag. **[FAIL]** tested, no gain or worse. **[?]** neutral, mixed or inconclusive.

---

## 1. TO DO

**Do first (user, 2026-11-07). Code for IL-109 (`--tol`), IL-110 and IL-111 is done 22:00 Nov 7 (opt-in); all other fixes are in `Fixes-Concise.md` and run before any idea below.**
1. IL-109: replace the "within 0.0006" gate with a 3-seed paired tolerance.
2. IL-110: effective sample count and bootstrap interval for every tail number.
3. IL-111: gates must also beat a margin over climatology and the Gaussian/GRAM-style baseline.
4. IL-112: derive the shear-vs-IGRA gate from the 987-station scatter (waits for `igra_heights`).
5. IL-117: check every `era5_cds` consumer masks below-ground rows (ARCO vs CDS humidity differs under terrain).

**Long-range (5 GB download budget; data arrived)**
6. IL-118: Mode M test — ridge on weekly anomalies vs E12 per week (`wb2_ifs_extended` is on disk; window = 168 h from 12 h before day k).
7. IL-120: skill-by-lead table (vs trend-aware climatology and Gaussian baseline).
8. IL-121: fix T 12-18 km (negative skill on 2026): recent-years fit or per-year shift.
9. IL-74: blend mode F into the climate generator by lead.
10. IL-119: add MJO and PNA/AO to the slow predictors.
11. IL-122: trend-aware climatology for 2027+ queries.
12. IL-123: pick climatology years by ENSO/QBO/MJO phase.
13. IL-124: score weekly and monthly mean anomalies, not just single hours.
14. IL-125: soil moisture and SST predictors (small point download, approved).
15. IL-126: calibrate spread as a function of lead.
16. IL-127: GraphCast/Pangu as extra first guess for days 5-10 (low priority).

**Tails and gates**
17. IL-103: fit the shear/wind tail on balloons, not ERA5.
18. IL-104: cap the shear overshoot (stack gives 1.7x ERA5).
19. IL-105: calibrate shear as its own target after the shuffle.
20. IL-106: regime-conditioned tails (jet, stability, hour, terrain).
21. IL-107: tail-weighted scores (upper 1 %, exceedance).
22. IL-108: validate shear above 18 km with the extended IGRA heights.

**Validity of results**
23. IL-113: second untouched confirmation window (2024-25 is development data).
24. IL-114: split balloon scores by stations seen vs unseen (ERA5 assimilates sondes).
25. IL-115: trend-aware climatology baseline next to the fixed one.
26. IL-116: label layers above 18 km "filled, not skilled"; keep out of the headline.
27. IL-143: rescore L3-43 `fill_mask` with filled heights masked (verdict may change).
28. IL-76: retrain with validation 2021-22 and calibration 2023 only (they overlap now).

**From the Gemini code review (`tempest_weather`; see Fixes-Concise.md)**
29. IL-128: whole-profile selection instead of Gaussian-copula rebuild (reproduce the loss first).
30. IL-129: linear tail extrapolation in `_cdf`/`_ppf` for conditioning.
31. IL-130: Dryden N², boundary-layer floor, resolved w (with S1).
32. IL-131: 0 m pad node and geopotential altitude conversion.
33. IL-132: `site_shift` artificial lapse change — test two alternatives.
34. IL-133: update `w` after the coherence reordering.
35. IL-134: lead-dependent surface-pressure spread in past/forecast modes.
36. IL-135: per-sample boundary-layer height and gust peak.
37. IL-137: smooth the shear map in metres, not 9 heights.
38. IL-138: conditioning inflation that decays with correlation distance.
39. IL-139: permute within `M_CAL` blocks before slicing `[:n]`.
40. IL-140: make `pit_recal.apply` keep the input member order (opt-in).
41. IL-141: smooth the trust-blend weights across heights.
42. IL-142: debias humidity in the transformed coordinate.
43. IL-136: low priority: acoustics moist sound speed, one saturation formula.

**Mode F and generator follow-ups still open**
44. IL-81: shape metrics for mode F per lead (main target).
45. IL-83: same vertical-coherence check for the climate generator (main target).
46. IL-87: date-block bootstrap for mode F shape numbers.
47. IL-78: mode F on live forecasts (network trained on archived HRES).
48. IL-79: mode F at any lead (lead as continuous input).
49. IL-75: second HRES pull, 00+12 UTC every 2nd day (optional).
50. IL-102: damped PIT recalibration (half-way).
51. IL-6: calibrate modes F/F2 on WeatherBench2 HRES — log shows "running"; state not updated, check.

**In progress or waiting**
52. L3-44: 21 pressure-level build (running).
53. L3-27 jump head (inversions): waits for IGRA balloon targets.
54. Fetch chain: global extras → IGRA 987 stations → 6 G2 boxes.
55. G0 global loader with holdout and 2026 guard; statics join.
56. int16 tail check on the global store.
57. G2 training (8 boxes, leave-one-box-out), then G3/G4.
58. Launch plan: A2 launch-day correction, A1 80 km extension, A3 tails, tracer-drift check.
59. Test #3 future climate.
60. `tempest_weather` v2 upgrade: Section 1 bug fixes (F1-F3, S1, F6, C3), then flexibility, speed, usage, validation (`docs/plans/SECTIONS_PLAN.md`).
61. GLOBAL_PLAN §7.2: 7 candidate ideas logged, not run.
62. IL-30 / IL-64 / F-17: 21-level Mode P retrain (blocked on L3-44 data).

---

## 2. WORKED

**Pilot-phase model (PLAN items)**
1. P-1 [KEPT] surface pressure as departure from standard: sp skill -0.072 → -0.010.
2. P-2 [KEPT] step loss on height-to-height differences: variogram v -0.087 → -0.034.
3. P-3 [KEPT] range calibration on ERA5: 99 % coverage 0.980-0.997 per band.
4. P-5 [KEPT] calibration fitted on 5 years (2019-23): worst column T 5-12 km 0.963 → 0.982.
5. P-7 [KEPT] balloon-leftover draws by moisture: RH CRPS 9-13 km 5.78 → 5.34.
6. P-9 [KEPT] fixed validation noise at early stopping (it moved the val loss by about 0.002).
7. P-10 [KEPT] station-corrected model (st2) over the plain one.
8. P-19 [KEPT] station correction fitted on 1991-2020 (leak fix).
9. P-21 [KEPT] 4 members trained side by side; 6000 steps is enough.
10. P3-1 [KEPT] gust module (Gumbel).
11. P3-2 [KEPT] vertical wind head.
12. P3-4 [KEPT] soak history.
13. P3-7 [KEPT] regression index forecast (ENSO/QBO/WWV).
14. P3-8 [KEPT] coupled file.
15. P5-1, P5-2, P5-3, P5-5, P5-7 [KEPT] tool exporter and engine, distributions and coupling, four calls and ranking, standalone ops, validation. P5-4 partly (2 of 5 modes live), P5-6 partly (flight-sim readers).

**Tool and mode F**
16. F-8 forecast mode in the tool (0.75-7.5 days).
17. IL-73 mode F first version: CRPS skill 0.69 / 0.54 / 0.34 / 0.18 at 1 / 3 / 5 / 7 days (test 2022).
18. IL-80 [KEPT] 50:50 mix of network and ridge: 0.691 / 0.539 / 0.350 / 0.209.
19. IL-82 [KEPT] Schaake shuffle for mode F: vertical correlation error 0.30-0.51 → 0.04-0.12.
20. F-12 [KEPT] past-date surface spread: t2m CRPS 1.16 → 0.68 K, sp 48.8 → 25.9 Pa.
21. F-11 part 1 [KEPT] station-correction hybrid for RH 12-18 km: CRPS 3.70 vs 4.76 (network).
22. F-13 ridge-driver scoring for unknown drivers.
23. F-27 [KEPT] w-head range map: cov99 0.984 → 0.990 (opt-in asset).
24. IL-98 B [KEPT] online EWMA bias tracker: surface MAE lower in nearly every cell, never worse.
25. IL-101 [KEPT] station-scale widening of 10 m wind: 90 % interval 59-80 % → 88-89 %.

**Shape stack (final system)**
26. IL-91 / F-16 [KEPT] shuffle + whole-distribution shear map: vertical corr 0.08 → 0.03, shear KS 0.044 → 0.010.
27. IL-16 [KEPT] final stack A = shuffle with 2° templates + refit shear map (dev: shear 0.0196 → 0.0090; 2026: 0.0333 → 0.0274).
28. IL-92 / IL-93 noise floor and seed tolerance (ERA5 skill15 0.0006, balloons 0.0013).
29. IL-94 / IL-95 / IL-96 tool version of the shape stack, template resolution, refit shear map.
30. IL-11 [KEPT as flag] seasonal widths for RH and surface: cov error 0.0034 → 0.0025 (ERA5).
31. IL-58 [KEPT as flag] whole-distribution shear map (shape metrics better, headline unchanged).

**Loop 3 (Denver transfer, all hours)**
32. L3-29 DI-gated trust blend: Denver -0.1918 → +0.0099 (physics worse, see list 4, item 45).
33. L3-33 stack + shuffle: NM/TX +0.0278; Denver +0.0100, every band skill15 > 0.
34. L3-35 [KEPT] shuffle blocks on the real grid (9 x 9); c8 kept.
35. L3-38 / L3-39 [KEPT] all 24 hours: night -0.0072 → +0.0274, day unchanged over 3 seeds.
36. L3-40 / L3-41 [KEPT] Denver all-hours stack: night +0.0088 → +0.0102, day inside tolerance.
37. L3-42 [KEPT] NM/TX stack on all hours (new base `l3_h_all24`).

**Findings that changed the plan (not model gains)**
38. L3-0b / L3-0c baselines: never-seen box -0.1764 vs local +0.0162.
39. L3-25 Denver is harder than measured (mountain columns dropped 23 %): -0.1764 → -0.1918 with fill-top.
40. L3-31 / L3-32 calibration adds the surface jumps and superadiabatic layers; Denver inversion error is in the model.
41. IL-67 T 12-18 km target shifted around 2020 (balloon-ERA5 -0.5..-0.9 K to -1.05..-1.10 K).
42. P-18 audit: no overfitting; model is input-limited.
43. D1-D7 data-need runs: keep 1991-2025 and every hour (13 yrs +0.0050, 23 +0.0221, 33 +0.0277); 0.5° lattice loses nothing.

---

## 3. SIDELINED (not done, code and flags stay)

**Cut by the capped loops (user)**
1. L3-6 physical clocks; L3-7 climatology inputs; L3-9 smoothed SAMOS; L3-10 context FiLM; L3-11 terrain head; L3-13 variogram loss; L3-14 coordinate-only baseline.
2. L3-8 SAMOS target space: sidelined, but the G2 design candidate.
3. L3-15 to L3-19: range-map transfer, spread-conditional calibrator, pooled balloon correction, pooled EGPD tail, DI test.
4. L3-20 / L3-21 / L3-22: stacks, unified NM/TX + Denver model, ONNX export.
5. Gemini idea 2 (Pairformer trunk) removed; idea 3 (jump head) waits for IGRA.
6. IL-8 height-token generator: deferred (about 5.6 h for 6000 steps, worse early validation); IL-9, IL-23, IL-29 depend on it.

**Generator shape, loss and noise ideas skipped on purpose**
7. IL-46 repair interior shape directly; IL-47, IL-48, IL-49 loss variants.
8. IL-50 noise shape; IL-51 conditional shape; IL-52 clipped RH ends; IL-53 keep marginals, restore joint shape.
9. IL-61, IL-62 heavier tails in the network; IL-63 raw-sounding comparison; IL-65 last-in-track map.
10. IL-68, IL-69, IL-70, IL-71 worst-cell fixes (vertical correlation, PIT, month x band shift, event coverage).
11. IL-24 worst-cell blends; IL-25 patch rate fit; IL-100 dynamic balloon leftover in training.
12. IL-43 / IL-44 / IL-45 stress-table diagnostics (partly done, first batch).

**Shifts, index forecasts, small items**
13. IL-14 Chronos + regression for ONI/WWV (tied in the bake-off); IL-26 phase-aware QBO; IL-27 WWV scaling.
14. IL-15 Mode P tendency inputs; IL-17 analog-driver K tuning; IL-18 shear codebook / spectral probes.
15. IL-19 / IL-20 / IL-21 / IL-22 shift per year / per month / joint fit / stack re-fit (IL-19 now feeds IL-121).

**Needs the flight simulator (stage 6)**
16. IL-31 landing-scatter proof; IL-33 + G `observe()` conditioning (scheduled for stage 6); IL-35 / IL-36 time and downrange coherence (before stage 6).
17. IL-38, IL-39, IL-40, IL-41 tails/readers/noise labels/trust line; IL-42 beyond the pilot box (feasibility note only).
18. Discarded by the user: IL-32 vehicle-sensitivity loss, IL-34 tail importance sampling, IL-37 launch-window query layer, above-18 km extension (later reinstated as the 80 km A1 plan).

**Blocked on data or on you**
19. IL-6, IL-30, IL-64, IL-75, F-17 (Colab pulls and the 21-level build).
20. Group R (other places, hours, far future): R-2, R-3, R-4, R-7, R-8, R-9.

**Ideas from the other session's plan (`Strong improvment.md`)**
21. G `observe()` weighting; H sample-derived lapse in `to_site`; I spread-conditioned width; K Haar/DCT vertical CRPS; J ConvToken; L lagged-run ensemble.
22. C live-ensemble EMOS (waits for 60-90 days of logger); A, D, E, F (HRES refetch consequences, richer mode F inputs, per-lead ridge cascade, multi-model first guess) need Colab pulls.

**Loop 2 and not planned**
23. H5 shear map per season (inside noise); IL-79 continuous lead (needs data).
24. A4 GFS-on-AWS download (about 160 GB; the Colab pull replaces it).
25. Real Earth-GRAM (needs NASA; Gaussian proxy scored instead).
26. R-6 North America build; second HRES diurnal pull (ASK_LATER 8).

---

## 4. FAILED OR INCONCLUSIVE

**Pilot-phase model (PLAN items)**
1. P-4 [FAIL] balloon range calibration on 2023: T 1-5 km 0.989 → 0.979, RH 1-5 km 0.997 → 0.983.
2. P-8 [FAIL] range calibration split by season or spread tercile (cov99 0.990-0.991 vs 0.992).
3. P-6 [?] liquid-water ERA5 RH: raw bias -8..-16 % → -1 %, but after the station fit almost no gain.
4. P-11 [FAIL] moisture-tercile station leftovers (st2 kept).
5. P-12 [FAIL] balloon calibration on 5 years: RH collapses where one pooled band is off.
6. P-13 [FAIL] afCRPS alpha 0.99 (0.95 kept).
7. P-14 [FAIL] balloon calibration one map per column; flag removed.
8. P-15 [FAIL] ERA5 calibration on the latest 3 years only.
9. P-16 [FAIL] ERA5 calibration on 150k rows (60k kept).
10. P-17 [?] month-block bootstrap: no change, every 95 % interval contains 0.99.
11. P-20 [?] block validation option: no verdict recorded (F-7b discarded the same idea).
12. P-22 [FAIL] training years 1980-2020: T worse on both truths (B0 kept).
13. P3-5 [FAIL] longer record 1980-2023 with global-temperature input: cold bias stays.
14. P3-3 [?] thermals module built, off; check blocked.

**Review-driven experiments (F-n)**
15. F-7 / F-7b [FAIL] split validation windows: skill15 +0.0277 → +0.0254.
16. F-9 [?] u100 / 2 m dew-point ratios: neutral (kept: physical).
17. F-10 [FAIL] ERA5 along the balloon path: not worth a retrain.
18. F-11 part 2 [FAIL] post-2022 indicator: no gain.
19. F-14 [FAIL] driver interactions: skill15 +0.0277 → +0.0003 (far worse).
20. F-15 [FAIL] m = 8 samples per row: no gain, vertical correlation slightly worse.
21. F-19 [FAIL] RH in the loss (weight 0.3): +0.0277 → +0.0276.
22. F-20 [FAIL] station-blend dataset (first run invalid; redo no better).
23. F-23 [?] spread-fit order-statistic fix: inside seed noise.
24. F-24 [?] dynamic balloon leftover target: not pursued.
25. F-25 [FAIL] soak library wind matching; F-26 [FAIL] gust stability inputs.
26. F-29 [?] float16 vs float32 training rows: no effect.

**Autopilot / loop items (IL-n)**
27. IL-3, IL-10, IL-12, IL-13, IL-54..IL-57 [FAIL] discarded by the rule (gains under the 0.001 margin; IL-13 shift tiny).
28. IL-66 [FAIL] shift fitted on 2011-2023 hurts ERA5 (+0.0277 → +0.0266).
29. IL-72 [FAIL] recent-years balloon offset: zero for temperature, -3.2 % RH.
30. IL-77 [?] mode F regularisation: no gain over the existing settings.
31. IL-85 [?] PIT recalibration for mode F: no gain on 2022.
32. IL-86 [?] PIT recalibration for the climate generator alone: mixed.
33. IL-97 [FAIL] restricted ONI x QBO interactions: +0.0277 → +0.0274, shape worse.

**Loop 3 (Denver transfer)**
34. L3-1 [FAIL] drop raw lat/lon (NM/TX -0.010; Denver T 12-18 km breaks).
35. L3-2 / L3-3 [FAIL] spherical harmonics L = 10 / 20 (shape fails).
36. L3-4 [?] SH L=10 + SIREN: NM/TX and shape pass, Denver 22 % of gap, T 12-18 km band fails.
37. L3-5 [FAIL] terrain statics (Denver -0.207 vs -0.192; shape fails).
38. L3-12 [FAIL] width 768, depth 6.
39. L3-23 [FAIL] ctxsep (+0.0250 vs +0.0277, shape fails).
40. L3-24 [FAIL] SIREN w0 = 15 (shape fails, Denver -0.182).
41. L3-26 / L3-30 [FAIL] Student-t noise and its clip (vertical correlation 0.076 → 0.109).
42. L3-34 [?] debias alone fixes Denver (-0.1918 → -0.0313) but fails when stacked and ruins humidity coverage; L3-36 without humidity: inside noise.
43. L3-37 [?] Sobol noise: neutral (-0.0002 over 3 seeds), dropped.
44. L3-43 [?] `fill_mask`: neutral (+0.0154 = +0.0154), dropped — the scoring may have used filled truth (IL-143).
45. L3-29 / L3-33 [?] trust blend wins on skill but physics worse (superadiabatic 0.283 → 0.474; fixed partly by the shuffle).
