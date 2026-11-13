# Innovative idea review

## What to try first (written 2026-11-10)

Every idea rated 6 or more, from all sections below, in the order to run them. Highest potential first, but cheap checks that decide a bigger idea come before it. Names: "G1-1" is Group 1 idea 1; "C1" to "C6" are the contenders; "#13", "A4" are ideas from the source file. Nothing here has been run.

Machine limits used for the plan: one GPU job at a time; CPU jobs share 12 threads, so 3-4 small CPU jobs can run side by side. Every run has its kill rule in its own section; set it before the run. Tests use 2024-25 only, never 2026.

**Step 1. Four checks, all at once (CPU, 1-2 days in total, no model change).** They decide the form of the three best ideas.

| Run together | Rating | What it decides |
|---|---|---|
| G2-7 shape scores, printed per stage | 7 | The baseline every later step is judged on. Do this first of all. |
| C5 three-way referee | 7 | How much balloon shear is real: the size of the shear correction. |
| C1 step 1: does missing shear rise with stability? | 8 | Whether the shear target is C1's law or G1-1's plain ratio. |
| C2 premise check (2 hours) | 8 / 6 | Whether C2 is a GPU fine-tune or a few-line CPU fix of the shuffle. |

One-hour checks to slot in beside them: does the generator already have a trend input (G1-7); IL-128 on the real pool (G3-3); spectrum check for detail between heights (G2-1).

**Step 2. The three best ideas, in parallel (one on the GPU, two on the CPU).**

| Lane | Idea | Rating | Note |
|---|---|---|---|
| GPU | C2 fine-tune through the shuffle (if the check says "network") | 8 | If the check says "shuffle", C2 becomes a CPU fix and the GPU goes straight to C3. |
| CPU 1 | Shear target: C1's law or G1-1's ratio, at C5's lower bound | 8 | Fit the number now; it does not depend on the network. Refit the shear map once, after C2 lands, so the stack is fitted in order. This also covers source idea A4 (8). |
| CPU 2 | C4 radar error without truth, then G1-6 calibrate `observe` | 7, 7 | Same code (`obs.py`), so one after the other, not together. Covers source idea #14 (7) at the ground. |

Do not judge C2 and the shear target on the same scores in the same week: C2 is judged before the shear map, the shear target after it.

**Step 3. The large bet on the GPU, small trackers on the CPU.**

| Lane | Idea | Rating | Note |
|---|---|---|---|
| GPU | C3 day-coded generator, stage 1 (stop if under 40 %), then stage 2 | 7 | Stage 2 is judged against `observe` as improved in step 2. |
| CPU 1 | G1-5 spread tracker and G1-7 drift tracker | 6, 6 | Both are replays of the logger, hours each, independent of everything else. |
| CPU 2 | G2-2 Student-t widening, with the #13 fault gate (7) in its patched form | 6 | After G1-6. Covers source idea #3 (6). |
| CPU 3 | G2-4 two-scale persistence aloft; G1-3 radar + station score | 6, 6 | Both use the radar archive and C4's noise number. |

**Step 4. Second GPU bet.**

| Lane | Idea | Rating | Note |
|---|---|---|---|
| GPU | G3-5 learned monotone update | 7 | After C4, G1-6 and C3 stage 2, because it must beat all three. If C3 stage 2 already reaches coverage 0.85-0.92 on all radar levels, G3-5 may not be needed. |
| CPU | C6 run-to-run disagreement | 6 | Only once the 00Z + 12Z refetch (F-V2) is finished. |

**Step 5. Only if an earlier result asks for it.**

| Idea | Rating | Build only if |
|---|---|---|
| G3-1 detail network | 6 | The shape scores still show a gap after the shear target. |
| G2-1 detail between heights | 6 | The spectrum check in step 1 finds something missing. |
| G3-3 select, then nudge | 6 | IL-128 on the real pool shows tail inflation above 1.2x. |
| G3-2 next-hour generator | 6 | G3-5 is not built. |

**Step 6. Cheap extras from the other sections (rated 5, below the cut, but each is a short test that settles a question).** Run them in spare CPU time beside steps 2-3; none needs the GPU.

| Idea | Rating | Time | Why it is still worth the test |
|---|---|---|---|
| G1-4 oracle test for similar-day templates | 5 | 1 hour | Uses perfect templates on purpose. If even that gains under 1 %, it closes the whole "better templates" direction (G1-4 and G3-4) for good. |
| G2-3 gust factor, information test at Midland | 5 | half a day | The lowest 300 m drive 87 % of apogee spread and no radar sees them. Keep only if held-out error falls by 5 % or more. |
| G2-6 quantile-average blend, first check only | 5 | 1 hour | Checks whether range calibration per lead already does the job for days 5-10 (open item IL-74). |
| G1-2 mixed pool, 10-20 % real days, climate mode | 5 | hours | Small gain expected (co-extremes 0.052 to about 0.056). Drop if the rise is under 0.005 or CRPS worsens. |
| G2-5 count of double jets after `observe_radar` | 4 | 1 hour | Count only, nothing built. A check of today's engine that feeds C4 and G3-5. |

Rated 6 in the first review but not listed as their own runs: #10 (trust-weighted blend) became G2-6, which fell to 5 in the stress test; A3 (stable-by-construction temperature) is what the lapse map and C2 already aim at.

Rough length if nothing is killed: step 1 two days, step 2 about a week, step 3 one to two weeks, step 4 one week. Most ideas will stop at their kill test, so expect less.

## How to build each idea in the list (written 2026-11-10)

One block per idea, in list order. File and function names were checked against the repository on 2026-11-10; anything marked "not checked" was not opened. No code has been written or run.

**Rules for every block**

- New script: `scripts/<name>.py`, CPU, run as `PYTHONPATH=. .venv/Scripts/python -W ignore scripts/<name>.py`, appends its table to `docs/results/logs/<name>.log`.
- A change inside a package is a new optional argument whose default keeps today's result bit for bit. Run `pytest tests tempest_weather_v2/tests` before and after.
- Fit years 2005-2022 (templates and real days: 1991-2023). Test years 2024-25. Never 2026.
- Tool samples: `api.atmosphere_set(lat, lon, iso_time, n=199, seed=k, mode="ai", elevation=station.ELEV[sid])` returns `atm["u"]`, `atm["v"]`, `atm["T"]`... as (199, 44).
- Balloons: `data/igra_heights/<station>.npz` (986 stations, 93 US; `u`, `v`, `T`, `RH`, `lnp` at 81 heights, int16 times 0.1, missing = -32768). Reader: `balloons(sid)` in `scripts/il103_balloon_shearmap.py`. EPZ = `USM00072364`, MAF = `USM00072265`.
- ERA5 at a balloon: `data/pilot/profiles.zarr` (NM/TX box only, 377 points, 44 heights), nearest point, as in `scripts/il103_balloon_shear.py`. ERA5 for stations outside the boxes: `data/raw/era5_global` exists, pairing not checked.
- Radar: `data/raw/nexrad_nvw/<SITE>_NVW_<date>` read with `radar.parse_nvw`. On disk: EPZ 611 files, FTG 485, HDX 127, MAF 133.
- Paired seeds on both sides of every comparison. A CRPS change under 0.0006 is noise. Intervals by resampling whole days.
- Stack order is fixed: range calibration, shuffle, shear map, lapse map. After any change, refit every later map in that order.

### Step 1

**G2-7 shape scores per stage.** New `scripts/shape_scores_by_stage.py`.
1. Copy the stage switch from `scripts/a3_stage_audit.py`: delete keys from `api._assets()["post"]` in memory. Stages: raw network (no `spread`, `rank`/`tpl`, `smap`, `lmap`), + range calibration, + shuffle, + shear map, + lapse map (shipped).
2. Cases: EPZ and MAF balloons, 00Z and 12Z, 2024-25, 400 per group. Truth: balloon layer-averaged onto the 44 heights. Also print the ERA5 row for the same hours.
3. Score A, per band (`shear_map.EDGES`): share of layers with Ri < 1. Ri = N² / S², N² = (g / θ)·dθ/dz, θ = T·(1000 hPa / p)^0.286, S² = (du/dz)² + (dv/dz)², differences between neighbouring heights.
4. Score B: mean count per profile, below 3 km, of layers where T rises by more than 2 K.
5. Score C: band-depth rank histogram. For each case stack truth + 199 members of u (then v, T). Depth of a profile = mean over heights of rank·(200 − rank + 1), normalised. Rank the truth's depth among the 200; 10 bins. Flat = good; print the largest bin deviation.
6. Run seeds 0, 1, 2 and print the spread per score. Report only, no gate.

**C5 three-way referee.** New `scripts/c5_triple_collocation.py`.
1. Three systems at El Paso, 00Z, 0.5-5 km: balloon (`igra_heights`), radar (latest EPZ volume within 45 minutes, `radar.latest_profile(..., fetch=None)`, cached files only), 24-hour HRES forecast (`data/raw/wb2_hres_v2/YYYYMM_00z.nc`, nearest point; El Paso coverage of that file not checked, fall back to `data/raw/wb2_hres`).
2. Put all three on the radar's reported heights. Quantity x = wind difference between heights 500 m apart (u and v separately).
3. Per height band, with covariances over days: error variance of balloon = Var(b) − Cov(b, r)·Cov(b, f) / Cov(r, f). Same pattern for r and f.
4. Real shear ratio, lower bound = sqrt(Cov(b, r) / Var(f)) (the part balloon and radar share, over the forecast). Upper bound = sd(b) / sd(ERA5) = today's 1.7.
5. Print by band and season, with the share of days the radar covered. Day-block bootstrap, 1000 draws.
6. Kill: bounds wider than 1.4-1.7 decide nothing; log and move on.

**C1 step 1: does missing shear rise with stability?** New `scripts/c1_wave_law_check.py`, built from `il103_balloon_shear.py` (same pairs, same `shear()`).
1. Per pair and layer: d = (balloon shear)² − (ERA5 shear)², and N² from the ERA5 T (formula in G2-7).
2. Per band, three equal-count classes of N². Print mean d per class with day-block intervals.
3. Fit d = c·N² through the origin at EPZ, 2005-2022. Print c per band.
4. Pass: d rises across all three classes in the 1-5 and 5-12 km bands. Otherwise C1 is dropped and step 2 uses G1-1's ratio.

**C2 premise check.** New `scripts/c2_premise_check.py`, 2 hours.
1. Truth rows: 4000 ERA5 rows of 2023 (same loader as `tempest.calibrate.shear_map` CLI).
2. Per group (`shuffle.cell_keys`, cell 8), draw 199 true rows as the "perfect distribution" and 199 templates with `shuffle.group_template(..., before_year=2023)`. Apply `shuffle.apply(x, template)`.
3. Print shear excess (p99 of `shear_map.shears`, shuffled over truth) and superadiabatic share (`lapse_map.lapse` above dry-adiabatic) for: truth, truth after shuffle, model after shuffle.
4. If truth-after-shuffle already shows most of the excess (4.7x, 0.324): the fault is the shuffle, do the fallback below on the CPU. If not: the fault is the network, do the GPU fine-tune.

**One-hour checks.** (a) G1-7: `tempest/generator/features.py` has a `year` input (`BASE_FEATURES`) and the `p2` set replaces it with `gmst`; print which set the shipped model's `cond_names` holds. If it has one, G1-7 only needs the replay. (b) IL-128 on the real pool: in `scripts/il128_copula_tail_check.py` swap the synthetic pool for `base._ensure_pool()["samples"]` of one Spaceport case. (c) G2-1: power spectrum of balloon u on the 81 `igra_heights` levels against the tool's 44 heights drawn as straight lines, 100 m to 1 km.

### Step 2

**C2 fine-tune through the shuffle (GPU, only if the check says "network").** Change `tempest/generator/train.py`.
1. New cfg key `shuffle_train` (default False). When True, `m = 16`.
2. Before the loop: for each training row, an integer tensor R of shape (16, n_out) = ranks 0..15 per column of 16 real training-year profiles from the row's group (`shuffle.group_template`), excluding the row's own day ± 3 days. Draw new templates each epoch.
3. Inside `score(samples, t)`: `s = torch.sort(samples, dim=1).values.gather(1, R)`. Keep `afcrps` on `samples` (unchanged by re-ordering). Compute `stride_loss`, `superadiabatic` and `shear_tail_loss` on `s`.
4. Put the frozen range map (`calibrate/spread.py` table as a fixed tensor layer) before the sort.
5. Start from the shipped weights, lr 1e-5, 5 % of the original steps.
6. Refit range calibration, shear map and lapse map in order. Score with `tempest/scoring/score.py --shuffle` without and with `--shear-map --lapse-map`, seeds paired.
7. Kill (measured before the shear and lapse maps): unstable share must fall from 0.32 to under 0.26, shear excess at least halve, CRPS inside 0.0006.

**C2 fallback: group-rank shuffle (CPU, if the check says "shuffle").** Change `tempest/calibrate/shuffle.py`.
1. New argument `group_rank=False` in `group_template`. When True, also return each template's rank fraction per column within its whole group (thousands of rows), not only among the m drawn.
2. In `apply`: member order per column = argsort of those fractions (ties broken by the old rank). Nothing else changes.
3. Refit shear and lapse maps; same scores and kill rule as above.

**Shear target (C1's law or G1-1's ratio).** Change `tempest/calibrate/shear_map.py`.
1. New argument `fit(..., target_shear=None)`. When given (same shape as `shears(uv_t)[1]`), it replaces the truth shear in the line `q_t = _quantiles(_band_values(shears(uv_t)[1], edges), lv)`.
2. New `scripts/shear_target_fit.py` builds `target_shear` from the ERA5 truth rows. G1-1 form: ERA5 shear × ratio per band `[1.0, r, r, r]`, where r = C5's lower bound (1.7 if C5 was killed), and the 12-18 km ratio is capped at the 5-12 km value. C1 form: `sqrt(ERA5 shear² + c·N²)` with c from step 1 scaled so the 1-5 km mean ratio equals C5's lower bound; 0-1 km unchanged.
3. Save as `models/shear_map_balloon.npz`. The shipped table is not replaced; add the new one as an opt-in asset.
4. Test like `il103_balloon_shearmap.py`: shear p50 / p99 / p99.9 per band against EPZ + MAF balloons 2024-25 and Denver, CRPS of u and v per band, and the G2-7 scores.
5. Pass: p99 within 10 % of balloons in 1-5 and 5-12 km, CRPS against balloons not worse than 0.0006. The ERA5 shear score gets worse by design; report it, do not gate on it.
6. Then refit the lapse map on top.

**C4 radar error without truth.** New `scripts/c4_innovation_fit.py`.
1. Every radar file on disk (all four sites). Prior: the tool's pool at that site and hour, n = 1024, free (no observation).
2. Innovation d = radar wind − pool mean, per level, u and v. Prior covariance B between levels from the pool.
3. Observation error covariance R = mean over volumes of d·dᵀ − B. Fit three numbers: sd = sqrt(mean diagonal of R); L from R(i, j) = sd²·exp(−|zi − zj| / L); fade a from repeating with the prior of 1, 2, 3 hours later, sd(age) = sd·(1 + a·age).
4. Day-block bootstrap for all three.
5. Apply: `engine.conditioned(obs, sensor_sigma=...)` takes one sd per key today (`launch._sensor_sigma`). Linked errors with the same call: inflate each level's sd by sqrt(n_eff), n_eff = sum over levels j of exp(−|zi − zj| / L). A true full-R update needs a change inside `engine.condition_on_observations` (not opened); do that only if the inflation form fails.
6. Test with `scripts/p3_vad_condition.py`: free, 4 levels, all levels with the new sd. Kill: all levels must beat 4 levels at 2.5-5 km with coverage ≥ 0.85; if not, keep 4 levels.

**G1-6 calibrate `observe`.** Change `tempest_weather_v2/obs.py` constants only.
1. Two numbers: `TAU_H` (now 6.3) and one new multiplier `SIGMA_SCALE = 1.0` inside `observation_sigma` (returns `SIGMA_SCALE * prior_sd * sqrt(1/gain − 1)`).
2. New `scripts/g16_observe_fit.py` from `scripts/w6_observe_eval.py`: all ASOS stations in `data/raw/asos`, 2015-22, lags 1, 3, 6 h. First print the bias after `observe`; if above 0.2 m/s fix the centre before the width.
3. Grid search: TAU_H 3-12 h (10 values) × SIGMA_SCALE 0.6-1.6 (11 values). Pick the lowest CRPS among pairs with 90 % coverage in 0.88-0.92.
4. Test on 2023-25 (TCS, MAF): CRPS ≤ linear persistence (1.035 / 0.923), coverage 0.88-0.92. Repeat aloft with `p3_vad_condition.py` before using the same numbers there.

### Step 3

**C3 day-coded generator (GPU).** Changes in `tempest/generator/model.py` and `train.py`, all behind cfg key `day_code` (default 0).
1. `day_id` = integer index of each training row's UTC date. `self.codes = nn.Embedding(n_days, 32)`, initialised normal(0, 0.01).
2. `forward(cond, m, eps, code=None)`: pass `code` to the blocks through the existing `ctx_sep` path (`Block.forward(h, z, zc)`, zero-initialised FiLM), added to the context embedding if one exists. `code=None` = today's behaviour.
3. Training: look up `codes(day_id)`, clamp its norm to 3, add loss `1e-4·code²`. Same loss otherwise. Full training run.
4. Stage 1 (held-out days of 2024): network frozen, fit one code per day by 200 Adam steps on half the box points; score CRPS on the other half against the no-code model. Kill: under 40 % skill against climatology.
5. Stage 2: export the code bank (`n_days × 32`, float16) with the assets. In `observe`: weight w_k ∝ exp(−0.5·T·Σ((obs − mean_k) / sd)²) over the day codes of that season ± 30 days, T chosen so effective days ≥ 30; draw members by w; then today's update. Below 30 effective days fall back to today's engine.
6. Test on `w6_observe_eval.py` and `p3_vad_condition.py`. Kill: must beat today's `observe` beyond seed noise, coverage ≥ 0.85.

**G1-5 spread tracker and G1-7 drift tracker.** Extend the existing replay, `scripts/bias_backtest.py`; runtime side `tempest_weather/bias.py`.
1. G1-5: per site, UTC hour and lead, r = (obs − pool mean)² / pool variance. EWMA with alpha = 1/60 per day, start 1. Factor = sqrt(clip(1 + n / (n + 60)·(r̄ − 1), 0.8², 1.5²)), n = cases seen. When r > r̄ use alpha = 1/20 (widen fast). Multiply member departures from the pool mean by the factor.
2. Pass: 90 % coverage error falls at two thirds of sites or more; CRPS never worse at any site.
3. Runtime: one more field in the JSON state written by `scripts/update_bias.py`, read in `bias.correction`; used only when `bias_dir` is passed, as today. State format not opened.
4. G1-7: new `scripts/g17_drift_replay.py`. Monthly mean of (ERA5 − climate-mode pool mean) per band and variable, 2015-25. Tracker = EWMA over 12 months (3 months only where the replay shows a step). Pass: mean absolute bias of the following month falls in most bands. Skip if the one-hour check shows the trend input already removes it.

**G2-2 Student-t widening + #13 fault gate.** In `tempest_weather_v2/launch.py`, after `_conditioned_pool`.
1. t rule: with k observed numbers (k ≤ 10), D² = Σ((obs − prior mean) / sqrt(prior var + obs var))², ν = 8. Scale the conditioned members' departures from their mean by sqrt((ν + D²) / (ν + k)), limited to 1.0-2.0 (never narrows).
2. Fault gate in `_check_observation`: reject a reading only if it differs from the same sensor's previous reading by more than 4·prior sd·sqrt(1 − ρ^(2·Δt)), ρ = `SPEED_RHO_PER_HOUR`, or from a second sensor by more than 4 combined sd. A reading that is only surprising (the existing "> 4 sd from the prior" flag) is used in full.
3. Flag `t_update=False` on `observe`. Test: `p3_vad_condition.py` and `w6_observe_eval.py`; coverage on the 10 % most surprising cases must move toward 0.90, CRPS on the rest inside noise.

**G2-4 two-scale persistence aloft.** New `scripts/g24_two_scale_persistence.py`.
1. Radar volume pairs at the same site, 15 min to 6 h apart, all sites.
2. Split each profile: column mean wind (0.5-5 km) and departures per level.
3. Correlation against time gap for both parts; fit ρ(Δt) = ρ0·exp(−Δt / τ). The noise share is 1 − ρ0.
4. Hold forecast: mean_part·ρ_mean + departure·ρ_dep, against the single rate 0.72 per hour, scored on held-out days (every fifth day).
5. Pass: CRPS aloft better beyond the day-block interval. Then the two rates go into `tempest_weather_v2/persistence.py` as a second table, opt-in.

**G1-3 radar + station score.** New `scripts/g13_radar_station_score.py`.
1. First check at El Paso: P(10 m speed and 0.5-1.5 km shear both above their q95) / 0.05 from balloons and from radar + ASOS of the same hours. If they disagree beyond the day-block interval, stop.
2. Model side: same number from the tool's pool at the same site, hours and heights, only for hours the radar reported, with normal noise of C4's sd added to the model winds.
3. Report only (`coext` in `scripts/a3_coextremes.py`).

### Step 4

**G3-5 learned monotone update (GPU).** New `tempest/generator/update_net.py` plus a training script.
1. Input per case: the pool's 9 quantiles (5-95 %) per height for u, v, T (44 × 3 × 9), and per height a masked reading: value, noise sd, age, mask (44 × 3 × 4).
2. Output: 9 new quantiles per height and variable, built as median + cumulative softplus steps (cannot cross). Final layer zero-initialised and multiplied by "any mask on", so no sensor = no change.
3. Loss: quantile (pinball) loss against the true profile.
4. Training data: ERA5 truth rows + the generator's pool for the same row. Hide the truth the way sensors do: surface only; 4 radar levels; all levels to 5 km; random. Noise sd drawn from 0.5-5 m/s, given as input and added to the reading.
5. Apply in numpy: per height, map each member through the piecewise-linear map old quantiles → new quantiles (order kept). Then recompute p, rho, a as today.
6. Test: `p3_vad_condition.py` and `w6_observe_eval.py`. Pass: beats `observe` after C4 + G1-6 (and C3 stage 2 if built), coverage 0.85-0.92 at all radar levels.

**C6 run-to-run disagreement (CPU, after F-V2).** New `scripts/c6_lagged_spread.py`.
1. `modeF.load_year_v2(year, ds, starts=("00z", "12z"))`; pair runs 12 h apart valid at the same hour and point.
2. d = RMS(newer run − older run) per band. Premise: rank correlation of d with |newer run − ERA5|, 2016-2020. Kill: under 0.3.
3. Spread factor f = a + b·d / median(d), fitted (2 numbers) on 2016-2020 so that mean squared error / variance = 1; multiply member departures by f.
4. Test on 2022 next to `scripts/fv2_eval.py`: PIT deviation must fall by more than the date-block interval (0.06-0.09), CRPS not worse.

### Step 5 (build only if asked for by a result)

- **G3-1 detail network.** Input: ERA5 profile (44 × 4) + sonde type + year. Target: layer-averaged balloon minus ERA5. Same `Generator` class and `train()` with `cond` = the ERA5 profile. Hold out whole stations (Denver + 20 % of US stations). Needs ERA5 at stations outside the box (not checked). Must beat the shear target on held-out stations, paired seeds.
- **G2-1 detail between heights.** Library of real between-grid pieces from 1-second soundings (not on disk; a download, ask first), straight line removed, smoothed to 50 m, in 3 × 3 classes of layer shear and N². Add in the height reader behind a flag.
- **G3-3 select, then nudge.** Weights w ∝ exp(−0.5·T·D²) on 2-3 summary numbers of the observed levels (mean u, mean v, shear across them) over a pool of 20,000-50,000; T so that ≥ 50 members carry weight; resample; then `engine.conditioned`. Print the effective member count.
- **G3-2 next-hour generator.** `train()` with lead (1, 2, 3, 6, 12 h) as an extra `cond` column and target = profile(t + lead) − profile(t); same `eps` for all leads of a member.

### Step 6

- **G1-4 oracle templates.** In a copy of the scorer path, replace the template rows by the 199 training-year profiles nearest (RMS over standardised columns) to the true profile of each test row. Variogram score against today's templates. Under 1 % gain: close G1-4 and G3-4.
- **G2-3 gust factor.** Midland, 12Z and 00Z: target = balloon speed at 300 m / ASOS 10 m speed. Ridge regression on hour and speed, then + gust factor (peak / mean from `data/raw/asos1min`). Fit 2015-22, test 2023-25. Keep only if the held-out error falls by 5 % or more.
- **G2-6 blend check.** From the mode F score logs: CRPS and coverage per lead, days 5-10, with range calibration per lead. If coverage is already 0.88-0.92, nothing to build.
- **G1-2 mixed pool.** After the stack, replace 15 % of members by whole real profiles (1991-2023, same month ± 1, same hour, nearest point). `coext` from `a3_coextremes.py` and CRPS. Drop if the rise is under 0.005 or CRPS worsens beyond 0.0006.
- **G2-5 double jets.** After `observe_radar` on the 120 El Paso days: count members with two speed maxima above 1.5× the column mean, more than 2 km apart, against the same count in balloons. Count only.

---

Source: `Downloads/tempest_arknet_final_ideas.md` (40 ideas from several AIs, read as a report). Reviewed 2026-11-10 against the handover, `Improvements-Concise.md` and the code.

**How they were judged.** The rating (1 to 10) is how much the idea would help Tempest-ARKNET itself, on its real open problems:

- wind shear is too smooth (real balloons have 1.7x the ERA5 shear; our 0-1 km p99 is about 45 % of the balloons),
- strong ground wind together with strong low shear is too rare at Santa Teresa (IL-187 on 2026-11-10 showed this is a one-site problem; Midland already matches),
- the lowest 300 m drive 87 % of the apogee spread, and the ground-wind gap is site-specific,
- hold / observation updates, long range, and transfer to Denver.

Ideas are marked down when they need a flight simulator, extra hardware or other tools, when they need a whole new generator, or when we already have the thing or already tried it. The source file ranks by "sub-millisecond GPU speed" and "6-DOF coupling"; neither is a problem we have, so its own ranking was ignored. Many of the "bugs" it claims to fix belong to its own proposed designs, not to our code.

Nothing here was tested. Ratings are judgement from the logs.

## Useful

| Idea | Rating | Why |
|---|---|---|
| **A4** Cepstral split: calibrated smooth profile + fine detail taken from real balloon profiles | 8 | Hits our biggest measured gap (shear too smooth because ERA5 is smooth). Uses balloon data we already have, works as a post-processing step, no retraining. Must be fitted together with the shear map so shear is not counted twice. |
| **#14** Hold persistence with several time scales (5 min / 45 min / 6 h) | 7 | Our one-scale Weibull persistence (W3) already beats tool + observe by about 8 %. This is a small extension of `persistence.py`, fitted on station data we have. The "fractional" maths can be dropped; three plain time scales give the same thing. |
| **#13** Check each observation for faults before it is used (chi-square gate), weight by trust | 7 | Only the gate is new. `observe` has no bad-reading check today (only METAR impossible values); one bad anemometer reading bends the whole pool. A few lines. The "sheaf Laplacian" part is what our update already does. |
| **#3** Student-t copula on a few main patterns + extended-Pareto tails | 6 | Fits the two places that still use a Gaussian copula (observe engine, opt-in `couple`), where joint extremes are lost. Limits: the audit showed the co-extreme deficit comes mostly from the training data, and the pooled Pareto tail (L3-18) and Student-t noise inside the network both failed before. |
| **#10** Blend pad data / forecast / climatology by how much each can be trusted at that lead | 6 | The simple weighting part fits `forecast/router.py` and is cheap. The chaos-theory part (FTLE, Fisher-Rao) adds nothing we can measure; skip it. |
| **A3** Build temperature from stable-by-construction steps (also the softplus part of #1) | 6 | Removes impossible unstable layers by design. Our gap is already small after the lapse map (23.6 % vs 21.9 %), so the gain is modest; only worth it as a post-step, not as a retrain. |

## Mediocore

| Idea | Rating | Why |
|---|---|---|
| **#1** Rough-noise fine-structure synthesizer (Volterra-DDSP) | 5 | Same goal as A4, but with invented noise instead of real balloon detail, and written as a new generator. Keep only if A4 fails. |
| **#2** Analog retriever (find similar real days, then adjust) | 5 | Real profiles carry real detail, but the shuffle templates already bring that in, and the P-18 audit says the model is limited by its inputs, not by its type. `tempest/analogs` is empty, so it is a new build. |
| **A2** Two-state model for sharp inversions and shear layers | 5 | Sharp layers are a real weakness, but the surface-jump work (L3-27) was sidelined as a seed effect, and A4 gives sharp layers from real data with less work. |
| **C2** Doob-Hopfield bridge (one update rule for all modes) | 5 | Its exact part is the Kalman-style update we already have in `observe`. Only the lead-dependent observation error is new, and W6 already covers part of that. The learned part is a research project. |
| **S2** Student-t / R-vine copula for everything | 5 | The useful half is #3. A vine over 176 coupled columns is heavy and the default pool does not use a Gaussian copula anyway (it uses the shuffle). |
| **#7** Line up jets and inversions before averaging profiles | 4 | Sound, but we rarely average profiles (the shuffle keeps whole members), so there is little for it to fix. |
| **#4** Richardson-number mixing layer | 4 | Physically nice, but it mixes shear away, and our problem is too little shear, not too much. |
| **#9** Causal model for "what if" stress tests | 4 | `Launch.stress` already does stress tests. This is a more formal version with no accuracy gain. |
| **#25** Separate the climate trend from balloon hardware changes | 4 | Real issue for the 1991-2023 balloon record we use as truth, but the effect on our scores is likely small and the method is hard to verify. |
| **#17** Thermal bubbles (Hill's vortex) | 3 | A thermals module already exists and is switched off; it only matters once a flight simulator uses it. |
| **#18** Long-range pattern forecaster (Koopman) | 3 | Long range has very little skill to win: the index regression and Chronos tied. A fancier model on the same inputs will tie too. |
| **#20** Wavelet blender for the seam between forecast horizons | 3 | The router already ramps between modes; no seam problem has been measured. |
| **#21** Wasserstein average of several models | 3 | We have one generator per box; nothing to fuse yet. |
| **#26** Shape-based (topological) training loss | 3 | Several loss variants already failed or tied within seed noise (0.0005), and the model is input-limited. |

## Discard

| Idea | Rating | Why |
|---|---|---|
| **S1** Flow-matching generator with a hydrostatic head | 3 | Whole new generator. Pressure, density and sound speed are already recomputed from the final profile, so the consistency it promises already holds. |
| **#5** Terrain-following 3D turbulence | 3 | Flight-simulator side. Dryden / von Karman turbulence already exists. |
| **#23** Launch-commit risk measure | 3 | A decision rule on flight-simulator results; does not make the atmosphere more accurate. |
| **#6** Tensor-train pad assimilation | 2 | Exotic rewrite of the working `observe` engine with no stated gain. |
| **#8** Adjoint importance sampling | 2 | Needs 6-DOF runs. `run_importance` already exists, and IL-34 was discarded earlier. |
| **#11** Fast surrogate of the 6-DOF | 2 | Flight-simulator tool, out of scope. |
| **#12** "Virtual radiosonde" from surface gravity waves | 2 | The source itself is unsure of the equation; weak physics and no data for it. |
| **#22** Conservation-law programming language | 2 | A refactor (against the no-refactor rule) with no accuracy gain. |
| **#24** Quantum-fidelity similarity for analogs | 2 | Just another similarity measure for an analog system we do not have. |
| **#28** Hyperbolic attention on climate indices | 2 | Driver interactions already failed twice (F-14, IL-97); long range has little skill to gain. |
| **#29** Multi-site launch-window optimizer | 2 | A scheduling tool on top of the system (IL-37 was discarded for the same reason). |
| **S3** Continuous profile via FNO / SIREN | 2 | SIREN and spherical-harmonic variants already failed on shape. |
| **C1** CG-WSO generator | 2 | Whole new physics-structured generator; months of work, no evidence it beats the current one. |
| **C3** MTTN-Funnel tail model | 2 | Very heavy maths for the tails; a simple tail fit on balloons (IL-103) does the same job. |
| **A1** Path-signature generator | 2 | Whole new generator again; input-limited model means little to gain. |
| **#15** Acoustic tomography with pad microphones | 1 | Needs new hardware. |
| **#16** Onboard guidance lookup | 1 | Rocket guidance, not weather. |
| **#19** Rocket-wake coupling | 1 | Flight-simulator physics. |
| **#27** Adaptive integrator step control | 1 | Flight-simulator internals. |
| **#30** Post-flight acoustic reconstruction | 1 | Needs flight recordings and hardware. |
| The 7 raw "paradigms" | 1 | Idea sketches with nothing concrete to build; their usable parts are the numbered ideas above. |

## Suggested order if any are tried

1. **#13** fault gate (hours, low risk).
2. **#14** multi-scale persistence (small change to existing code, score on held-out station data).
3. **A4** real-balloon fine detail (largest possible gain; score on held-out 2024-25 balloons, same as IL-187).
4. **#3** last: IL-187 showed the co-extreme deficit is specific to one site, so the gain is smaller than first thought.

---

# New ideas

Written 2026-11-10. Three groups, ranked inside each group. Same 1-10 scale as above. Nothing here has been run; every idea names its own test. Every test uses held-out 2024-25 data (never 2026) and must beat the seed noise (0.0005 on skill15, paired seeds).

## What the history says

**What has worked, again and again:**

1. **Borrowing structure from real profiles after the network** (shuffle, shear map, range calibration). This gave the largest shape gains of the whole project (vertical correlation error 0.08 to 0.03, shear error 0.044 to 0.010).
2. **Simple statistics next to the network** (50:50 ridge mix, EWMA bias tracker, Weibull persistence, station-scale widening). Small, cheap, "never worse".
3. **Fits on a lot of data** (5 calibration years, all 24 hours, 1991-2025). More rows beat cleverer methods every time.
4. **Real observations on launch day** (radar: +32 % aloft; persistence: about +8 %).
5. **Recasting the target** (pressure as a departure, step loss on height differences).

**What has failed, again and again:**

1. **Changing the network itself** (wider, deeper, driver interactions, spherical harmonics, SIREN, heavy-tailed noise, extra loss terms). The audit says the network is limited by its inputs, not by its type.
2. **Fits on few balloons with many free numbers** (P-4, P-12, P-14; IL-187 had 0-2 joint events per group).
3. **Splitting calibration into small groups** (by season, by spread, per column).
4. **Site-specific patches** judged on pooled numbers.

So good new ideas: sit after the network or beside it, use many real samples, have few free numbers, and give the network richer inputs rather than a fancier body.

## Stress test (2026-11-10)

Every idea below was attacked with the experiment log and the mistake log, then patched. Each idea now has an "Attack" and a "Patched version" line. Idea numbers are unchanged so the cross-references still work; the table gives the new order. Two ideas were added (Group 1 ideas 6 and 7).

**Traps that hit many ideas:**

1. **Our headline is scored against ERA5.** Any idea that moves the pool toward balloons (more shear, sharper layers) lowers the headline by design. Such ideas need balloons as a declared second referee (2005-2022, above 1 km) and stay opt-in until you decide which truth the tool serves.
2. **The stack has an order.** The shuffle adds extreme shear (4.7x ERA5's rate), then the shear map removes it (L14b). A new step in the wrong place is undone by the next one. Every new step must say where it sits and be fitted there.
3. **Never mix two sources of ranks.** IL-161: blending template ranks with the network's order made physics worse (superadiabatic share 0.324 to 0.437). Whole members may be mixed; ranks may not.
4. **Samples close in time are not independent** (IL-110). Count days, not readings.
5. **Low-level balloon tails after 2022 are not a safe target** (processing change, L18). Fit on 2005-2022.
6. **2024-25 has already been used for 17+ decisions** (IL-113). Every new gate on it is weaker than it looks. Set the kill rule before the run.
7. **"Better templates" has failed twice** (P6W, IL-187), and G3b showed template resolution is not the limit. IL-169: the templates themselves hold a co-extreme ratio of about 0.068 and our pool after the shuffle has 0.052. No template idea can go much above 0.068.
8. **A simple rule often beats us.** W3 / W6: plain linear persistence (1.035) beats tool + `observe` (1.156). Every idea must first beat the simplest rule.

**Ratings after the stress test:**

| Group | Idea | Was | Now | Verdict |
|---|---|---|---|---|
| 1 | 1 Shear curve, now as the shear map's target | 8 | 8 | Do (it is IL-103, patched) |
| 1 | 6 Calibrate `observe` itself (new) | - | 7 | Do after W6B |
| 1 | 3 Radar + station data, as a score | 7 | 6 | Do as a score only |
| 1 | 5 Spread tracker | 6 | 6 | Do, on a continuous number |
| 1 | 7 Slow drift tracker for climate mode (new) | - | 6 | Do after a one-hour check |
| 1 | 2 Mixed pool | 7 | 5 | Small gain at best |
| 1 | 4 Similar-day templates | 6 | 5 | Oracle test decides |
| 2 | 7 Shape scores | 6 | 7 | Do first |
| 2 | 1 Detail between heights | 8 | 6 | Spectrum check decides |
| 2 | 2 Student-t update | 7 | 6 | Widen only, never reject on surprise |
| 2 | 4 Scale-dependent persistence | 7 | 6 | Two scales only, aloft only |
| 2 | 3 Gust factor | 7 | 5 | Information test decides |
| 2 | 6 Quantile-average blend | 6 | 5 | May already be done by calibration |
| 2 | 5 Shift, then adjust | 6 | 4 | Do not build |
| 2 | 8 Satellite referee | 6 | 4 | Do not build; see Group 1 idea 7 |
| 3 | 5 Any-sensor, now a learned monotone update | 8 | 7 | Best structural idea left |
| 3 | 1 Detail network | 8 | 6 | Only if the 2-number fit leaves a gap |
| 3 | 2 Next-hour generator | 7 | 6 | Only if idea 5 is not built |
| 3 | 3 Select, then nudge | 7 | 6 | Real-pool IL-128 check decides |
| 3 | 6 Reachability | 7 | 5 | Score merged into Group 2 idea 7 |
| 3 | 4 Split generator | 7 | 4 | Do not build |

Plain summary: four ideas hold at 7 or above. Most of the others shrink to a cheap test with a kill rule.

## Group 1: more of what already works (5 ideas + 2 added)

**1. One pooled balloon-to-ERA5 shear curve. Rating 8.**
- What: fit one smooth curve (shear ratio balloon / ERA5, by height and by quantile) on all IGRA stations pooled, and apply it on top of the shear map.
- Why here: real shear is 1.7x ERA5 and this is our largest measured gap. Earlier balloon fits failed because they had many free numbers on two stations. This one has a handful of numbers on hundreds of stations.
- Cost and test: CPU, about a day. Score shear quantiles on held-out balloons at stations left out of the fit.
- Risk: the ratio may differ between flat land and mountains; check Denver separately.
- Attack: (a) "On top of the shear map" is wrong. The shear map is fitted to ERA5 and changes shear against balloons by under 3 % (L18); two stacked maps would fight (trap 2). (b) This is close to IL-103, already planned, so it is less new than it looked. (c) Balloon shear includes instrument noise, largest at 12-18 km; the 2.6x there is partly noise, so the full ratio over-corrects. (d) At 0-1 km the balloon tails changed in 2023; before that balloon / ERA5 was 0.8-1.0, so there may be no real gap to fix there (trap 5). (e) Corrected 2026-11-10: balloons for 986 stations (93 US) are on disk in `data/igra_heights`; what is not confirmed is the matching ERA5 outside the NM/TX and Denver boxes. (f) The ERA5-based shear score gets worse by design (trap 1).
- Patched version: do not add a map; change the shear map's *target*. Target = ERA5 shear quantiles times one ratio per band. The ratio is 1.7 at every quantile, so this is 2 numbers (1-5 km, 5-12 km). Leave 0-1 km alone. At 12-18 km cap the ratio at the 5-12 km value until the noise share is known. Fit on 2005-2022, test on 2024-25 balloons and on Denver (left out of the fit). Ship as an opt-in switch because of trap 1. Honest size: the model is already 1.4x ERA5, so the gap left is about 20 %, not 70 %.

**2. Mixed pool: add real past days as members. Rating 5 (was 7).**
- What: a share of each pool is real historical profiles for the same place, month and hour; the rest is the network. The share is one number, chosen on score.
- Why here: the 50:50 ridge mix worked for mode F. Real days have perfect coupling between all variables, which the network alone lacks (its own co-extremes are near zero before the shuffle).
- Cost and test: CPU, hours. Compare CRPS, variogram and co-extremes against the current pool.
- Risk: real ERA5 days are smooth, so they go through the same shear map.
- Attack: (a) IL-169 measured the ceiling: a pool of real ERA5 days has a co-extreme ratio of about 0.07; ours after the shuffle has 0.052. A 20 % share of real days moves 0.052 to about 0.056. Tiny. (b) Real days know nothing about today's drivers, so they dilute the small skill we have (+0.03 over climatology). (c) Real members must skip range calibration and the shuffle (they are already real). The pool then holds two kinds of members, and every map was fitted for one kind. (d) In past and forecast modes, climate days are far too wide: two bumps. (e) Leak risk if the real days come from test years.
- Patched version: climate mode only. Real members are added whole, after the stack, never rank-mixed (trap 3). Share fixed at 10-20 %, not tuned. Days from 1991-2023 only. Kill rule set now: if co-extremes rise by less than 0.005 or CRPS worsens beyond seed noise, drop it. Expect a small gain at best.

**3. Radar + 1-minute station data as the big sample for joint statistics. Rating 6 (was 7).**
- What: use the radar wind archive (`data/raw/nexrad_nvw`) with the 1-minute ASOS wind (`asos1min`) as truth for "ground wind and wind aloft together", instead of two balloons a day.
- Why here: IL-187 could not judge co-extremes because 120 soundings give 0-2 joint events. Radar gives a profile every few minutes: thousands of events.
- Cost and test: CPU, 1-2 days. First check radar against the balloons at El Paso (same site).
- Risk: radar is blind below about 300-500 m and in very clear dry air, so the sample is not all weather.
- Attack: (a) Trap 4: profiles every 5 minutes are not independent. The real sample is a few hundred days, not thousands of events. (b) Radar only sees air that carries insects, dust or rain. Windy dusty days are over-represented and clear cold nights are missing, so the "true" rate is biased up. (c) Radar gives volume-average wind on about 300 m levels, and the lowest level is 300-500 m up. "0-1 km shear" from a 10 m mast and a radar level mixes two instruments; independent noise in both lowers the joint rate (the same dilution trap as the V2 low-level check). (d) Radar against balloons was checked only at El Paso, 120 days, 00Z.
- Patched version: use it as a score, never as a fit target. Give the model the radar's blindness too: compute the model's number at the same heights and hours, only at times the radar reported, with radar-size noise added. Both sides then share the same flaws and the comparison is fair. Intervals by resampling whole days. First step: the same number from El Paso balloons and El Paso radar must agree, or stop.

**4. Similar-day templates for the shuffle (forecast and past modes). Rating 5 (was 6).**
- What: take the shuffle's real profiles from past days whose forecast looked like today's, not from any day of that month and hour.
- Why here: the shuffle is our best tool; this is its published flow-dependent version (SimSchaake). Climate mode has no day-specific information, so it applies to modes that do.
- Cost and test: CPU, 1 day. Variogram score per lead for mode F.
- Risk: fewer matching days means noisier templates; keep a minimum count.
- Attack: (a) Trap 7: this is the direction that failed twice, and G3b showed finer templates changed nothing. (b) Fewer matching days means noisier ranks: the "small groups" failure (P-8). (c) The forecast archive has one start hour (00 UTC) and few years, so few candidate days. (d) The similarity measure adds free numbers. (e) Published gains from this method were modest.
- Patched version: run a one-hour "oracle" test first. Pick the templates as the real days closest to the *true* profile of each test day (cheating on purpose). No matcher can do better than that. If the variogram score improves by less than 1 %, drop this idea and Group 3 idea 4 together. If it passes: no hard selection. Keep the whole month-hour bin and draw templates with weights from one driver chosen in advance (jet-level wind speed), with no tuning.

**5. Running tracker for spread, not only for bias. Rating 6.**
- What: extend the EWMA bias tracker (IL-98 B) so it also tracks how often the truth falls inside the 90 % range at a site, and widens or narrows slowly.
- Why here: the bias tracker was "never worse". Width errors are site-specific (10 m wind needed widening from 59-80 % to 88-89 %).
- Cost and test: CPU, hours, on the forecast logger. Coverage before and after.
- Risk: needs a few weeks of local data before it helps.
- Attack: (a) Coverage is a yes / no signal. With 30 recent cases, a 90 % coverage is only known to about 5 points either way. The tracker would chase noise, the opposite of "never worse". (b) Misses come in runs (the same weather for days), so the independent cases are even fewer. (c) Narrowing after a lucky run is dangerous: ranges that are too narrow are the costly error.
- Patched version: track a continuous number instead: squared error divided by the pool's variance (it should average 1). It carries several times more information per case. Shrink it toward 1, memory of 60 days or more, limits 0.8-1.5, widen fast and narrow slowly. Test by replaying the logger: coverage error must fall at two thirds of the sites or more, and CRPS must never be worse.

**6. Calibrate `observe` itself with one or two numbers. Rating 7.** (added by the stress test)
- What: W6 showed two faults. After `observe`, the 90 % range holds the truth only 72 % / 86 % of the time. And plain linear persistence (CRPS 1.035 / 0.923) beats tool + `observe` (1.156 / 1.006). Fit the two numbers behind this (how much we trust a reading, how fast that trust fades per hour) on many station-hours, so coverage returns to 90 % and the observed height matches the persistence law that already won.
- Why here: simple statistics beside the network, on a big sample (1-minute ASOS, many stations). The hooks exist: the soft reading error, the 0.72 per hour fade, the IL-138 widening code (off).
- Cost and test: CPU, 1 day. Fit on 2015-22, test on the 2023-25 W3 cases: CRPS no worse than linear persistence, coverage 0.88-0.92.
- Risk: overlaps the running W6B (`speed_space=True`); wait for it and fit on top of whichever wins.
- Attack: (a) the evidence is ground-only, two stations. (b) Fitting per station would repeat the "small groups" failure. (c) Widening to fix coverage can hide a wrong centre.
- Patched version: one fit pooled over all stations. Check the centre (bias after `observe`) before widening. Aloft, repeat the check on the El Paso radar days before trusting the same numbers there.

**7. Slow drift tracker for climate mode. Rating 6.** (added by the stress test, replaces Group 2 idea 8)
- What: ERA5 arrives five days late. Keep a slow running mean (about 12 months) of "ERA5 minus pool median" per height band, and remove it.
- Why here: temperature at 12-18 km had negative skill on 2026, and balloons and ERA5 moved apart around 2020 (IL-67). A fixed 1991-2023 fit cannot follow a drift (IL-115). The same tracker for forecast mode was "never worse".
- Cost and test: CPU, hours. Replay over 2015-25 (no 2026 data).
- Risk: one number per band, pooled over the box, or it becomes a small-group fit.
- Attack: (a) if the generator already has a year or trend input, the gain is small. (b) A 12-month mean lags a sudden step by months. (c) It tracks ERA5's own changes, real or not (trap 1).
- Patched version: check (a) first, one hour. Use a shorter memory (3 months) only for bands where the replay shows a step. Say in the output that the centre follows ERA5.

## Group 2: old ideas from the file, used in a new way (8 ideas)

"New" means: we found no published use in this form. Where close work exists, it is named.

**1. Real detail between our 44 heights, grid values untouched. Rating 6 (was 8).** (from A4 and #1)
- What: our grid has 500 m steps aloft; a flight sees a straight line between them. Add wiggles between grid points, taken from real 1-second balloon soundings, scaled by the member's own shear and stability. The values at the 44 heights do not change.
- Why new: A4 was proposed on the grid. Using it only between grid points means no existing score, calibration or test can change. It adds the missing sharp layers without risk.
- Cost and test: CPU, 2-3 days plus a download of US high-resolution soundings. Compare the shear spectrum at 50 m steps with soundings left out.
- Risk: must not double-count with Dryden turbulence; set a scale split (detail above about 50-100 m, turbulence below).
- Attack: (a) No score of ours can see it. That was the selling point; it is also the flaw: nothing can accept or reject it, and it only matters to a flight simulator (scope). (b) Double counting with Dryden is larger than I said: Dryden's length scale aloft is several hundred metres, the same scales as the wiggles. (c) "Scaled by the member's own shear and stability" is a fitted law on two balloon sites: the failed pattern. (d) 1-second soundings carry swing and GPS noise below about 50 m, and their processing changed in 2023 (trap 5). (e) The grid shear itself stays about 20 % low. (f) Where steps are 500 m (above 2 km) a small rocket is fast and stable, so the flight effect may be small.
- Patched version: first an afternoon check: the spectrum of (grid profile drawn as straight lines + Dryden) against real 1-second soundings from a few dozen flights. Add only what is missing. If nothing is missing between 100 m and 1 km, stop. If something is: no fitted law. Re-use real between-grid pieces (the straight line between the two grid heights removed) from a library sorted by three classes of layer shear and three of stability. Smooth soundings to 50 m first, use pre-2023 soundings only, and keep it opt-in in the height reader.

**2. Student-t update in `observe`: one number does two jobs. Rating 6 (was 7).** (from #3 and #13)
- What: measure how surprising a reading is given the pool. Very surprising: treat it as a likely fault (the #13 gate). Somewhat surprising: use it, but keep the spread wider afterwards.
- Why new: the maths exists for ensemble filters (Le Provost et al. 2023), not for launch-weather pools. For us it is a few lines in the existing update. Radar conditioning already showed over-tightening (coverage 0.49 with all levels).
- Cost and test: CPU, 1 day. Coverage after conditioning on the 120 El Paso radar days.
- Risk: one extra number (tail weight) to fit; fit it once, pooled.
- Attack: (a) After `observe` the range is too narrow on *ordinary* readings (truth inside 72 % of the time at TCS, not 90 %). The t rule only helps on surprising ones. (b) Rejecting surprising readings is dangerous. Our pool is barely better than climatology, so on an unusual day the reading is right and the pool is wrong. The gate would throw away the most valuable readings on the days users care about most. (c) "One number, two jobs" was too neat: where to reject and how much to widen are separate choices. (d) The method's known limit: the surprise measure collapses with fewer members than numbers. Fine for 8 radar numbers, not for a full profile. (e) An out-of-range reading still makes a shear spike (IL-129; the fix exists, switched off).
- Patched version: never reject on surprise alone. Reject only when a sensor disagrees with itself: with its own reading minutes earlier (beyond what persistence allows) or with a second sensor. A surprising but consistent reading is used in full, and the spread stays wider afterwards (the t rule), on 10 numbers or fewer at a time. Do new Group 1 idea 6 first, and switch on IL-129.

**3. Gust factor as a free low-level sensor. Rating 5 (was 7).** (from #12, the "virtual radiosonde" aim, with real physics)
- What: a pad anemometer gives mean wind and peak gust. Their ratio tells how stirred the lowest air is, and that tells how much the wind changes in the first few hundred metres. Let `observe` accept it.
- Why new: gust factor is used for stability classes on towers, not for conditioning a profile pool. The lowest 300 m drive 87 % of our apogee spread, and no radar sees them.
- Cost and test: CPU, 2-3 days. Learn the link from 1-minute ASOS plus radar on disk; test on held-out days.
- Risk: the link may be weak at night; ship only if it beats plain `observe`.
- Attack: (a) Gust factor mostly measures ground roughness, which is a site constant we already have (`roughness.py`). Second, it measures daytime stirring, and hour of day plus wind speed already give most of that. (b) Low-level shear is most dangerous at night, with a jet above calm, cut-off surface air. Then the surface says nothing about the air above. So the sensor fails when it is needed. (c) No truth to learn from: radar is blind below 300-500 m, balloons fly twice a day, and mast and balloon share a site only at Midland. (d) Routine reports give gusts only above a threshold; only the 1-minute data works.
- Patched version: an information test first, half a day. At Midland, predict the balloon wind ratio (300 m over 10 m) from hour and wind speed, then add gust factor. Keep the idea only if the held-out error falls by 5 % or more. If kept: no new formula with height. Use gust factor to weight existing pool members by their own low-level stability, so whole members are kept. Daytime only.

**4. Persistence that depends on layer thickness. Rating 6 (was 7).** (from #14 and #20)
- What: thick wind patterns last hours; thin layers change in minutes. During a hold, age each scale at its own rate.
- Why new: #14 gave time scales for the ground wind only. Radar every few minutes lets us measure this aloft, which hourly ERA5 cannot.
- Cost and test: CPU, 2 days. Hold forecasts 15 min to 6 h, against the current W3 / W6.
- Risk: radar noise can look like fast change; estimate the noise first.
- Attack: (a) W3: the cleverer law did not beat plain linear persistence. The 8 % room is against tool + `observe`, and new Group 1 idea 6 should take that first. (b) Radar averages over a volume on 300 m levels. It cannot see thin layers, so "thin layers change in minutes" would be measured from noise. (c) Many scales means many decay rates: many free numbers.
- Patched version: two scales only: the mean wind of the whole column, and the departures from it. Two decay rates. Remove radar noise the standard way: follow the correlation back to zero time gap; what is missing from 1 there is noise. Fit on all radar days pooled. Test hold forecasts aloft against today's single rate (0.72 per hour). Aloft only; the ground belongs to Group 1 idea 6.

**5. Shift, then adjust, when conditioning on a profile. Rating 4 (was 6).** (from #7)
- What: if radar shows the jet 500 m higher than a member has it, move the member's jet up, then adjust strength. Today we only adjust strength, which can leave two weak jets.
- Why new: known for 2-D weather maps (field alignment, Ravela 2007); not used for 1-D launch profiles.
- Cost and test: CPU, 2 days. Jet height and peak error after `observe_radar`.
- Risk: no proof yet that double jets happen often; measure that first (one hour of work).
- Attack: (a) Four radar levels 500 m apart with 3 m/s noise cannot place a jet better than about 500 m. The shift would be fitted to noise. (b) Shifting a member means interpolating on our uneven grid, which flattens peaks. (c) Wind must move together with temperature, or the link between them breaks. (d) The need is still unproven.
- Patched version: do not build it. Selection (Group 3 idea 3) gives the shift for free: it keeps whole members whose jet already sits at the right height. Keep only the one-hour count of double jets after `observe_radar`, as a check of today's engine.

**6. Blend climate and forecast pools by averaging quantiles. Rating 5 (was 6).** (from #10 and #21)
- What: for the open item IL-74, do not mix members from both pools. Average the two pools quantile by quantile, with a weight that fades with lead.
- Why new: this is the 1-D form of the Wasserstein average from #21, which costs nothing. It keeps one clean bell shape instead of two bumps.
- Cost and test: CPU, hours. CRPS and PIT per lead, days 5-10.
- Risk: none beyond a wasted afternoon.
- Attack: (a) "Risk: none" was wrong. Averaging quantiles gives a narrower result than mixing members. When a day-7 forecast is confidently wrong, a mix hedges and the average does not. (b) It only sets the range per height. The order of members must come from one pool (trap 3), and switching pool with lead makes a jump. (c) Range calibration fitted per lead may already do this job.
- Patched version: check (c) first, one hour. If still needed: keep the forecast pool's members and their order at all leads, and move each height's values onto the blended quantiles (a quantile map, the kind of step that works here). One number sets the fade with lead. Gate: coverage per lead at least as good as plain member mixing, CRPS not worse.

**7. Two new shape scores: feature counts and Richardson number. Rating 7 (was 6).** (from #26, #7, #4)
- What: count jets and inversions per profile and their strength; count layers where wind shear beats stability. Compare with balloons.
- Why new: the file wanted these as training losses, which have failed here. As scores they are safe, and they test wind and temperature together, which no current score does.
- Cost and test: CPU, 1 day. No model change.
- Risk: none; it may reveal a new gap.
- Attack: (a) Counts depend on resolution and thresholds. Balloon files list "significant levels", chosen because something changes there, so they show more features than an even grid. (b) On 500 m layers the Richardson number almost never drops below the textbook 0.25; a count at that threshold would be all zeros. (c) Stability must use exact potential temperature (IL-130: the shortcut was 31-45 % low). (d) Every new score is another way to fool ourselves on 2024-25 (trap 6). (e) Published rank tests already answer "does the truth look like one of the members" for whole profiles (band-depth and minimum-spanning-tree rank histograms). My Group 3 idea 6 score reinvented them badly.
- Patched version: three numbers, fixed now: the share of layers with Richardson number below 1, per band; inversions stronger than 2 K per profile below 3 km; and the band-depth rank histogram for whole profiles. Balloons are first averaged onto the 44 heights by layer means. Print all three per stage of the stack, like the L14b audit that led to the lapse-map win. Report only; not a gate until the spread over 3 seeds is known. Rating up: cheapest idea here, and stage audits are where our last win came from.

**8. Satellite temperature as a third referee at 12-18 km. Rating 4 (was 6).** (from #25)
- What: balloons and ERA5 drifted apart around 2020 (IL-67) and we cannot tell which moved. GPS radio-occultation temperatures are independent of both. Use them to decide, then correct the right one.
- Why new: #25 proposed heavy causal statistics; a third measurement answers the same question directly.
- Cost and test: CPU, 2 days plus a small download. Not confirmed: free access to the data, and whether ERA5 changed its use of it in 2020.
- Risk: only helps one band; T 12-18 km had negative skill on 2026, so it matters.
- Attack: (a) Not independent. ERA5 takes in these satellite data, and (not re-checked) their volume grew sharply around 2020. That may itself be the cause of the 2020 shift; ERA5 and the satellite then agree by construction. (b) Access to the data is still unconfirmed. (c) The answer would not change what we do: we train on ERA5 either way. What hurts is that the pool cannot follow a drift.
- Patched version: skip the download. Check in one hour whether (ERA5 minus balloon) at 12-18 km is a step in 2020. Then handle the drift directly with new Group 1 idea 7.

## Group 3: changes to the basic structure (4 ideas)

Each keeps the engression training recipe that already works. Each attacks "the network is input-limited" by giving a network rich inputs, not a new body.

**1. Detail network: ERA5 profile in, balloon-like profile out. Rating 6 (was 8).**
- Mainstream part replaced: we train on smooth ERA5, then repair with several separate maps (station correction, shear map, tail fit).
- New design: a second small generator. Input: one ERA5 profile plus place and time. Output: random draws of what a balloon would have measured. Train on ERA5-balloon pairs from all IGRA stations. Run it on the first network's members.
- Why it should work: the input is a full profile, so it is not input-limited. It learns the 1.7x shear, sharp inversions and wind-temperature links in one step. It is learned once and used at any site, which helps Denver.
- Closest published work: a plain (non-random) network restoring detail from coarsened soundings; diffusion models conditioned on IGRA. We found none doing ERA5 to balloon as a random 1-D generator.
- Cost and test: small; hours on the 32 GB machine or one short supercomputer job. Test on stations and years left out.
- Risk: ERA5 has already seen these balloons, so the gap looks smaller at balloon sites than elsewhere. Past balloon fits failed; this one differs by pooling hundreds of stations.
- Attack: (a) It must beat a 2-number fit. Balloon shear is 1.7x ERA5 at every quantile, so most of what it would learn is one constant. Our history: simple fits beat networks. (b) A balloon reading carries instrument noise, an hour-long climb and 50-100 km of drift. The network would learn to add all of that as "detail". (c) It would learn sonde eras (the 2023 change) unless told. (d) It sits after a stack calibrated to ERA5. It changes the ranges, so the coverage we tuned is gone and needs a second calibration against few balloons. (e) The headline falls (trap 1). (f) The balloons of hundreds of stations are on disk (986 in `data/igra_heights`), but the matching ERA5 outside the two boxes is not confirmed. (g) ERA5 has already seen these balloons.
- Patched version: build it only if a shape gap remains after Group 1 idea 1, shown by the Group 2 idea 7 scores. Then: predict only the difference balloon minus ERA5; average balloons to layer means first; give sonde type and year as inputs (set to "modern" at run time); hold out whole stations. It must beat Group 1 idea 1 on held-out stations with paired seeds, or it is dropped.

**2. Next-hour generator. Rating 6 (was 7).**
- Mainstream part replaced: every draw is a single moment. Time behaviour is added afterwards (persistence tables, soak history).
- New design: the same generator type, with one more input: the atmosphere one hour before. Trained on hourly pairs.
- Why it should work: the previous hour is the richest input there is. One model then gives holds, launch-window sequences and short nowcasts from an observed state.
- Cost and test: one training run of the current size. Test: 1-12 h against W3 persistence, which is the bar.
- Risk: errors grow when chained; limit to 12 h. ERA5 hours are too smooth at the ground; use 1-minute ASOS there.
- Attack: (a) The bar is high: plain linear persistence beat our tool at the ground. (b) ERA5's hour-to-hour change is a model's change: too smooth, with small jumps where its analysis windows meet. A network trained on it gives over-confident holds, and `observe` is already too narrow. (c) A rich input invites the lazy answer "copy the last hour". (d) Chaining 1-hour steps: a spread that is right at 1 h is wrong at 6 h.
- Patched version: no chaining. Lead time (1, 2, 3, 6, 12 h) is an input and the target is the *change* over that lead (recasting the target is what worked: P-1, P-2). Use the same random numbers for all leads of a member, which gives a smooth path in time. Aloft only; the ground stays with the persistence law. Gate: beat "persistence fading into climatology" per height on ERA5, and on real radar pairs aloft. Build only if Group 3 idea 5 is not built (there, an hour-old reading is just one more sensor).

**3. Select, then nudge: a new `observe` engine. Rating 6 (was 7).**
- Mainstream part replaced: `observe` rebuilds members in a Gaussian-copula space. The IL-128 check showed this inflates tail shear 3.6-4.8x on a heavy-tailed pool.
- New design: make a very large pool (cheap). Keep the members closest to the readings, using the Student-t measure from Group 2 idea 2. Then apply only a small adjustment to those.
- Why it should work: kept members are whole, coupled profiles. This is the open item IL-128 plus two additions (large pool, small final nudge).
- Cost and test: CPU, 3-4 days, behind a flag. Same radar and METAR tests as today.
- Risk: with many readings (a full radar profile) too few members match; the nudge step is there for that.
- Attack: (a) The premise is unproven: the 3.6-4.8x tail inflation was on a synthetic pool; the repeat on the real pool is pending. (b) Arithmetic: matching 8 radar numbers to 3 m/s in a pool with 8 m/s spread keeps, at worst, about 1 member in a few thousand. 200 survivors could need 500,000 members, each through the whole stack. (c) Only K = 3 template sets exist, so a huge pool repeats the same rank structures. (d) On an unusual day nothing matches, and we are back on the old engine exactly when it matters.
- Patched version: first run the IL-128 check on the real pool; if the inflation is below 1.2x, stop. If it is real: soft weights, not a hard cut, on 2-3 summary numbers of the observed levels (not all 8), softened until at least 50 members carry real weight. Then today's update for the small mismatch left (a small update distorts little). 20,000-50,000 members are enough. Print the effective member count with every call.

**4. Split the generator: simple statistics for the ranges, real days for the links. Rating 4 (was 7).**
- Mainstream part replaced: one network must produce both the range of every variable and how they move together. It does the first well and the second poorly.
- New design: ranges come from the network mixed with ridge. Links come from real days, chosen by a small learned matcher (which past days fit these conditions?) instead of a fixed month-hour bin.
- Why it should work: it makes our best two results (shuffle, ridge mix) the design itself. It extends Group 1 idea 4 from a rule to a learned choice.
- Cost and test: one small training run plus CPU. Variogram and co-extreme scores.
- Risk: the matcher may learn nothing beyond month and hour in climate mode; then keep it for forecast mode only.
- Attack: (a) In climate mode the matcher sees the same drivers as the network, and those lift us only 3 % over climatology. There is nothing to learn beyond month and hour, which is today's bin. (b) Trap 7: a third try in a direction that failed twice, with a measured ceiling. (c) In forecast mode it is Group 1 idea 4 with more free numbers.
- Patched version: none worth building now. The oracle test in Group 1 idea 4 decides it: if perfect templates do not help, a learned matcher cannot.

### Group 3 additions: two ideas taken from architectures released in the last 6 months

Added 2026-11-10. Each starts from a new published design in another field, then is changed several times to fit us. After the stress test, idea 5 is first in Group 3 (see the table above).

**5. Any-sensor generator. Rating 7 (was 8).** (from GenToka, fusion-reactor model, 5 November 2026)
- The source: one generative model for a fusion reactor that takes whatever signals are available (profiles, single numbers, time series), each through its own small encoder, and produces whichever signals are asked for. It is trained once on everything, then adapted per task.
- What is unique in it: (a) one encoder per signal type, so a profile stays a profile and a number stays a number; (b) which signals are inputs and which are outputs is chosen per call, not fixed; (c) pre-train on all signals, then adapt.
- Mainstream part of ours it replaces: `observe` uses a hand-built Gaussian-copula update, one sensor type at a time, and each mode (climate, past, forecast, hold) has its own path.
- Our version, after four changes:
  1. *Drop their generator type.* They use diffusion, which is slow and cannot run in our numpy-only runtime. We keep our one-step engression recipe; only the input side is borrowed.
  2. *Train by hiding parts of real profiles the way our sensors do.* Take a real profile, keep only what a sensor would see (four radar heights with 3 m/s noise; the surface only; a reading that is one hour old; mean wind plus peak gust), and ask the network to draw the rest. It learns how much each reading says about everything else, including the non-Gaussian links the copula loses.
  3. *Make it a correction, starting at zero.* The input also includes a member from the current pool, and the output is a change to that member. With no sensors, the change is exactly zero. So every climate-mode score stays as it is today, by construction.
  4. *Pre-train on simulated sensors, adapt on real ones.* Real radar-plus-balloon pairs are few (120 days at El Paso). So train on millions of hidden-part examples from ERA5 and balloons, then adapt lightly on the real pairs.
- Why it should work here: readings on launch day gave our largest gains (+32 % aloft from radar). The input is rich, so the "input-limited" problem does not apply. It absorbs Group 3 ideas 2 and 3 (the previous hour is just one more sensor) and Group 2 ideas 2 and 3 (surprising readings, gust factor).
- Closest published work: diffusion models conditioned on mixed observations (2026), masked autoencoders for satellite data. We found none that is one-step, score-trained and aimed at launch profiles.
- Cost and test: one training run of the current size plus four tiny encoders. Test: the 120 El Paso radar days and the METAR tests, against today's `observe`; coverage must stay near 0.90 (today's full-radar update drops to 0.49).
- Risk: simulated sensors may be cleaner than real ones; the adaptation step is there for that. A radar 100 km from the pad sees other air; feed distance in as an input.
- Attack: (a) "Zero change with no sensors" is not guaranteed by starting at zero; after training it drifts unless forced. (b) Bigger: a free change per member breaks the order the shuffle set, so the work of calibration, shear map and lapse map is lost. And trained on (random member, truth) pairs, the network learns to ignore the member and redraw from the sensors. (c) Adapting network weights on 120 days is the "few balloons, many free numbers" failure. (d) Simulated sensors read ERA5; a real radar reads the real air. That mismatch is the main error and it is unknown away from El Paso. (e) Four encoders are over-building for 44-height vectors. (f) Realistic gain: fix the over-tightening (coverage 0.49) and take part of the 8 % room. Not a leap.
- Patched version: a **learned monotone update**. The network does not touch members. Input: the readings as one masked vector (value, noise size and age per height; no encoders) plus the pool's own quantiles. Output, per height and variable: a new set of quantiles. Each member is then moved by a quantile map from old to new. That is the same kind of step as range calibration and the lapse map: order is kept, so the shuffle's links survive. With no sensors the mask forces "no change". Train on real profiles hidden the way sensors hide them, with the noise size drawn at random and given as an input. No weight adaptation: on the 120 real days fit one number per sensor type (its effective noise). Gate: beat `observe` after Group 1 idea 6 on CRPS, with coverage 0.88-0.92 on all radar levels. Hole left open: a monotone map cannot change how heights move together after a reading; measure that with the variogram score.

**6. "Every real day must be reachable": coverage score, then coverage training. Rating 5 (was 7).** (from ROMS-IMLE, image generator, July 2026)
- The source: a small one-step image generator that matches diffusion models. Its training rule: for every real example, find the closest generated example and pull it closer. No real example may be left without a near neighbour.
- What is unique in it: (a) the rule works from the real data outward, so rare cases cannot be dropped; (b) it measures closeness separately at coarse and fine scales; (c) it uses a forgiving distance, so a few bad examples do not dominate.
- Mainstream part of ours it replaces: our loss (afCRPS) scores each height on its own. It cannot see whether a whole real profile is missing from the pool. That is why the network's own co-extremes are near zero and the shuffle has to rebuild them.
- Our version, after three changes:
  1. *First as a score, with no training.* For each real balloon profile, find the nearest pool member for the same month and hour. The share of real profiles with a near member is "recall": does the pool contain every kind of real day? The reverse share is "precision": is every member a believable day? No current score answers either, and this is the direct measure of "representative of all cases".
  2. *Then as a training term, but not in the main network.* Loss changes in the main network have failed or tied here. Use the rule in the two new networks where whole-profile realism is the point: the detail network (idea 1) and the any-sensor generator (idea 5). Keep afCRPS for the ranges; add the pull-nearest term for whole profiles.
  3. *Measure closeness per vertical scale, with the forgiving distance.* Thick layers, medium layers and thin layers each count equally, so thin shear layers are not drowned out. The forgiving distance stops balloon glitches from steering the fit.
- Why it should work here: the one loss change that did work for us (the step loss, P-2) also targeted structure across heights. This is the same direction, taken to whole profiles.
- Closest published work: none found for weather pools, either as a score or as a training rule.
- Cost and test: the score is CPU, one day. The training term adds a nearest-neighbour search per batch (cheap at our sizes). Gate: recall rises, CRPS and coverage stay inside seed noise.
- Risk: the pull-nearest rule is not a proper score, so it can narrow or widen the spread; that is why afCRPS stays and the gate checks coverage.
- Attack: (a) As a score it reinvents, badly, published rank tests (see Group 2 idea 7). With 199 members in about 200 numbers per profile, all nearest distances are nearly equal; the "near" radius is arbitrary; a wider pool scores better, so it rewards ranges that are too wide; balloon noise makes every real profile "unreachable". (b) "Precision" cannot be computed per case: there is one truth per case. (c) As a training rule it needs many draws per case, and more draws per case gave nothing here (F-15). Its only homes are two networks that may never be built. (d) It is not a proper score.
- Patched version: the score part moves into Group 2 idea 7 as the band-depth rank histogram. The training part is parked; revisit only if Group 3 idea 1 is built and its profiles fail that histogram.

## Contenders (2026-11-10): six ideas that could match or beat number 1

Number 1 so far is the shear map's balloon target (Group 1 idea 1, rating 8). The other three of the top four are: calibrate `observe` (7), shape scores per stage (7), learned monotone update (7). Each idea below was attacked several times; the attack rounds are kept so the reasoning can be checked. Nothing here has been run. Ratings are judgement.

Ranking: C1 (8), C2 (8 if its premise check passes, else 6), C3 (7), C4 (7), C5 (7), C6 (6). C2 and C3 are the two structural ones (they change the main network or how it is trained).

**C1. Wave-law shear target: missing shear grows with stability, one constant. Rating 8.**
- What: number 1 multiplies ERA5 shear by a ratio fitted at two balloon sites. C1 replaces the ratio with a physical law. Fine-scale shear in the free atmosphere comes mostly from gravity waves, and their strength follows a known rule: shear variance per scale is proportional to N squared (N is the stability of the air, which we already have from the temperature profile). So: target shear = sqrt(ERA5 shear squared + c x N squared), with one constant c. The shear map stays as it is; only its target changes, exactly as in number 1.
- Why it could beat number 1: (a) one number instead of two, and no cap needed at 12-18 km: the stratosphere is about twice as stable, so the law predicts a larger gap there by itself, which is what we measured (2.6x against 1.7x). (b) It moves to any site, season and hour, because N comes from ERA5 everywhere. Number 1's ratio is only known at El Paso and Midland. (c) It ties shear to stability, which is what the Richardson-number shape score checks. (d) Published work agrees on both halves: ECMWF model shear is 2.5-3x too small against high-resolution balloons (Houchi et al. 2010), and the wave spectrum follows N squared (Smith, Fritts, VanZandt 1987). My own rough arithmetic with the textbook constant gives about 1.9x in the troposphere; the constant is not verified, so treat this as encouraging only.
- Attack round 1: the measured ratio is 1.7 at every quantile. An added variance would lift small shears more than large ones. So a pure add-on may be the wrong shape. Patch: let the data choose between three forms on held-out balloons: ratio only, add-on only, both (2 numbers at most).
- Attack round 2: the wave law holds best in the stratosphere; the troposphere also has convection and fronts. And 0-1 km is boundary layer, not waves. Patch: use the law only as the form of the fit, above 1 km. Leave 0-1 km alone (trap 5).
- Attack round 3: balloons carry noise, so c fitted on balloons is too big. Patch: C5 gives a lower bound; ship the lower value. Opt-in switch, because the ERA5-based shear score gets worse by design (trap 1).
- Cost and test: CPU, 1-2 days, data on disk (`il103_balloon_shear.py` already pairs balloons and ERA5). Step 1, one afternoon: sort the pairs into three classes of N squared; does (balloon shear squared minus ERA5 shear squared) rise in a straight line with N squared? Step 2: fit c at El Paso 2005-2022; predict Midland, Denver and the 12-18 km band without refitting.
- Kill rule: if step 1 shows no rise with N squared, drop C1 and keep number 1's plain ratio. If step 2 misses Denver or 12-18 km by more than the plain ratio does, same.
- Paper angle: "A one-constant closure for the vertical shear that reanalysis leaves out."

**C2. Train the network through the shuffle. Structural. Rating 8 if the premise check passes, else 6.**
- What: today the network is trained on its own samples, then the shuffle throws away the network's joint structure and uses real rank orders instead. The shuffle then adds too much shear (4.7x) and too many unstable layers, and two more maps (shear, lapse) repair that. C2 fine-tunes the network with the shuffle inside the training loop: draw 16 samples, sort each column, re-order by the ranks of 16 real profiles from the same group, and compute the step loss on that shuffled result. Sorting passes gradients to the values, and the rank order is fixed by real data, so no special "soft sorting" is needed. The network then learns per-height distributions that give the right shear and lapse after the shuffle, which is the thing we ship.
- Why it could beat number 1: it fixes at the root what the shear and lapse maps patch afterwards, and the whole-profile band (0.903 where 0.99 is asked) depends on the same thing. All ten failed network changes trained a joint structure that the shuffle discards; this one trains what survives. I found no published work that trains through a Schaake shuffle (differentiable sorting exists; nobody has joined the two).
- Attack round 1: the network can only move per-height distributions, and the CRPS term pins those. If the excess shear comes from the shuffle itself (rank noise with few members, pooled 2-degree templates), training cannot remove it. Patch: a free premise check first. Shuffle the true climatology with the templates (the IL-169 log already has this row for co-extremes) and measure shear excess and unstable-layer share. If true distributions plus template ranks already give the excess, the fault is in the shuffle. Then do the fallback instead: read each template's rank against its whole group (thousands of profiles, a smooth number) and not among the 16-200 templates drawn. That is a CPU change of a few lines.
- Attack round 2: range calibration sits between network and shuffle and is fitted afterwards; it creates surface jumps (L14b). Patch: put the frozen range map inside the loop as a fixed layer, fine-tune, refit all maps in order (trap 2), repeat once.
- Attack round 3: "loss variants failed" and seed noise is 0.0006. Patch: headline CRPS is expected to stay flat (the shuffle never changes per-height distributions). Judge on shape scores before the shear and lapse maps, with paired seeds.
- Attack round 4: template leak. Patch: templates from training years only, never the row's own day or the three days around it.
- Cost and test: premise check, CPU, 2 hours. Fine-tune: one short GPU run (the C4b run already used 16 samples).
- Kill rule: after fine-tuning, measured before the shear and lapse maps: unstable-layer share must fall from 0.32 to under 0.26 and the shear excess must at least halve, with CRPS inside seed noise. Otherwise stop.
- Paper angle: "Learning distributions that survive the shuffle: end-to-end training through rank re-ordering."

**C3. Day-coded generator: one learned code per real day. Structural. Rating 7.**
- What: the network is input-limited (P-18): in climate mode it knows place, month, hour and slow drivers, never which kind of day it is. C3 gives every training day its own 32-number code, learned together with the network (an "auto-decoder": no encoder, the codes are free numbers). The code enters through the same FiLM path the noise uses now. One code is shared by all points, hours and heights of that day, so it has to hold the weather pattern of the day. To generate, draw codes from the bank of real days of that season; the remaining noise fills in the rest.
- Why it could beat number 1: it is the first network change that adds information, not capacity. Three gains. (a) Members become coherent across hours and across the box, because one code is one real day. That gives the time-coherent launch window that Group 3 idea 2 wanted, with no second network. (b) `observe` can weight day codes by how well each fits the last hours of surface and radar readings, then run today's update on what is left. Real days carry the day's evolution, and that is the thing linear persistence has and we lack (1.035 against our 1.156). (c) Structure that today comes only from the shuffle would partly come from the network.
- Attack round 1: 32 numbers cannot hold a whole day over the box. Patch: they need not. Whatever share they explain is new; the noise path and the stack keep doing the rest. Measure the share first (see test).
- Attack round 2: in climate mode no code is known, so headline CRPS will not move. Correct. The gain must show in `observe`, in time coherence and in raw structure, or the idea is dead. Stated up front.
- Attack round 3: free codes memorise. Patch: small code, norm limit, test years have no codes at all, and codes are never blended (blending two rank sources broke coherence in IL-161; same risk).
- Attack round 4: weights over about 1000 candidate days collapse onto one or two. Patch: one tempering number, and a floor of 30 effective days; below it, fall back to today's engine.
- Attack round 5: is this just an analog method? Partly, and analog ensembles are a proven method (Delle Monache et al.). The difference: the bank is 32 numbers per day, the network turns a code into a profile at any point and hour, and the tool stays numpy-only. I found no auto-decoder of this kind on reanalysis data.
- Cost and test: one GPU training run plus CPU scoring. Stage 1: on held-out days, fit the code with the network frozen and see how much skill the "right" code gives. Stage 2: `observe` by code on the W6 station cases and the 120 radar days, against today's engine and linear persistence.
- Kill rule: stage 1 under 40 % skill against climatology with the fitted code: stop. Stage 2: must beat today's `observe` beyond seed noise with coverage at least 0.85.
- Paper angle: "Day codes: giving an input-limited weather generator a memory of real days."

**C4. Fit the observation error without truth, including error links between radar levels. Rating 7.**
- What: radar at 4 levels gave +32 %; all levels to 5 km over-tightened (coverage 0.49). In data assimilation this is the classic sign of treating linked errors as independent: neighbouring radar levels share the same retrieval error. The fix there is the innovation method (Desroziers et al. 2005): the spread of (reading minus prior), compared with the prior's own spread, gives the reading's error and how errors at two levels move together. No balloon is needed, so every radar volume counts, not only the 120 balloon days. Fit three numbers: error size, vertical link length, fade per hour.
- Why it could beat number 1: launch-day readings are our largest proven gain, and this unlocks the radar levels we now throw away. It is also the sound way to get the "one or two numbers" of Group 1 idea 6 aloft, where truth is scarce. Weather centres use exactly this for Doppler radar winds (Waller et al. 2016, 2019).
- Attack round 1: the method assumes the prior's spread is right; if not, the reading gets blamed. Patch: accept it. What we need is the effective error that makes the update calibrated, and the monotone update (top four) asks for that same number.
- Attack round 2: a full error table between 20 levels is many free numbers on linked days (traps 4 and 7). Patch: 3 numbers only, pooled over sites, confidence by whole-day blocks.
- Attack round 3: G1 localisation failed. Different thing: that cut the prior's long-range links, which carry real information. This leaves the prior alone and fixes the reading's error.
- Attack round 4: the cached radar files are El Paso at balloon times. Patch: 1356 radar files are on disk (El Paso 611, Denver 485, Holloman 127, Midland 133; counted 2026-11-10), against 120 used. More hours need a small public download; ask first.
- Cost and test: CPU, 1-2 days. Fit on radar without balloons; then the 120 balloon days are used only to accept or reject.
- Kill rule: with the fitted numbers, all levels must beat 4 levels at 2.5-5 km with coverage at least 0.85. If not, keep 4 levels and log it.
- Paper angle: "Truth-free tuning of observation error for conditioning a generated ensemble on radar winds."

**C5. Three-way referee: how much of the balloon shear is real? Rating 7.**
- What: number 1 and C1 both assume balloons are the truth for shear. Trap 1 says ERA5 is not; IL-114 says balloons and ERA5 are not independent. Use a third system. With three systems whose errors are independent, the error of each can be worked out without calling any of them truth (triple collocation, standard for satellite winds). Our three at El Paso, 0.5-5 km, 00Z: balloon, radar wind profile, and the 24-hour HRES forecast (it was made before that balloon flew, so it cannot have absorbed its noise). All on disk.
- Why it matters as much as number 1: the model is already 1.4x ERA5 and balloons are 1.7x. If a fifth of balloon shear is noise or one-point detail, the model is already right and number 1 would add false shear. This decides the direction of our top idea for one or two days of CPU.
- Attack round 1: radar and balloon both see small scales the forecast lacks, so their "errors" are linked. Patch: that link is the result. The part of the missing shear that balloon and radar share is confirmed real: a lower bound. The balloon ratio is the upper bound. Ship the lower bound.
- Attack round 2: radar averages over tens of km; a balloon is one point. The method cannot split balloon noise from real one-point detail. Stated limit; the lower bound stays valid.
- Attack round 3: radar only reports when the air has scatterers (mostly daytime boundary layer and moist layers), so the sample is not all weather. Report by height and season, and say what share of days is covered.
- Cost and test: CPU, 1-2 days. Output: one table (error of each system, by height band) and a lower / upper bound for the real shear ratio. Report-only; changes no model.
- Kill rule: if bounds come out wider than 1.4-1.7, it decides nothing; log and move on.
- Paper angle: "Who referees a generator trained on reanalysis? Bounding real shear with three systems."

**C6. Run-to-run disagreement as the spread signal in forecast mode. Rating 6.**
- What: mode F is our largest skill (0.69 at one day) and its spread is miscalibrated (IL-87). It sees one forecast run. The 00Z + 12Z refetch (F-V2) gives two or three runs for the same hour. Their disagreement, by height band, is a free sign of an uncertain day. First as statistics beside the network: member spread times a factor that depends on the disagreement (2 numbers). Only if that works, as an extra network input.
- Why here: it adds information to an input-limited model, the pattern behind every network-side win. Lagged runs are the standard cheap ensemble for single-run AI weather models.
- Attack round 1: published results on "jumpiness" as a skill sign are weak for ensemble means. Patch: premise check on disk before anything: link between run disagreement and the newest run's actual error, by height band.
- Attack round 2: live upper-air "previous runs" are not served by Open-Meteo (HTTP 400). Patch: the tool's own logger keeps yesterday's run.
- Attack round 3: where a live ensemble is fetched, its spread is the better signal. So this is for single-run sources; that keeps the tool flexible.
- Cost and test: CPU, 1 day after F-V2. Kill rule: link under 0.3, or no PIT gain beyond the date-block interval (0.06-0.09): drop.
- Paper angle: modest; a short note at most. Included because it is cheap and aimed at our largest skill.

Looked at and discarded while searching (so nobody repeats them):
- Re-weighting real profiles to match the network (entropy pooling, from finance): perfect structure, but needs every real profile at every point shipped with the tool. Loses flexibility.
- A second network that generates rank orders in place of templates: a network is smoother than real ranks, and better templates failed twice (trap 7).
- A "source" input (ERA5 or balloon) on the generator: the stack is fitted to ERA5 afterwards and would undo it.
- Balloon profiles as shuffle templates: three stations, two hours a day, and no independent referee left.
- Building profiles as a patchwork of real profile pieces (from genomics): the joins create false shear.
- Quantile-output network, distilling the stack into the network: simpler tool, no accuracy gain.
- One-minute station variability as a stability signal: overlaps Group 2 idea 3 (gust factor).
- Already done or dropped in the logs: adaptive conformal padding (M10), localisation (G1), variogram / multi-scale loss (L3-13), mode F hours (F-V2).

## Suggested order for the new ideas

1. Group 2 idea 7 (scores per stage): one day. With it, four one-hour kill tests: oracle templates (Group 1 idea 4), IL-128 on the real pool (Group 3 idea 3), range calibration per lead (Group 2 idea 6), trend input (Group 1 idea 7).
2. Group 1 idea 6 (calibrate `observe`, after W6B) and Group 1 idea 1 (shear map target, which is IL-103).
3. Group 1 ideas 5 and 7 (trackers); Group 2 ideas 2 and 4 in their patched form.
4. Group 3 idea 5 (learned monotone update), only after step 2.
5. Anything else only if its kill test passes.

Contenders, added 2026-11-10 (they slot in before step 2, because two of them decide what number 1 should be):
- First, three cheap checks on data on disk: C5 (three-way referee), C1 step 1 (does missing shear rise with stability?), C2 premise check (does the shuffle alone create the shear excess?).
- Then number 1 in the form the checks pick: plain ratio, or C1's law, at C5's lower bound.
- Then C4 (with Group 1 idea 6), then the C2 fine-tune or its fallback.
- C3 is the one large bet: one GPU run, only after C4 shows how far today's `observe` can go. C6 after F-V2.

## Sources checked

- Le Provost et al., ensemble filter for heavy-tailed distributions: https://arxiv.org/pdf/2310.08741
- Schefzik, similarity-based Schaake shuffle: https://ar5iv.labs.arxiv.org/html/1507.02079
- Ravela, Emanuel, McLaughlin, data assimilation by field alignment: https://texmex.mit.edu/pub/emanuel/PAPERS/physD-Final.pdf
- Diffusion super-resolution conditioned on IGRA: https://arxiv.org/abs/2506.22780v2
- Network restoring vertical detail from coarsened soundings: https://www.osti.gov/pages/servlets/purl/2518977
- Gust factor and stability on towers: https://wes.copernicus.org/preprints/wes-2023-35/wes-2023-35.pdf
- ECMWF, stratospheric temperature bias in ERA5 and ERA5.1: https://www.ecmwf.int/node/19362
- GenToka, generative foundation model for tokamak tasks (Nov 2026): https://arxiv.org/abs/2611.08153
- ROMS-IMLE, single-step generative modelling (Jul 2026): https://arxiv.org/abs/2607.19332
- Original IMLE method: https://arxiv.org/pdf/1809.09087
- Diffusion conditioned on mixed in-situ observations (2026): https://arxiv.org/pdf/2609.29027
- Random-masking generation for any subset of channels: https://arxiv.org/html/2507.02902v1
- Houchi et al. 2010, ECMWF shear 2.5-3x smaller than high-resolution balloons: https://cdn.knmi.nl/system/data_center_publications/files/000/068/612/original/2009jd013196pip.pdf
- Saturated gravity-wave spectrum, N squared over m cubed (1987 NASA report): https://ntrs.nasa.gov/api/citations/19870001034/downloads/19870001034.pdf
- Desroziers et al. 2005, error statistics from innovations: https://next.sciencegate.app/document/10.1256/qj.05.108
- Waller, correlated observation errors for Doppler radar winds: https://research.reading.ac.uk/flooding/diagnosing-correlated-observation-error-statistics/
- Triple collocation for wind errors (radar profiler, model, satellite): https://amt.copernicus.org/articles/15/4107/2022/
- Differentiable sorting networks: https://arxiv.org/abs/2105.04019
- Generative methods for multivariate post-processing (ECC, Schaake): https://arxiv.org/pdf/2211.01345
- COBASE, copula-based shuffling (2025): https://arxiv.org/html/2510.25610v1
- Auto-decoder neural fields from sparse observations: https://arxiv.org/html/2401.11611v1
- Analog ensemble (Delle Monache et al.): https://opensky.library.ucar.edu/islandora/object/articles%3A12922
- Named from memory for the contenders, not re-checked: lagged ensembles (Hoffman and Kalnay 1983), jumpiness and skill (Zsoter et al. 2009), generative latent optimisation (Bojanowski et al. 2018), entropy pooling (Meucci 2008).
- Named from memory in the stress test, not re-checked: band-depth rank histogram (Thorarinsdottir, Scheuerer, Heinrich 2016); minimum-spanning-tree rank histogram (Smith and Hansen 2004; Wilks 2004); averaging quantiles vs mixing (Lichtendahl, Grushka-Cockayne, Winkler 2013).
