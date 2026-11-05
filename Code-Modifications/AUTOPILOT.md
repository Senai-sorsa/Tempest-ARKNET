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
