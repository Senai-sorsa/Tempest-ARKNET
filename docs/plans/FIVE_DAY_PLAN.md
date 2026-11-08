# Five-day plan (2026-11-08 03:30 to 2026-11-13 03:30): everything except the G (global) stages

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
3. Every tick (either loop) calls `CronList`: if no backup cron exists, `CronCreate` it again (same cron and prompt below). Cron jobs expire after 7 days: on the last day (5.5) both are renewed for another 5 days unless the user ends the plan.
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

## 3. The schedule (check off as done; times are targets, order matters more than hours)
Capacity: roughly 100 GPU hours exist in five days and the GPU items below total about 35, so everything fits if nothing breaks. CPU work runs alongside GPU jobs.

### Day 1 (Nov 8 afternoon to Nov 9 03:30)
- [ ] 1.1 **C3 quick test (CPU):** does HRRR 10 m wind beat our tool against ASOS (GW-1 style)? Check feasibility of anonymous point access (`hrrrzarr`, Open-Meteo historical forecast); if no free path, record why and move on.
- [ ] 1.2 **C1 stage 1:** pull small ASOS histories for 8-10 southern NM / west Texas stations (IEM, 2015-2025), leave-one-station-out experiment (naive update vs `obs.py` weights vs data-fitted localisation: distance, elevation, age, stability), refit the weights in `obs.py` behind a flag, tests, verdict.
- [ ] 1.3 **IL-112** shear-vs-IGRA gate from the 986 stations (CPU, stream the files).
- [ ] 1.4 **Section 2 small items in `tempest_weather_v2`:** F8/F10/F11, `_guards.py` (C1-C3), S3 `save_fast`, S4 hash cache, S5 partial block and F2 block seeds in `atmosphere_set`, M1-M3 caps. Tests per module.
- [ ] 1.5 Daily checks #1 (section 4).

### Day 2 (Nov 9)
- [ ] 2.1 **C2 data:** size check, then ARCO ERA5 MODEL-level point extraction for the pilot and Denver points (target under 3 GB), near-surface dataset build (0-300 m, about 10 levels, station-corrected).
- [ ] 2.2 **C2 GPU:** train, calibrate, score 3 seeds against the l21 stack on 10-200 m wind, shear, rail-exit wind; verdict.
- [ ] 2.3 **C4a** past-mode spread x 1.2 as a flag in the tool, tests; **C4b** M = 16 + speed-aware vector energy + 3x weight below 300 m: one GPU run behind a flag, verdict.
- [ ] 2.4 **Section 2 finish:** F4 GPD tail, F5/R2 general observation operator and morning sounding, region-pack manifest, `pyproject`, `ATTRIBUTION.md`, `examples/`, README.
- [ ] 2.5 **Mode F (CPU):** IL-74, 81, 83, 84, 85, 87 (the items that need no user; IL-75 / IL-79 / IFS ensemble unzip need the user's Colab runs and are skipped).
- [ ] 2.6 Daily checks #2.

### Day 3 (Nov 10)
- [ ] 3.1 **C3 build:** HRRR / WTK point extraction (20-30 points, 2018-2025, under 100 MB) if 1.1 is positive; forecast-mode scoring on the apogee of the three validation flights (archived forecasts); distillation prototype (GPU).
- [ ] 3.2 **C5 domain-of-applicability check** in `Launch` (inside / edge / outside, DI from L3-28, blend to climatology outside) + tests.
- [ ] 3.3 **IL-151 physics:** check on `mc.csv` rows, then the penalty experiment (GPU, flag).
- [ ] 3.4 **L3-27 jump head:** IGRA-matched dataset builder, train, score on Denver (GPU).
- [ ] 3.5 **Long range, first part (CPU):** IL-118 Mode M ridge test on `wb2_ifs_extended`, IL-120 skill-by-lead table.
- [ ] 3.6 Daily checks #3.

### Day 4 (Nov 11)
- [ ] 4.1 **Long range, rest (CPU, alongside GPU):** IL-119, 121, 122, 123, 124, 125 (small approved point download), 126; IL-127 last and optional.
- [ ] 4.2 **Validity:** IL-76 retrain with the 2021-22 / 2023 split (GPU), IL-155 / IL-113 confirmation window rescore, IL-114 sondes seen vs unseen, IL-115 trend-aware baseline, IL-116 label filled layers.
- [ ] 4.3 **Tails and gates:** IL-103 to IL-108 (retrain parts on GPU, gate parts on CPU).
- [ ] 4.4 **Launch plan:** A2 launch-day correction (code and test), A1 MERRA-2 fetch script (write and dry-run only; the download waits for the last Wi-Fi slot), A3 wind / shear tails.
- [ ] 4.5 **Older ideas, triaged:** from the remaining shape / loss rows in AUTOPILOT run the six with the best evidence as one GPU queue (3 seeds each); the rest stay sidelined with a reason.
- [ ] 4.6 Daily checks #4.

### Day 5 (Nov 12 to Nov 13 03:30)
- [ ] 5.1 **Stack the winners** of C1-C4 and the fix verifications on NM/TX and Denver, 3 seeds, decide the new base.
- [ ] 5.2 **Test #3, future climate** (trend-aware, IL-122 backtest).
- [ ] 5.3 **Final development report and trust card;** rerun the three-flight true-validation with the new tool (observation weights, finer levels) and update `FlightSIM&Validation with Tempest-ARKNET.md`.
- [ ] 5.4 **Full test suite,** docs sync, commits; resume `fetch_cds` (last Wi-Fi job); G hand-off notes (what the supercomputer needs: bundle list, scripts).
- [ ] 5.5 **Renew both loops** (cron expires after 7 days), write the summary for the user, and propose the next five days.

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
