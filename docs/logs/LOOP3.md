# Improvement loop 3: the global architecture tried on Denver (user 2026-11-06, ~12 hours)

Purpose: stage **G1** of `docs/plans/GLOBAL_PLAN.md`. Every feature, slight change and structural change the two Gemini reports propose for a global model is tried here at small scale: **train on NM/TX only, ask about Denver (never seen), and check that NM/TX does not get worse.** Then the best changes are stacked, and the stack is trained on NM/TX + Denver together.

The adopted pilot model and its tool assets are not touched: every run writes new files `models/l3_<id>*`, all new code is behind new options whose default is the old behaviour, `tests/test_flags_off.py` must stay green.

## Rules (same spirit as loops 1-2)
- **Zero-shot verdict** (Denver, ERA5 truth, 2024-25): mean skill15 vs Denver climatology up by more than the Denver seed tolerance (measured in L3-0d), no height band worse by more than the tolerance, 99 % coverage error not worse by more than 0.0004.
- **No-regression verdict** (NM/TX, 2024-25): ERA5 headline within the pilot seed tolerance of the row's own baseline (skill15 0.0006), shape rule not FAIL. A change that helps Denver but costs NM/TX is recorded as "transfer-only" and not stacked by default.
- **Baseline of a row** = the row it modifies (stated in the row), so effects are measured one at a time.
- One GPU job at a time; CPU work (fetch, fits, scoring of finished runs) in parallel; 12 CPU threads at BelowNormal (`scripts/cap_cpu.sh`); no pytest while a GPU job runs.
- A run that crashes: fix once, rerun; second failure: `blocked`, next row (AUTOPILOT failure rules).
- Results: one line per row here + a summary row in `AUTOPILOT.md` (group L3); verdict logs in `data/l3_verdicts.txt`.
- Training budget per run: the p2f config (4 members, 6000 steps, ~13-20 min on the GPU) unless the row says otherwise; scoring ERA5 at both places (~10 min CPU).
- Harvest after every 4 rows (LOOP2 method): keep the positive part of a mixed result, restrict or damp the negative.

## Timeline (approximate; rows run in this order)
| Hours | Rows |
|---|---|
| 0-1.5 | L3-0 data and baselines (CPU fetch in parallel with the B-local GPU run) |
| 1.5-5 | L3-1 ... L3-7 input encodings (cheap: features only, same network) |
| 5-7.5 | L3-8 ... L3-10 target space and conditioning (structural) |
| 7.5-9.5 | L3-11 ... L3-14 terrain head, capacity, loss, sampling |
| 9.5-11 | L3-15 ... L3-19 calibration transfer, honesty tests (mostly CPU, overlap with the stack runs) |
| 11-12+ | L3-20 stack (NM/TX only) and L3-21 unified NM/TX + Denver; L3-22 export check |

## Rows
| ID | Kind | Change | Baseline | How | State |
|---|---|---|---|---|---|
| L3-0a | data | Denver ERA5 1991-2025 (13 levels + surface + w extras), profiles, dataset (dpd humidity, base features), Denver IGRA to 2025, Denver station map fitted 2016-2020 | — | `scripts/l3_0_data.sh` (fetch_earthmover / to_heights / fetch_igra / calibrate.station / build_dataset with `TEMPEST_REGION=configs/region_denver.toml`) | **done** 11:01: `denver_full_dpd.npz` 3,066,271 rows, 81 points (38-40N, 104-106W, elev 1395-2984 m), 1991-2025, same 13 cond and 179 target columns as NM/TX; station map `models/station_map_denver_full.npz` |
| L3-0b | baseline | **B-raw**: adopted p2f (NM/TX-trained) asked at Denver with raw lat/lon | — | `score` on the Denver dataset with the p2f range map | todo |
| L3-0c | baseline | **B-local**: same config trained on Denver 1991-2020 (upper bound) | — | train + spread (2021-23) + score on Denver | todo |
| L3-0d | baseline | Denver seed tolerance: B-local seed 1 vs seed 0 | — | second train, `compare_headline` | done: mean Δ < 0.0001, bands ±0.003 |
| L3-0e | baseline | **B-clim / B-gauss** at Denver (come with every `score` run) | — | read from L3-0b | todo |
| L3-1 | slight | Drop raw lat/lon (keep elevations, time, drivers) | p2f retrained on NM/TX with the same code path (L3-1r) | new `--features` option `nolatlon` | done: FAIL (NM/TX -0.010; Denver +0.034, T 12-18 km breaks) |
| L3-2 | slight | Spherical harmonics L = 10 in place of lat/lon | L3-1r | `tempest/geo/sh.py`, features `sh10` | done: FAIL (shape; Denver 4 % of gap) |
| L3-3 | slight | SH L = 20 | L3-2 | features `sh20` | done: FAIL (shape; Denver 14 % of gap) |
| L3-4 | structural | SH L = 10 through a 2-layer SIREN (64 units) before the network | L3-2 | model option `siren` | done: NM/TX PASS + shape PASS; Denver 22 % of gap, band FAIL (T 12-18 km) |
| L3-5 | feature | + terrain statics: Δz, sdor, slor, anor, isor, lsm, TPI (0.25° neighbours), distance to coast | best of L3-2/3/4 | `tempest/geo/statics.py`, features `+terrain` | queued (`ap_l3_lean.sh`) |
| L3-6 | feature | + physical clocks: Coriolis f, cos solar zenith, TOA insolation (keep sin/cos DOY and solar hour) | L3-5 | features `+clock` | sidelined 2026-11-06 |
| L3-7 | feature | + climatology inputs: climatological tropopause height and the per-height climatological mean/sd of T and wind for the place, month, hour (from training years) | L3-6 | `tempest/geo/clim.py`, features `+clim` | sidelined 2026-11-06 |
| L3-8 | structural | **SAMOS target space**: learn (y − μ_clim)/σ_clim per output column, μ, σ from a smooth harmonic climatology (3 annual × 2 diurnal harmonics) fitted per point on 1991-2020; samples are mapped back | L3-7 | dataset option `--anomaly`; Sampler un-standardises | sidelined 2026-11-06 |
| L3-9 | slight | SAMOS climatology smoothed in space (1° Gaussian), as the global model will have to use | L3-8 | `clim.py --smooth-km 100` | sidelined 2026-11-06 |
| L3-10 | structural | **Context FiLM**: location/terrain/climatology inputs go through a context MLP whose output shifts and scales every block (next to the noise FiLM) instead of being concatenated at the input | best of L3-7/8/9 | model option `context_film` | sidelined 2026-11-06 |
| L3-11 | structural | Altitude-decayed terrain head: output += exp(−z_AGL/H)·MLP(terrain) for the lowest heights, H learned (start 1 km) | L3-10 | model option `terrain_head` | sidelined 2026-11-06 |
| L3-12 | slight | Capacity for many places: width 768, depth 6 | best so far | config only | training; then scored (`ap_l3_lean.sh`) |
| L3-13 | slight | + vertical variogram term in the loss (weight 0.05) | best so far | `train.py` option `vario_weight` | sidelined 2026-11-06 |
| L3-14 | slight | Coordinate-only baseline: SH only (no terrain, no clim inputs, no SAMOS) — **honesty check, not a candidate** | — | features `sh10` alone vs the stack | sidelined 2026-11-06 |
| L3-15 | calibration | Range map / PIT map transfer: NM/TX-fitted map applied at Denver vs Denver-fitted map vs none | best model so far | `calibrate.spread` on each dataset, `score` | sidelined 2026-11-06 |
| L3-16 | calibration | Spread-conditional affine calibrator γ(x), β(x) (x = predicted spread, height band, Δz, hour), fitted on NM/TX 2021-23, applied at Denver | L3-15 NM/TX map | new `tempest/calibrate/condspread.py` | sidelined 2026-11-06 |
| L3-17 | calibration | **Pooled covariate balloon correction**: ~15 western-US IGRA stations (+ their ERA5 columns), Denver held out; regression of Δy(z) mean and spread ratio on ERA5 shear, N², Ri, z/BLH, sdor, Δz (no lat/lon, no station id) | Denver with no correction / with its own station map | `tempest/calibrate/covstation.py`, `scripts/l3_17_igra.sh` | sidelined 2026-11-06 |
| L3-18 | calibration | Pooled EGPD shear tail (shape per band shared, scale from ERA5 shear and N²) vs the present shear-tail map, both NM/TX-fitted, applied at Denver | present map | `tempest/calibrate/egpd_tail.py` | sidelined 2026-11-06 |
| L3-19 | test | DI / area-of-applicability: DI of Denver rows w.r.t. NM/TX training inputs; does DI predict the Denver error (correlation per column)? Plus the rotate-longitude check on the SH model (artifact should be ~0 once lat/lon are gone) | best model | `tempest/scoring/spatial.py` | sidelined 2026-11-06 |
| L3-20 | stack | All kept changes together, NM/TX only, 2 seeds | p2f (L3-1r) | config `generator_l3stack.toml` | sidelined 2026-11-06 |
| L3-21 | stack | Unified model NM/TX + Denver (box-balanced sampling: each box drawn equally often) vs the two separate models | L3-20 at NM/TX, L3-0c at Denver | merged dataset | sidelined 2026-11-06 |
| L3-22 | deploy | ONNX export of L3-21, FP16 and dynamic INT8: CRPS and 99.9th shear vs FP32, time for 100 members on 4 CPU cores | L3-21 | `scripts/l3_onnx.py` | sidelined 2026-11-06 |
| L3-23 | structural | **ctxsep**: L3-10 ctxall with the context in its own zero-initialised FiLM per block (was added to the noise embedding, so one weight matrix served both) | L3-10 | config `context_film_sep`, model `ctx_sep` | queued (`ap_l3_lean.sh`) |
| L3-24 | slight | **sirenw15**: L3-4 with SIREN first-layer frequency w0 = 15 (SIREN-paper init) | L3-4 | config `geo_siren_w0` | queued (`ap_l3_lean.sh`) |
| L3-25 | data | **Denver with mountain rows**: rebuild with `build_dataset --fill-top` (heights above the 50 hPa top copy the highest valid one); score p2f zero-shot on it vs the present Denver set | L3-0b | `ap_l3_more.sh` | queued (`ap_l3_lean.sh`) |
| L3-26 | structural | **studt** (Gemini idea 1, improved): p2f with 8 of the 32 noise numbers Student-t (ν = 4, unit variance); the first 4 also scale a zero-init output head after the last layer norm (the layer norms otherwise erase an extreme draw's size) | p2f | config `noise_t_dims`, `noise_t_head` | queued (`ap_l3_lean.sh`) |
| L3-27 | structural | **jump** (Gemini idea 3): learned tanh jumps (inversions; BLH centre prior) + a T kink at the tropopause (climatological prior), head only, base frozen, on IGRA-resolution targets | p2f | config `generator_l3_jump_igra.toml` | **waits for IGRA** (user) |

## Harvest notes
(filled every 4 rows)

## Results
(one line per row: the zero-shot and no-regression numbers, verdict, kept or not)
- **L3-0b B-raw** (p2f zero-shot at Denver, 2024-25): mean skill15 **-0.1764** vs Denver climatology, all 19 bands negative except v 5-12 km. Worst: u 0-1 km -1.76 (MAE 8.2 vs 2.9 m/s local), RH 12-18 km -0.28, rh2m -0.28, sp -0.11, T 0-1 km -0.11; cov99 down to 0.950. The low levels and the surface fail most, i.e. the 1.4-3.0 km terrain (NM/TX tops out lower) is what the model has never seen.
- **L3-4 siren** (SH L=10 through a 64-unit SIREN): NM/TX skill15 +0.0277 → +0.0278 (PASS), coverage PASS, **shape PASS** (vcorr_err 0.076 → 0.075; the plain sh10 had 0.098). Denver zero-shot -0.1764 → **-0.1377** (22 % of the gap, best coordinate row so far): u 0-1 km -1.76 → -1.32, RH 12-18 km +0.14, T 0-1 km +0.06; but **T 12-18 km -0.006 → -0.30** (cov99 0.959) and u 12-18 km -0.06, RH 1-5 km -0.05, so band rule FAIL. Candidate for the stack once the upper-T loss is fixed (clim inputs L3-7 carry the stratospheric T the coordinates are dropping); retest on G2 multi-box (single-box SH tests are weak: the basis is nearly collinear over 3°x7°).
- **L3-0c B-local** (same config trained on Denver 1991-2023): mean skill15 **+0.0162**, worst band -0.0028, cov99 0.983-0.996. The architecture target: close >= 50 % of the 0.193 gap without losing NM/TX.
- L3-0d: blocal_s1 crashed once (transient cuBLAS execution failure at ~2 min, not OOM: 6.5 GB host RAM free); `ap_l3.sh` reruns it before the next row. Retry trained cleanly (15.3 min, 12:14); **Denver seed tolerance: mean skill15 +0.0162 both seeds (Δ < 0.0001), bands within ±0.003 (worst v 0-1 km +0.0028, T 12-18 km -0.0023), cov99 ≥ 0.980.** Zero-shot gains under ~0.003 per band at Denver are noise.
- **L3-2 sh10**: NM/TX skill15 +0.0277 → +0.0270 (-0.0007, at the 0.0006 tolerance: neutral to slightly worse), no band worse, coverage PASS, but **shape FAIL** (vcorr_err 0.076 → 0.098, shear_ks 0.020 → 0.024, event_cov_gap T 1-5 km). Denver zero-shot -0.1764 → **-0.1684** (4 % of the gap): RH 12-18 km and sp better, but **u 0-1 km stays at -1.77** (nolatlon fixed it). So the degree-10 SH features extrapolate at Denver like raw lat/lon do, and they hurt vertical coherence. Not kept; decide on SH normalisation after sh20.
- **L3-3 sh20**: NM/TX skill15 +0.0277 = p2f (neutral), no band worse, coverage PASS, **shape FAIL** worse than sh10 (vcorr_err 0.076 → 0.135, shear_ks 0.020 → 0.024). Denver zero-shot -0.1764 → **-0.1496** (14 % of the gap): T 0-12 km, RH 12-18 km, sp, rh2m better, u 0-1 km only -1.76 → -1.55, T 12-18 km -0.15, u 12-18 km -0.07. Not kept.
- **SH normalisation: not queued.** The SH values enter the network unstandardised (orthonormal, O(1), `model._geo`). Inside one 3°×7° box they hardly vary, so the network needs large weights to use them, and those weights extrapolate at Denver. Standardising them by the box's spread would make Denver many standard deviations away, i.e. worse. No coordinate encoding can learn how weather changes with place from one box: both SH rows only cost vertical coherence. Location must come from inputs that describe the place (terrain L3-5, climatology L3-7, ctxall L3-10, still queued) and from training on more places (G2 / the global store). The SH rows go back to the table at G2, when there are several boxes to learn from.
- **L3-1 nolatlon**: NM/TX **FAIL** (skill15 +0.0277 → +0.0179, -0.0098 = 16× the seed tolerance; u/v 0-1 km -0.018; coverage PASS, shape PASS with 4 metrics better). Denver zero-shot skill15 -0.1764 → **-0.1425** (closes 18 % of the 0.193 gap; target 50 %): u 0-1 km -1.76 → -0.14 (the lat/lon extrapolation was the main u failure), but T 12-18 km -0.006 → -0.57, T 5-12 km -0.15, t2m -0.23, cov99 down to 0.908. Lat/lon was carrying the stratospheric T climate and surface temperature; dropping it fixes the low wind and breaks the upper T. **Not kept alone**; it is the base the SH rows (sh10/sh20) replace lat/lon with, so their Denver T 12-18 km is the number to watch.

### Run notes (2026-11-06)
- **Gemini review (2026-11-06, triage `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md`) found that every Denver number so far is on the low ground only**: the Denver build dropped 934,359 of 4.0 M rows (23 %) because columns over ground above ~2.6 km put the 18 km-AGL top above the 50 hPa level (NaN, then the row is dropped). NM/TX lost 0-1 rows. B-raw, B-local and every Denver zero-shot score exclude the high Rockies. L3-25 measures how much that changes the picture; comparisons inside loop 3 stay valid (all on the same rows).
- **Queue cut (user, 2026-11-06): only the important runs + Gemini.** `scripts/ap_l3_lean.sh` replaces the default queue, `ap_l3_data.sh` (D1-D7) and `ap_l3_more.sh`: Denver fill-top rescore → w768 (already training) → terrain → ctxsep → sirenw15 → studt → jump. Sidelined (rows kept, nothing deleted): L3-6..11, L3-13..22, the sh10ctx retry (SH already failed shape), the D1-D7 data-need runs. Gemini idea 2 (Pairformer) removed (user); L3-27 jump waits for IGRA (config renamed, so the running queue skips it and logs a harmless "no config" / failed Denver score for `jump`). See `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md`.
- sh10ctx training died at step 2000 (13:50) with `CUBLAS_STATUS_INTERNAL_ERROR` (one-off, like blocal_s1). Retried by `scripts/ap_l3_more.sh` after the D1-D7 data queue, together with L3-23/24 and L3-25.
- L3-8 SAMOS note (review): the loss standardises rebuilt profiles with ONE global mean/sd (`train.py` pm, ps). Fine for one box; for G2/G4 standardise each row by its local climatological sd, or temperature (equator-pole spread ~40 K) is down-weighted 5-8x against wind. Standardise levels, not steps, if SAMOS is done in target space.
- Runner `scripts/ap_l3.sh` (resume wrapper `scripts/ap_l3_resume.sh`). Model files `models/l3_<v>.pt`, configs `configs/generator_l3_<v>.toml` = p2f + the row's keys. Queue: nolatlon (L3-1), sh10 (L3-2), sh20 (L3-3), siren (L3-4), sh10ctx (L3-10a: elevations through the context FiLM), w768 (L3-12), terrain (L3-5), clocks (L3-6), clim (L3-7), ctxall (L3-10: elevations + terrain + climatology through the context FiLM), thead (L3-11).
- NM/TX baseline: the adopted p2f itself. L3-1r is not needed because seeds s1/s2 already give the tolerance: skill15 −0.0006 / −0.0001 against p2f.
- L3-5/6/7/10/11 use one overlay per dataset (`scripts/l3_overlay.py` → `data/train/*_l3x.npz`, 12 extra columns; the variants switch groups off with `ignore_inputs`). They run on p2f, not on the best SH row, so they can run during the SH rows; the stack (L3-20) combines the winners.
- Climatology inputs are fitted on years ≤ 2020 only. Profile targets are height steps, so a level climatology is the sum of the step means up to that level. (The first build used raw steps by mistake, e.g. 0.9 m/s for "u at 5 km"; it was rebuilt before any run used it.)
- Expected caveat for SH: degree 10 resolves about 18° and degree 20 about 9°, both coarser than the 6° NM/TX box. Inside the box the SH features are nearly constant, so on NM/TX they can at best match nolatlon. Their value is global (G2 onward). The Denver zero-shot test still applies.
- nolatlon training hit a CUDA OOM at step ~500. The likely cause is host RAM exhaustion while the overlay was being built (1.1 GB available). It is retried automatically. Rule: don't build overlays while a GPU job is running.
- `ap_l3_resume.sh` had a function named `tr` that called `tr -d` itself, so it recursed endlessly (about 1,300 processes). It was killed after about 20 minutes, with no effect on the sh10 training. The function is renamed `ntrain`.
- L3-0c/0d B-local now lives in `ap_l3.sh` (`blocal`): configs `generator_l3_blocal.toml` (p2f) and `_blocal_s1.toml` (seed 100, as p2f_s1). Before each queue row, if the Denver dataset exists: B-raw, then train/calibrate/score both on Denver, then write the verdicts "B-local vs B-raw" and "Denver seed tolerance".
