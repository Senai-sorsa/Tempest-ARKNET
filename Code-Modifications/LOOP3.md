# Improvement loop 3: the global architecture tried on Denver (user 2026-11-06, ~12 hours)

Purpose: stage **G1** of `docs/GLOBAL_PLAN.md`. Every feature, slight change and structural change the two Gemini reports propose for a global model is tried here at small scale: **train on NM/TX only, ask about Denver (never seen), and check that NM/TX does not get worse.** Then the best changes are stacked, and the stack is trained on NM/TX + Denver together.

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
| L3-0a | data | Denver ERA5 1991-2025 (13 levels + surface + w extras), profiles, dataset (dpd humidity, base features), Denver IGRA to 2025, Denver station map fitted 2016-2020 | — | `scripts/l3_0_data.sh` (fetch_earthmover / to_heights / fetch_igra / calibrate.station / build_dataset with `TEMPEST_REGION=configs/region_denver.toml`) | todo |
| L3-0b | baseline | **B-raw**: adopted p2f (NM/TX-trained) asked at Denver with raw lat/lon | — | `score` on the Denver dataset with the p2f range map | todo |
| L3-0c | baseline | **B-local**: same config trained on Denver 1991-2020 (upper bound) | — | train + spread (2021-23) + score on Denver | todo |
| L3-0d | baseline | Denver seed tolerance: B-local seed 1 vs seed 0 | — | second train, `compare_headline` | todo |
| L3-0e | baseline | **B-clim / B-gauss** at Denver (come with every `score` run) | — | read from L3-0b | todo |
| L3-1 | slight | Drop raw lat/lon (keep elevations, time, drivers) | p2f retrained on NM/TX with the same code path (L3-1r) | new `--features` option `nolatlon` | todo |
| L3-2 | slight | Spherical harmonics L = 10 in place of lat/lon | L3-1r | `tempest/geo/sh.py`, features `sh10` | todo |
| L3-3 | slight | SH L = 20 | L3-2 | features `sh20` | todo |
| L3-4 | structural | SH L = 10 through a 2-layer SIREN (64 units) before the network | L3-2 | model option `siren` | todo |
| L3-5 | feature | + terrain statics: Δz, sdor, slor, anor, isor, lsm, TPI (0.25° neighbours), distance to coast | best of L3-2/3/4 | `tempest/geo/statics.py`, features `+terrain` | todo |
| L3-6 | feature | + physical clocks: Coriolis f, cos solar zenith, TOA insolation (keep sin/cos DOY and solar hour) | L3-5 | features `+clock` | todo |
| L3-7 | feature | + climatology inputs: climatological tropopause height and the per-height climatological mean/sd of T and wind for the place, month, hour (from training years) | L3-6 | `tempest/geo/clim.py`, features `+clim` | todo |
| L3-8 | structural | **SAMOS target space**: learn (y − μ_clim)/σ_clim per output column, μ, σ from a smooth harmonic climatology (3 annual × 2 diurnal harmonics) fitted per point on 1991-2020; samples are mapped back | L3-7 | dataset option `--anomaly`; Sampler un-standardises | todo |
| L3-9 | slight | SAMOS climatology smoothed in space (1° Gaussian), as the global model will have to use | L3-8 | `clim.py --smooth-km 100` | todo |
| L3-10 | structural | **Context FiLM**: location/terrain/climatology inputs go through a context MLP whose output shifts and scales every block (next to the noise FiLM) instead of being concatenated at the input | best of L3-7/8/9 | model option `context_film` | todo |
| L3-11 | structural | Altitude-decayed terrain head: output += exp(−z_AGL/H)·MLP(terrain) for the lowest heights, H learned (start 1 km) | L3-10 | model option `terrain_head` | todo |
| L3-12 | slight | Capacity for many places: width 768, depth 6 | best so far | config only | todo |
| L3-13 | slight | + vertical variogram term in the loss (weight 0.05) | best so far | `train.py` option `vario_weight` | todo |
| L3-14 | slight | Coordinate-only baseline: SH only (no terrain, no clim inputs, no SAMOS) — **honesty check, not a candidate** | — | features `sh10` alone vs the stack | todo |
| L3-15 | calibration | Range map / PIT map transfer: NM/TX-fitted map applied at Denver vs Denver-fitted map vs none | best model so far | `calibrate.spread` on each dataset, `score` | todo |
| L3-16 | calibration | Spread-conditional affine calibrator γ(x), β(x) (x = predicted spread, height band, Δz, hour), fitted on NM/TX 2021-23, applied at Denver | L3-15 NM/TX map | new `tempest/calibrate/condspread.py` | todo |
| L3-17 | calibration | **Pooled covariate balloon correction**: ~15 western-US IGRA stations (+ their ERA5 columns), Denver held out; regression of Δy(z) mean and spread ratio on ERA5 shear, N², Ri, z/BLH, sdor, Δz (no lat/lon, no station id) | Denver with no correction / with its own station map | `tempest/calibrate/covstation.py`, `scripts/l3_17_igra.sh` | todo |
| L3-18 | calibration | Pooled EGPD shear tail (shape per band shared, scale from ERA5 shear and N²) vs the present shear-tail map, both NM/TX-fitted, applied at Denver | present map | `tempest/calibrate/egpd_tail.py` | todo |
| L3-19 | test | DI / area-of-applicability: DI of Denver rows w.r.t. NM/TX training inputs; does DI predict the Denver error (correlation per column)? Plus the rotate-longitude check on the SH model (artifact should be ~0 once lat/lon are gone) | best model | `tempest/scoring/spatial.py` | todo |
| L3-20 | stack | All kept changes together, NM/TX only, 2 seeds | p2f (L3-1r) | config `generator_l3stack.toml` | todo |
| L3-21 | stack | Unified model NM/TX + Denver (box-balanced sampling: each box drawn equally often) vs the two separate models | L3-20 at NM/TX, L3-0c at Denver | merged dataset | todo |
| L3-22 | deploy | ONNX export of L3-21, FP16 and dynamic INT8: CRPS and 99.9th shear vs FP32, time for 100 members on 4 CPU cores | L3-21 | `scripts/l3_onnx.py` | todo |

## Harvest notes
(filled every 4 rows)

## Results
(one line per row: the zero-shot and no-regression numbers, verdict, kept or not)

### Run notes (2026-11-06)
- Runner `scripts/ap_l3.sh` (resume wrapper `scripts/ap_l3_resume.sh`). Model files `models/l3_<v>.pt`, configs `configs/generator_l3_<v>.toml` = p2f + the row's keys. Queue: nolatlon (L3-1), sh10 (L3-2), sh20 (L3-3), siren (L3-4), sh10ctx (L3-10a: elevations through the context FiLM), w768 (L3-12), terrain (L3-5), clocks (L3-6), clim (L3-7), ctxall (L3-10: elevations + terrain + climatology through the context FiLM), thead (L3-11).
- NM/TX baseline: the adopted p2f itself. L3-1r is not needed because seeds s1/s2 already give the tolerance: skill15 −0.0006 / −0.0001 against p2f.
- L3-5/6/7/10/11 use one overlay per dataset (`scripts/l3_overlay.py` → `data/train/*_l3x.npz`, 12 extra columns; the variants switch groups off with `ignore_inputs`). They run on p2f, not on the best SH row, so they can run during the SH rows; the stack (L3-20) combines the winners.
- Climatology inputs are fitted on years ≤ 2020 only. Profile targets are height steps, so a level climatology is the sum of the step means up to that level. (The first build used raw steps by mistake, e.g. 0.9 m/s for "u at 5 km"; it was rebuilt before any run used it.)
- Expected caveat for SH: degree 10 resolves about 18° and degree 20 about 9°, both coarser than the 6° NM/TX box. Inside the box the SH features are nearly constant, so on NM/TX they can at best match nolatlon. Their value is global (G2 onward). The Denver zero-shot test still applies.
- nolatlon training hit a CUDA OOM at step ~500. The likely cause is host RAM exhaustion while the overlay was being built (1.1 GB available). It is retried automatically. Rule: don't build overlays while a GPU job is running.
