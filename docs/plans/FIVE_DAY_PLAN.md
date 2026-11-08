# Work plan (target about five days, 2026-11-08 to 2026-11-13): everything except the G (global) stages, as one ordered list

Owner: Claude, running automatically. The user does not need to step in. This file is the single source of truth for both wake-up loops: every tick reads it, does the next item, ticks the box, and re-arms. G stages (G0, G2-G6, the global store training) run on the user's supercomputer and are NOT in this plan.

## 1. How the system keeps itself running

| Loop | Mechanism | Period | What it does |
|---|---|---|---|
| **Primary** | `ScheduleWakeup(1800)` re-armed at the end of EVERY turn | 30 min | does the next plan item (TICK PROTOCOL below) |
| **Backup** | `CronCreate` recurring, cron `23 */2 * * *` (jobs fire only while the session is idle; the scheduler may shift a job by up to 30 min) | about 2 h | checks the heartbeat; if the primary chain is dead, restarts it; re-creates itself if it is missing; then does the same work |
| **Heartbeat** | `data/loop_heartbeat.json` + `data/loop_ticks.log`, written by `scripts/loop_heartbeat.py` at the START of every tick | every tick | tells the other loop whether this one is alive |

Rules that keep both loops alive:
1. Every turn that does anything ends with `ScheduleWakeup(1800)` (primary). A turn that is interrupted or forgets this is repaired by the backup within about 2 h.
2. The backup tick starts with `python scripts/loop_heartbeat.py --check`: if the newest heartbeat is older than 55 min it prints `PRIMARY_DEAD`; then call `ScheduleWakeup(1800)` first (restart), log it, and carry on with the normal work.
3. Every tick (either loop) calls `CronList`: if no backup cron exists, `CronCreate` it again (same cron and prompt below). Cron jobs expire after 7 days: on the last day (L25) both are renewed for another 5 days unless the user ends the plan.
4. Never let two work threads fight: a tick that finds a heartbeat younger than 20 min from the OTHER loop only does health checks and returns.
5. A GPU job is never started while another python training/scoring/build process runs (one GPU job at a time); pytest never runs while a GPU job runs.

### The two prompts (stored here so they can be re-created exactly)
**Primary (ScheduleWakeup):** `PRIMARY TICK. Follow TICK PROTOCOL in docs/plans/FIVE_DAY_PLAN.md (Tempest-ARKNET). Standing rules: automatic, no user input, safety (12 threads low priority, one GPU job, RAM > 2 GB free, no security or policy changes, kill only exact PIDs this work started; Git Bash taskkill //PID), scope (small diffs, flags off by default, read git diff, stage files by name, never git add -A, never commit flight_sim_trial/ data/ models/), local commits only, no Claude attribution, never touch 2026 or holdout data or the other session's files. End the turn by re-arming ScheduleWakeup(1800) with this same prompt.`
**Backup (cron `23 */2 * * *`):** `BACKUP TICK. Run python scripts/loop_heartbeat.py --check. If it prints PRIMARY_DEAD, call ScheduleWakeup(1800) with the PRIMARY TICK prompt from docs/plans/FIVE_DAY_PLAN.md section 1 FIRST. Call CronList; if no backup cron exists, CronCreate it again (cron 23 */2 * * *, this prompt). Then follow TICK PROTOCOL in docs/plans/FIVE_DAY_PLAN.md exactly as a primary tick would (unless the other loop's heartbeat is younger than 20 min: then health checks only). Same standing rules.`

## 2. TICK PROTOCOL (every 30 min / 2 h)
1. `python scripts/loop_heartbeat.py --kind primary|backup --item <current plan id> --note "<one line>"` (writes the heartbeat first).
2. Health: `date`; GPU (`nvidia-smi`), free RAM, disk, python/bash processes of this project (no orphans, no duplicate queue scripts), forecast loggers alive (`tempest.ops.logger`, `logger_p4`), `git status` (no stray files staged).
3. Read this file. Find the first unchecked item whose prerequisites are done. If a GPU queue is running, work on CPU items instead; if the GPU is idle and the next GPU item is ready, write a NEW detached queue script (`nohup`, RAM wait <= 6 GB, skip-if-output-exists, retry once, exclude its own name from the `queues()` regex, log to `data/l3.log`) and launch it. Never edit a running bash script.
4. Do the work in small steps; test; record verdicts in `docs/logs/LOOP3.md` and `docs/logs/AUTOPILOT.md`; keep `To-do-Concise.md` current; commit by file name.
5. Tick the box here (`[x]`) with a short result, or write why it was skipped (blocked items are skipped, never waited for).
6. Daily checks (section 4) when their time comes.
7. Re-arm `ScheduleWakeup(1800)`; run `CronList`.
If a plan item fails twice: log it in AUTOPILOT, mark `[!]`, move on. If everything is done early: pull the next sidelined idea from AUTOPILOT, or improve tests and docs.

## 3. The work list (one ordered list, not split by days; work through it as fast as possible)
Target horizon: about five days (to 2026-11-13 03:30), but the order is what matters, not the clock. **CPU and GPU items run side by side:** while a GPU job runs, take the next CPU-only item further down the list (marked CPU); when the GPU is idle, launch the next GPU-ready item. Skip blocked items and note why; come back to them on later ticks. GPU items total about 35 hours; about 100 are available.

**Core (highest value first)**
- [x] L1 (CPU) **C3 quick test:** does HRRR 10 m wind beat our tool against ASOS (GW-1 style)? Check anonymous point access (`hrrrzarr`, Open-Meteo historical forecast); if there is no free path, record why and move on. **DONE 2026-11-08:** HRRR (Open-Meteo archive, near-analysis) 10 m wind CRPS 1.04 vs tool climate 1.98, past 1.17 (speed MAE 1.05 / 2.97 / 1.58 m/s); past + HRRR (fitted weight ~1.0, spread x0.8) 0.76 = -35 % vs past. C3 build (L12) justified. Log: data/hrrr_vs_asos.log.
- [x] L2 (CPU) **C1 stage 1, observation assimilation:** small ASOS histories for 8-10 southern NM / west Texas stations (IEM, 2015-2025); leave-one-station-out experiment (naive update vs `obs.py` weights vs data-fitted localisation by distance, elevation, age, stability); refit the weights in `obs.py` behind a flag; tests; verdict. **DONE:** weights fitted on 9 ASOS stations (obs_loso.py) now in obs.py: day 0.62 / night 0.48 within 100 km, falling to 0.32 / 0.18 beyond 350 km; own-station persistence 0.85 at 1 h; age factor flat 3 h; tests pass.
- [x] L3 (CPU) **IL-112:** shear-vs-IGRA gate from the 986 stations (stream the files). **DONE 2026-11-08:** `scripts/igra_shear_gate.py` (odd vs even years, 2000-25, 863 / 848 stations): sampling scatter alone puts 5 % of stations beyond ±16 % (0-1 km) and ±12 % (1-5 km); 90 % beyond ±12 % / ±7.5 %. A per-station ±12 % gate at 0-1 km is not reachable; pooled medians are 1.008 / 1.004. Gate rule: per-station ±15 % (0-1 km), ±12 % (1-5 km) at the 95th percentile, plus pooled median ±5 %. Log data/igra_shear_gate.log.
- [ ] L4 (CPU) **Section 2 small items in `tempest_weather_v2`:** F8 / F10 / F11, `_guards.py` (C1-C3), S3 `save_fast`, S4 hash cache, S5 partial block and F2 block seeds in `atmosphere_set`, M1-M3 caps, T1-T2 `Launches`. Tests per module. **PARTIAL 2026-11-08:** already present: S3 (pool and engine cached on the Launch, uncompressed savez), float32 pools, Sobol sampling, 10 m tables. Added: F8 `k="auto"` in `Coupled`, T1/T2 `Launches` (loop, own pools). Still open: F10 pad-elevation shift, F11 Sobol strata check, `_guards.py`, S4 hash cache, S5, F2 block seeds, M2/M3 LRU caps.
- [!] L5 (CPU / IO) **C2 data:** size check, then ARCO ERA5 MODEL-level point extraction for the pilot and Denver points (target under 3 GB) and the near-surface dataset build (0-300 m, about 10 levels, station-corrected). **BLOCKED 2026-11-08 (size check):** ARCO model-level zarr is chunked as whole-globe fields per time step, so point extraction means downloading the globe (hundreds of GB per month); gcsfs not installed; no `.cdsapirc`. Only route is CDS/MARS model-level requests for ~20 station points (about 1-3 GB but a multi-day queue), left to L24 with fetch_cds. Meanwhile C3 (HRRR near-surface as teacher, L12) is the better near-surface lever.
- [ ] L6 (GPU) **C2 train, calibrate, score** 3 seeds against the l21 stack on 10-200 m wind, shear and rail-exit wind; verdict.
- [x] L7 (CPU) **C4a:** past-mode spread x 1.2 as a flag in the tool; tests. **DONE:** `Launch(past_wind_spread=1.2)` widens the past-mode u, v spread about the median at the ground, tapering to 1 at 300 m (flag "past-wind-spread-widened"); default 1.0 = off; tests pass (89).
- [x] L8 (GPU) **C4b:** M = 16 samples + speed-aware vector energy score + 3x weight below 300 m, one run behind a flag; verdict. **RUNNING 2026-11-08 05:50:** flags `low_weight`, `wind_vec_weight` (off, golden test passes) in train.py; `configs/generator_c4b.toml`; queue `scripts/ap_l3_c4b.sh` (train, calibrate, score day+night vs l3_h_l21 with extras; verdict in data/l3_verdicts.txt). No pytest while it runs. **VERDICT 2026-11-08 08:42 (single seed, 21-level truth, day | night):** mean skill15 +0.0281 -> +0.0283 | +0.0292 -> +0.0298, rules a-d PASS. 0-1 km wind improves: u +0.0082 | +0.0069, v +0.0006 | +0.0047; speed MAE 0-1 km 3.63 -> 3.58 (-1.3 %) | 3.98 -> 3.93 (-1.2 %); but 0-1 km T -0.002 / -0.003 and RH -0.007 / -0.006 (rh2m -0.006 day). Small, mixed: flags stay OFF by default; candidate for the L21 stack only with a humidity guard. Three-seed pairing not run.
- [ ] L9 (CPU) **Section 2 finish:** F4 GPD tail, F5 / R2 general observation operator and morning sounding, region-pack manifest, `pyproject`, `ATTRIBUTION.md`, `examples/`, README.
- [ ] L10 (CPU) **C5 domain-of-applicability check** in `Launch` (inside / edge / outside, DI from L3-28, blend to climatology outside); tests.
- [ ] L11 (CPU then GPU) **IL-151 physics:** check on `mc.csv` rows, then the penalty experiment behind a flag. **PARTIAL 2026-11-08:** built `tempest_weather_v2/hrrr.py` + `Launch.observe_hrrr()` (ground wind below 300 m: median moved to HRRR 10 m wind, spread x0.8, fitted weights; Open-Meteo archive or live run; tests pass, 91). Still open: HRRR/WTK table for 20-30 points, apogee scoring of the three flights with archived forecasts, forecast-lead skill (only near-analysis measured), distillation prototype.
- [ ] L12 (CPU then GPU) **C3 build** (if L1 is positive): HRRR / WTK point extraction (20-30 points, 2018-2025, under 100 MB); forecast-mode scoring on the apogee of the three validation flights with archived forecasts; distillation prototype.
- [ ] L13 (GPU) **L3-27 jump head:** IGRA-matched dataset builder, train, score on Denver.

**Backlog that was asked for (all non-G, in this order)**
- [ ] L14 (CPU) **Mode F items that need no user:** IL-74, 81, 83, 84, 85, 87 (IL-75, IL-79 and the IFS ensemble unzip need the user's Colab runs: skipped).
- [ ] L15 (CPU) **Long range, first part:** IL-118 Mode M ridge test on `wb2_ifs_extended`, IL-120 skill-by-lead table.
- [ ] L16 (CPU) **Long range, rest:** IL-119, 121, 122, 123, 124, 125 (small approved point download), 126; IL-127 last and optional.
- [ ] L17 (GPU / CPU) **Validity:** IL-76 retrain with the 2021-22 / 2023 split, IL-155 / IL-113 confirmation-window rescore, IL-114 sondes seen vs unseen, IL-115 trend-aware baseline, IL-116 label filled layers.
- [ ] L18 (GPU / CPU) **Tails and gates:** IL-103 to IL-108 (retrain parts on GPU, gate parts on CPU).
- [ ] L19 (CPU) **Launch plan:** A2 launch-day correction (code and test), A1 MERRA-2 fetch script (write and dry-run only; the download waits for the last Wi-Fi slot), A3 wind / shear tails.
- [ ] L20 (GPU) **Older ideas, triaged:** from the remaining shape / loss rows in AUTOPILOT run the six with the best evidence as one queue (3 seeds each); the rest stay sidelined with a reason.

**Closing (when the items above are done or exhausted)**
- [ ] L21 (GPU) **Stack the winners** of C1-C4 and the fix verifications on NM/TX and Denver, 3 seeds, decide the new base.
- [ ] L22 (CPU) **Test #3, future climate** (trend-aware, IL-122 backtest).
- [ ] L23 (CPU) **Final development report and trust card;** rerun the three-flight true validation with the new tool (observation weights, finer levels) and update `FlightSIM&Validation with Tempest-ARKNET.md`.
- [ ] L24 (CPU) **Full test suite,** docs sync, commits; resume `fetch_cds` (the last Wi-Fi job); G hand-off notes (what the supercomputer needs: bundle list, scripts).
- [ ] L25 **Renew both loops** (the cron expires after 7 days), write the summary for the user, and propose the next list.
If the list is exhausted early, take the next sidelined idea from AUTOPILOT, or strengthen tests and docs. The daily checks (section 4) run in quiet gaps regardless of where the list stands.

## 4. Daily checks (once per calendar day, in a quiet gap; each appends one dated block to `FlightSIM&Validation with Tempest-ARKNET.md` section "Daily log")
1. **Health:** disk, RAM, GPU, temperatures, processes, loggers, `git status`, last test run.
2. **Tests:** full suite once per day when no GPU job runs (tool + `tempest_weather_v2`).
3. **Flight-sim validation:** rerun the three Spaceport America flights (Prometheus, Juno III, Heart of Steel) through the current tool (climate, past, past + observation) with 60 atmospheres each: apogee error table and the trend since yesterday. Never fit to these; they are a regression check.
4. **Ground-wind benchmark smoke** (`scripts/ground_wind_bench.py --n-fit 120 --n-test 120`): CRPS and coverage trend of the climate, past and persistence variants.
5. **Doc sync:** `To-do-Concise.md`, `AUTOPILOT.md`, `LOOP3.md`, this file's boxes.

## 5. What can stop the plan, and the automatic response
- Application-control or other security block on python: record it in To-do and wait for the user (never bypass); other items continue where possible.
- Low RAM / overheating: pause GPU items, keep CPU items, retry next tick.
- A stuck queue script: write a replacement script, kill only the exact PID if allowed, otherwise route around.
- Anything needing the user (Colab runs, unzips, downloads over the data cap): skip it, note it, keep going.
