# AUTOPILOT: the work queue that runs without the user (created 2026-11-05)

Goal: the user can walk away for hours or days. Nothing below needs the user. Every question that comes up is written to `Code-Modifications/ASK_LATER.md`
(one line, with what was assumed) and work continues with the assumption. Never wait for an answer.

## How a session wakes up and continues (read this first after any pause, summary or restart)
1. Read this file; find the first row below with state `todo` or `running`. Check `data/` logs for its result files.
2. If the item is `running`: look at its log; if finished, evaluate it (rule 4) and set it `done`/`discarded`/`blocked`; if the process is dead, relaunch the script (they resume).
3. Launch the next `todo` item. GPU jobs: one at a time. While a GPU job runs, do CPU-side prep for the next one (code, tests, docs).
4. Verdict rule for every item: run `scripts/compare_headline.py` on ERA5 and on balloons against the adopted model (p2f). **Keep** if the phase pass rule holds on both (mean skill15 not lower, no band worse with non-overlapping intervals, mean cov99 error not worse by more than 0.001) AND there is a real gain (mean skill15 up by more than 0.001, or mean cov99 error down by more than 0.0005 without a band getting worse). Otherwise **discard** (flag stays off; code stays; one `salvage` look: which bands gained, can a restricted version be queued once).
5. Log every item as a row in `docs/PLAN.md` (improvement-loop queue table plus a result line), commit locally (small commits, NO Claude attribution, never push, never `data/` or `models/`).
6. Machine rules: 12 CPUs (`source scripts/cap_cpu.sh`), one GPU job, never edit a running script, never run pytest while a scoring job runs, 2026 Jan-Jun is only touched in the final test (E4).
7. NO stop rule on failures (user decision 2026-11-05): a string of discarded items never ends the loop. Keep taking the next item. Group E starts only when the queue AND the idea backlog (below) hold no `todo` item that can run without the user; items waiting on user data stay `blocked-on-data` and are re-checked each tick.
7b. **Idea intake (standing rule):** every time a possible improvement shows up (a limit found while building, a pattern in a result, a bias that a fix leaves open, a new source, a salvageable part of a discarded item), append it at once to the idea backlog below as a new `IL-n` row (hypothesis, why it might work, how to test, state `todo`). Do this when the idea appears, not later. The backlog is part of the queue.
8. Safety net: a recurring wake-up prompt ("Autopilot tick") re-enters this file every ~25 minutes while the session lives. It is session-only; if the session ended, a new session reads this file and continues.

## Queue (state: todo / running / done / discarded / blocked-on-data)
| ID | Group | Item | Command / work | Needs | State |
|---|---|---|---|---|---|
| IL-8 | G | Height-token generator (attention along the 44 heights) | new `tempest/generator/tokens.py` + config key `arch = "tokens"` (default `"mlp"`), `configs/generator_il8.toml`, train with `scripts/phase2_variant.sh VAR=il8 FEAT=base DS=pilot80_dpd`, then verdict vs p2f | GPU 1-2 h | running (started 10:14, log data/phase2_train_il8.log; checkpointing keeps it inside 12 GB) |
| IL-10 | S | Trust layer refit on p2f, bands chosen on 2021-23 gain only, RH>=5 km and u/T aloft at zero | `python -m tempest.calibrate.trust ...` with a band mask option; `score --trust` | GPU 20 min | code done; run by `scripts/ap_s_chain.sh` (waits for IL-8, log data/ap_s.log, verdict text data/ap_s_verdicts.txt) |
| IL-11 | S | Seasonal factors for RH and surface groups only | mask `models/generator_80_p2f.seasonal2021.npz` (scale 1 elsewhere); `score --seasonal` | GPU 15 min | code done; run by `scripts/ap_s_chain.sh` (waits for IL-8, log data/ap_s.log, verdict text data/ap_s_verdicts.txt) |
| IL-12 | S | Shear patches at 5-12 km only | `shear_tail` with `sigma=[0,0,s,0]`, refit s; physics check + `score --shear-tail` | GPU 20 min | code done; run by `scripts/ap_s_chain.sh` (waits for IL-8, log data/ap_s.log, verdict text data/ap_s_verdicts.txt) |
| IL-13 | S | Median bias shift per variable x band fitted on 2021-23 | new `tempest/calibrate/shift.py` + `score --shift`; median error and skill | GPU 20 min | code done; run by `scripts/ap_s_chain.sh` (waits for IL-8, log data/ap_s.log, verdict text data/ap_s_verdicts.txt) |
| IL-9 | G | Mask tokens with random input dropout + arcsinh scaling for shear/gust targets | extend the IL-8 code, or add to the MLP: `input_dropout`, `target_arcsinh` | GPU 1-2 h | todo |
| IL-14 | S | Chronos + ridge average for ONI/WWV | `scripts/chronos_bakeoff.py --blend` (CPU; libs via `CHRONOS_LIB`) | CPU 15 min | todo |
| IL-15 | S | Mode P tendency inputs for wind columns only | `scripts/p4_modeP.py --tendency` with a column mask | GPU 15 min | todo |
| IL-16 | S | Stack check: all kept S-items together vs p2f | `score` with all kept flags | GPU 20 min | todo |
| IL-6 | D | Calibrate modes F/F2 on WeatherBench2 HRES | when `data/raw/wb2_hres/*.nc` exists (the user runs the Colab notebook whenever they like) | data | blocked-on-data |
| 4.6 | D | 21-level retrain of mode P and the generator | when `data/raw/era5_cds` has 420 months (CDS or ARCO .nc): `to_heights`, rebuild dataset, retrain p2f, verdict | data | blocked-on-data |
| IL-17 | L | Analog-driver K tuning (A6), block validation (row 20) | existing scripts | CPU/GPU | todo |
| IL-18 | L | 2C shear codebook / 2B spectral generator probes | only if G items showed that structure matters | GPU | todo |

## Idea backlog (add rows whenever an idea appears; they are queue items)
| ID | Group | Idea and why | Test | State |
|---|---|---|---|---|
| IL-19 | S | IL-13's shift is a 2021-23 average, so it cannot follow a warming trend. Fit the shift per year over a longer window (2015-23, using only years not used to train the shift target) and extrapolate a linear trend in the shift; or let the shift depend on year with a ridge slope | `tempest/calibrate/shift.py --trend`; test 2024-25 vs plain shift | todo |
| IL-20 | S | Shift per calendar month (smoothed 3 months) and per hour bin: the cold bias is probably seasonal/diurnal like the T 5-12 km summer miss | month x band shift, same fit window | todo |
| IL-21 | S | IL-2/IL-11 and IL-13 share one idea (a table over month x band): fit them jointly (shift then width) so the width is measured around the shifted median | joint fit script | todo |
| IL-22 | S | Stack IL-10 (trust), IL-11, IL-12, IL-13 in the best order and re-fit each on the output of the previous one (they were fitted separately) | stack run, then verdict vs p2f | todo |
| IL-23 | G | Pool the members of the token model (IL-8) with the MLP members (p2f) into one ensemble: different architectures make different errors | `Sampler` over a merged members file; score | todo (after IL-8) |
| IL-24 | S | Worst measured cells (stress table): DJF evening t2m skill15 -0.046, T 0-1 km -0.038, JJA evening T 5-12 km cov99 0.955: cell-specific blend toward the 15-year climatology (trust idea) or width fix for exactly these season x hour cells, chosen on 2021-23 | month x hour-bin table for t2m / T low | todo |
| IL-25 | S | Shear patch rate p and size per band were fixed (p = 0.05, 0.01): fit p jointly with sigma on the calibration years (grid over p) instead of picking | `shear_tail --p` grid + physics check | todo |
| IL-26 | D | QBO forecast: ridge beat Chronos and analog, but a phase-aware model (QBO is nearly periodic, ~28 months) should do better still: regression on sin/cos of the QBO phase from the last values | `scripts/index_bakeoff.py` new method | todo |
| IL-27 | D | WWV is in raw m3 (1e13): standardising/log before ridge and analog may change which method wins (the covariance fix in the numpy tool already needed it) | bake-off with standardised WWV | todo |
| IL-28 | S | Balloon-side: IL-11 could not be scored against balloons (no month hook in `sonde`); add the month so seasonal tables can be judged on balloons too | patch `sonde.py` draw() with month | todo |
| IL-29 | G | After IL-8/IL-9: if tokens help the shear tail, try depth/width of the token model (d = 192, 6 layers) and a second pass with the shear-tail loss weight raised | variants of `configs/generator_il8.toml` | todo (after IL-8) |
| IL-30 | D | Mode P with the 21 levels (4.6) and the ARCO fill: retrain residual network and compare MAE vs balloons 2.571 | after 420 months exist | blocked-on-data |

## Usefulness goals (added 2026-11-05 after the assessment: 7/10 as a Monte Carlo source, 9 vs standard atmosphere, 6 vs plain climatology)
The model is accurate to about the climatology level and well calibrated; what makes it valuable is joint structure. These goals raise the usefulness for Monte Carlo
work and beyond, each with a measurable target. They are queue items (group U); same verdict and logging rules; none needs the user (the first one removes the need for the user's simulator).

| ID | Goal | Why it helps | Test / success criterion | State |
|---|---|---|---|---|
| IL-31 | **Downstream test without the user's simulator.** Add a small in-repo rocket ascent model (3 degrees of freedom, drag, weathercocking into the relative wind, parachute descent; generic parameters, not the user's vehicle) in `tempest/downstream/`. Run it on (a) real balloon soundings 2024-25, (b) our coupled samples, (c) independent-variable samples, (d) standard atmosphere + uniform wind, (e) the gauss baseline. | The only honest proof that coupling and tails matter for the thing the user does; replaces the missing landing-scatter test C6 | scatter of apogee, drift and landing distance from (b) matches (a) better than (c)/(d)/(e): compare the distributions with CRPS and tail quantiles (95th/99th drift). Success: (b) has the smallest error in the tails | todo |
| IL-32 | **Downstream scores inside the scorer.** Feed IL-31's outputs (drift at 3 km and 10 km, max shear in the max-Q layer, apogee error, landing distance) into the headline table as extra rows, with the same intervals | Optimises what is used, not only per-column CRPS | rows in `*_headline.csv`; every later experiment is also judged on them | todo (after IL-31) |
| IL-33 | **Conditional sampling: "I know something about today".** Given observations (launch-site surface wind and temperature, a morning sounding, a forecast value at some heights) return samples consistent with them: draw a large pool (5,000), weight by a kernel on the observed quantities (approximate Bayesian computation), resample; optional nudge of the nearby heights. Output includes the effective sample size | The most useful day-of-launch capability: Monte Carlo around what is known, with honest spread | held-out test: condition on surface values of 2024-25 balloons, score the unconditioned heights vs unconditioned samples; success: CRPS improves aloft near the surface (0-3 km) and 99 % coverage holds | todo |
| IL-34 | **Tail-directed sampling with weights.** Option to oversample extreme shear / wind / low-temperature cases (importance sampling) and return weights, so the Monte Carlo reaches 1-in-1000 events with far fewer runs; helper that says how many samples a tail probability needs | Rare dangerous cases are exactly what a Monte Carlo is run for | weighted tail probabilities agree with brute force (1e5 plain samples) within the bootstrap interval; fewer runs by >= 10x for P = 1e-3 | todo |
| IL-35 | **Hourly sequences (launch window).** Coherent atmospheres at T-3 h ... T+6 h: consecutive hours correlated with exp(-dt/tau) fitted on ERA5 hourly pairs (idea from Earth-GRAM CorrMonte) and checked against balloon 00Z/12Z pairs; builds on the soak library | A launch slips by hours; the same atmosphere must evolve realistically, not be redrawn | correlation vs lag matches ERA5 within 0.05; 12-hour wind change distribution matches balloons | todo |
| IL-36 | **Downrange spatial coherence.** Correlated profiles at points displaced 0-60 km from the launch site (horizontal decorrelation length fitted on the ERA5 grid, 377 points), so a drifting vehicle sees a consistent field | A rocket flies 10-30 km downrange; today every point is a separate draw or one shared profile | spatial correlation vs distance matches ERA5 within 0.05 for u, v, T | todo |
| IL-37 | **Derived hazards with checks.** Richardson number and shear layers, icing layers (T and RH), CAPE-style instability, tropopause height, jet height and speed, inversion strength, from each sampled profile, each checked against the same quantity from balloons | Decision-relevant quantities, not just raw columns | distribution of each hazard from samples vs balloons 2024-25 (coverage of the 99 % range, KS distance) | todo |
| IL-38 | **Fix the known shape gaps with numbers.** Targets: 99.9th-percentile shear within 5 % of truth in all bands (now 6-20 % low); T bias within +-0.1 K at 0-12 km (now -0.36..-0.46 K, IL-13/19/20); every season x hour cell of T 5-12 km above 0.975 coverage (now 0.955); whole-profile joint 99 % band coverage above 0.95 for temperature (RH 0.903 now) | The tails and joint behaviour are what the Monte Carlo depends on | measured in `scripts/physics.py`, the stress table and `joint` band tests; the goal is met when all four numbers hold on 2024-25 | todo (runs through IL-8..IL-30) |
| IL-39 | **Export formats and examples.** One call writes samples as CSV, NetCDF and JSON, plus a worked example for each and a numpy-only reader (tool-specific layouts such as OpenRocket or RASAero are sidelined, see below) | Removes friction: any simulator can read it without custom code | round-trip test (write, read, compare) | todo |
| IL-40 | **How many samples do I need?** A helper and a printed statement with every output: Monte Carlo standard error for the mean, a quantile and a tail probability at the chosen N; plus a throughput figure (atmospheres per second) | Prevents misreading Monte Carlo noise as real differences | helper agrees with bootstrap; throughput >= 1,000 atmospheres per second on the laptop CPU (numpy engine) | todo |
| IL-41 | **Plain-language trust card per query.** Each output carries, per variable and height band, the measured 2024-25 coverage and skill of the mode used and a one-line caution (for example "winds above 12 km: calibrated; thermals: physics only, unverified; forecast modes: uncalibrated") | The user always sees what to rely on | present in `atmosphere()` output and the CLI; unit test that every flag exists | todo |
| IL-42 | **Other sites inside CONUS (long term).** Same generator for another launch site (the plan's phase 8): needs the CDS/ARCO levels, new station map and training; first only a feasibility check of data size and the transfer test of the pilot model to a neighbouring box | The tool is useful beyond the pilot box | feasibility note in `docs/PLAN.md`; transfer score of the pilot model on a held-out box | sidelined (feasibility note only, see Sidelined) |

## Diagnostic metrics (added 2026-11-05): 18 new measurements, all computable offline from the scorer's samples and truth (no simulator)
Why: today the headline table (skill15, cov99, MAE) says whether a change helps, not WHERE the system is weak. These metrics locate weaknesses and each one can turn into a backlog idea.
Implementation: `tempest/scoring/metrics_ext.py` (one function per metric, unit-tested on synthetic data) and `scripts/diagnose.py MODEL CALIB DATA` which runs them for ERA5 and balloons 2024-25 (flags such as `--shift`, `--trust` pass through) and writes `<stem>_diag2.csv` plus a ranked "weakest ten" list.
Rule: from IL-44 on, every experiment is also run through `diagnose.py`; the weakest ten metrics of the adopted model become new backlog rows (idea intake rule 7b).

| # | Metric | What it measures | Weakness it can expose | Exists today? |
|---|---|---|---|---|
| M1 | PIT calibration error: area between the PIT histogram and uniform, and its slope (bias) and U-shape (spread) parts, per variable x band x season | whether probabilities are right everywhere, not only at 99 % | spread too narrow in one season; systematic bias vs spread problems told apart | histograms only |
| M2 | Tail-weighted CRPS (weights on the upper and lower 5 % of the climate distribution) and exceedance frequencies at the 0.1, 1, 5, 95, 99, 99.9 % climatological quantiles vs their nominal rates | accuracy of the tails, where Monte Carlo risk lives | tails too light or too heavy at specific quantiles | partly (cov99 only) |
| M3 | Event-conditional coverage: among the 1 % most extreme truth cases (shear, wind speed, low and high T, high RH), the share inside the 99 % band and the mean PIT | the blind spot of unconditional coverage: a model can cover 99 % overall and miss the extreme cases | extremes systematically outside the range | no |
| M4 | Bias and median error (MAE, RMSE) by band x month x launch-hour bin, and the slope of bias against year over 2021-25 | where the cold bias sits and whether it drifts | missing warming trend (IL-19), seasonal or diurnal bias (IL-20) | bias per band only |
| M5 | Spread-skill ratio per band x season x hour (ratio of ensemble spread to median error) | under or over dispersion by regime | narrow summer T 5-12 km | training diagnostic only |
| M6 | Vertical correlation error: Frobenius distance between the sampled and the true correlation matrix of each variable's profile (44 x 44), and of the neighbour-height correlation vs lag | does the profile have the right vertical coherence | too smooth or too jagged profiles | variogram score only |
| M7 | Shear distribution distance: KS and Wasserstein distance of neighbour shear and of 1, 3 and 5 km layer shear per band, plus exceedance frequency of fixed thresholds (10, 15, 20 m/s per km) | the whole shear distribution, not two percentiles | 99.9th gap, wrong mid-range frequency | percentiles only |
| M8 | Cross-variable consistency: thermal-wind closure (vertical wind shear vs horizontal temperature gradient from coupled neighbours), hypsometric closure error, share of supersaturated and super-adiabatic samples, correlation of RH with lapse rate | physical coupling between variables | incoherent atmospheres | supersaturation and lapse shares |
| M9 | Calibration by regime: coverage and skill split by ENSO phase (ONI < -0.5, neutral, > 0.5), QBO phase (westerly, easterly), season and wind regime (monsoon-flow vs westerly); report the largest deviation | whether calibration depends on state | works in neutral, fails in El Nino | no |
| M10 | Hersbach CRPS decomposition per band: reliability, resolution, uncertainty | tells whether the weakness is bad probabilities (reliability) or lack of information (resolution) | focuses effort: reliability can be fixed by calibration, resolution cannot | no |
| M11 | Brier skill scores for decision events vs climatology: shear above 15 and 20 m/s per km, wind above 25 m/s in the 8-12 km layer, RH 2 m above 90 %, T 2 m below 0 C, gust above 20 m/s; with reliability curves | usefulness for go/no-go style questions | good CRPS but poor event probabilities | no |
| M12 | Drift proxy without a simulator: horizontal displacement of a tracer rising at 10 m/s through the sampled wind profile, at 3, 10 and 18 km; distribution (mean, spread, 95/99th) vs the same from truth profiles | the simplest downstream quantity, before IL-31's ascent model | wrong drift scatter although columns look fine | no |
| M13 | Directional scores: circular CRPS and mean angular error of wind direction, and speed CRPS, per band | direction errors that u and v scores hide | direction too random above 12 km | partly in extras |
| M14 | Seed and member stability: repeat the sampler with 20 seeds; spread of the mean, a quantile and a tail frequency across seeds, vs the 4-member and the 8-member model | how much of a result is Monte Carlo noise of the generator itself | noisy tails that make comparisons unreliable | no |
| M15 | Memorisation and novelty: distance of each sample to its nearest training profile vs the distance of truth to its nearest training profile; share of samples (and of truth) outside the training min-max per column | whether samples are copies or genuinely new, and whether the model extrapolates | copying (too small), or inventing impossible profiles (too large) | no |
| M16 | Driver response: skill with known drivers minus skill with unknown drivers (the driver gain), and the response of the median to a +-1 sigma ONI or QBO change against the sign known from climate science | whether the ENSO and QBO inputs do real work | drivers ignored or wrong-signed | known vs unknown skill only |
| M17 | Temporal and spatial coherence (needs IL-35, IL-36): correlation of consecutive hours vs lag, and correlation vs distance across the 377 grid points, sampled vs ERA5 | whether sequences and downrange fields are realistic | decorrelated hours, too-small or too-large spatial scale | no |
| M18 | Monte Carlo efficiency: standard error of a 1 % and a 0.1 % tail probability at N = 200, 1,000, 10,000 draws (bootstrap), and effective sample size under conditioning (IL-33) or weights (IL-34) | how many runs a user needs | wasteful tails | no |

## Queue items for the metrics (group M)
| ID | Work | State |
|---|---|---|
| IL-43 | Write `tempest/scoring/metrics_ext.py` (M1-M16 now, M17 after IL-35/36, M18 after IL-33/34) with unit tests on synthetic data; `scripts/diagnose.py` | todo |
| IL-44 | Run `diagnose.py` on p2f (ERA5 and balloons, 2024-25), publish the table and the weakest ten in `docs/PLAN.md`, add one backlog row per weak metric | todo (after IL-43) |
| IL-45 | Add the diagnostics to the E12 and Earth-GRAM-style (gauss) baselines for the final comparison table | todo (after IL-44) |

## Sidelined (need the flight simulator, its owner, or outside tools; stay out of the queue until the user brings them)
- C3-C6 integration of the readers into `flight_sim` and the one-dimension LHS agreement with the EDITH owner (the readers themselves stay as built and tested).
- IL-39 parts that name OpenRocket or RASAero layouts and reference readers of those programs: only the generic CSV, NetCDF and JSON writers with a numpy reader stay in the queue.
- IL-42 other launch sites (needs new data and training; feasibility note only).
- The user's own landing-scatter test with a real vehicle file (IL-31 replaces it with a generic in-repo ascent model).

## Group E: end of work (runs when the stop rule fires, or the queue has no `todo` left)
| ID | Step | How |
|---|---|---|
| E1 | `pytest` (nothing else running), all green | `.venv/Scripts/python -m pytest -q` |
| E2 | Rescore the final model files on 2024-25 once with the final flag set; compare with the logged numbers (must match within noise) | `score` / `sonde` |
| E3 | Hash checks: model, calibration, trust/seasonal/shift files carry matching `model_sha`; no `data/` or `models/` in git; no 2026 rows in training or calibration | `git ls-files`, loaders, tests |
| E4 | The single 2026 Jan-Jun test: pull the missing 2026 data (surface and w extras via `fetch_earthmover --last 2026-06-30`), score the final system ONCE (`--first-test-year 2026 --last-test-year 2026`), plus the E12 baseline and the gauss (Earth-GRAM-style) baseline with the same code | write `scripts/final_test.sh` first |
| E5 | Final report in `docs/FINAL_REPORT.md`: numbers with intervals, which years, every cell not clearly better, the Earth-GRAM-style table, what is open (ASK_LATER); plain language | |
| E6 | Commit locally; list the open ASK_LATER items for the user | |

## Rules for what to do when a step fails
- A script fails: read its log, fix the cause once, rerun. Second failure: mark the item `blocked`, add a line to ASK_LATER, take the next item.
- Out of memory or process killed: rerun the same script (all stages skip finished outputs).
- Unclear design choice: pick the simplest option, write the assumption in the PLAN row and in ASK_LATER, continue.
