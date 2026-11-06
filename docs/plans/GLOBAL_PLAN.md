# Global Tempest: plan for scaling the weather generator from one box to the whole Earth (written 2026-11-06)

Sources weighed: the two Gemini reports the user supplied ("Scaling Atmospheric Profile Generator Globally.docx", called **D** below, and "Tempest_ARKNET_Global_Scaling_Blueprint.pdf", called **B**), checked against what this repository already has and what this machine can do. The user's frame: **test the architecture on Denver first, scale globally only after that works, then run one final test of the whole AI.** Tempest stays a stand-alone weather tool (SIDELINED.md, user decision 2026-11-06); nothing in this plan trains anything vehicle-specific.

How to read the Gemini numbers: both reports quote many literature figures (Rußwurm 2024 SH+SIREN, Rasp & Lerch 2018 pooling, Lang 2024 afCRPS, Meyer & Pebesma 2021 AOA ...). Several citations look real and match what this project already uses (afCRPS, Engression, FiLM noise conditioning). Some cannot be checked from here (e.g. "Höver et al. 2026", "Lakatos 2026", exact percentages). **Every claimed gain is treated as a hypothesis and tested on our own data with our own verdict rules** (skill gain larger than the seed spread, shape rule, no band worse). Nothing is adopted because a report says so.

---

## 1. Where the two reports agree (adopted as the target design)

| Topic | Both reports say | What we already have | Change needed |
|---|---|---|---|
| Overall shape | ONE global column generator conditioned on continuous location + terrain features; not 50 regional boxes; not fine-tuning a 3D foundation model | one regional Engression generator (`tempest/generator/model.py`): residual MLP, noise FiLM in every block, afCRPS 0.95 + energy score + step CRPS + shear-tail term, 4 members, EMA | keep the generator family; change its inputs, its target space and how the location enters |
| Target space | predict **standardised anomalies** (SAMOS): (y − μ_clim) / σ_clim with a smooth harmonic climatology | targets are raw profiles in "difference space" (height-to-height steps), normalised per column globally | add a climatology anchor and train on anomalies; keep the difference-space trick on top of it |
| Location | no raw lat/lon, no station IDs; **spherical harmonics (+ SIREN)** + static fields | raw lat, lon, site and grid elevation | replace lat/lon by SH; add terrain statics |
| Static fields | z_site, Δz = z_site − z_ERA5, sub-grid orography (sdor, slor, anor, isor), land-sea mask, distance to coast, Köppen, TPI | site and grid elevation only | add them (ERA5 invariants + a DEM) |
| Conditioning | context enters by **FiLM** (scale/shift per block) | noise enters by FiLM, location by concatenation | context FiLM next to the noise FiLM |
| Loss | afCRPS α = 0.95 (+ energy score, + shear tail) | exactly this | none; optionally the variogram term (B) |
| Data | equal-area global sampling + stratified extra points in mountains/coasts/rare climates/IGRA sites; temporal thinning (6-hourly or diurnal-cycled) because hourly states are redundant; int16 storage | 377 points hourly, float64 profile store (158 GB pilot) | a new compact store: pressure-level columns, int16, thinned in time |
| Honest tests | spatial block CV, leave-one-region/climate-out, AOA/DI applicability flag instead of a hard box refusal, coordinate-only baseline, symmetry checks, seam transects | in-box tests only; the tool refuses outside the box | new test harness (§6) |
| Calibration | one pooled, covariate-conditioned correction (ERA5 → balloon departures from shear, N², Ri, z/BLH, sdor ...) over hundreds of IGRA stations; spread-conditional calibrator; pooled shear tail; regime-matched Schaake templates | per-station linear map at 2 stations; range map per band; shear-tail map; Schaake shuffle + GaussianCopula; group C coherence tables | rebuild each as a pooled covariate model (§5) |
| Mode F | one global forecast corrector with a lead-time input and an ensemble-size-invariant input (HRES M=1, IFS-ENS M=51) | per-box residual network + ridge, leads 1/3/5/7 | global version trained on WeatherBench2 HRES (global archive, Colab pull) |
| Deployment | single global backbone, small (tens of MB), CPU, < 1 s for 100 members | 75 MB asset set per region | ONNX export, quantisation test |

## 2. Where they disagree, and the choice made here

| Question | D says | B says | Choice for Tempest | Why |
|---|---|---|---|---|
| Base mesh | Fibonacci ~1,500 + stratified, tile-aligned to the Earthmover 12×12 chunks, ~4,500-5,000 points, 3-hourly staggered, ~37-41 GB | HEALPix nside=32 (12,288) + 12,712 stratified = 25,000 points, diurnal-cycled 25,568 steps, 89.5 GB raw | **HEALPix nside=16 backbone (3,072, ~3.7°) + ~3,000 stratified/IGRA points ≈ 6,000 points, tile-aligned where possible, diurnal-cycled steps (every local solar hour, ~25,600 steps over 1991-2025), int16 pressure-level columns ≈ 22 GB raw, ~12-15 GB compressed.** nside=32 kept as the stage-G4 upgrade if the G4 gate shows lattice-density error | the 100 GB data cap already holds 66 GB of `data/raw`; 89.5 GB cannot fit; D's tile alignment makes extraction cheap; both reports agree that more places beat more time steps |
| Storage form | profiles on our height grid | 13 pressure levels + surface (71 channels, 142 B/profile) | **store pressure levels (as now in `data/raw`) and convert to the 44 heights in the data loader** | 3× smaller than storing 223 height values; `to_heights` already exists |
| SH degree | L = 10 + 2-layer SIREN | L = 20 + SIREN | **test both on Denver (loop L3)**; keep the smaller one if equal | L = 10 resolves ~18°, L = 20 ~9°; terrain statics carry the small scales anyway |
| SatCLIP land embeddings | no | yes (frozen 256-D) | **not in the first build**; an optional G4 test | extra dependency, zero over oceans, our terrain statics cover the physical part |
| Mixture of experts | only later, by Köppen zone, soft | top-2 of 16 spatial experts in the middle blocks at the global stage | **only if the G4 leave-climate-out gate fails in specific regimes** | adds collapse risk; one well-conditioned network may be enough |
| Terrain/PBL | post-generator AGL corrector for the lowest 3 km | inside the generator: altitude-decayed terrain conditioning, z_AGL coordinate in the lowest 4 km | **inside** (B): our height grid is already above ground in the lowest levels; add an `exp(−z/H)·MLP(terrain)` term to the output (test L3) | B's argument (post-hoc downscalers fail when the upstream wind direction is wrong) is sound; it is one extra head |
| Stage-1 test bed | NM/TX + Denver refactor, zero-shot Denver gate | 8 North-American boxes, leave-one-box-out | **user's frame: Denver first (G1), then 8 boxes (G2)** | Denver is cheap (81 points, data and IGRA station already fetched), different terrain (1.4-3.4 km), a real out-of-box test |
| Copula | SimSchaake template library (regimes × seasons × diurnal) | MDSS or end-to-end energy/variogram training | **keep GaussianCopula + regime templates (group C), refit globally conditioned on latitude band and regime; test MDSS at G3** | the generator already produces joint columns; the copula only ties times and distances |
| Shear tail | covariate shear-tail network on IGRA | pooled EGPD tail, altitude-regularised shape, covariate scale | **pooled EGPD with covariate scale (B) as the candidate, current map as the baseline** | extrapolates beyond the training maximum, pools rare events |
| Quantisation | FP16 backbone, FP32 tail | dynamic INT8 + FP32 head | **test both at G5; keep INT8 only if it passes B's parity gate (≤ 0.3 % CRPS, ≤ 1 % of the 99.9th shear)** | size is not our bottleneck; accuracy is |

## 3. Things neither report covers but this project must handle

1. **The final test window is already used.** Group E ran the one-time 2026 Jan-Jun test (`data/FINAL_TEST_DONE`). The global AI needs its own untouched test. **Locked now:** (a) time window **2026-07-01 → the latest ERA5 day available when G6 runs**; (b) **held-out places never used for training, tuning or calibration**. Denver cannot be one (G1 trains on it), so the locked spatial set is **Wallops (37.9 N, 75.5 W), Kwajalein (8.7 N, 167.7 E), Esrange (67.9 N, 21.1 E), Woomera (31.2 S, 136.8 E)** (from D) plus **one IGRA station per WMO region** chosen by a fixed random seed at G0 and written to `configs/global_holdout.toml`. No script may read these places or that window before G6 (enforced by a loader check, like the 2026 check in E3).
2. **Night hours** (R-8): the pilot data only holds solar hours 06-21. The global store is built for all hours from the start (diurnal-cycled sampling), so R-8 is solved as a side effect for the global model.
3. **Disk.** `data/raw` is 66 GB of the 100 GB cap. The global store (~12-15 GB compressed) + 8 boxes (~3 GB) + IGRA (~2 GB) fit, but the hourly pilot store must not be duplicated. Pilot float64 profile caches outside `data/raw` (the 6 GB `data/train/*.npz` copies) are the first thing to prune if space runs short (asked in ASK_LATER, not deleted unattended).
4. **Download (measured 2026-11-06, replaces the old "~500 tiles, 6-10 h" estimate, which was wrong).** The Earthmover *temporal* group is chunked 1 year × 3°×3°, so a scattered point set must pull every tile's full hourly record: Denver (4 tiles) took 39 min, so ~6,000 scattered points would be ~3,000+ tiles, ~18 TB, weeks. The *spatial* group (one global field per chunk, ~2 MB) costs the same whatever the point count: 12,784 diurnal-cycled steps × 72 fields ≈ 920k fields ≈ 1.9 TB transferred, bandwidth-bound at ~7-10 fields/s from this laptop (16 vs 64 concurrent requests made no difference). `tempest/ingest/fetch_global.py` (launcher `scripts/fetch_global.sh`, log `data/global_fetch.log`) does this, started 2026-11-06: 7,483 points (987 IGRA sites active ≥ 2020 + Fibonacci lattice + 1,505 relief-weighted terrain points, added because L3-0b showed unseen terrain is the main failure; holdouts removed), int16 store ≈ 11.6 GB, months 2011-2025 first. **Measured: ~150-180 s per month (transfer does not depend on the point count) → ~21 h for 1991-2025; 2011-2025 alone ~9 h.** WeatherBench2 HRES (global Mode F) still needs a Colab pull (ASK_LATER 9). A Colab pull of the same script would be far faster, since a Colab VM's bandwidth is much higher than the home link.
5. **What stays per-region.** Group C coherence tables, the gust model and ASOS station-scale widening were fitted at the pilot; they are refitted as functions of latitude band, terrain and regime at G3, and until then the tool marks them "pilot-fitted" outside NM/TX.
6. **Verdict rules stay.** Headline (skill15, 99 % coverage), shape rule, seed tolerances. New places need their own seed tolerance: two seeds of the baseline at each new test site, computed once (G1-0).
7. **Extend, never replace (user, 2026-11-06).** The global work must cause NO drop at the pilot region; it only extends coverage outward. Two layers enforce this:
   - *Gate* (every stage G1-G6): at NM/TX the new model must be within the pilot seed tolerance of p2f (skill15 0.0006 ERA5 / 0.0013 balloon), cov99 not worse, shape rule PASS. A change that costs NM/TX is "transfer-only" and is not stacked.
   - *Routing* (the hard guarantee): the tool keeps the frozen pilot model (p2f + its calibration, gust, coherence tables) as the NM/TX model. Inside the pilot box it is used as is; the global model serves everywhere else, with a short blend band at the box edge (seam test, G3). The global model replaces the pilot model at the pilot only if it is clearly *better* there (beyond the seed tolerance, on both ERA5 and balloons), decided once at G6.

---

## 4. Stages

Stage names are **G0-G6** so they do not clash with AUTOPILOT's flight-tool "stage 6".

### G0. Setup and locks (CPU, ~2 h)
- `configs/global_holdout.toml` (the locked places of §3.1) and a loader check that refuses them and dates ≥ 2026-07-01 unless `TEMPEST_FINAL_GLOBAL=1`; a test for the check.
- Static fields for any point: ERA5 invariants (z, lsm, sdor, slor, anor, isor; from the Earthmover/ARCO invariant fields) + distance to coast from the land-sea mask + TPI over 0.25° neighbours; Köppen class from the ERA5 climate (computed, no new download). One module `tempest/geo/statics.py`, cached per point.
- Spherical-harmonic encoder `tempest/geo/sh.py` (real SH up to L via associated Legendre recursion; numpy and torch; test: orthonormality on a HEALPix grid, values at the poles finite).
- Harmonic climatology fitter `tempest/geo/clim.py`: per point, per height and variable, μ and σ as annual (3 harmonics) × diurnal (2 harmonics) Fourier series fitted on the training years only; the global version on a 1° grid with 12 EOFs (D) at G4.

### G1. Denver: the architecture test bed (GPU + CPU, the 12-hour loop L3 in `docs/logs/LOOP3.md`)
Question: **which input encoding, target space and conditioning lets a model trained on NM/TX predict Denver it has never seen, without losing anything at NM/TX?**
- Data: Denver ERA5 1991-2025 (the R-5 store only covers 2016-23), profiles, dataset with the pilot builder; Denver IGRA USM00072469 to 2025; ~15 western-US IGRA stations + their ERA5 columns (for the calibration-transfer test).
- Baselines: **B-raw** (the adopted p2f model, NM/TX-trained, queried at Denver with raw lat/lon extrapolation: the "no architecture work" answer), **B-local** (same config trained on Denver 1991-2020: the "own box" upper bound), **B-clim** (Denver ERA5 climatology), **B-gauss** (Earth-GRAM-style proxy). The gap B-raw − B-local is what the architecture must close.
- Experiments: one change at a time, then stacks (L3 rows).
- **Gates (all on 2024-25):**
  - G1-a zero-shot: the best NM/TX-only architecture closes **≥ 50 % of the B-raw → B-local CRPS gap** at Denver (D's go/no-go 2) and has skill15 > 0 vs B-clim in every band (B's "beats climatology" gate, made band-wise).
  - G1-b no regression: at NM/TX the same model is within the pilot seed tolerance of p2f on the ERA5 headline and the balloon headline (skill15 0.0006 / 0.0013), shape rule PASS.
  - G1-c unified parity: one model trained on NM/TX + Denver matches the two separate models at both places within tolerance (D's go/no-go 1).
  - G1-d calibration transfer: the pooled covariate balloon correction trained on the western stations **without Denver** brings Denver's balloon gap at least half way from "no correction" to "Denver's own station map" (wind step gap, shear99 ratio, T step gap).
  - G1-e honesty: the coordinate-only baseline (SH alone, no terrain/clim) is clearly worse than the full model at Denver (else the model is memorising geography); the DI applicability score is higher at Denver than inside NM/TX and correlates with the Denver error.
- Output: the chosen architecture (`configs/generator_global.toml`), written into this file's §7 with the evidence. If G1-a fails after the loop, stop and report: scaling the architecture to the globe would only scale the failure.

### G2. Eight diverse North-American boxes, leave-one-box-out (GPU ~1 day, data ~3 GB, all from this laptop)
Boxes (B's list, 3°×3°, 2°×2° where terrain is uniform): NM/TX (existing), Denver (G1), Vandenberg/Pt Mugu CA (marine layer, sea breeze), Cape Canaveral FL (deep convection), Fairbanks/Poker Flat AK (arctic inversions), Wasatch/Salt Lake UT (valley and mountain waves), Lamont OK (low-level jet), Hilo HI (trade-wind inversion). Plus ~25 IGRA stations inside or near them.
- Add the **climatological tropopause height** input (D stage 2) and the altitude-decayed terrain head if G1 did not already adopt it.
- **Box-balanced sampling** so 377 NM/TX points do not dominate 81-point boxes.
- **Gates:** leave-one-box-out for each of the 8: CRPSS > 0 vs that box's ERA5 climatology, 90 % interval coverage within 87-93 % (D) at every band, 99th-percentile shear within ±12 % of ERA5 and within ±15 % of IGRA (D's ±12 % on IGRA is not reachable with the present 0.61→0.98 Denver map scatter; stated as an assumption); in-sample: the pooled 8-box model matches each standalone model (G1-c rule).
- Calibration: covariate balloon correction trained leave-one-box-out; pooled EGPD shear tail vs the present map; spread-conditional calibrator (affine γ, β as functions of predicted spread, height, terrain, hour; BQN only if affine fails).

### G3. North America continental lattice (data ~5 GB, GPU ~1-2 days; Mode F needs the Colab HRES pull)
- Points: HEALPix nside=32 restricted to 15-75 N, 170-50 W (~1,000) + stratified mountain/coast points (~600) + ~180 North-American and Pacific IGRA sites (B's Stage 2 layout at the smaller density of §2).
- Global-style Mode F: one corrector with a lead-time input (continuous, needs IL-75 more leads), the climate generator's output as prior input, a DeepSets mean/spread summary so HRES (M=1) and IFS-ENS (M=51) use the same network. WeatherBench2 HRES over North America (Colab).
- Refit group C coherence (lag and distance correlation) as a function of latitude band + regime.
- **Gates:** 1,000 km spatial block CV with 30 % of the IGRA stations held out: unseen-station CRPS within 0.08 K (T) / 0.15 m/s (wind) of seen stations (B); **seam test** along 125→75 W and along the old NM/TX border 108→101 W: no step in median, spread or 99th shear larger than the seed tolerance; continental Mode F beats the per-box Mode F at NM/TX (and at Denver once Denver HRES exists) at 1-7 days.

### G4. Global (data ~8-16 GB, user approved 16 GB on 2026-11-06, GPU ~3-4 days for 3-5 seeds)
- Points: §2 design (HEALPix nside=16 backbone + stratified + all IGRA sites with ≥ 10 years), all hours, 1991-2025.
- Global climatology anchor on a 1° grid (12 months × diurnal harmonics × 12 EOFs, ~38 MB, D).
- Global covariate balloon correction over ~600-800 IGRA stations; global pooled EGPD tail; DI-gated shrinkage of the boundary-layer bias toward zero outside the area of applicability (B).
- The tool replaces the hard box refusal by the **DI/AOA flag** ("inside / near / outside the trained feature space", with the expected error from the DI-error fit).
- Only if a gate fails in specific regimes: soft MoE (top-2 of 8-16, load-balance loss 0.01), denser lattice (nside=32), or SatCLIP land embeddings, one at a time.
- **Gates:** leave-one-climate-out (5 Köppen main groups) and leave-one-continent-out: CRPSS > 0 everywhere, 99th / 99.9th shear error < 10 % vs held-out IGRA blocks (B); kNNDM 10-fold CV estimate within the bootstrap band of the block CV (otherwise the CV is optimistic); **rotate-longitude test** (all inputs of a column moved by 180° with local solar hour kept): artifact < 0.05 K (B) — near zero by construction once lat/lon are gone, so a failure means a leak; reverse-latitude test reported (seasons flip, so judged on the season-matched anomaly). NM/TX and Denver: the global model within seed tolerance of the G1 unified model.

### G5. Packaging (GPU ~1 day, no new data)
- Export the global generator, the corrector and the statics/climatology tables; ONNX FP16 and dynamic INT8 (final projection in FP32).
- Optional: distil the 4-member ensemble into one student; optional rank-8 LoRA packs for launch ranges with dense balloons (only if a range shows a gap the global model cannot close).
- **Gates:** INT8 within 0.3 % CRPS and 1 % of the 99.9th shear of FP32 (B), else ship FP16; 100 members in < 250 ms on 4 CPU cores; base download < 75 MB (D) (B's 50 MB as a stretch).

### G6. The final test of the overall AI (once, like E4)
- `scripts/final_test_global.sh`, lock file `data/FINAL_GLOBAL_TEST_DONE`: score the frozen G5 bundle **once** on the locked window (2026-07-01 → latest ERA5 day) at (a) every locked holdout place of §3.1 against ERA5 and their balloons, (b) a global HEALPix nside=16 sample of ERA5, (c) NM/TX and Denver against ERA5 and balloons, (d) the same for B-clim and B-gauss with the same code.
- Report in `docs/FINAL_GLOBAL_REPORT.md`: skill and coverage per region, per Köppen group, per height band, with day-block intervals; every cell not clearly better than climatology listed; DI flag reliability (does "outside" really mean larger error?); the plain-language verdict whether the global model can replace the pilot model at the pilot.
- Only after G6: the tool switches its default to the global bundle (the pilot assets stay as `assets_pilot`).

---

## 5. Calibration and coupling at global scale (detail)
1. **Balloon correction** (replaces the per-station a + b·ERA5 map): a network predicting the distribution of Δy(z) = y_IGRA − y_ERA5 per height from inputs available everywhere — ERA5 shear, N², bulk Richardson number, z/BLH, z − z_tropopause, sdor, Δz, distance to coast, solar zenith — no lat/lon, no station id. Trained on IGRA stations pooled; evaluated leave-stations-out by blocks. Output: mean shift + spread-inflation factor per height (the shear inflation of 2.5-3× that Houchi 2010 reported is the expected size), applied as now (median shift + resampled leftover).
2. **Spread calibrator** (replaces the range map per band): affine γ(x), β(x) on the anomaly scale with x = predicted spread, height, terrain, hour; fitted on 2021-23 pooled; monotonic BQN only if affine misses the per-region coverage gate.
3. **Shear tail**: pooled EGPD, shape ξ per height band shared by all places, scale as a function of ERA5 shear and N²; current per-box map as the baseline.
4. **Copula**: GaussianCopula time and distance tables (group C) refit as functions of latitude band, season and shear regime; MDSS tested at G3.
5. **Observation conditioning** (stage 6 IL-33/G `observe()`): works unchanged with the global generator (sampling-time weighting).

## 6. Test harness (new `tempest/scoring/spatial.py`, built at G1 and reused)
- Block CV (2°/10°/20° blocks), leave-one-box/climate/continent-out, kNNDM fold builder (prediction-to-training distance matching).
- DI / AOA: distance in the standardised, importance-weighted input space to the nearest training point, threshold = 95th percentile of the training CV DI; fitted DI → error curve.
- Coordinate-only baseline (SH only), seam transect checker, rotate-longitude / reverse-latitude involution checks.
- All reuse `tempest/scoring` (crps_ensemble, coverage, variogram, PIT) so the numbers stay comparable with the pilot.

## 7. Decisions log (filled as G1-G6 run)
| Date | Stage | Decision | Evidence |
|---|---|---|---|
| 2026-11-06 | plan | design of §2, locks of §3.1 | this file |

## 8. Cost summary
| Stage | New data | GPU | Needs the user |
|---|---|---|---|
| G0 | statics (< 100 MB) | none | no |
| G1 | Denver 1991-2025 (~1 GB) + 15 IGRA stations (~0.5 GB) | ~12 h loop | no |
| G2 | 6 boxes (~3 GB) | ~1 day | no |
| G3 | NA lattice (~5 GB) + WB2 HRES NA (Colab) | ~1-2 days | the Colab pull |
| G4 | global (~11.6 GB int16, 16 GB approved; fetch running since 2026-11-06) | ~3-4 days | approved 2026-11-06; `data/raw` was 80 GB, so later stages need ASK_LATER 12 pruning |
| G5 | none | ~1 day | no |
| G6 | 2026-07 → latest ERA5 at the holdouts (~1 GB) | < 1 h | no (once) |

## 9. Monte Carlo accuracy at global scale (added 2026-11-06)
A Monte Carlo user draws thousands of members and uses the whole column, including its tails and the joint structure between heights and variables, not each band on its own. Per-band CRPS (skill15) can look good while the members are physically wrong or their tails are wrong. These items close that gap, ranked by expected value. None of them is queued on the GPU now (lean queue, user). Each one has a stage and a gate.

1. **Physical checks on every member (G1 CPU, gate at every stage).** New `tempest/scoring/physics.py`, which reuses `geometric_height` and `es_liquid`. For each member it checks:
   - RH stays within [0, 100.5] %;
   - no superadiabatic layer above 200 m AGL deeper than 1 K;
   - hypsometric thickness between levels (from T and RH) matches the generated heights within 0.5 %;
   - |shear| stays below the 99.99th percentile of ERA5;
   - the surface values connect smoothly to the first profile level.
   *Gate:* the violation rate per member is not above ERA5's own rate (+0.5 percentage points) at every test place. *Why:* the fill-top columns (isothermal T above 50 hPa) and mountain ground are where violations will appear first, and the Monte Carlo inherits every bad member.
2. **Score the whole joint distribution, per place and regime (G1 harness, then every stage).** Add the energy score and the variogram score (p = 0.5) over the full 44 × 5 column, plus the coverage of derived quantities that Monte Carlo users actually integrate: bulk shear 0-6 km, max wind and its height, the BL-top inversion, and the tropopause height/T. Split them by regime (jet / convective / stable / tropical). *Gate:* no regime is worse than the coordinate-only baseline. *Why:* the shape rule (event_cov_gap, shear_ks, vcorr) is the only joint check today, and it is computed at NM/TX only. The w768 and terrain failures were shape failures that skill15 did not show.
3. **Never worse than climatology (G4 routing, the global twin of §3.7).** Where the DI exceeds the AOA threshold (§6), the tool blends the members toward a local ERA5 analog/climatology ensemble (same place, ±15 days, same hour, 1991-2020), with the weight taken from the fitted DI → error curve. Outside the AOA the members are flagged. *Gate:* at every held-out place, skill vs climatology ≥ 0 per band, with the blend switched on. *Why:* Denver zero-shot was −0.19 (worse than climatology). A global user must never get a model that is worse than the free baseline.
4. **Variables relative to the place, not absolute (G2, from the L3-8 SAMOS note).** Standardise the loss and the noise per row by the local climatological σ (not one global mean/sd). This keeps tropical T (σ ~1 K) from being ignored next to polar T (σ ~8 K), and stops the Monte Carlo spread from being tuned to the training box's variability. *Gate:* the per-latitude-band coverage90 stays within ±3 points everywhere. *Why:* at global scale, one pooled sd is the easiest way to get the spread right on average and wrong almost everywhere.
5. **Diversity of places beats width (G2).** w768 was worse at Denver (capacity is not the limit), and siren took only 22 % of the gap. So the transfer gain must come from training places that span terrain, climate and coast: the G2 boxes balanced by Köppen class × elevation band, sampled equally per box and not per row. *Gate:* the leave-one-box-out skill rises with the number of boxes. If it stops rising, add physical descriptors next, not width.
6. **Physical descriptors instead of coordinates (G1-G2).** Raw lat/lon extrapolate badly (nolatlon fixed u 0-1 km), SH alone fails shape, and terrain alone fails shape at NM/TX. Feed the context FiLM (L3-10) with quantities that mean the same thing everywhere: Coriolis f, the climatological tropopause, BLH and N², the climatological mean/sd per height (L3-7), elevation/sdor and distance to coast, with SIREN-SH only as a small residual. *Gate:* the rotate-longitude involution check (§6) changes the samples by less than the seed tolerance.
7. **Terrain-aware top (G4, from L3-25).** 23 % of the Denver rows were mountain columns that had been dropped. Every high-ground place has this problem, which covers ~10 % of land. Replace the isothermal `fill_top` with a fitted stratospheric lapse rate (the `fill_top` shortcut comment), and mark filled heights so that the loss down-weights them and the members report them as extrapolated. *Gate:* T 12-18 km AGL coverage over ground > 2 km matches flat ground within 3 points.
8. **Tail calibration per place (G4, extends §5.3).** Monte Carlo risk numbers come from the 1 % tails. Check cov99 and the 99th-percentile shear PIT per latitude band and per terrain class, not only pooled. If a band misses, fit the EGPD scale on that band. *Gate:* cov99 is within 98.5-99.5 % in every band.
9. **Reproducible members (G5).** The member seed is fixed per (place, time, member index), and the copula (§5.4) gives spatially and temporally coherent members across nearby places. Then two users who query neighbouring points get consistent scenarios. *Gate:* the seam transect test (G3) passes on members, not only on means.

**Testing §9 (user, 2026-11-06: after the current tests, whenever the GPU and memory have room).** `scripts/ap_g9.sh` waits for the loop-3 lean queue and the fill-top rescore, then runs `tempest.scoring.score --mc` (module `tempest/scoring/mc.py`) for p2f and every loop-3 candidate at NM/TX and on the fill-top Denver set. It runs one job at a time, only with ≥ 9 GB free RAM, and writes the model copies as `models/g9_*` so no existing score is overwritten. The results go to `data/g9_verdicts.txt` and `data/g9_mc_all.csv`. It covers items 1, 2, 3 (a fixed-weight blend: an upper bound before the DI exists), 7 (filled-height T) and 8 (cov99 per ground-elevation class). Not testable yet:
- 4 and 5 need the G2 multi-box data;
- 6 is partly the running ctxsep row, and the climatology inputs (L3-7) are not built;
- 9 is a G5 packaging test.
