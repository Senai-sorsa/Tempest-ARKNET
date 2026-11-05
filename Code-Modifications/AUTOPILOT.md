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
7. Stop rule for the improvement loop: three consecutive finished items (kept or discarded) with no kept gain, counted over groups S and G below -> go to group E.
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
