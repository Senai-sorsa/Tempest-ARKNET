# New_Plan: everything before global mode, in about 2 days

Written 2026-11-10. Sources merged: `Innovative idea review.md` (run list C1-C6, G1-G3 ideas),
`Limitations to solve.md` (audit defects A1-A9, "what to do first" table), and the open list in
`docs/HANDOVER_2026-11-10b.md` section 14.4 plus the unticked boxes of `docs/plans/FIVE_DAY_PLAN.md`.
The global track (G0-G6, supercomputer) is not in this plan.

**STOP FIRST (user, 2026-11-12 evening): section 15 comes before everything else in this file.** A code audit found
that the climatology baseline is scored unfairly (a no-skill model shows about +1.2 % "skill" against the recent-15-year
pool), two forecast-mode height bugs, too-narrow bootstrap intervals and eleven smaller defects. No new trial
(training, verdict score, export) starts until 15.1 to 15.4 are done; running jobs may finish but their verdicts are
not read before AU-1. Sections 10 to 14 wait.

**Status 2026-11-11:** the code for this plan is in `new_plan_kit/` (runbook: `new_plan_kit/README.md`; read it first).
Most of block 1 and the CPU fits of block 2 have been run; the results and what they changed are in section 9.
Where this file names a `scripts/...` file or a switch that section 9 says does not exist, the kit script named there is the real one.

**Permission (user, 2026-11-10): the user has already given permission for everything in this plan.**
That covers all downloads (MERRA-2 included), adopting results that pass their rule, the default
changes this plan proposes, and the exports needed to ship a passed item. Do not stop to ask; do it,
log it in `docs/logs/AUTOPILOT.md`, and list it in the final verdict table. A change still has to
pass its own rule first (section 5), and every adoption is checked on the shipped tool
(`scripts/tool_audit.py`, `scripts/shipped_check.py`) with a backup of the old assets kept.
Not covered, because they are not part of this plan: the final test on 2026 data (waits for
"the model is final"), pushes, deleting data, and security or registry changes.

---

## 1. What "done in 2 days" means

The idea review's own estimate for its full list is 4-5 weeks. Two days is possible only like this:

- Every item gets its **first verdict** (go / kill / needs more) in 48 h, not a finished build.
- Every item has a **kill rule written before it starts**. A killed item frees its lane at once.
- A GPU winner gets one confirming second seed inside the 48 h. A winner confirmed on two seeds is
  adopted (permission is given); a third seed runs after the 2 days as a late check.
- Builds that only make sense after another item passes are listed in section 7 with their trigger.

---

## 2. Machine limits (hard rules for every lane)

Machine: Ryzen AI 9 465 (20 threads), 31 GB RAM, RTX 5070 Laptop 12 GB, C: 82 GB free (92 % full).

| Resource | Rule |
|---|---|
| GPU | **One GPU job at a time.** One sequential runner (`scripts/gpu_direct_*.sh`), chained by log lines in `data/l3.log`. Never two waiting queues. |
| CPU | **12 threads in total**, BelowNormal priority (`source scripts/cap_cpu.sh`). Three CPU lanes of **3 threads each** (`OMP_NUM_THREADS=3`) + 3 threads left for GPU data loading, downloads and the two loggers. |
| RAM | Keep > 2 GB free always; start a job only with >= 6-8 GB free. A GPU **score** holds 11-14 GB: during a score the CPU lanes run **light jobs only** (no pool building, no ERA5 store read, no IGRA full read of 4 GB). During GPU **training** all three CPU lanes may run. |
| Disk | Stop new writes below 10 GB free. Download budget 50 GB (about 5 GB used); this plan needs about 15-20 GB. Each download in its own new folder, logged in `data/download_ledger.txt`. |
| Heat | If hot: lower threads of the next job. Never pause or stop a running job for heat. |
| Kills | Only in real danger (out of memory, disk full, two writers on one file, thermal danger), only a process this plan started, by exact PID. |
| Tests | `pytest tests tempest_weather_v2/tests` only while the GPU is idle (4-7 min). Once at the start, once at the end, and after any code change in a GPU gap. |
| Never | 2026 data, `scripts/final_test_2026h2.sh`, pushes, deletes, security or registry changes, edits to a running bash script, the two forecast loggers. Exports and default changes: only for an item that passed its rule, with the old assets backed up first. |

Launch form for every long job: its own detached runner (`nohup bash scripts/X.sh > /dev/null 2>&1 &`),
exact command line in the runner header, `&&` chains before every "done" log line.

---

## 3. Lanes

| Lane | Threads | Used for |
|---|---|---|
| GPU | 1 job (+2 loader threads) | training, scoring, pool building |
| CPU-A | 3 | shape and shear work (reads pools and balloons) |
| CPU-B | 3 | observe / radar / persistence work |
| CPU-C | 3 | blends, trackers, long range, small fixes |
| NET | about 1 | one download at a time, started in hour 0, runs unattended |

Two items must not be judged on the same scores at the same time: **C2 (shuffle fine-tune)** and the
**shear target map**. C2 gets its verdict first; the shear and lapse maps are refitted after it.

---

## 4. Duplicates merged (one run answers several list entries)

| One run | Covers |
|---|---|
| C4 radar error fit (`new_plan_kit/b2_c4_innovation_fit.py`) | idea review C4, limitations A4 and 5.2.17 idea 2 |
| Observe from neighbour stations (`new_plan_kit/b1_observe_loso.py`) + observe numbers (`new_plan_kit/b2_g16_observe_fit.py`) | limitations A1 (already measured by `scripts/w6_observe_eval.py`), A3; idea review G1-6 (there is no `SIGMA_SCALE`; the kit changes the two numbers in memory) |
| Shear target map (`new_plan_kit/b2_shear_target_fit.py`) | idea review shear target, limitations row 9, L18 IL-103, L19 A3, IL-194 (fit on pre-2023 balloons, check on ASOS one-minute) |
| IL-128 on the real pool | idea review G3-3 check, limitations row 9 copula check, old CPU queue |
| Drift tracker (`g17_drift_replay.py`) | idea review G1-7, limitations 5.2.19(a) (T 12-18 km bias) |
| Blend check | idea review G2-6, L14 IL-74 |
| C5 three-way referee | idea review C5, limitations 5.2.15 |
| Shared sample pool, built once on the GPU | input for G2-7, C2 premise, IL-128, G2-1, G2-5, G1-4 |

---

## 5. Schedule (48 h wall clock, runs through both nights)

Times are hours from the start. If a lane finishes early it takes the next item in its column.
If a lane is late, the item marked (cut first) in that block is dropped to section 7.

### Hour 0 - 0.5: preflight (all foreground, short)
1. Read `docs/results/logs/il194_shear_2021_22.log` (IL-194 was started at the last handover).
2. `git status`, disk and RAM check, confirm no GPU job (`nvidia-smi`).
3. Full test suite once (GPU idle). This is the "before" number (last: 385 passed).
4. Write the kill rule of every block-1 item into `docs/logs/AUTOPILOT.md`.
5. NET lane: start downloads, in this order (grep `data/raw` and the logs first, some may exist):
   ERA5 point pull for the five sodar sites, ERA5 1-70 hPa, ERA5 model levels (box), second daily
   forecast run (00Z + 12Z) for C6, list of 1-second balloon stations, then MERRA-2 (write the
   fetch script, dry-run it, then download; permission is given). Stay inside the disk rule.

### Block 1, hour 0.5 - 6: measure first

| Lane | Jobs (in order) | Kill / pass rule |
|---|---|---|
| GPU | (1) Build **one shared sample pool per stage** (raw, range-calibrated, shuffled, shear map, lapse map; test 2024-25; m 199), about 1 h. (2) Then train the **seed-1 base** of the shipped stack: every later GPU verdict needs a base retrained with the same seed. | pool: none. base: none (it is the yardstick). |
| CPU-A | C5 three-way referee (no pool needed) -> when the pool exists: **G2-7 shape scores per stage** (do first of all pool jobs) -> G2-1 spectrum check, G2-5 double-jet count (1 h each) | C5: kill if the error bounds are wider than 1.4-1.7. |
| CPU-B | **A1 observe vs persistence** with A3 leave-one-station-out (20-150 km) in the same script | none: this is a measurement. It decides the block-3 fix. |
| CPU-C | C1 step 1 wave-law check (balloons only) -> **C2 premise check** (needs the pool, 2 h) -> IL-128 on the real pool, G1-7 trend-input check, G1-4 oracle templates (1 h each) | C2 premise: decides GPU fine-tune or CPU group-rank shuffle. IL-128: if inflation > 1.2x, G3-3 becomes a candidate (section 7). |

### Block 2, hour 6 - 14: the three main fits

| Lane | Jobs | Kill / pass rule |
|---|---|---|
| GPU | ~~C2 fine-tune through the shuffle~~ **SKIPPED (section 9): the premise check says the shuffle, not the network, makes the excess, and the CPU fallback was killed.** GPU goes on with the seed-1 base, then C3 stage 1. | - |
| CPU-A | **Shear target map** fit (`new_plan_kit/b2_shear_target_fit.py`, forms `ratio` and `c1`; tables go to `data/kit/`, opt-in). C2 is closed, so its verdict no longer waits. | adopt-candidate only if tails move toward balloons and CRPS does not get worse (IL-103 already showed aloft yes, 0-1 km no). |
| CPU-B | **C4 radar error fit** (covers A4) | pass if all levels beat the 4-level set at 2.5-5 km and coverage >= 0.85. |
| CPU-C | **Safe Gaussian-marginal blend** (`scripts/gauss_blend_fit.py`, wind cells + T 12-18 km) | kill if any wind cell is worse than baseline by more than 0.0009. |

During each GPU score (about 5-10 min, 11-14 GB RAM) the CPU runners wait at their next step
boundary if free RAM is under 6 GB. They do not get killed, they wait.

### Block 3, hour 14 - 24 (overnight 1): long unattended jobs

| Lane | Jobs | Kill / pass rule |
|---|---|---|
| GPU | **C3 day-coded generator, stage 1** (cfg `day_code`, to be written: `new_plan_kit/README.md` part 5.2) | C3 stage 1: kill below 40 % skill. |
| CPU-A | G2-4 two-scale persistence (needs a radar download first, README part 5.1) | G2-4: must beat plain persistence by more than 0.0009. |
| CPU-B | **A3-fix: wider error for neighbour-station reports** (README part 5.1; A3 showed coverage 0.67-0.82) -> **A2 past-mode spread x1.2** test with the ERA5 anchor at TCS / MAF / USCRN | A3-fix: coverage 0.85-0.95 for every neighbour, CRPS not worse. A2: change the default to 1.2 only if coverage improves at all three sites without a CRPS loss above 0.0009. |
| CPU-C | G1-5 spread tracker + G1-7 drift tracker backtests (`bias_backtest.py`, `g17_drift_replay.py`; covers the T 12-18 km bias) -> L16 long range IL-119, 121, 123, 124, 126 (cut first) | trackers: keep only if better than no tracker by more than 0.0009 on 2024-25. |

### Block 4, hour 24 - 32: things that needed block 2-3 results or downloads

| Lane | Jobs | Kill / pass rule |
|---|---|---|
| GPU | C3 stage 1 score and verdict -> if passed: **C3 stage 2** (through observe). If C3 was killed: second-seed confirmation of any other GPU winner, else GPU stays idle on purpose. | compare with `scripts/compare_headline.py`, paired with the seed-1 base. |
| CPU-A | **18-80 km extension** (needs the ERA5 1-70 hPa download) | off by default; check against the levels held out. |
| CPU-B | G1-3 radar + station score (`g13_radar_station_score.py`, uses C4's error size) -> G2-2 Student-t widening + fault gate (`launch.py`, flag `t_update=False`) | G2-2: no loss on clean days, gain on faulty-observation days. |
| CPU-C | **Launch-day row** in the headline table with a fair baseline and persistence -> G2-6 / IL-74 blend check (1 h) -> G1-2 mixed pool (cut first) | none: reporting. |

### Block 5, hour 32 - 42 (overnight 2): referees and small fixes

| Lane | Jobs | Kill / pass rule |
|---|---|---|
| GPU | C3 stage 2 finishes and scores. G3-5 learned update only if C4, the A1 fix and C3 stage 2 all passed and at least 6 h are left; otherwise not started (section 7). | G3-5 is the first item to drop. |
| CPU-A | **Sodar referee 30-200 m** (needs the sodar point download; fix the sodar time zone A8 first) | measurement only. |
| CPU-B | C6 run-to-run disagreement (`c6_lagged_spread.py`, only if the 00Z + 12Z download arrived) -> G2-3 gust factor at Midland (cut first) | C6: spread must track error (correlation clearly above zero) or kill. |
| CPU-C | Small items, each with its test: A5 opt-in `below_10m="loglaw"`, A6 stale docstring (`tempest_weather/flight_sim_readers.py` lines 9, 90), A7 roughness into turbulence, A9 duplicate IL-192 id, labels in saved files, input archive with hash, RH range map widening, IL-129 `_cdf` / `_ppf`, climatology answer outside the boxes + dissimilarity index, L19 A1 MERRA-2 script dry run | each one: tests pass, default output bit-identical. |

### Block 6, hour 42 - 48: close

1. Wait for the GPU to be idle. Full test suite. Must be >= the "before" count, 0 failed.
2. One verdict table (item, numbers, pass / kill / needs more, seed count) in `docs/logs/AUTOPILOT.md`
   and a short section in `docs/FINAL_REPORT.md` (L24 docs sync).
3. Adopt what passed (two seeds for GPU items): back up the assets, export, run `scripts/tool_audit.py`
   and `scripts/shipped_check.py`, and list every adoption and default change in the verdict table.
4. Update `To-do-Concise.md` (delete done items), tick the plan boxes, local commit, files staged by name.

---

## 6. Order of cuts if time runs short

Dropped first to last: G3-5 learned update, G2-3 gust factor, G1-2 mixed pool, L16 long range,
C6, small items of block 5 (except A6 and A9, which take minutes), C3 stage 2.
Never cut: A1 / A3, C2 premise + C2, C4, shear target, G2-7, safe blend, launch-day row, final test suite.

---

## 7. Not in the 2 days (and why)

| Item | Reason / trigger |
|---|---|
| G0-G6, finer low levels, six local packs, global model | supercomputer track ("global mode") |
| ASK_LATER 21 (ensemble features opt-in), IL-197 | waits for the user's answer |
| ASK_LATER 20 (SWiFT / WFIP1 sodars, Jornada login), ASK_LATER 15 (pad wind, GPS logs), V9, P5, L19 A2 | needs data or access only the user can give |
| Final test on 2026 July-October | only when the user says the model is final |
| G3-1 detail network, G2-1 detail between heights | needs 1-second soundings and a passed spectrum check |
| G3-3 select-then-nudge | not triggered: IL-128 on real pools shows no inflation (worst ratio 0.84) |
| G3-2 next-hour generator | only if G3-5 is not built |
| Third-seed confirmations | after the 2 days, as a late check on what was adopted |
| L4 leftovers (F10, F11, `_guards.py`, S4, S5, M2 / M3), L12, IL-196, R1, L25 | small and speculative or low value; not tests |
| Earth-GRAM, limitation 5.2.7 | parked, not available |

---

## 8. Already permitted by the user (do, log, report; do not ask)

1. MERRA-2 download and all other downloads in this plan.
2. A2: past-mode spread default 1.0 -> 1.2, if the test passes its rule.
3. Adoption and export of anything that passes (C2 weights, balloon shear map, safe blend, observe
   fix, trackers), each with an asset backup and a shipped-tool check.

Still waiting on the user (outside this plan): the final 2026 test ("model is final"), pushes, and
the data only the user can get (pad wind, GPS logs, sodar and Jornada access).

---

## 9. Results so far and what they changed (state on 2026-11-11)

Code, run commands and step-by-step instructions for everything not built: `new_plan_kit/README.md`. Logs: `docs/results/logs/kit_*.log`.

| Item | Result | What it changed |
|---|---|---|
| C5 three-way referee | ERA5-to-real shear ratio: lower bound 1.33 [1.14, 1.53], upper 1.63 (80 hours, biased high) | shear target uses 1.33, not 1.7 |
| C1 step 1 wave law | PASS (c per band 0.12 / 0.31 / 0.33 / 0.27) | the `c1` form of the shear target may be tried |
| C2 premise | the shuffle, not the network, makes all the excess; shipped maps already give 0.213 / 0.0066 (truth 0.206 / 0.0031) | GPU fine-tune SKIPPED |
| C2 fallback, group-rank shuffle | KILLED (CRPS +0.0022, limit 0.0006; shear rate not halved) | C2 closed; "refit maps on the C2 output" dropped |
| G1-7 trend | the network already has a `year` input | G1-7 = replay only |
| IL-128 on real pools | no inflation (worst ratio 0.84); the copula sampling loses 16-34 % of p99.9 shear | G3-3 not triggered |
| G1-4 oracle templates | mean gain -4.5 % (worse) | G1-4 and G3-4 closed |
| A3 observe from a neighbour | all 7 neighbours FAIL on coverage (0.67-0.82); CRPS improves for 5 of 7 | block-3 fix = wider error for distant stations (A3-fix), not the same-station law |
| A3-fix v2 (`b3_a3fix_neighbour_rho.py`, 2026-11-11) | cause: the default speed-space step uses rho = 0.72^age with no distance term (a wider sigma cannot reach it). B (rho = the tool's own distance gain) lifts neighbour coverage 0.69-0.76 -> 0.81-0.92, CRPS better at 6 of 7 (FST +0.05, interval crosses 0); FAILS only at LRU, 0.81 vs floor 0.81. C (component only) fails FST CRPS +0.14; D (quantile map) adds nothing | replicate on new hours (`--seed 1`): B fails at ONM (coverage 0.75 vs floor 0.80; LRU passes now), C passes there but failed FST in run 1 -> **no variant passes both runs: shipped default kept**. B beats shipped on coverage (+0.07 to +0.15) in 14 of 14 neighbour runs and on CRPS in 13 of 14; whether to adopt it as a plain improvement is ASK_LATER 23 |
| G2-7 shape scores | full run 1600 cases x 3 seeds (seed spread <= 0.007): Ri<1 shares vs balloons 0-1 km 0.73 / 1-5 km 0.35 / 5-12 km 0.20 / 12-18 km 0.15; '+ shuffle' is closest in 0-12 km (0.675 / 0.307 / 0.196) with the smallest depth-dev (u 0.023, v 0.033, T 0.018); the shear map then moves Ri<1 AWAY from balloons (0.650 / 0.287 / 0.168) and the lapse map recovers only part; all stages too few Ri<1 at 12-18 km (0.06-0.08 vs 0.15) and too many T-rises below 3 km (0.52 vs 0.32) | report only. Shipped stack is better than ERA5 everywhere; the shear+lapse maps cost a little shape (0.01-0.02, below the 0.03 depth-dev noise) -> no change, but the 12-18 km Ri and low-level T-rise excess are new known limitations |
| IL-207 TCS spread diagnosis (`b3_il207_site_spread.py`, 300 h/site) | TCS no-report coverage 0.80: obs above the 95 % in 0.150 vs below the 5 % in 0.047, bias +1.44 m/s (tool too calm), worst MAM (+2.25) / JJA (+1.76) and 16-20 local (+1.79); |err|/spread 1.35. MAF fine (0.92, bias +0.39) | **BIAS, not spread** -> IL-207b per-site factor test running |
| Shear target, form ratio | FAIL: p99 new / balloon 1.22 in 1-5 km (5-12 km 1.03), CRPS +0.01 % | form c1 running (auto-started); if c1 also fails, close the shear target |
| C4 radar error | measured on 945 radar hours: one-level sd 2.37 m/s, 95 % [2.57, 3.55] (hand-set 3.0); L 901 m; no growth with age; engine-equivalent sd 3.02 (4 levels) / 4.16 (10 levels); R negative above 3.5 km (tool spread already wider) | test by `p3_vad_condition.py --sigma 3.0 / 3.02 / 4.16` (EPZ, then MAF) RUNNING since 03:10, logs `c4_vad_sigma_<radar>_<sigma>.log`; changing VAD_SIGMA_MS is a core change. Note: the printed 95 % interval is NOT for sd (it bootstraps the uncentred d^2 - B, i.e. includes the 0.6-1.3 m/s bias, while sd uses the centred R) |
| Shear target, form c1 | FAIL: p99 new / balloon 0.97 in 1-5 km but 0.82 in 5-12 km (CRPS -0.03 %, noise) | both forms failed -> **shear target CLOSED** (IL-201 had already shown the 100-300 m shear does not move apogee) |
| C4 sigma sweep (`p3_vad_condition --sigma 3.0 / 3.02 / 4.16`, EPZ and MAF) | the score barely depends on sigma: 3.02 = 3.0 to the second decimal; 4.16 slightly worse for 'radar' at 2.5-5 km at both sites (+31.3 -> +30.0 %, +21.5 -> +19.5 %); adopt rule fails at every sigma ('radar+all' covers 0.49-0.55, overlapping levels) | **keep VAD_SIGMA_MS = 3.0; C4 CLOSED** (logs `c4_vad_sigma_*.log`) |
| A2 past-mode spread x1.2 | decided from existing logs `gw_uscrn_bench.log` / `gw_uscrn_bench_monahans.log` (same hours, anchor on): x1.2 raises CRPS at both USCRN sites (Las Cruces day 0.744 -> 0.750, other 0.845 -> 0.924; Monahans day 0.604 -> 0.634, other 0.866 -> 0.912) and pushes day coverage past 0.90 (0.95 / 0.96) | **A2 FAILS (rule: CRPS loss <= 0.0009 at all three sites); keep 1.0**. The extra spread helps only at the airports (TCS 0.78) -> site-specific, see IL-207 |
| IL-207b per-site factor (`b3_il207b_site_shift.py`) | PASS on 2 hour sets: TCS CRPS -0.079 [-0.116, -0.042] and -0.075 [-0.140, -0.009], cov 0.81->0.85 / 0.80->0.86; MAF guard neutral | CONFIRMED; adoption is ASK_LATER 24 (TCS is a 30 km proxy for the pad) |
| S2 step 0 day/night bias (`b4_s2_step0_daynight.py`, 60 h each, 2021-22) | opposite day/night sign at 2 of 9 (LRU, ELP; both intervals span 0). TCS too calm day AND night (+0.52 / +1.08 m/s); PEQ night -1.58; ONM, FST, ABQ not servable | **PREMISE WRONG -> S2 STOPPED**; the TCS error is a site offset, not a flat daily cycle, so the TCS factor stays per-site (ASK_LATER 24) |
| O4 analog tail fix (`b4_analog_tail.py`, 2024-25, K 40) | strong-wind under-prediction TCS 2.44 -> 2.11, MAF 1.87 -> 1.37 m/s (rule: halve); CRPS better at both (TCS -0.010 [-0.017, -0.004], MAF -0.027 [-0.033, -0.019]), coverage TCS 0.89 -> 0.83 | **FAIL** (tail not halved); the plain analog stays the referee. Side note: the gap fix is a better analog overall, but not the fix the rule asked for |
| S1 map first, update second (`b4_debias_then_update.py`) | FAIL: seed 1 ONM map+B coverage 0.78 (rule 0.80); cell factors differ by 0.086 between seeds (rule 0.05). Map+B beat B on CRPS at all 12 pair-seeds (-0.007 to -0.063) | S1 closed; B (adopted, ASK_LATER 23) and the map (ASK_LATER 24) stay separate |
| G1-6 observe numbers (`b2_g16_observe_fit.py`, 659 reports 2015-22, test 2023-25) | fit chose tau 13 h, scale 2.2; vs shipped speed-space default: TCS +0.022 [-0.013, +0.057], MAF +0.068 [+0.024, +0.108] (worse). Centre bias -0.25 m/s at the shipped numbers | **CLOSED**, nothing changes; the shipped default stays |
| S3 radar thinned (`b4_radar_thinned.py`, 150 days per block, 2 seeds) | KILL: on the EPZ 2021-22 choice days no thinned setting reaches 2.5-5 km coverage 0.85 (thin5 0.68-0.74, thin4 0.75-0.80; shipped 0.94-0.95). Thinning does sharpen CRPS (2.5-5 km +33 vs +28-32 %; 5-12 km about +10-13 % vs shipped lower), but the spread at the observed levels is too tight | closed for good (a full error matrix would need a core change); shipped four levels stay |
| O2 radar over distance (`b4_radar_distance.py`, 107 common EPZ + HDX days, cached files, seed 0) | measurement: HDX (~145 km) at sigma 3.0 keeps nearly the EPZ gain: 2.5-5 km +27.6 % vs +29.1 % (both intervals exclude 0), 5-12 km +15.0 % vs +13.5 %; HDX coverage 0.92 / 0.94 | no distance term needed for observe_radar at ~145 km (23 UTC hours only) |
| O1 two neighbours at once (`b4_two_neighbours.py`, 200 h per target, 2 seeds; TCS from LRU + ONM with the TCS map on, ELP from LRU + ALM) | merged report beats the best single neighbour in all 4 runs but the interval excludes 0 only once: TCS -0.043 [-0.096, +0.013] / -0.019 [-0.104, +0.066]; ELP -0.105 [-0.153, -0.053] / -0.038 [-0.089, +0.008]; coverage 0.84-0.89; error correlation r 0.39 / 0.43 | FAIL (pre-set rule: interval excludes 0 at both targets, both seeds) -> O1 closed; `observe_latest` keeps one station |
| O3 launch-week factor (`b4_launch_week_replay.py`, 150 test days per site, 2 seeds; start = no factor because S2 was dropped; alpha 1/30 per day) | k = 7 minus no factor: TCS -0.016 [-0.039, +0.007] / -0.044 [-0.070, -0.018]; MAF +0.008 [-0.013, +0.029] / -0.029 [-0.047, -0.013] with coverage 0.91 -> 0.90. k = 3 and 14 similar; the factor moves only 0.9-1.2 in 1-2 weeks | FAIL (pre-set rule: both sites, both seeds, coverage not lower) -> O3 closed |
| O5 ECC vs Schaake in forecast mode (`b4_ecc_modeF.py`, IFS ENS 00z starts 2023-24, 30 points per start and lead, leads 1-7, 2 seeds) | ECC about equal to Schaake at leads 1-2 and +0.5 to +1.7 % WORSE (variogram) at leads 3-7; shear rate ratio 0.98, IL-128 p99 ratio 0.976 (both ok). Data note: about 20 % of the 2023-24 ENS wind (whole start x lead slices, all members) is NaN, so those rows are skipped; the finite rows look normal (lead-1 u10 bias +0.16 / +0.17 m/s, rmse 1.0-1.6, as 2022). Reproduction on 2022 (`--years 2022`, the M4 year) matches M4: ECC -0.9 to -3.3 % at leads 1-7, shear ratio 0.93 | FAIL (pre-set rule: >= 1 % better at every lead) -> keep Schaake; the M4 gain does not carry to 2023-24 |
| N5 step 0 row count (rows beyond 7.5 d lead in the Mode F stores) | NM/TX 153,359, Denver 116,037; the longest lead stored is 10 d | PASS (>= 20,000) -> full N5 (continuous lead + beyond-7.5 d rows) allowed |
| N2 step 0 pair count (`data/raw/wb2_hres_global` vs `data/raw/era5_global`, same 7483 points) | 8,499 HRES records 2016-22 (leads 6-240 h every 6 h), every valid time has ERA5 truth: 63.6 M matched point pairs | Pair count PASS (>= 300,000) |
| N2 step 0 box checks (`b5_n2_step0.py`, `il6_modeF.py --levels13 / --no-place`, ENSF2 HRES-only recipe, seed 0, same-run base) | 13 levels + surface: NM/TX -0.50 %, Denver +0.00 %; no lat / lon: NM/TX +0.00 %, Denver +0.20 %. First run of --levels13 had no surface level (lowest input 9 of 44) and lost 1.84 % at Denver; the world store has u10, v10, t2m, so the surface level was added and the arm rerun (rule unchanged) | PASS (pre-set: under 1 % and under 0.5 %, both boxes) -> N2 full run (world pairs) allowed |
| N4 optional ensemble inputs in one network (`b5_modeF_mask.py`, ENSF2 recipe + `--ens-mask 0.3` + present bit, both boxes, 2 seeds) | With the feed vs ENSF2: +0.2 to +2.4 % per lead, mean of leads +1.0 to +1.7 % in every box and seed. Without the feed vs HRES-only: +1.4 to +2.6 % at leads 1-3, about equal at leads 5-7 | KILL (pre-set: a side > +1 % mean of leads in both seeds) -> keep the two single-purpose networks; the width 192 arm is not run |
| N3 step 0 more real years (`b5_n3_step0.py`, `il6_modeF.py --fit-years 1-4`, 2020 validation fixed; the plan's 1/2/3/5 is not possible, only 4 fit years exist, so 3 -> 4 is used) | Lead-1 CRPS 1.810 / 1.671 / 1.656 / 1.641 for 1 / 2 / 3 / 4 years (seed 0); gain 3 -> 4 years +0.66 % seed 0, +0.34 % seed 1 (seed 1 added: the gain is the size of seed noise) | CLOSED (pre-set: gain under 0.5 % -> closed; under in seed 1). More stand-in years are not expected to help |
| N2 full run world Mode F (`cpu_n2_full.sh`, `il6_build_world.py` 645k rows 2016-20 at the 7,483 world points, no lat / lon; `b5_modeF_world.py`; ENSF2 HRES-only recipe, seeds 0 and 1; note: 7 world points lie inside the NM/TX box and 4 inside Denver, no time leak: world fit 2016-20, test 2022) | World as it is vs own model, change at lead 1 / 3 / 5 / 7 d: NM/TX +1.2 / +3.7 / +2.0 / +2.3 % (s0), +1.2 / +3.5 / +2.1 / +2.3 % (s1); Denver +1.4 / +3.3 / +1.6 / +0.7 % (s0), +1.3 / +3.0 / +1.6 / +0.2 % (s1). World + 300 fine-tune steps on the box rows: NM/TX -2.6 / -0.8 / -1.3 / -2.1 % (s0), -2.7 / -1.1 / -1.4 / -2.0 % (s1); Denver -2.2 / -1.0 / -1.1 / -1.8 % (s0), -2.4 / -1.5 / -1.1 / -1.9 % (s1); interval < 0 at 16 of 16 lead x box x seed checks. Control added 2026-11-11 23:53 (`cpu_n2_control.sh`, own model + 300 extra steps): change vs own -0.6 / -0.6 / +0.1 / +0.3 % (NM/TX s0), -0.6 / -0.6 / 0.0 / +0.1 % (s1); Denver -0.6 / -0.6 / 0.0 / +0.9 % (s0), -1.1 / -1.0 / -0.2 / +1.1 % (s1). Fine-tuned world minus own + 300: interval < 0 at leads 1, 5 and 7 d in all 4 box x seed cases (NM/TX s0: 1 d -0.033 [-0.048, -0.019], 5 d -0.039 [-0.068, -0.016], 7 d -0.089 [-0.124, -0.057]); at lead 3 d the interval includes 0 | MISS (pre-set: world as is must be within 1 % at every lead; it is not). With the control: the fine-tuned gain comes from the world start, not from the 300 extra steps (3 of 4 leads, every box and seed). No adoption by rule; user decision whether a fine-tuned box model becomes its own item |
| N5 full run one network from day 1 to climate (`cpu_n5_full.sh` + `cpu_n5_rest.sh`, `b5_modeF_alllead.py`; rows `data/modeF_v2{,_denver}`, binned vs all-lead + 10 % climate anchors, seeds 0 and 1) | All-lead vs binned, change at lead 1 / 3 / 5 / 7 / beyond 7.5 d: NM/TX +2.7 / +1.0 / +0.2 / -0.7 / -3.2 % (s0), +2.5 / +1.0 / +0.2 / -0.7 / -2.9 % (s1); Denver +2.6 / +1.1 / +0.4 / -0.2 / -3.7 % (s0), +2.4 / +0.9 / +0.4 / -0.2 / -3.5 % (s1). Beyond 7.5 d all-lead minus binned: NM/TX -0.139 [-0.193, -0.097] / -0.128 [-0.177, -0.087]; Denver -0.167 [-0.218, -0.121] / -0.157 [-0.205, -0.115]; minus the climate model about -0.51 (NM/TX), -0.65 (Denver) | KILL (pre-set: worse by more than 1 % at leads 1-3). Nothing changes in the tool. Kept as a fact: beyond 7.5 d one network beats the binned model by about 3 % and the climate model clearly, so a long-lead-only network is a possible later item |
| N6 step 0 full-size Mode F on the GPU (`gpu_n6_step0.sh`, `il6_modeF.py --fit-only`; width 512, depth 4, 4 members, all 44 heights, world rows 645k, seed 0, 3000 steps, 2.8 min on the RTX 5070) | validation CRPS 0.4986 at step 250 -> 0.4787 at step 2750 (still falling slowly; train 0.48, so no overfitting as in IL-77) | **PASS (step 0)**: full run queued (`gpu_n6_full.sh`: world seed 1, then 300 box steps x 2 boxes x 2 seeds after [N2B]); verdict `b5_modeF_big.py` with the pre-set rule |
| N1 step 1 (data <= 2020 with fixed steps must reproduce p2f within 0.0006) | Every p2f member's best validation step is its last (6000; data/phase2_train_p2f.log), so p2f is that model (difference 0) | **PASS (step 1, no run needed)**: full run started 2026-11-11 23:19 (`gpu_n1_crossfit.sh`, seeds 0 / 100); verdict `b5_crossfit.py` with the pre-set rule |
| N2 modification B, data-scarce box (`cpu_n2b_scarce.sh`, `b5_modeF_scarce.py`; box model on 1 fit year (own1), own1 + 300 extra steps (own1p300), world start + 300 steps on the same 1-year rows (ft1); seeds 0 and 1, both boxes) | ft1 vs own1p300, change at lead 1 / 3 / 5 / 7 d: NM/TX -5.1 / -2.5 / -1.9 / -2.3 % (s0), -4.8 / -2.3 / -1.9 / -2.2 % (s1); Denver -4.8 / -3.6 / -2.9 / -4.1 % (s0), -4.7 / -4.2 / -2.9 / -3.7 % (s1). ft1 vs own1: -1.6 to -8.9 %. Interval < 0 at 16 of 16 lead x box x seed checks against EACH arm (NM/TX s0 lead 1 vs own1p300: -0.089 [-0.123, -0.063]). Note: ft1 on 1 box year (NM/TX lead 1 1.648) about equals the own model on 4 years (N3: 1.641) | **PASS** (pre-set: better than both arms with interval < 0 at >= 3 of 4 leads, both boxes and seeds). The world start is worth about 3 box years of forecast data. Adoption stays with the user (no shipped path uses it yet) |
| N6 full run full-size Mode F (`gpu_n6_full.sh`, `b5_modeF_big.py`; width 512, depth 4, 4 members, no lat / lon, world fit 3000 steps + 300 box steps, GPU; vs the small own model as shipped, seeds 0 and 1) | Big minus small, change at lead 1 / 3 / 5 / 7 d: NM/TX -5.0 / -3.1 / -1.9 / +2.2 % (s0), -5.8 / -3.4 / -1.8 / +2.4 % (s1); Denver -4.7 / -1.4 / +1.5 / +4.0 % (s0), -4.7 / -2.1 / +1.6 / +3.5 % (s1). Lead 1 interval < 0 in all 4 (NM/TX s0 -0.083 [-0.120, -0.054]); lead 7 worse in all 4 (Denver s0 +0.160 [+0.020, +0.322]). cov99 within 0.003 except Denver s0 lead 7 (+0.0060) and s1 lead 5 (-0.0054). For scale: the small fine-tuned world model of N2 gave -2.2 to -2.7 % at lead 1 | **KILL** (pre-set: not better at 2 or more leads in a box x seed; Denver is worse at 5 and 7 d in both seeds). N7 is not started (it needed N6 to show that size helps). Kept as a fact: at leads 1-3 d the big world-start model is the best Mode F seen (-4.7 to -5.8 % at lead 1); a lead-split (big at 1-3 d, small beyond) would be a new item with its own rule |
| N1 full run cross-fitted members (`gpu_n1_crossfit.sh`, `scripts/n1_crossfit.py`, `b5_crossfit.py`; 4 members on 1991-2023, member k leaves out its own 4 years of 2008-23, fixed 6000 steps, range map from held-out years; vs p2f; seeds 0 and 100; test 2024-25 ERA5 + balloons) | ERA5 skill15 0.0277 -> 0.0297 (+0.0020, s0), 0.0271 -> 0.0298 (+0.0026, s1); balloons 0.0084 -> 0.0115 (+0.0030), 0.0073 -> 0.0111 (+0.0037); ERA5 coverage error 0.0034 -> 0.0030, 0.0031 -> 0.0033. The gain is 4-5 x the seed-noise yardstick (0.0005) in both seeds. Caveats: the members see 3 more training years (2021-23) than p2f, so part of the gain may be data, not cross-fitting; 2024-25 has been used for 30+ decisions | **PASS** (pre-set: ERA5 skill15 >= 0.0287 in both seeds, balloons and coverage not worse). Not exported: a tool export needs the user's go at the moment it runs (B29); ASK_LATER 26 |
| N2 modification C, climate descriptors instead of lat / lon (`cpu_n2c_place.sh`, `--place-clim`, `b5_modeF_place.py`; world-C and ft-C vs the box's own model and vs plain world / ft; NM/TX and Denver; seeds 0 and 1; test 2022) | world-C vs own +1.4 to +3.6 % at leads 1-3 (NM/TX 1d +1.6 / +1.5, 3d +3.6 / +3.4; Denver 1d +1.6 / +1.4), only lead 7 Denver better (-0.8 / -1.0 %); vs plain world -1.2 to -1.9 % at lead 7, about 0 at lead 1. ft-C vs own -0.5 to -3.4 %, interval < 0 at 15 of 16; vs plain ft about 0 at NM/TX, -0.3 to -1.1 % at Denver | **MISS** (pre-set: PASS needs world-C within 1 % of own at every lead; KILL needs the descriptors to help neither arm in 2 of 4 cases). Recorded, no adoption. The descriptors help the world model only beyond 3 days; the fine-tuned box model stays the useful form of N2 (user decision) |
| RA stage 1a, gap rows + arm A1 (`new_plan_kit/b6_realair_rows.py`; HRES at the 986 balloon points vs balloon vs ERA5, 84 months 2016-22, 426 matchable valid times, 30.9 million rows; fit 2016-20 at kept stations; check at 197 left-out stations incl. El Paso, Midland, Denver and the 7 world-held) | Gap sd per component (6 numbers): 10 m 1.54, 0-1.5 km 1.63, 1.5-3 km 1.49, 3-6 km 1.49, 6-10 km 1.83, 10-17 km 1.98 m/s. 90 % band coverage on 2022, left-out stations: model error only (A0) 0.831 / 0.872 / 0.881 / 0.891 / 0.897 / 0.899; with the gap (A1) 0.902 / 0.904 / 0.904 / 0.909 / 0.911 / 0.919. 2016-20 left-out the same within 0.01. Limits: coverage pooled over leads 6 h-10 d (at long leads model error dominates); bands from per-band sd, not a member ensemble; balloon QC only drops errors >= 60 m/s | **PASS** (pre-set: 0.87-0.93 in every band; kill < 0.85). The gap is a simple added part: A1 is the floor for stage 2. Stage 2 needs 1b (Colab download, ASK_LATER 25) |
| SWiFT check, tool vs the TTU 200 m tower (`new_plan_kit/b6_swift_check.py`; 131 tower hours on 4 days of 2013-14, 10-min window at hh:00; arms: climate (default call), past (local ERA5 day + night stores), ERA5 value itself; 512 members) | Median bias (tool - tower) at 10 / 47 / 75 / 116 / 158 / 200 m: climate -2.1 / -3.6 / -4.3 / -4.4 / -4.5 / -4.4; past -0.6 / -1.9 / -2.5 / -2.5 / -2.6 / -2.4; ERA5 -1.0 / -1.1 / -1.7 / -2.1 / -2.6 / -2.8 m/s. 90 % coverage past 0.82 at 10 m, 0.51-0.60 at 47-200 m; gust band 0.97. 200-10 m speed difference: tower 5.9, ERA5 4.1, past 4.0 m/s (real 1.45 x ERA5). Reading: the 4 days were windy (climate about 2 m/s under ERA5), and ERA5 itself is too calm and too weakly sheared here, more so with height; past mode inherits it, and its band is too narrow against real air | **Sanity check, no adoption** (reading set before the run: off if coverage < 0.70 or PIT mean outside 0.3-0.7: off for climate everywhere and past at 47-200 m). Independent support for RA (section 11): the missing part is the ERA5-vs-real gap, not the generator. 4 days only; tower position from memory (a few km) |
| README Part 5 A2, past-mode spread x1.2 as default (no new run: the switch `Launch(past_wind_spread=1.2)` exists and all three sites are already scored on the same hours with and without it; `gw_past_anchor.log`, `gw_uscrn_bench.log`, `gw_uscrn_bench_monahans.log`) | Airports (M5c, with the ERA5 anchor): CRPS -8 % / -13 % at TCS / MAF with x1.2 vs -5 % / -11 % without. USCRN Las Cruces by day 0.744 -> 0.750 (cov 0.90 -> 0.95); USCRN Monahans by day 0.604 -> 0.634 (cov 0.94 -> 0.96); other hours worse too (0.845 -> 0.924, 0.866 -> 0.912) | **FAIL** (rule in README Part 5: CRPS not worse by more than 0.0009 at any of the three sites; both USCRN sites worse by 0.006 and 0.030, coverage moves away from 0.90). Default stays 1.0; x1.2 stays an opt-in for airport-like sites (agrees with IL-168: the factor is a site property) |
| README Part 5 G1-7 drift replay, does climate mode drift from ERA5 month by month, would a 12-month EWMA tracker fix it (`new_plan_kit/b3_g17_drift_replay.py`, points nearest TCS/MAF, 2015-2025, 20 hours/month, n 100) | NO TRACKER NEEDED: mean abs monthly bias under one month's day-block half-width in 9 of 12 var x band cells; the tracker beats no tracker in only 2 of 12. Mean bias small (u -0.2 to -0.7 m/s, v -0.1 to +0.2, T -0.2 to +0.2 K); 2021-25 (unseen) not worse than <= 2020 | no tracker; nothing in the tool changes | `docs/results/logs/kit_b3_g17_drift_replay.log` |
| README Part 5 G1-5 spread tracker replay (`new_plan_kit/b3_g15_spread_replay.py`): the live-feed archive starts 2026-11 (off limits), so WB2 IFS ENS 50 members (00Z every ~8 days, 2016-24, leads 1-7 d) at the points nearest TCS / MAF vs ASOS 00 UTC, 10 m speed and 2 m T; recipe tracker (alpha 1/60 per day, 1/20 when widening, factor clip 0.8-1.5); scored 2023-24 | FAIL by the pre-set rule: coverage error falls in 4 of 4 cells (e.g. MAF wind 0.27 -> 0.14, TCS T 0.17 -> 0.06) and CRPS improves in 3 cells (MAF wind 1.315 -> 1.273), but TCS T CRPS 1.290 -> 1.292 (+0.002 > 0.0009). Factor sits at the 1.5 cap almost always: the raw ENS is far too narrow against station readings | no tracker. Reading: the gain is mostly a fixed widening of the raw ensemble, not tracking; the tool's own forecast-mode recalibration may already cover it (not tested here) | `docs/results/logs/kit_b3_g15_spread_replay.log` |
| README Part 5 G1-3 radar + station score (`new_plan_kit/b3_g13_radar_station_score.py`, report only): co-extreme ratio P(shear 0.5-1.5 km extreme given 10 m speed extreme, both > q95) at El Paso, 690 balloon hours 2021-23 with balloon + ELP ASOS + EPZ radar | step 1 passes narrowly: balloon 0.14 [0.03, 0.26], radar + ASOS 0.03 [0.00, 0.06] (intervals touch). Tool climate mode 0.05 [0.04, 0.06] with or without C4 radar noise (sd 2.37, corr 0.33): inside the radar + ASOS interval, below the balloon value; 0.05 = independent | report only, no change. Reading: about 35 extremes per source, so the truth itself is uncertain by a factor of 3; no case for changing the tool's speed-shear coupling | `docs/results/logs/kit_b3_g13_radar_station_score.log` |
| README Part 5 G2-2 Student-t widening (`tempest_weather_v2/launch.py` `_t_widen_factor`, flag `observe(..., t_update=False)` and `observe_radar(..., t_update=False)`, OFF by default; eval `new_plan_kit/b3_g22_t_update.py`): conditioned u, v, t2m departures x clip(sqrt((8 + D^2) / (8 + k)), 1, 2). W6 cases, TCS + MAF ASOS 2023-25, 600 previous-hour soft observations, same seed | PASS by the pre-set rule: top 10 % surprise (60 cases, D^2 >= 5.8) cov90 0.85 -> 0.92 (spread x1.24); other 90 % CRPS change -0.0003 [-0.0020, +0.0013]. Top 10 % CRPS +0.011 [-0.046, +0.061] (not worse beyond noise, not better) | flag shipped OFF (opt-in); making it default is the user's call. Not tested: radar (p3_vad_condition.py bypasses Launch); T / p / RH profiles not widened. Fault gate (step 2) BLOCKED: needs a previous reading of the same sensor or a second sensor, observe() has no such input | `docs/results/logs/kit_b3_g22_t_update.log` |
| C6 run-to-run disagreement, step 2 premise (`scripts/c6_lagged_spread.py`): lagged HRES pairs from the F-V2 refetch, 36 h apart (00Z newer vs 12Z older; the recipe's 12 h pair is not on disk), 2016-2020, 182 400 rows; Spearman rho of d = RMS(newer - older) with e = RMS(newer - ERA5) per band | PREMISE PASSES narrowly: mean within-lead-bin rho >= 0.3 in 4 of 8 cells (wind 0-1 km 0.30, 1-5 km 0.37, 5-12 km 0.38; T 5-12 km 0.33; wind 12-18 km 0.26, T 0-1 / 1-5 / 12-18 km 0.18 / 0.27 / 0.22). Rule amended BEFORE the 2016-2020 run (after a 2016 smoke run) from rho pooled over leads (0.30-0.62, inflated: d and e both grow with lead) to the within-lead mean (stricter) | go to step 3 (fit f = a + b d / median(d) on 2016-2020) and step 4 (2022 PIT / CRPS next to fv2_eval.py); expect the gain, if any, in wind 1-12 km | `docs/results/logs/c6_lagged_premise.log` |
| C6 steps 3-4 (`scripts/c6_lagged_spread.py --step34`): spread factor f = a + b d / median(d) per wind / T band (8 x 2 numbers), fitted on 2016-2020 (2500 00Z-start rows with the 36 h older run), applied to the shipped mode F members, tested on 2022 (2500 rows, 36 init dates) | FAIL by the pre-set rule (C6 dropped): PIT distance over u, v, T 0.0545 -> 0.0527, change -0.0018 [-0.0051, +0.0007] (interval not below 0). CRPS did improve: -0.69 % [-1.19, -0.24] (u 2.301 -> 2.287, v 2.386 -> 2.369, T 0.890 -> 0.883); fitted b +0.10 to +0.21, test f 5-95 % about 0.8-1.5 | no change to the tool; a CRPS-based rule would pass, but changing the rule after the result is the user's call (shortcut: 36 h lag only, 12 h pairs not on disk) | `docs/results/logs/c6_lagged_step34.log` |
| A5 (Limitations to solve): wind below 10 m above ground. Opt-in `below_10m="loglaw"` in `tempest_weather_v2.readers.Atmosphere` and `tempest_weather.flight_sim_readers.TempestWind` (z0 from `z0_m=`, number or per-sample array, else samples["surface_roughness_m"], else 0.03 m): horizontal wind = 10 m wind x ln(z / z0) / ln(10 / z0), 0 below z0 | DONE behind a flag, default unchanged (straight line to the 0.72 pad node). New tests: log shape at 1 / 2 / 5 m in the scalar, vector and velocity paths, calm below z0, unchanged at and above 10 m, T / p / RH unchanged, sample roughness used, bad option and bad z0 raise. Full suite 395 passed | making loglaw the default is the user's call; only matters for rails under about 3 m | `docs/results/logs/tests_after_A5.log` |
| Architecture step 0 for section 14 (`new_plan_kit/b7_arch_step0.py`; Mode F rows 2016-2019, NM/TX, 350,399 rows, read-only) | Today's target (truth - forecast) grows 12.6 x (wind) / 18 x (T) in variance from lead < 1 d to 7.5-10 d and exceeds the climate spread beyond 7.5 d (1.11; 10 m 1.45); a measured pull toward climate cuts it to 0.77. Two runs 30-72 h apart: error correlation 0.37-0.53, best fixed mix -1 to -5 % squared error up to 4 d, -6 to -13 % at 4-7.5 d. A run's own 6 h change ranks its error at 0.25-0.39 (0.5-9 km). One run's errors 6 h apart correlate 0.16-0.28 at days 1-2, up to 0.80 at days 6-7.5. A place's own error memory adds under 2.2 % for wind | Premises of SIGMA and CHORUS hold; STRAND holds beyond day 4 only; ECHO dropped. Nothing trained, nothing in the tool changes | `docs/results/logs/kit_b7_arch_step0.log` |
| A7 (Limitations to solve): does the site roughness reach the turbulence step? Traced: `Launch.engine()` built the engine with no roughness and `TempestFlightSimEngine.sample_sobol_batch` used `z0_roughness_m=0.03` unless the caller passed `launch.z0()` by hand; it was not passed on any path | DONE behind a flag, default unchanged: `Launch.engine()` now puts the site roughness (median of the land-cover map values, = `Launch.z0()`) in `engine.info["z0_m"]`, and `sample_sobol_batch(z0_roughness_m="site")` uses it (a bad string or a missing value raises). New tests: default unchanged, 'site' = the info value and differs from 0.03, errors; Launch test checks info z0_m = Launch.z0(). Full suite 396 passed | making 'site' the default for Launch engines is the user's call (changes Dryden strength near the ground at rough sites) | `docs/results/logs/tests_after_A7.log` |
| IL-129 (`_cdf` / `_ppf` past the pool min / max; CPU-C list) | ALREADY DONE: `tail_extrap` (outer-5 % slope) has been in `TempestFlightSimEngine` and ON by default since 2026-11-08; the real-pool IL-128 rerun (2026-11-11, `kit_b1_quick_il128.log`) ran with it: no inflation, worst ratio 0.84 (the copula sampling loses 16-34 % of p99.9 shear) | nothing to build; item closed | `docs/results/logs/kit_b1_quick_il128.log` |
| Labels in saved files (CPU-C; Limitations 5.2.13 / 5.2.16) | BUG FOUND AND FIXED: `Launch.save` wrote the observations but `Launch.load` never read them back, so a reloaded CONDITIONED file (its samples are conditioned, 10 m wind 14.0 mph) said it was a plain climate estimate; same for the HRRR anchor. Now save also writes `hrrr_note`, and load adds "conditioned on N measurements before saving (not yet validated)" / "ground wind anchored to ... before saving" to the trust line. Mode and "atmosphere only" were already carried. Numbers unchanged; old files with observations get the label too. New test; full suite 397 passed | label-only fix (plain bug) | `docs/results/logs/tests_after_labels.log` |
| Input archive with hash (CPU-C; Limitations 5.2.20) | DONE: `Launch.save` already archived the whole sample pool + provenance (asset manifest hash, modes, seed, source) in the `.tempest` file, and `tempest doctor` already exists. Added the hash stamp: save writes `meta["sha256"]` over every saved array (name, dtype, shape, bytes); load refuses a file whose numbers no longer match. Files without a hash (older saves) still load. Saved numbers unchanged. New test (changed file refused, old file loads); full suite 398 passed | shortcut: the raw Open-Meteo responses are not archived, only the samples made from them (enough to re-run the flight sims of a decision, not to rebuild the samples); add the raw inputs if a review board asks | `docs/results/logs/tests_after_archive_hash.log` |
| RH range map widening (CPU-C; Limitations 5.2.19 c) | **FAIL by rule** (`new_plan_kit/b3_rh_widen.py`, rule in its header before the run): the RH 12-18 km station correction (served by the past-mode hybrid) stretched around each sounding's median by k, k picked on 2021-23 00Z (smallest k with 99 % coverage >= 0.99: k = 1.95), scored once on 2024-25 00Z (1306 soundings): 99 % coverage 0.948 [0.940, 0.956] -> 0.991 [0.987, 0.994], CRPS 3.704 -> 3.924 (+5.9 %; paired +0.219 [+0.170, +0.270]); the rule needed CRPS <= +1.5 %. A uniform stretch buys the last 4 % of coverage with the whole distribution; the misses are in the tails (`station.apply` shortcut: leftovers never exceed what the 1991-2020 balloons saw) | no tool change; a tail-only fix (GPD tails on the leftover pool, PLAN S4) is the next thing to try if wanted | `docs/results/logs/kit_b3_rh_widen.log` |
| Dissimilarity index in `Launch.domain()` (CPU-C; Limitations 5.2.18 idea 2, IL-150 part) | DONE (report only): `domain()` now also returns `di`, `di_threshold`, `di_region` = the L3-28 dissimilarity index of the place against each trained asset grid (lowest wins), same maths as `tempest/scoring/di.py` (new test checks equality). NM/TX threshold 2.57 (L3-28: 2.54; the grid height stands in for both training heights). Examples: inside 0.85, NM/TX edge 1.17, just north of the box 7.25, (45, -90) 43.4. Status still from the box test, so answers are unchanged; outside the boxes the site height is not looked up online (di None unless elevation= is given). Full suite 399 passed | open: replacing the box test with DI (changes answers: user's call); the climatology answer outside the boxes from the global ERA5 store (larger item, not started) | `docs/results/logs/tests_after_di.log` |
| L19 A1 MERRA-2 fetch script, dry run (Limitations 5.2.8) | DONE (dry run only): `tempest/ingest/fetch_merra2.py` (M2I3NVASM model levels; T, U, V, H, PL; box 31-40 N, 108-101 W; 00Z + 12Z; days 1/11/21). GES DISC on-prem OPeNDAP now answers 410 (retired), so the script uses Earthdata Cloud OPeNDAP (DAP4, collection C1276812900-GES_DISC; ';' between variables must stay unencoded or Hyrax answers 500). 2024-01-01: 72 levels, 19 x 13 grid, top mid-layer height 75.6 km (lowest 0.70 km), 0.49 MB in 6.7 s; streams 100/200/300 granules (1991, 1995, 2005) also resolve; missing granule = 404 (stream-401 fallback kept). Full 1991-2025 run: 1260 days, about 0.62 GB, about 2.4 h | open: the full download (approved in the plan; network-only, can run in a RAM gap), then the A1 18-80 km climatology | dry run printed in the tick, no log file |
| AV1 lead split (New_Plan 13.1; variation of N6) | **KILL by the pre-set rule** (`new_plan_kit/b8_av1_lead_split.py`, rule in its header before the run; 2021 scored with `il6_modeF.py --test-year 2021`, range map on 2022, runner `scripts/cpu_av1.sh`). Step A (2021 must pick the same split: big better at 1 and 3 d, not at 5 and 7 d, per box, mean of 2 seeds): Denver 0.981 / 0.981 / 1.018 / 1.027 (confirmed), NM/TX 0.966 / 0.978 / 0.999 / 1.030: big 0.1 % better at 5 d (a tie, intervals -0.041..+0.051 and -0.055..+0.041), so not confirmed. Step B (2022) not met either: Denver seed 0 at 3 d interval [-0.069, +0.006]. Benefit is real: 1 and 3 d better on 2021 with the interval below 0 in 7 of 8 box x seed x lead cells (2-3.5 %; Denver seed 1 at 1 d [-0.070, +0.007]); 2021 cov99 at 3 d Denver seed 0 +0.0037 | per section 13's standing note, one more variation logged as AV22 in 13.1 (smooth N6 / small weight by lead, picked on 2021, judged on 2022); whether a 0.1 % tie at 5 d should count as 'not better' is the user's call (not re-judged) | `docs/results/logs/kit_b8_av1_lead_split.log` |
| AV2 long-lead-only use of the N5 all-lead network (New_Plan 13.1; variation of N5) | **MISS by the pre-set rule** (`new_plan_kit/b8_av2_long_lead.py`; no new run, N5 test rows). Skill is large and real: days 8 / 9 / 10 all-lead vs climate -0.82 / -0.53 / -0.35 (NM/TX) and -1.07 / -0.63 / -0.48 (Denver) CRPS, every interval < 0 (7-22 %); vs binned -0.03 to -0.25, interval < 0 in 11 of 12 cells (NM/TX seed 1 at 8 d [-0.061, +0.002]). Fails on the range: cov99 beyond 7.5 d 0.978-0.983 vs climate 0.990-0.991 (diff -0.008 to -0.012, limit 0.003) | not adopted. AV3 (router AV1 + AV2) not run: needs both to pass. Per section 13's standing note, AV23 logged in 13.1 (all-lead network blended toward climate by lead, which should also restore the range) | `docs/results/logs/kit_b8_av2_long_lead.log` |
| SIGMA stage 1, arm B0 (New_Plan 14.3; `new_plan_kit/b8_sigma_stage1.py`; no training; fit 2016-2019, scored on 2020, both boxes) | Measurement, no rule. B0 = climate + beta x forecast anomaly + s x bell draw. With beta and s TABLED per lead day (B0tab), mean CRPS by lead bin 1 / 3 / 5 / 7 / beyond 7.5 d: NM/TX 1.615 / 2.263 / 3.099 / 3.779 / 4.347, Denver 1.816 / 2.344 / 3.141 / 3.789 / 4.310; better than the forecast + tabled bell (FC) at every bin (beyond 7.5 d -14 to -17 %, intervals < 0 for B0) and than climate at every bin. The two-number curves of improvement 1 (exponential decay) are the wrong shape: beta overshoots to 1.07-1.11 at 1 d (table 0.94-1.00), so curve-B0 is 9 % worse than B0tab at 1 d, 6-7 % at 3 d, 3.5 % at 5 d, a tie beyond 7.5 d (intervals exclude 0). cov99 of all bell arms 0.966-0.99 (bell tails) | the bar for SIGMA stage 2 is B0tab, not curve-B0; stage 2 needs a flatter early shape (e.g. exp(-(L / tau)^p), 3 numbers) or the table. Comparing B0 with the shipped network needs the same rows: stage 2 scores both on 2022 | `docs/results/logs/kit_b8_sigma_stage1.log` |
| AU-1 code + tests (New_Plan 15.1, 2026-11-12 evening) | DONE (steps 1-4; step 5, the full GPU rescore, next). Opt-in `--fair-baseline` in `tempest/scoring/score.py` and `sonde.py` (off by default; flag off is byte-identical on all 4 output CSVs of a 300-row shipped-stack score): every set scored with the fair CRPS (Ferro 2014, spread over m(m-1)); clim and clim15 scored from the WHOLE pool without replacement (clim R median 168, clim15 R median 76, 10-90 % 63-86; clim15 pools under 20 rows fall back to all years, 0 rows did); the 199-draw arrays are kept for shuffle, coverage, tail, mc, stress. Measured bonus of the plain formula for a no-skill model at R = 75: +0.008 (not +0.0125 as the audit estimated; analytic (1/150 - 1/398) E|X-X'| / CRPS); fair is unbiased. 300-row smoke (no --mc): mean skill15_known 0.031 -> 0.016, skill_known 0.031 -> 0.027, skill15_gauss -0.054 -> -0.071 (smoke only, the verdict is step 5). Tests `tests/test_fair_baseline.py` (4); full suite 267 passed. Other callers with with-replacement pools, not yet changed: `scripts/il6_modeF.py` clim (Mode F verdicts), `scripts/fv2_eval.py`; `tempest/scoring/stress.py`, `mc.py` inherit clim15 draws. Making the flag the default needs the user's go. |
| AU-1 step 5: shipped stack rescored with `--fair-baseline` (New_Plan 15.1; `scripts/gpu_au1_fair.sh`, l3_c4w + lapse map, DAY data, 2024-25, --mc, exact flags of the l3_c4wl headlines; logs `data/au1_*.log`) | MEASURED, the headline shrinks. Mean over 19 bands, plain -> fair: ERA5 seed 0 skill15_known +0.032 -> +0.019, skill15_unknown +0.030 -> +0.017, skill_known (all-years clim, R 166) +0.032 -> +0.026, skill15_gauss -0.050 -> -0.064; seed 1 +0.034 -> +0.021, +0.031 -> +0.018. The shift reproduces across score seeds to 0.0002 (-0.0133 / -0.0131); the score-seed noise of the level itself is about 0.002 at this size. clim15 whole pool R median 75 (10-90 % 63-87), no fallback rows. Fair skill15_known per band, seed 0: interval above 0 in 9 of 19 (all T bands +0.035 to +0.058, t2m +0.054, u 1-18 km +0.016 to +0.047), point below 0 in 3 (u 0-1 km -0.008, RH 5-12 km -0.001, rh2m -0.003), none with the whole interval below 0; v, RH and sp are about 0. Balloons (`sonde`, independent truth, seed 0): skill15_known +0.017 -> +0.013, skill15_unknown +0.010 -> +0.007 (shift -0.003, smaller than on ERA5). margin_gauss_unknown barely moves (+0.080 -> +0.081): the model-vs-Gaussian ranking stands. Reading: about 0.013 of the README's ERA5 skill15 (+2.8 %) was the thin-pool handicap; the honest ERA5 number is about +1.7 to +1.8 % (unknown drivers). Every older skill-vs-clim15 verdict scored as a DIFFERENCE between two models on the same rows keeps its sign (the bonus cancels; the size rescales by the clim15 CRPS ratio, about 1 %); verdicts read as 'beats climatology' need the 15.4 re-read. Making `--fair-baseline` the default (and rewriting the README headline) waits for the user: ASK_LATER 27. |
| AU-2 forecast-mode site shift (New_Plan 15.1; `tempest_weather/api.py`) | FIXED (plain bug, ON by default; `OPTIONS["forecast_single_shift"] = False` = old line): forecast and past rows all move by elev - grid elevation; only the climate generator keeps its per-row blend-point height. Test `test_forecast_mode_moves_every_sample_by_one_grid_shift` (on: one value equal to elevation_m - grid_elevation_m; off: the old two values at Spaceport America). tool_audit (climate mode) identical to the previous log in every number; full suite 272 passed. |
| AU-3 forecast surface values shifted for height twice (New_Plan 15.1) | CONFIRMED by step 0 and FIXED. One live Open-Meteo call, Spaceport America (32.99, -106.97), tomorrow 18Z: default request answers at elevation 1400 m (its 90 m terrain) t2m 17.5 C sp 862.2 hPa; `elevation=1495.5` (ERA5 grid) 16.9 C 852.5 hPa; `elevation=nan` 1434 m 17.3 C 858.7 hPa. So the tool read terrain-height values as grid-height values and then shifted them again: +9.7 hPa, +0.6 K at the pad. Fix (plain bug, ON by default; `OPTIONS["forecast_grid_elevation"] = False` = old request): `openmeteo.url / fetch` take `elevation`; `_forecast_phys` asks for the grid height; a response at another height (> 5 m, e.g. a caller's three-argument fetch) has t2m and sp moved to the grid height (site_shift formulas) with the flag `forecast-surface-values-moved-from-source-height:<m>m`. Bias state (`scripts/update_bias.py`): built from Previous Runs fetched at the site with the default elevation against the station, so its bias is a forecast error at about terrain height, not a grid offset: applied as before, no rebuild. `tempest/nearterm/ensemble.py` already uses `doc["elevation"]`: nothing to do. Tests: canned response 90 m below the grid -> t2m -0.585 K and sp x exp(-g 90 / (Rd T)) exactly once, flag set; default URL carries `elevation`. tool_audit unchanged, suite 272 passed. OPEN: the live A13 check (forecast-mode pad pressure vs the nearest ASOS altimeter-derived station pressure on three days, before and after). |
| AU-4 bootstrap blocks (New_Plan 15.1; `tempest/scoring/diag.py`) | FIXED, ON by default (`--block-days 1` in score / sonde = the old intervals). Step 0 (2026-11-12): opt-in `score --daily` (headline byte-identical on a rerun of the shipped l3_c4wl seed 0 stack); `scripts/au4_autocorr.py`: daily model(unknown) - clim15 CRPS autocorrelation over 728 test days, lag 1 0.05-0.71 (u/v 0-1 km 0.05-0.10, T 12-18 km 0.71); first lag below 0.1: 1-7 days in every band except T 12-18 km (19: slow seasonal drift; 3 after a 31-day running mean is removed). Fix: `diag.headline` and `block_bootstrap_ci` take `block_days` (true day numbers via datetime64, so blocks cross the year end; 1 = as before, identical); default `diag.BLOCK_DAYS = 21` (the plan's rule, 19 rounded up to whole weeks). Intervals 1/3/5/7/10/14/21/30 days side by side in `docs/results/logs/au4_block_days.txt`: median width x1.32 / 1.46 / 1.50 / 1.64 / 1.45 / 1.60 / 1.65 of the 1-day width (T 12-18 km, u 5-12 km x2.0-2.6). Shipped stack ERA5 skill15_unknown: 17 of 19 bands stay clear of 0 at 7 and 21 days (RH 0-1 km and rh2m now touch 0; at 1 day all 19). DEVIATION from the pass rule: the plan asks 93-97 % coverage of an AR(1) rho 0.7 mean; simulated (730 days, 600 repeats) no block reaches it (1 d 0.58, 7 d 0.86, 14 d 0.90, 21 d 0.92, 30 d 0.91, 45 d 0.90: longer blocks lose less cross-cut correlation but leave fewer blocks), so the test bound is 0.88-0.97 at the chosen block and < 0.80 at 1 day. Tests: daily sums rebuild skill15; block 1 = unchanged headline, block 7 wider; AR(1) coverage. Suite 275 passed. Old interval-based verdicts are re-read in 15.4. |
| AU-6 dropped soundings (New_Plan 15.2; `tempest/scoring/sonde.py`) | DONE 2026-11-12 (fix opt-in). `sonde --partial`: keeps held-out and pool soundings with u, v, T to 5 km and surface complete; missing upper columns count in no mean (per-column mask, headline `valid=`); climatology draws fill a missing column from pool soundings valid there; Gaussian from complete pool soundings; variogram / whole-profile coverage / charts / per-station lines on complete soundings; refuses --fair-baseline, --offset-from-year, --station-calib-year, --shear-table, --extras; `_part` suffix. Flag off: shipped l3_c4wl seed 0 sonde score.csv byte-identical (`scripts/gpu_au6_partial.sh`). With the flag: 44 of 111 dropped 2024-25 00Z soundings come back (1,306 -> 1,350, 0.5 % of columns missing); the other 67 lack wind below 5 km (mostly the Feb-Mar 2024 outage) and stay out. Headline (19 bands): skill15_unknown mean +0.0102 -> +0.0105 (max band change 0.006), cov99_unknown mean 0.9914 both (max 0.003), bands clearing 0: 4 -> 5, margin over the Gaussian +0.0325 -> +0.0360. Verdict: the wind-biased dropping does not move the balloon headline beyond noise; keep the flag opt-in (default switch needs the user's go), quote plain numbers. Tests `tests/test_au6_partial.py` (low-level rule, fill only from valid soundings, no random numbers without gaps); suite 283 passed. Step 0 below: STEP 0 DONE 2026-11-12 (rule triggers). `scripts/au6_dropped.py` -> `docs/results/logs/au6_dropped.txt`: 2024-25, 2758 soundings with ERA5, 6.8-8.8 % dropped by the sonde.py rule; by tercile of ERA5 wind at 5.6 km MSL (per station x hour) calm 1.4-2.2 %, windy 10.9-16.9 %: windy minus calm +8.7 to +15.3 points, over the 5-point line. Cause is NOT humidity above 10 km as the plan guessed (0.4 %): wind missing (98 % of drops are wind or wind+T+RH, the balloon lost or burst). 122 drops are wind missing below 2 km; 98 of them are Feb-Mar 2024 at BOTH stations (a data outage: Feb 2024 44 % dropped), and Jan-Mar are the windy months, so most of the tercile gap is season + outage. Terciles within station x hour x month, Jan-Mar 2024 excluded: windy minus calm +2.0 / +1.7 points (72265), +1.5 / +1.6 (72364): under 5. Decision: the plan's rule (plain terciles) is over the line and Feb-Mar 2024 is under-sampled in the balloon scores, so do the `sonde.py --partial` fix (opt-in, per-column validity mask) after AU-5/AU-7 step 0; the pool refit only if the windy-tercile correction moves. |
| AU-5 seen-noise ERA5 truth (New_Plan 15.2; `tempest/calibrate/station.py`, `scripts/au5_*.py`) | DONE 2026-11-12 (fix = wording + standard coverage truth, no retraining). Step 1: third truth with the fresh pool de-meaned per group x tercile (`au5_fresh_pool.py --demean`, `models/station_map_mix_pool2123dm.npz`, rows `data/train/au5_l21_freshdm.npz`). Seen-noise effect (freshdm minus old, summary.csv per band): cov99 within 0.003 in every band (max 0.0027, mean -0.0003); cov90 over 0.003 in 8 bands (RH 12-18 km -0.022, v 0-1 km +0.010, v 12-18 km -0.009, u 12-18 km -0.008, RH 1-5 / 0-1 km -0.005 / -0.004, T 1-5 / 12-18 km +0.004); skill_unknown max 0.008 (RH 12-18 km); headline skill15_unknown mean +0.0305 -> +0.0300, cov99_unknown 0.9914 -> 0.9912. Rule fails on cov90 only. Drift effect (fresh minus freshdm): RH 12-18 km cov90 -0.175, cov99 -0.018, T 12-18 km skill -0.023, RH 5-12 km cov90 -0.022: the bulk of step 0 was the 2021-23 balloons drifting from the 1991-2020 line, not seen noise. Caveat: the fresh pool is thin (50-149 per group x tercile) and its spread is the 2021-23 balloons' (u, v 12-18 km sd 3.2 -> 3.6, RH 7.5 -> 9.8), so the seen-noise numbers are an upper bound. Fix done: README coverage sentence says the 99 % claim holds against the unseen-noise truth and 90 % ranges for winds and RH above 12 km move up to 0.02; ERA5 coverage claims from now on are quoted against `au5_l21_freshdm` (or with that caveat); balloon coverage stays the reference. Follow-up (after section 15, not a trial now): the station line a, b (1991-2020) misses the 2021-23 balloons by RH -8 to -11 % above 5 km and T -0.3 K above 12 km; the balloon (sonde) RH 5-12 km skill is negative (-0.015 plain), which fits; a recent-years line or a time-varying offset is the candidate. Step 0: `station.fit(ab=)` (keep given lines, refill only the pool; default None = as before), `scripts/au5_fresh_pool.py` (shipped station_map_mix a, b + leftover pool from 2021-23 balloon pairs on `data/pilot/profiles.zarr`; thin: 50-149 per group x tercile vs 450-705), `scripts/au5_splice.py` (shipped file's pre-2024 rows by year mask + rebuilt 2024-25 rows; the shipped file is in 30-Dec date blocks, not year-sorted), runner `scripts/gpu_au5_freshpool.sh`. Shipped l3_c4wl seed 0 stack (gpu_au7 flags) scored on the same 388,826 rebuilt 2024-25 rows corrected with the old vs the fresh pool (summary.csv per band): most bands move under 0.003, but RH 12-18 km cov90 0.930 -> 0.733 (cov99 0.994 -> 0.974), RH 5-12 km cov90 -0.02, u/v 12-18 km cov90 -0.01, T 12-18 km skill -0.019 to -0.022; headline mean cov99_unknown 0.9914 -> 0.9903, skill15_unknown +0.031 -> +0.032. Cause is mostly NOT seen noise: the fresh leftovers have a mean shift (balloon minus corrected ERA5, 2021-23 vs the 1991-2020 line): RH -11.2 % at 5-12 km, -8.1 % at 12-18 km, T -0.28 K at 12-18 km; spreads alike (RH 12-18 km sd 7.5 -> 9.8). The 2021-23 balloons read drier aloft than the map's line (drift / sensor era). Step 1: score a third truth with each group x tercile mean removed from the fresh pool (`au5_fresh_pool.py --demean`: new noise, no drift) to split seen-noise from drift. Tests: same data reproduces the pool, fresh pool keeps lines, splice (sorted and date-block base), demean. |
| AU-7 Gaussian margin split (New_Plan 15.2; `tempest/scoring/score.py`, `diag.py`) | DONE 2026-11-12, opt-in `score --gauss15` (recent-15-year rows of each group, month fallback below 300 rows, own random stream; headline adds `skill15_gauss15`, `margin_gauss15_{known,unknown}`, old columns untouched: point estimates of the shipped l3_c4wl seed 0 stack identical to the 20:33 run, only intervals differ by the AU-4 21-day default). Shipped stack ERA5, margin over the Gaussian (unknown site), mean of 19 bands: against a fixed-climate Gaussian (what such tools ship) +0.080, against a Gaussian of the recent climate (the shape part alone) +0.074: about 92 % shape, 8 % trend. Trend share is largest for T: 1-5 km +0.076 -> +0.045, 5-12 km +0.079 -> +0.041, 12-18 km +0.051 -> +0.039; for u and v above 1 km, sp and RH 12-18 km the recent Gaussian is the weaker baseline (margin grows +0.003 to +0.009: 15 years of rows give a noisier fit). Report both labels; `new_plan_kit/b9_gram_compare.py` numbers need the same two labels when quoted. Tests: gauss15 uses the recent rows and falls back to the month; headline adds the columns, old ones equal. Suite 277 passed. |
| AU-8 index forecast tool vs ingest (New_Plan 15.3; `tempest/ingest/index_forecast.py`, `scripts/index_bakeoff.py`) | DONE 2026-11-13 (bug fix, on; `qbo_phase=True` = switch back). Step 0: the 2012-25 bake-off tested the ridge WITHOUT QBO-phase inputs (the tool's design); the phase terms came with fix F-28 and were never hindcast. Added `regression_phase` to the bake-off (`models/au8_index_bakeoff.csv`; the plain regression column reproduces `models/index_bakeoff.csv` exactly): with the phase terms CRPS is worse for ONI at all 12 horizons (+2 to +8 %, mean 0.342 -> 0.359), qbo30 at 1-10 months (+1.6 to +5.9 %, better only at 11-12: -0.1, -3.6 %), qbo50 at all 12 (+0.8 to +4.4 %), WWV mixed (-1.4 to +1.6 %); no horizon's bootstrap interval separates. So the TESTED design ships: `index_forecast` now leaves the phase out by default and the tool is a true copy. Parity test on the shipped snapshot (`tempest_weather/assets/indices.npz`, last month 2026-09) at h = 1, 6, 12: means equal to 1e-6 (exactly), covariances within 0.2 % (ddof 1 in the tool vs 0 in ingest). Affects only `--driver-mode ridge` scores and `tempest/output/atmosphere.py`; old ridge-mode verdicts used the phase version (re-read in 15.4). |
| AU-12 conditioned pool launch times (New_Plan 15.3; `tempest_weather_v2/launch.py`) | DONE 2026-11-13 (bug fix, on): `observe()` keeps the base pool's window times cycled to n (was every member at the first one's time), the gust law is evaluated per member hour (`_regust` already could), and a windowed pool carries the flag `window-hours-not-used-by-conditioning` (the conditioned members come from the whole window's copula, so the hours are labels). Single-time launches unchanged. Test: windowed Launch + `observe()` keeps >= 4 distinct hours and carries the flag; a single-time launch does not. |
| AU-16 ONI lag draw (New_Plan 15.3; `tempest/ingest/index_forecast.py`, `tempest/scoring/ridge_drivers.py`) | DONE 2026-11-13 (bug fix, on; inactive today, no shipped model has `oni_lag3`): new `index_forecast.draw_lag`: the lag month is the observed value when it is known at the origin (h <= 3), else a draw at h - 3 whose standardised error has the hindcast-residual correlation of the two horizons with the target month's draw (was an independent draw). Tests: at h = 6 on a synthetic AR(1) table the drawn pair correlation 0.60 vs observed forecast-error correlation 0.61 (rule: within 0.1); lag observed at h = 2 is used as is. |
| AU-14 shuffle template years (New_Plan 15.3; `tempest/scoring/score.py`) | DONE 2026-11-13 (opt-in): `score --template-before-year Y` takes the `--template-cell` / `--pooled-template` templates from years before Y (export: 2021); prints a header line and adds `_tbY` to the stem; default = first test year as before (no number changes). Runs that claim "as shipped" use 2021 from now on. |
| AU-9 humidity site shift (New_Plan 15.3; `tempest_weather/_core.py` site_shift, `tempest/generator/sample.py` to_site) | DONE 2026-11-13 (bug fix, on; switch back `RH_SHIFT_BLEND = True` in each module): the humidity keeps the dew point fully, `rh * es(t_old) / es(t_new)`; the height fade acts once, through T (was applied a second time to RH). Hand value (500 m higher site, T 280 K, RH 50 % at 1.5 km): 54.30 % (old 51.58 %), both paths agree (`tests/test_au9_rh_shift.py`). Sonde check `scripts/gpu_au9_rhshift.sh` (pass: RH 0-1 km and 1-5 km skill15 not worse than the shipped run by more than 0.003): PASS, skill15_known RH 0-1 km -0.0057 -> -0.0057 (+0.0000), 1-5 km +0.0045 -> +0.0045 (+0.0001), other RH bands and rh2m unchanged, cov99 unchanged. The balloon sites sit a few metres from their grid points (Santa Teresa 1254 vs 1262 m), so the change is tiny there; it matters at tool sites with large offsets (about 4 RH points at 1.5 km for 500 m). |
| AU-15 near-term wind below the first level (New_Plan 15.3; `tempest/nearterm/ensemble.py`, `tempest/profiles/to_heights.interp_columns`) | DONE 2026-11-13 (bug fix, on; switch back `ensemble.LOG_TO_FIRST_LEVEL = False`; not used by the shipped tool): new opt-in `interp_columns(..., log_first=True)` interpolates in ln(height) between each column's lowest two valid levels (10 m anchor -> first level above ground); the ERA5 store keeps the default (off, unchanged). Test (`tests/test_au15_log_anchor.py`): neutral log profile, 10 m -> 400 m, error at 100 / 150 / 200 / 300 m 0.00 m/s (old line -2.9 / -2.8 / -2.4 / -1.3); levels above the first unchanged. |
| AU-13 Santa Teresa launch height (New_Plan 15.3; `tempest/calibrate/station.py` read_igra / station_pairs / CLI) | DONE 2026-11-13 (bug fix, on for new fits; switch back `--launch-tol -1`; the function default stays off): `read_igra(..., launch_height, tol_m=30)` drops soundings whose first level is more than 30 m from the listed launch height and prints the count (`tests/test_au13_launch_height.py`). Step 0 (`scripts/au13_step0.py`, `models/au13_step0.csv`): 914 soundings dropped (Santa Teresa 1991-95, launched about 60 m off), 182 of 2,816 map-A entries move by more than 2 bootstrap sd (max 6.4 sd, RH bias up to 2.5 points in groups 1 and 7). Verdict: retrain candidate; refit of the shipped station map + dataset rebuild + retrain queued after the section 15 gate (a new trial). |
| AU-11 batch width floor of the range map (New_Plan 15.3; `tempest/calibrate/spread.py` _standardise, `_core.py`) | CLOSED 2026-11-13, no change: step 0 (`scripts/au11_step0.py` via `scripts/gpu_au11_floor.sh`: the shipped l3_c4wl seed 0 ERA5 score, flags as gpu_au1_fair without --fair-baseline, with `_standardise` wrapped to count) found the floor binding in 0 of 10,000 rows x every column (2 apply calls, known and unknown), RH included; rule (under 0.1 % outside RH) -> close. Tool (N = 1) and scorer therefore apply the same map. `models/au11_step0.csv`. |
| AU-18 false shear step at 100-150 m (New_Plan 15.3; `tempest/profiles/to_heights.py` profiles_from_levels) | DONE 2026-11-13 (opt-in, off; the built stores keep 100): step 0 (`scripts/au18_step0.py`, raw era5_em80 + CDS, 1995 / 2010 / 2024, every 4th kept hour, `models/au18_step0.csv`): 18.2 % of columns have a pressure level at 100-150 m AGL (the same each year); their 100-150 m shear p50 0.0075 vs 0.0056 /s and p99 0.0384 vs 0.0317 /s for the rest (+21 %); with level winds only from 150 m up the flagged rows give p99 0.0257 (below the rest: the line from the anchor smooths them). It shows, so `profiles_from_levels(..., wind_from=150)` / `to_heights --wind-from 150` added for the next planned store rebuild (test `tests/test_au18_wind_from.py`: the 120 m level no longer sets 150 m; columns without such a level identical). |
| 15.4 old verdicts re-read after AU-1 / AU-4 (New_Plan 15.4; `scripts/au15_4_scan.py`, `docs/results/au15_4_reread.md`) | DONE 2026-11-13. Scan of section 9, LOOP3 and AUTOPILOT: 62 intervals, 25 exclude 0 within one width (14 verdicts). No verdict flips: FAIL / KILL / MISS / CLOSED cannot (wider intervals only make 'excludes 0' harder; AU-1 cancels in model-vs-model). To confirm (|mean| / half-width below the x1.65 widening of 21-day blocks): IL-207b seed 1 (TCS -0.075 [-0.140, -0.009], ratio 1.15; CONFIRMED -> seed 0 holds, seed 1 to confirm; not adopted, ASK_LATER 24), A1 step 2 MAF +0.037 [+0.007, +0.067] (1.23; the option it allowed was never built), IL-198 12-18 km +6.4 % (1.75, crosses at the x2-2.6 of T 12-18 km), C6's CRPS side note (FAIL stands). N1 PASS stands (threshold = p2f + 0.001, a difference; AU-1 shift cancels). Mode F / AV1 / AV2 climate: pool of thousands of rows, bonus <= ~0.25 %, negligible. README skill15 overstated by ~0.013 (AU-1 step 5); wording waits for ASK_LATER 27. Earth-GRAM: AU-7 two labels. 2026 final test: caveat only (fair baseline + 21-day blocks when run). | **SECTION 15 GATE COMPLETE** (15.1-15.4). Suite 431 passed, tool_audit served 120 refused 0 (2026-11-13 01:30) |
| CHORUS stage 1 (New_Plan 14.4; rows `scripts/chorus_stage1_rows.py`, runner `scripts/cpu_chorus1.sh`, verdict `new_plan_kit/b9_chorus_stage1.py`, rule in its header before the run) | **MISS by the pre-set rule.** Shipped-recipe own-box mode F fed the closed-rule mix of the newest run and the 36 h older run (12Z start 36 h before; no 12 h older run in wb2_hres_v2, deviation stated before the run; weights per lead x variable x height from 2018-20 moments, w_new median 0.70-0.83) vs the newest run alone, 2022, same rows. Mix better at every lead in all 4 box x seed runs: NM/TX -0.9 / -1.1 / -1.4 / -2.2 % (s0), -0.8 / -1.1 / -1.3 / -2.3 % (s1); Denver -1.1 / -1.0 / -1.2 / -3.5 % (s0), -1.1 / -1.0 / -1.1 / -3.5 % (s1). 7 d interval below 0 in all 4 (e.g. Denver s0 -0.142 [-0.292, -0.006]); 5 d interval crosses 0 in all 4 (NM/TX s0 [-0.098, +0.019], Denver s1 [-0.071, +0.007]); 1 and 3 d within the 0.5 % clause (all better). cov99 up +0.001 to +0.014 (largest Denver 7 d). Note: network, PIT recal and range map were fitted on newest-run inputs only, so the mixed 2022 profile is off their training world | Not adopted. Benefit with an interval excluding 0 (7 d, all runs) -> per section 13's standing note one more variation logged as AV24 (mix in every year, network and calibration refitted on mixed inputs); CHORUS stage 2 waits | `docs/results/logs/kit_b9_chorus_stage1.log` |
| STRAND stage 0 (New_Plan 14.5; `new_plan_kit/b10_strand_stage0.py`, rule in its header before the run) | **GO by the pre-set rule.** ERA5 store 1991-2020, 377 points, 164,368 three-hour window starts; cells point x month x start hour with 0.05 <= P_indep <= 0.95. P(10 m wind under L for 3 h running), real vs independent hours: L 5 m/s 0.637 vs 0.409 (mean |diff| 0.228, p90 0.311); 8 m/s 0.894 vs 0.796 (0.099); 10 m/s 0.943 vs 0.885 (0.058). Every gap is positive: drawing hours independently understates calm windows, most at the tight limit. STOP line was 0.02 | STRAND stage 1 (aged noise + moving templates, climate and past mode first) is cleared to build; queued after AV4 / AV6 / AV24 per 13.5 | `docs/results/logs/kit_b10_strand_stage0.log` |
| AV4 C6 factor in the premise cells only (New_Plan 13.1; `scripts/c6_lagged_spread.py --step34 --cells 0 1 2 6`, opt-in flag, rule in the header before the run) | **MISS by the pre-set rule.** Same rows and members as C6 (2500 fit 2016-20, 2500 test 2022, 36 init dates). PIT distance 0.0545 -> 0.0526, change -0.0019 [-0.0037, +0.0001] (C6 all cells: -0.0018 [-0.0051, +0.0007]); CRPS -0.48 % [-0.92, -0.13] (better, interval excludes 0). u / v / T PIT 0.061->0.060, 0.050->0.048, 0.053->0.049. Factors a 0.72-0.83, b 0.13-0.21; test f median 0.97-0.99, p95 1.40-1.49. Note: the script's legacy C6 'FAIL' line also prints; the AV4 line is the verdict | Not adopted. PIT interval misses by 0.0001; CRPS benefit excludes 0 -> per section 13's standing note AV25 logged (more test init dates: 2021 + 2022) | `docs/results/logs/c6_av4_cells.log` |
| AV25 AV4 on 2021 + 2022 test dates (New_Plan 13.1; `scripts/c6_lagged_spread.py --step34 --cells 0 1 2 6 --test-years 2021 2022`, opt-in, fit rows unchanged, 5000 test rows, 73 dates; log `docs/results/logs/c6_av4_cells.log`) | MISS 2026-11-13 05:19 by the pre-set rule (AV4's): PIT distance 0.0309 -> 0.0336, change +0.0027 [+0.0001, +0.0041] (worse, interval above 0); CRPS -0.33 % [-0.58, -0.07]. Per variable PIT u 0.026->0.030, v 0.027->0.030, T 0.040->0.041; test factor median 0.92-0.96 (shrinks spread on 2021) | C6 / AV4 / AV25 line CLOSED for calibration: the PIT benefit did not hold over more dates. Only a CRPS benefit is left; a CRPS-only rule is the user's call (ASK_LATER 28), so no further AV row. |
| AV6 (a) fixed 10 m wind widening per site, no tracking (New_Plan 13; `new_plan_kit/b11_av6_fixed_widen.py`; G1-5 data: WB2 IFS ENS 50 members at the points nearest TCS / MAF vs ASOS 00 UTC, leads 1-7 d pooled; factor = CRPS-best on a 1.00-3.00 grid over 2016-22, scored 2023-24, 21-day blocks) | PASS 2026-11-13 05:55 by the pre-set rule: TCS factor 1.35, CRPS 1.2902 -> 1.2683, change -0.0218 [-0.0397, -0.0043], 90 % coverage error 0.238 -> 0.120; MAF factor 1.55, CRPS 1.3154 -> 1.2709, -0.0444 [-0.0683, -0.0202], coverage error 0.273 -> 0.121. Beats the G1-5 tracker on CRPS at both sites (tracker 1.274 / 1.273) | Confirms the G1-5 reading: the raw ENS needs a fixed widening, not tracking. Nothing adopted: the tool does not serve raw ENS members, and its wind is already widened from observed spread (IL-101, bias.widen_wind). Part (b) (the same test on the tool's forecast-mode output) is blocked on disk: the HRES archive mode F reads ends 2022-12, so there is no tool output for 2023-24. |
| AV24 CHORUS mix in every year, mode F retrained (New_Plan 13; `scripts/cpu_av24.sh`, `scripts/chorus_stage1_rows.py --all-years`, `new_plan_kit/b12_av24.py`; stage 1 weights, small recipe, seeds 0 / 1, NM/TX and Denver, scored on the stage 1 2022 rows vs the newest-run networks, 21-day blocks) | MISS 2026-11-13 07:22 by the pre-set rule (stage 1's): mix retrained better at EVERY lead in all 4 runs (1 d -1.6 to -2.4 %, 3 d -1.3 to -1.6 %, 5 d -0.8 to -1.6 %, 7 d -1.3 to -2.4 %); 1 and 3 d intervals below 0 in all 4 (e.g. Denver s0 1 d -0.0435 [-0.0662, -0.0209]); 5 d below 0 only in Denver s1 (-0.0449 [-0.0902, -0.0038]); 7 d crosses 0 in all 4 (e.g. NM/TX s0 -0.0453 [-0.1163, +0.0160]); cov99 change within +/-0.003 | Retraining on mixed inputs turns stage 1's long-lead-only gain into a gain at all leads. Benefit with intervals excluding 0 (1 and 3 d), so per the section 13 note one more variation: AV26 (pool 2021 + 2022 for the long-lead intervals). |
| AU-10 above_top "climatology" (New_Plan 15.3; `tempest_weather_v2/readers.py`) | DONE 2026-11-13: docstring corrected ("climatology" is an alias of "hold": T and p continue from the top value along the standard lapse rates; no true standard-atmosphere switch, it would put a jump at the top). No number changes. Test: the two policies return identical air and wind arrays below, at and up to 30 km above the top. |
| AU-17 Launch.stale naive time (New_Plan 15.3; `tempest_weather_v2/launch.py`) | DONE 2026-11-13 (bug fix, on): a naive `now` is taken as UTC (it raised TypeError). Test: naive 1 h and 7 h after creation give False / True. |

Found while building: the switches this plan named (`shuffle_train`, `day_code`, `target_shear`, `group_rank`, `t_update`, `SIGMA_SCALE`) do not exist, the kit works from outside the core; C6 needs no download (`data/raw/wb2_hres_v2` has 2016-22); G2-1 cannot be checked from disk; G2-4 needs a radar download first.

Next session, in order: (1) README Part 3 "RESULTS BLOCK", steps 1-4; (2) full G2-7 run; (3) README Part 5, top to bottom.

---

## 10. Secondary ideas (added 2026-11-11; nothing here has been run)

Where they come from: the results in section 9, the logs, the code, and outside research. The long list
of 21 ideas with the attacks on each is in `Secondary ideas.md`. All eight are measurement items: a kit
script in `new_plan_kit/` that works from outside the core, default output bit-identical, log to
`docs/results/logs/kit_b4_*.log`. Adoption stays with the user (ASK_LATER 22). Rules for all: fit on
<= 2022, test on 2023-25, never 2026; two seeds; day-block bootstrap; CRPS noise 0.0009; 12 threads at
low priority. Template for every script: `b3_il207b_site_shift.py` (about 2-3 s per pool hour).

The direction: what worked was (a) simple statistics beside the network and (b) real measurements on
launch day. What limited both was the same thing: the TCS-type prior is too calm by day, so the update
that follows it comes out too narrow. So: fix the centre first, then update, then use more of the
measurements already on disk.

### 10.1 Three structural ideas

**S1. Site map first, update second** (`b4_debias_then_update.py`)

| | |
|---|---|
| What | Apply the per-site speed map to the pool BEFORE the observe update, then use the variant B gain (rho = `obs.effective_gain`) for neighbour reports. Fit the map by matching distributions per season x hour block (6 cells) on all ASOS years <= 2022, not on 300 paired hours. |
| Why here | `launch._speed_space_update` ranks the report inside the prior pool's own speed distribution. A prior that is too calm puts the report in the far tail and the result is too narrow: TCS covers 0.82 even with its own report, and variant B misses the floor only with TCS as target (LRU 0.81, ONM 0.75). IL-207b alone lifts TCS 0.81 -> 0.85. The two confirmed candidates fix two halves of one fault. |
| Where in the code | No core change. `Launch(site_cal=...)` exists; `_apply_site_cal` runs at the end of `_ensure_pool`, and observe reads its prior after that. The kit builds the map and passes it in. |
| Test | Targets TCS and MAF. Arms: tool / B alone / map alone / map + B, for own-station and each neighbour (LRU, ONM -> TCS; FST, PEQ -> MAF). 200 test hours per pair, 2 seeds. |
| Pass rule (set now) | Map + B: coverage >= 0.80 at every pair in BOTH seeds, CRPS not worse than B alone by more than 0.0009 at any pair, and each cell factor within 0.05 between seeds. |
| Kill rule | Either seed misses 0.80 at any pair -> closed, keep B and the map as separate opt-ins. |
| Cost | About 2 h CPU per seed. No download. |
| Risk | The map is fitted at airports; at the pad it is a 30 km stand-in (ASK_LATER 24). S2 answers that. |

**S2. Regional day / night shape for sites with no record** (`b4_regional_shape_loso.py`)

| | |
|---|---|
| What | For each of the 9 ASOS stations fit the 6-cell factors (as S1), divide by their all-hours mean to keep only the SHAPE. For a held-out station apply the median shape of the other eight, level 1. Score at the held-out station. Monahans and Las Cruces (USCRN, not airports) are extra held-out sites. |
| Why here | The TCS error is a too-flat daily cycle, not an offset: all-hours quantiles are right (`e1_extremes_coverage.log`), daytime bias is +1.44 m/s (IL-207). If this comes from the ERA5 training data it is regional, so the shape should transfer. `p7_site_model.log` shows a borrowed constant already helps on average (0.960 -> 0.940, 6 of 8) but hurts PEQ and MONAHANS, because the level is site specific (0.92-1.20). Hence shape only. |
| What it decides | ASK_LATER 24. If the shape transfers, the pad gets it without a pad record. If it does not, the TCS factor is an airport effect and must not be used at the pad. |
| Step 0 (10 min) | From existing pools: day / night bias per station. If the night bias is not opposite in sign to the day bias at 6 or more of 9 stations, stop: the premise is wrong. |
| Pass rule (set now) | Mean CRPS better with an interval that excludes 0, at least 7 of 9 ASOS stations better, no site worse by more than 0.010, and both USCRN sites not worse. |
| Kill rule | Fewer than 6 of 9 better, or any site worse by more than 0.030 -> closed; site maps stay per site only. |
| Cost | About 4 h CPU per seed (9 stations x 560 pool hours). No download. |
| Risk | All fit sites are open and flat. Cross-check only: `wtk_pad_factors.log` (pad / airport 0.83 at night, 0.98-1.00 by day) agrees in direction. |

**S3. Whole radar profile, thinned** (`b4_radar_thinned.py`)

| | |
|---|---|
| What | Condition on the radar wind up to 5 km instead of 0.5-2 km, but at one level per error length (every 1000 m: 500, 1500, 2500, 3500, 4500) and with a larger sigma (sweep 3.0 / 4.5 / 6.0). |
| Why here | "radar+all to 5 km" already gives +17-20 % at 5-12 km against +7-15 % for four levels, but covers only 0.49-0.61 at 2.5-5 km, so it could not be adopted. The C4 fit points to the cause: radar errors are tied together over 901 m in height, while the update treats ten levels 500 m apart as independent. Changing sigma alone did nothing (C4 sweep). Thinning to the error length and inflating is the standard cure for correlated errors and needs no error matrix. |
| Where in the code | No core change: `observe_radar(levels_m=..., sigma_ms=...)` takes both. The kit adds a `--levels` option to a copy of `scripts/p3_vad_condition.py`. |
| Test | Choose levels and sigma on EPZ 2021-22 hours. Score once on EPZ 2023 hours and on MAF (MAF takes no part in the choice). |
| Pass rule (set now) | Coverage 0.85-0.95 at 2.5-5 km AND CRPS at 5-12 km at least 2 points better than the shipped four levels, at both sites. |
| Kill rule | No setting reaches coverage 0.85 on the EPZ choice hours -> closed for good (a full error matrix would need a core change; not worth it). |
| Cost | About 1 h CPU. Radar files are on disk (EPZ 611, MAF 133). |
| Risk | The radar is biased by +1.3 m/s near 5 km (C4); if the top level hurts, drop 4500 m and say so. |

### 10.2 Five other ideas

| # | Idea | Why here | Test and rule (set now) | Cost |
|---|---|---|---|---|
| O1 | **Two neighbours at once** (`b4_two_neighbours.py`). Merge the reports of two neighbour stations into one report (weights = variant B gains, second gain cut by the correlation between the two stations) and call `observe` once. Run after S1, with the map on. | `observe_latest` stops at the first usable station. One neighbour gave 1.437 -> 1.313 (`p1_diff_assim.log`). Outside work: a few chosen neighbours give nearly the full gain, but only if their shared error is counted. | TCS from LRU + ONM, ELP from LRU + ALM. PASS: CRPS better than the best single neighbour with an interval that excludes 0, coverage >= 0.80, both seeds. Else closed. | 1.5 h CPU |
| O2 | **Radar over distance** (`b4_radar_distance.py`). Score the Holloman radar (HDX, about 145 km away) against the EPZ balloons and compare with the EPZ radar on the same hours. | The pad has no radar: HDX is about 80 km away, EPZ about 125 km. The +31 % was measured with the radar beside the balloon. 127 common HDX / EPZ hours are on disk. | Measurement only: gain at 2.5-5 km and 5-12 km with intervals, and coverage. If coverage < 0.85, the sigma that restores it is the distance term for `observe_radar`. Caveat: all hours are 23 UTC. | 40 min CPU |
| O3 | **Launch-week factor** (`b4_launch_week_replay.py`). Replay: with k = 3, 7, 14 days of 10 m record before the test day, update the site map by a decaying average (weight 1/30 per day, as in `tempest_weather/bias.py`). | This is the pad's own way to a map: an anemometer set up a week early. NCEP has run this method since 2006. It also covers G1-5 for the climate and past modes. | TCS and MAF, starting from the S2 regional shape (as at the pad). PASS: at k = 7, CRPS better than the shape alone with an interval that excludes 0 at both sites, coverage not lower. Report k = 3 and 14 too. | 2 h CPU |
| O4 | **Analog referee and tail fix** (`b4_analog_tail.py`). Keep the analog ensemble (40 most similar hours of the station record) as the bar to beat in every 10 m table, and test one fix for its weak tail: add the gap between the forecast and the analog mean of the predictor. | It beats tool past by 11-23 % at TCS and MAF (`gw_analog.log`) but its median for winds >= 8 m/s is 7.71 against 10.16 observed. Outside work reports this tail bias and this fix. Works only at sites with a record, so it is a referee, not a pad tool. | PASS: under-prediction at >= 8 m/s halved (2.45 -> <= 1.2 m/s) with overall CRPS loss <= 0.0009, TCS and MAF. Then also score S1 against it. | 30 min CPU |
| O5 | **ECC ordering in forecast mode** (`b4_ecc_modeF.py`). Order the members across heights by the forecast ensemble's own ranks instead of the Schaake history. Depends on ASK_LATER 21. | `m4_ecc_test.log`: variogram score 1-3 % better at leads 1-7. It only reorders members at each height, so per-height CRPS cannot change; this separates it from the failed shuffle changes. | Two seeds, 2023-25. PASS: variogram score >= 1 % better at every lead 1-7 with intervals that exclude 0, shear rate within 10 % of the Schaake value, and the IL-128 inflation check passes. Else keep Schaake. | 1 h CPU |

### 10.3 Order

1. S2 step 0 (10 min), then S1 and O4 side by side.
2. S2 full run; S3 and O2 together (same radar files).
3. O1 and O3 only after S1 and S2 have a verdict (both build on the map). O5 after ASK_LATER 21 is answered.

Looked at and dropped (reasons in `Secondary ideas.md`): radar bias by height, 10 m -> 300 m taper fit
(data blocked), T-rise and unstable-layer fixes, spread per hour block, run-to-run disagreement,
physical gust law (already shipped: `MEASURED_GUST_LAW`), persistence centre (that is G1-6).

### 10.4 Five ideas that change how the AI system works (second set, 2026-11-11; nothing run)

The first set was rejected by the user and is replaced. Attack rounds, the facts behind each idea and
the reasons the first set was dropped are in `Secondary ideas.md` part 6. All five use data already on
disk and run on this laptop. Defaults stay bit-identical; a trained model gets a new name. Two
training seeds; fit and test years as stated per idea; never 2026.

| # | Idea | Why here (numbers from our logs) | Step 0, pass and kill rule (set now) | Cost |
|---|---|---|---|---|
| N1 | **Cross-fitted members** (`b5_crossfit.py`; option `holdout_fold` in `train.split`, default off). Each of the 4 members leaves out different 2-year blocks (about 4 of 33 years), trains on the rest with a fixed step count, and gets its range map from its own held-out years. Mode F part: leave one year out over 2016-22. | Today no member trains on 2021-23; F-7 puts about 0.003 skill15 on two recent years. Calibration uses 3 years; this gives 16. Mode F and ENSF2 are judged on 2022 alone; this gives 7 test years. | Step 1: data <= 2020 with fixed steps must reproduce p2f within 0.0006. PASS on 2024-25, both seeds: ERA5 skill15 >= +0.0287, balloons not worse by more than 0.0013, coverage error not worse by more than 0.0004. KILL: gain under 0.0006 in either seed. Mode F part kept either way. | 1 h GPU, 4 h CPU |
| N2 | **One forecast-error model for the world** (`b5_modeF_world.py`). Mode F trained on HRES / ERA5 pairs at 7483 world points (`data/raw/wb2_hres_global`, read by no model code), no lat / lon. Arms: as it is; as the start for 300 steps on the box rows. | Mode F is trained per box. Forecast error depends far less on the place than climate does; pooled fits worked. | Step 0: at least 300,000 matched pairs; box Mode F loses under 1 % with 13-level input and under 0.5 % without lat / lon; else stop. PASS: as it is within 1 % of each box's own model at every lead (NM/TX and Denver); fine-tuned better with an interval excluding 0 at 3 of 4 leads. KILL: worse by more than 3 % at both boxes. | 2.5 h CPU |
| N3 | **Pre-training on stand-in forecasts** (`b5_modeF_pretrain.py`). Stand-in forecast = ERA5 truth minus a whole real error profile of the same lead, season and hour bin; 33 years; then fine-tune on real pairs. Written in PHASE4_FORECAST line 281, never run. | Mode F sees 5 fit years and two start hours. | Step 0: fit on 1, 2, 3, 5 real years; 3 -> 5 gains under 0.5 % -> closed. PASS: better than from-scratch at leads 5 and 7 with an interval excluding 0, leads 1 and 3 not worse by more than 0.5 %. KILL: no gain at lead 7. | 20 min, then 2 h CPU |
| N4 | **Optional sources in one network** (`b5_modeF_mask.py`). ENSF2 trained with the 24 ensemble inputs zeroed on 30 % of rows plus an "ensemble present" bit. | ENSF2 is confirmed (-1.9 to -3.1 %) but needs the feed at launch; ASK_LATER 21 is a choice between two models. | PASS: with the feed within 0.5 % of ENSF2, without it within 0.5 % of HRES-only, both boxes. One extra arm at width 192 if it misses. KILL: either side worse by more than 1 % in both seeds. | 30 min CPU |
| N5 | **One network from day 1 to climate** (`b5_modeF_alllead.py`). Lead as a continuous input (IL-79, never run), rows beyond 7.5 days used, plus rows with a random same-season profile at the lead cap, so the network learns the fade to climate. | Leads sit in four bins, rows beyond 7.5 days are dropped (`lead_bin`), the hand-over to climate is an untuned ramp in `router.py`. | Step 0: at least 20,000 rows beyond 7.5 days, else only the continuous-lead half. PASS: leads 1-7 within 0.5 % of the binned model; beyond 7.5 days better than router mix and climate model; never worse than climate. KILL: worse by more than 1 % at leads 1-3. | 1.5 h CPU |
| N6 | **Full-size Mode F on the GPU** (`b5_modeF_big.py`). Width 512, depth 4, 4 members, all 44 heights of the forecast profile, trained on the N2 world pairs (plus N3 rows if N3 passes), then 300 steps on the box rows. | Mode F was cut to width 128 / depth 2 / every 4th height only because it overfitted within 250 steps on the box rows (IL-77: validation 0.53 -> 0.64, train 0.27). With 100 times the rows that reason is gone. N2-N5 are CPU jobs only because of this cut. | Needs N2 step 0 (pair count). Step 0: validation CRPS at step 2750 not above step 250, else stop. PASS: at least 1 % better than the shipped small model at every lead with an interval excluding 0, both boxes, both seeds, cov99 within 0.003. KILL: not better at 2 or more leads. | 2 h CPU rows, 30 min GPU |
| N7 | **One generator for climate and forecast** (`b5_one_generator.py`; option `optional_inputs`, default off). The main generator gets the forecast profile, the lead and a "forecast present" bit as an optional input group, blank on climate rows. Trained on the 33 ERA5 years with real pairs and N3 stand-in rows mixed in. | Mode F is a separate small net with 5 fit years; the main net has 33 years, the shear loss and the full calibration stack. One model to ship instead of two. Run only after N6 shows that size helps. | PASS: climate mode within 0.0006 skill15 of p2f AND forecast mode not worse than the better of N6 and the shipped model at any lead; both seeds. KILL: climate mode worse by more than 0.0015. | 1 h GPU, 2 h CPU |

Order: N3, N2 and N5 step 0 and all of N4 first (CPU, under 2 h together). N1 when the GPU is free;
its Mode F part before N2-N5 are judged. N3 full run only if step 0 passes. Honest odds: N4 high;
N1 test bed near certain and skill gain medium to high; N2 and N5 medium; N3 low to medium.

---

## 11. One new idea: RA, the real-air gap model (added 2026-11-12; step 0 measured, nothing else run)

Asked for: one idea that lifts the whole system, built from what already worked, improved in rounds.
This section keeps every round: the first form (11.2), each improvement in the order it was found
(11.3), the final form (11.4), what was measured today (11.5) and the tests with rules set now (11.6).
Nothing in the tool changes. Defaults stay bit-identical. The idea is opt-in until it passes.

### 11.1 The idea in four lines

1. Everything we train treats ERA5 as the truth. A rocket does not fly through ERA5. It flies through
   real air on one thin path, the way a balloon does.
2. On disk there are 986 balloon stations worldwide, and each one sits about 10 km from a point where
   we already hold 7 years of forecasts and ERA5. No model code has ever joined them.
3. Train ONE world model of the **gap**: real air minus model air, as random draws, given the model
   profile, the hour and a few facts about the site. Learn it from forecasts, which never saw the balloon.
4. Add one gap draw to every member the tool makes, in every mode:
   **real member = model member (today's tool, unchanged) + gap draw (new)**.

### 11.2 Version 0, the first form (before any check)

"World Mode F with the truth swapped": take the N2 world model (forecast in, ERA5 out) and train it
with the real balloon as the target instead. Reasons, all from our own logs:

| What our logs say | Where |
|---|---|
| Every shape limit left is an ERA5-against-reality gap: joint wind-shear extremes 0.07 against 0.17 real, and ERA5 templates cap them at 0.068; calm air 1.2 % in ERA5 against 6.1 % at stations; TCS too calm by 1.44 m/s; real shear at least 1.33 x ERA5 | handover section 7, review trap 7, IL-207, C5 |
| Fixing those with fits at 2-3 sites failed again and again (few balloons, many free numbers) | review "what has failed" 2-4, S1, S2, O1, O3 |
| World data plus a short local fit works: better at 16 of 16 checks, and the control showed the gain is the world start | N2 full run |
| The largest skill we have is "truth given a rich anchor" (forecast mode 0.69 at day 1; ERA5 anchor -3 to -20 % at the ground) | handover sections 1, 7 |
| Changing the network body gives nothing; more rows and richer inputs do | review "what has failed" 1, pattern P1 |

Version 0 keeps the network and the recipe that work. It changes only what the network is told the truth is.

### 11.3 The improvements, in the order they were found

Each one came from attacking the version before it.

| # | Attack on the version before | Improvement |
|---|---|---|
| 1 | Is the data really there? The review parked the "detail network" (G3-1) partly because ERA5 beside the world's balloons was "not confirmed on disk". | **Checked today: it is there.** `points.npz` in `data/raw/wb2_hres_global` and `data/raw/era5_global` carries a balloon station id per point. 986 stations have a balloon file in `data/igra_heights`; their world point is 9.7 km away in the median (worst 17 km). El Paso, Midland and Denver are among them. About 2.9 million forecast-balloon pairs for 2016-22 are on disk now. Mode F world was fitted on 0.645 million rows. |
| 2 | ERA5 has already used these balloons, so "ERA5 minus balloon" looks smaller at a balloon site than at the pad (mistake B30). | **Learn the gap from forecasts, not from ERA5.** A forecast made 6 h or more before the launch cannot have seen that balloon. This is the trick of the C5 referee, used for training. |
| 3 | If the gap is learned from forecasts, it is mixed with forecast error. Then it cannot be used in climate or past mode, where there is no forecast. | **Measured today (11.5): the gap does not depend on the lead.** Real error squared = model error squared + a constant. At 1.5 km the constant is 1.81, 1.82, 1.84 m/s at leads of 1 day, 3-5 days and 7-10 days, and ERA5 against balloons gives 1.89. So the gap is a separate, added part. One gap model then serves every mode: forecast, past and climate. This turned version 0 (a second forecast model) into the final form (one added layer for the whole tool). |
| 4 | A truth swap makes the ERA5 headline fall by design (review trap 1), and it would redo a stack that is calibrated and shipped. | **Add, do not replace.** The model member stays exactly as it is, so every ERA5 score stays as it is. The gap is added on top behind one switch (`truth="real"`, off by default). The user decides later which truth the tool serves. |
| 5 | A simple rule usually ties a network here (pattern P4). The gap may be just "add 1.8 m/s of noise". | **The simple rule is built first and is the bar.** Arm A1 = add independent noise, one size per height band (6 numbers). The network (arm A2) must beat A1 or it is dropped, and A1 ships instead. Either way the tool gains a measured real-air widening, so the work cannot end with nothing. |
| 6 | Where could a network beat 6 numbers? Only where the gap depends on something. | **Give it the things the gap is known to depend on, all available at any place on Earth:** the member's own profile (speed, shear, stability: C1 showed the missing shear follows stability, c = 0.12 to 0.33), local solar hour, day of year, site height, and "site height minus model terrain height". No latitude or longitude (N2 step 0: leaving them out costs under 0.5 %). This is richer input, not a bigger body. |
| 7 | Balloons fly only at 00 and 12 UTC. The tool must cover all 24 hours (user rule). | **World pooling covers the day.** 00 UTC is evening in New Mexico and morning in Japan. Counted today: launches fall in every 3-hour bin of local solar time (shares 5.5 % to 23 %). With solar hour as an input and no longitude, the hours missing at one site are learned from others. Risk: hour and region are tied together; stage 4 tests it by leaving out a whole sector. |
| 8 | Draws per height have no link between heights. Our best shape gains came from borrowing the order of real profiles (the shuffle). | **Order the gap draws by the ranks of real gap profiles** (balloon minus forecast, whole profiles, from the fit years). These are real air, from hundreds of stations, so they are not held to the ERA5 ceiling of 0.068. Whole profiles only; rank sources are never mixed (review trap 3). |
| 9 | The forecasts on disk have 13 levels; the tool has 44 heights. A gap measured against a 13-level profile would count "detail between levels" twice, because the tool's members already have some. | **Coarse gap first.** Fit the gap only at the heights where the 13 levels really sit, plus 10 m. Spread it smoothly to the 44 heights. That is a lower bound of the real gap and adds no false shear. The fine detail between levels stays with the shear map, and with 1-second soundings later (the parked G3-1). |
| 10 | The pad has no record, and 87 % of the wind-driven apogee spread comes from 0-300 m (P6). Site patches failed because each was fitted at one airport. | **The ground is inside the same model.** Each balloon file has the surface report and wind at 10-300 m (present in 99 % of profiles; partly interpolated from the surface report and the first level). That is real low-level wind at 986 sites, not at 9 airports. The model learns how real low wind differs from model wind by terrain and hour, and is then used at the pad with zero pad data. Measured today: real calm air (under 1 m/s) 17.3 %, forecast 9.5 %, ERA5 11.0 %. |
| 11 | `observe` ranks a real reading inside a pool of model air. Where that pool is too calm the result is too narrow (TCS covers 0.82 with its own report). S1 tried to repair this per site and failed on seed spread. | **With the gap added, a reading is compared with real-air members.** Centre and spread are repaired first, for every site at once. This is a later test (stage 5), not a claim. |
| 12 | 2.9 million pairs sounds large, but they come from only 426 valid times (213 at balloon hours). Days count, not readings (review trap 4). | **One small download makes it 24 times larger:** the same public forecast archive, read only at the 986 station points, for every 00 and 12 UTC of 2016-22 at five leads. About 3.5 GB (budget 50 GB, about 5 GB used). The test year then has about 730 balloon times, not 30. |
| 13 | Where do the new AI methods come in, if the body stays? | **Three of their principles, none of their bodies:** (a) train against the instruments themselves, not against an analysis (the direct-observation weather models of 2024-25); (b) one model trained on the world, then a short local fit (how the large weather models are adapted; our N2 is the small proof); (c) one-step random generators trained on a proper score (the family our engression recipe already belongs to). These are named from memory and were not re-read today. |

### 11.4 Final form

```
any mode (climate / past / forecast)          today's tool, unchanged
        |
   model member  (44 heights, ERA5-like)  ----------------------------->  truth="model" (default)
        |
   RA gap model  (one for the world)
     inputs : the member's own profile, solar hour, day of year,
              site height, site minus model terrain, year
     output : gap draws at the 13 level heights + 10 m (u, v, T, RH)
     order  : ranks of real gap profiles (whole profiles)
     fit    : forecasts (6 h and older) against balloons, 986 stations
     start  : the N2 world model; later 300 steps on the box's own balloons
        |
   real member = model member + gap draw  ------------------------------>  truth="real" (opt-in)
```

What it could retire later, each only by its own test: the per-site wind factor (IL-207b), the
station-scale widening, part of the neighbour-report fixes. What it does not touch: the generator,
the calibration stack, the templates, Mode F, every default.

### 11.5 Step 0, measured today (`new_plan_kit/b6_realair_step0.py`, log `kit_b6_realair_step0.log`)

Data on disk only, year 2019 (a fit year), 90 stations picked at random, 4 months: 12,220 matched
rows from 611 balloons on 15 valid times. Wind error per component in m/s. "Gap" is the part of the
real error that ERA5 as truth cannot show: sqrt(real^2 - model^2).

| Lead | Height | Forecast vs ERA5 (today's truth) | Forecast vs balloon (real) | Gap |
|---|---|---|---|---|
| 6-24 h | 10 m | 1.12 | 2.09 | 1.77 |
| 6-24 h | 1.5 km | 1.51 | 2.35 | 1.81 |
| 6-24 h | 5 km | 1.64 | 2.43 | 1.79 |
| 6-24 h | 12 km | 1.87 | 3.30 | 2.72 |
| 3-5 d | 1.5 km | 3.18 | 3.66 | 1.82 |
| 3-5 d | 12 km | 4.49 | 5.28 | 2.77 |
| 7-10 d | 1.5 km | 6.29 | 6.55 | 1.84 |
| 7-10 d | 12 km | 10.55 | 10.83 | 2.44 |

What it means in plain words:

- **On launch day the gap is as large as the forecast error itself.** One day ahead the forecast
  misses ERA5 by 1.5 m/s and misses the real balloon by 2.35 m/s. A forecast-mode band tuned on ERA5
  is then about 1.5 times too narrow against real air (1.9 times at the ground). I found no log where
  forecast mode was trained or scored against balloons.
- **The gap is the same at every lead** (1.81 / 1.82 / 1.84 m/s at 1.5 km). So it is a separate
  thing that can be learned once and added in every mode. Beyond a week it hardly matters (3 %).
- **At the ground, models have too little calm air:** real 17.3 %, forecast 9.5 %, ERA5 11.0 %.

Limits of this check: 15 days only; the 7-10 d gap is a difference of two large numbers; the 13
levels were joined by straight lines in height, which adds a little to the balloon columns, so the
gap is an upper estimate. Part of the gap is balloon noise and drift (about 0.5 m/s is usual for the
instrument; not measured here). Stage 3 bounds the real part with the radar as a third referee.

**Added after the second check (12.2):** real balloons carry 1.4 m/s (1-5 km), 1.7 m/s (5-12 km) and
3.0 m/s (12-18 km) of wind BETWEEN the 13 levels. So part of the gap above is fine detail that a
13-level forecast cannot hold. Stage 1a (section 9 row "RA stage 1a", run by the loop session on all
84 months) measured the gap at the level heights themselves: 1.5-1.6 m/s below 6 km and 1.8-2.0 m/s
above, against 1.8-2.7 here. The gap therefore has two parts with two owners: the coarse part stays with RA (improvement 9), the fine part goes to idea VS in section 12.

### 11.6 Tests, with the rules set now

Rules for all stages: fit on valid times 2016-20, range map on 2021, test on 2022 (the Mode F
protocol); never 2026. One station in five is left out of every fit by a fixed hash, and El Paso,
Midland and Denver are left out too. Two seeds, day-block intervals, CRPS against balloons. One heavy
job at a time; 12 threads, low priority. A script per stage in `new_plan_kit/` (`b6_*`).

| Stage | What | Pass rule | Kill rule | Cost |
|---|---|---|---|---|
| 0 | Pairs on disk; is there a gap, and does it grow with lead? | Done, 11.5. Dead if the gap were under 0.5 m/s or grew with lead; it is 1.7-2.7 and flat. | - | done |
| 1a | Build the gap rows from disk (`b6_realair_rows.py`, pattern of `il6_build_world.py`). Fit arm A1 (6 numbers). Quick look only, no verdict: the test year has about 30 balloon times. | A1 coverage of the 90 % band at left-out stations between 0.87 and 0.93 in every height band. | A1 cannot reach 0.85 in any band: the gap is not a simple added part; stop and rethink. | 1-2 h CPU |
| 1b | Download forecasts at the 986 points for every 00 / 12 UTC, 2016-22, leads 12 h, 1, 3, 5, 7 d (own new folder, ledger). | - | - | about 3.5 GB, unattended |
| 2 | **The verdict.** Arm A0 = member as is. A1 = 6-number rule. A2 = RA network (N2 world start), ordered by real gap ranks. Left-out stations, 2022. | A2 beats A1 by 2 % or more on CRPS at leads up to 3 d, interval excludes 0, both seeds; coverage 0.87-0.93 in every band; vertical variogram score better than A1, interval excludes 0; share of calm air at 10 m within 0.03 of the real one. | A2 not better than A1 on CRPS and not on the variogram score in either seed: the network part is closed and **A1 becomes the opt-in**. | 2-3 h CPU, or 30 min GPU at N6 size |
| 3 | How much of the gap is real air? Three-way referee as in C5 (balloon, radar, forecast) at El Paso. Ship the lower bound. | Bounds narrower than a factor 1.5. | Wider: ship the gap scaled to the lower bound and say so. | 1 h CPU |
| 4 | The 24-hour question. Leave out all stations of one quarter of the globe; score there by 3-hour bin of solar time. Ground: hourly airport wind at TCS and MAF, 2023-25, all hours. | Coverage 0.85-0.95 in every 3-hour bin; TCS daytime bias (+1.44 m/s) at least halved with no site factor; MAF not worse. | Any bin under 0.80: the gap is used only at hours with balloons nearby, and the tool says so. | 2 h CPU |
| 5 | All modes on the shipped tool path: past mode and climate mode against El Paso and Midland balloons 2023-25; `observe` with real-air members (TCS own report, the 7 neighbours). | Coverage error smaller than today in every band; shear ratio inside the C5 bounds 1.33-1.63; joint wind-shear extremes above 0.10 (today 0.07, real 0.17); `observe` coverage 0.85-0.95; every ERA5 score unchanged with the switch off. | Any ERA5 score moves with the switch off: fix before anything else. | 3 h CPU |
| 6 | Only after 5: 300 local steps per box; fine detail between levels from 1-second soundings. | own rules, set then | | later |

Order: 1a and 1b at once (CPU and network), then 2. Stages 3 and 4 side by side. Stage 5 last.

Honest odds: a gap that is real and worth adding in forecast and past mode, high (step 0 already
shows it). The network beating the 6-number rule, medium: likely at the ground and for the order
across heights, unsure aloft. The pad getting the right low-level wind with no pad data, medium to
low until stage 4 says so. Lifting joint extremes from 0.07 toward 0.17, low to medium, because the
coarse gap of improvement 9 leaves out the finest layers.

### 11.7 What is new here and what is not

Not new: the review already lists a "detail network" (Group 3 idea 1, ERA5 profile in, balloon out;
rated 6, parked) and the C5 referee. RA grows from both.
**Correction (2026-11-12, found while checking the logs for section 12):** `docs/plans/GLOBAL_PLAN.md`
line 21 already plans "one pooled correction, ERA5 to balloon departures, over hundreds of IGRA
stations" for the global model, and the world points were placed at balloon stations for that reason.
So point (a) below is not a discovery: it is a planned step that was never built, and its data is ready.
New: (a) the check that the data for it is on disk at 986 stations, with forecasts beside them, so it
can be built now and on this laptop, without waiting for the global model; (b) learning it from forecasts, so the truth is independent; (c) the
measured rule that the gap does not depend on lead, which makes it one added layer for all modes and
leaves every ERA5 score alone; (d) the ground, the 24 hours and the pad inside the same world model;
(e) a 6-number version that ships if the network fails.

Risks: balloon noise counted as real air (stage 3); hour and region tied together (stage 4); low
levels in the balloon files partly interpolated; the post-2022 change in balloon processing (review
trap 5: fit on 2016-22 only, year as an input); a gap added to a member can break the limits the
lapse map enforces (check the superadiabatic share in stage 5).

---

## 12. Second set: six ideas that change the structure (added 2026-11-12; step 0 measured for three, nothing else run)

Asked for: bolder ideas than section 11, taken from new AI work and from other fields, checked
against everything already logged, and improved in rounds. This section keeps the rounds.
Rules as before: nothing in the tool changes, every idea is opt-in, and every idea has a simple rule
it must beat and a rule that closes it.

### 12.1 How the set was made

1. **Everything logged was read first**, so nothing here repeats it: the 208 IL items and groups in
   `docs/logs/AUTOPILOT.md`, the review (Groups 1-3, C1-C6), `Secondary ideas.md` (21 ideas, both N
   sets), `Limitations to solve.md`, `docs/plans/GLOBAL_PLAN.md`, `docs/research/FUTURE_OPTIONS.md`.
   Each idea below names its nearest logged relative and says what differs.
2. **Outside work was searched** (list in 12.10). Where a search spoke against an idea, the idea was
   dropped or changed (12.9).
3. **The four patterns of our own history were kept as hard limits:** a new network body with the same
   inputs gives nothing; fits at 2-3 sites fail; a simple rule often ties a network; a step in the
   wrong place of the stack is undone by the next one.

The six, in order of how much they could change:

| Id | Name | Comes from | One line |
|---|---|---|---|
| VS | Vertical next-scale model | image generators that draw coarse first, then finer (2024-26) | One learned step, trained on millions of real balloons, writes the fine layers between the heights the models can see. Replaces the shear map and the lapse map with one joint step. |
| SV | Site vector | recommender systems ("cold start") and few-shot learning | Every place gets 8 numbers. Unknown place: guessed from terrain, with honest extra spread. Each real reading sharpens them by an exact formula. |
| IT | Instrument switches | batch correction in single-cell biology; before / after studies in economics | When a station changes its balloon model, the air does not change. That jump measures instrument noise, so it can be removed from the truth. |
| DP | Drone profiler | robot state estimation | A hobby drone flying a cross pattern calibrates itself, then measures the wind from 10 to 120 m at the pad: the layer that carries half of the apogee spread and has no truth today. |
| MF | Two-speed Monte Carlo | NASA entry and landing studies | Thousands of cheap flights steer a few hundred full flights. Same accuracy for a fraction of the flights. |
| FF | Flow frame | protein-structure and geometric networks | Describe wind along and across the flow, and mirror the southern half of the globe, so world data looks alike everywhere. Weakest of the six after its own check. |

### 12.2 Step 0, measured today (`new_plan_kit/b6_ideas_step0.py`, log `kit_b6_ideas_step0.log`)

Data on disk only, fit years only, 90 stations picked at random.

**(a) For VS. What a 13-level view of a real balloon loses** (21,847 balloons, 2019):

| Height | Real wind between the 13 levels (m/s, typical / 1 in 10) | Thin unstable layers (Richardson number under 1): real balloon | The same balloon seen at 13 levels |
|---|---|---|---|
| 1-5 km | 1.40 / 1.97 | 15.2 % | 3.5 % |
| 5-12 km | 1.72 / 2.41 | 14.8 % | 2.6 % |
| 12-18 km | 2.98 / 4.34 | 12.3 % | 0.7 % |

In plain words: the thin layers where shear and turbulence live are 4 to 17 times rarer in a coarse
view than in real air. The fine wind rises a little with stability (5-12 km: 1.54 / 1.75 / 1.87 m/s
from the least to the most stable third), the direction C1 found. Limit: part of the fine wind is
balloon noise (that is idea IT), and the tool's own members are finer than 13 levels (stage 0b of VS).

**(b) For SV. Is the ground-wind gap a fixed property of the place?** (10 m speed, real minus ERA5,
71 stations, 8,846 pairs, 2016-20)

- Real / ERA5 mean speed per station: 0.61 at the calm tenth, 0.98 in the middle, 1.33 at the windy
  tenth. The TCS factor we fitted by hand is an ordinary case, not a special one.
- A station keeps its offset: odd dates against even dates agree with a correlation of 0.88.
- The fixed offset is 1.01 m/s between stations, against 2.06 m/s of day-to-day scatter (19 % of the
  squared gap).
- **A plain average of the first 5 / 10 / 30 readings explains 25 % / 53 % / 71 % of the station's
  later offset.** Ten readings at a new pad recover half of what years of record would give.

**(c) For FF. Is the gap different along the wind and across it?** (4,133 rows, leads 6-24 h)

- Overall, no: 2.47 against 2.33 m/s at 1.5 km, 3.29 against 3.30 at 12 km.
- In the fastest tenth of jet winds (57 m/s), yes: 4.25 along against 3.41 across, and the real wind
  is 1.0 m/s faster than the forecast (part of that is the straight-line joining of 13 levels).
- So the first form of FF (turn everything into the flow frame) is not supported. A smaller form is.

### 12.3 VS: the vertical next-scale model

**What it replaces.** Today the fine structure of a member is made by three separate steps: the
shuffle borrows the order of ERA5 days, the shear map bends the wind, the lapse map bends the
temperature. They are fitted one after another and they fight: the shear map moves the share of
unstable layers AWAY from balloons (0.675 -> 0.650 at 0-1 km, 0.307 -> 0.287 at 1-5 km; real 0.73
and 0.35), and the 12-18 km band sits at 0.06-0.08 against 0.15 real (section 9, G2-7). Stability
depends on wind and temperature together, and no step sees both.

**Where it comes from.** The image generators that won in 2024-26 do not draw a picture pixel by
pixel. They draw a small coarse picture first, then each finer scale given all coarser ones (VAR,
"next-scale prediction"; later MVAR and the "iterative refinement" reading of it). The search found no use
of this on vertical profiles or on weather data with results, only a proposal.

| Version | Attack on the version before | Change |
|---|---|---|
| v0 | - | A small "language model" of balloons: one token per height, read from the ground up, trained on real balloons. |
| v1 | A token model along the heights was tried inside the generator (IL-8, IL-9, IL-23, IL-29) and body changes give nothing (pattern P1). | **Not in the generator.** VS is a step after the stack. Its input is the member's own coarse profile, which is rich. It writes only what lies between the heights the member can be trusted at. |
| v2 | Ground-up order piles up error, and the big things (where the jet is) are already known. | **Coarse to fine.** Scale 0 = the member seen at about 13 heights (given, never changed). Scale 1 = 26 heights, scale 2 = all 44. Scale 3 = a 100 m grid, later, where fine balloon data exists. Each scale is drawn given all coarser ones. |
| v3 | Bins lose the tails; a raw value output would be a new head with a new loss (pattern P7). | **Tokens are 64 bins of the leftover at each scale**, sized by the member's own shear and stability. Inside a bin: uniform. In the outer bins: the tail law the tool already uses. The training score is the log score, which is proper, so the ranges come out calibrated. One "temperature" number per scale is fitted on the held-out year (3 numbers). |
| v4 | Drawing all heights of a scale at once makes wind and temperature independent again, and that is the exact fault of today's stack. | **Each layer is drawn as one piece:** u, then v given u, then temperature given both, on alternating heights (two half-passes per scale). The model then learns the link the Richardson number checks. |
| v5 | It would move calibrated ranges (review trap 2) and the ERA5 headline (trap 1). | **Values at the coarse heights are never changed**, so the calibrated ranges and every score at those heights stay. Only the heights between move. Opt-in `detail="real"`; with it on, the shear map and lapse map are switched off, not stacked. |
| v6 | The tool's members are not 13-level objects; where does "trusted" end? | **Stage 0b decides it from data:** variance of member against balloon, scale by scale. The hand-over is the finest scale where the member still has 80 % of the real variance. |
| v7 | Simple rules tie networks here (pattern P4). | **The bar is a library:** add one whole real leftover (a balloon minus its own coarse view) from a balloon of the same band and stability third. This is the logged "wiggles" idea (review Group 2 idea 1), which was never run because it waited for 1-second data. On the 44 heights it needs none. VS must beat it. |
| v8 | Balloon swing and sensor noise would be learned as real layers. | Idea IT gives VS an instrument input, set to "no instrument" when the tool runs. |
| v9 | The tool is numpy-only. | A 4-layer model of width 128 needs 6 passes for 199 members: plain matrix products. Export as arrays, as today. |

**Final form.** `member (after calibration and shuffle) -> coarse view (kept) -> VS draws scales 1, 2 (u, v, T together, real-balloon statistics) -> member with real fine layers`.

| Stage | What | Pass rule (set now) | Kill rule | Cost |
|---|---|---|---|---|
| 0 | What does a coarse view lose? | Done, 12.2 (a). Dead if the loss were small; it is 4-17 times. | - | done |
| 0b | Member against balloon variance per scale, El Paso and Midland 2021-22. Sets the hand-over scale. | - | Members already hold 80 % at the finest scale: nothing to add, close VS. | 1 h CPU |
| 1 | The library bar on the shipped stack with shear and lapse maps off. Left-out stations and El Paso / Midland, 2022. | Share of unstable layers within 0.03 of balloons in every band; share of temperature rises below 3 km within 0.05 (today 0.52 against 0.32); top 1 % shear within 10 % of balloons; CRPS against balloons not worse than the shipped stack. | - (it is the bar) | 3 h CPU |
| 2 | VS itself. Fit on balloons 1991-2020 of all stations but one in five (roughly 5-8 million profiles, estimated from the 2019 count, not counted), check on 2021, test on 2022. | Beats the bar on the vertical variogram score with an interval that excludes 0, both seeds, and meets every stage-1 limit. | Not better than the bar in either seed: the bar ships as the opt-in, VS is closed. | 1-2 h GPU per seed |
| 3 | On the shipped tool path, all modes; apogee and max-shear spread through the flight engine. | ERA5 scores at the coarse heights unchanged; `tool_audit.py` and `shipped_check.py` pass. | Any coarse-height score moves. | 2 h CPU |

Nearest logged relatives: IL-8 (tokens inside the generator), the detail network (ERA5 in, balloon
out, one step, parked), the wiggles library (never run). New: coarse-to-fine order, wind and
temperature drawn together, the coarse heights locked, one step in place of two maps.
Honest odds: the bar improving the unstable-layer shares, medium to high (it uses real leftovers).
VS beating the bar, medium. Risk: a real leftover added to a member that already has some fine
structure counts it twice; stage 0b is there for that.

### 12.4 SV: the site vector

**What it replaces.** Site effects are handled today by hand-fitted single numbers at places with a
record (IL-207b at TCS: CRPS -0.079, confirmed), and every attempt to reach the pad failed: borrowed
day / night shape (S2, premise wrong), map then update (S1, seed spread), launch-week average (O3: the
factor moved only 0.9-1.2 in two weeks), two neighbours (O1). The pad has no record.

**Where it comes from.** A film service facing a new user has the same problem: no history. The
standard cure is a short vector per user, guessed from what is known about them, then updated with
each rating. Few-shot learning uses the same idea (a small "context" vector per task, the rest shared).

| Version | Attack on the version before | Change |
|---|---|---|
| v0 | - | Inside RA, every station gets its own 8 numbers, learned with the network. For the pad, guess them from terrain. |
| v1 | The first "in-context site calibrator" was rejected: no airports beside ERA5 points, more name than mechanism. | **The data objection is gone** (986 stations with surface wind beside world points, section 11) **and the mechanism is one line:** the last layer of RA is linear, `gap = features(conditions) x (shared weights + site vector)`. |
| v2 | A guessed vector is wrong by an unknown amount, and the tool's spread is "weather only" (limitation 5.2.16). | **Learn how wrong the guess usually is.** Across the 986 stations fit `site vector = B x terrain facts + scatter`. The scatter becomes extra spread at any place without a record. The tool is then honestly wider at an unknown pad than at an airport. |
| v3 | How do readings enter? O3 used a slow fixed average. | **Exact update.** With a linear last layer and a known prior, the new site vector after k readings is one closed formula (Bayes for a linear model), numpy-only: `Launch.learn_site(readings)`. It moves fast when readings agree and slowly when they scatter. Step 0: even a plain mean gets 53 % from 10 readings. |
| v4 | One bad reading would bend the site. | Readings far outside the predicted range get less weight (two passes of a Student-t weight; the patched review idea G2-2: widen, never reject). |
| v5 | Where do pad readings come from, if there is no anemometer? | Any of: a week of a cheap anemometer; the drone of idea DP; the user's past launch-day notes. Each is a few numbers; SV does not care which. |
| v6 | "What helps at home hurts away" (pattern P2): a vector learned on flat airports may mislead in a valley. | **Train so that no station is left behind:** add to the loss the spread of the per-station losses (risk extrapolation, V-REx). The model is pushed toward rules that hold at every station. One number to set, chosen on left-out stations. |

| Stage | What | Pass rule (set now) | Kill rule | Cost |
|---|---|---|---|---|
| 0 | Is the gap a fixed property of the place, and how fast is it learned? | Done, 12.2 (b): correlation 0.88; 10 readings explain 53 %. | - | done |
| 1 | Linear version, no network: speed factor and offset per station from terrain facts (ridge), update from k readings. Leave-station-out over all stations, 10 m wind, test 2022. | k = 0 (terrain only) beats "no site term" with an interval that excludes 0. k = 10 reaches half of the gain of the station's own full fit. Coverage 0.85-0.95 at k = 0, 10, 30. | k = 30 reaches under 30 % of the full-fit gain: site terms stay per site, by hand. | 2 h CPU |
| 2 | Replay at TCS and MAF with hourly airport data 2023-25 (never used in the fit): k = 1, 3, 7 days of readings before each test day. | At TCS, 7 days give at least half of the IL-207b gain (-0.079) with coverage 0.85-0.95; MAF not worse. | TCS gain under a quarter. | 1 h CPU |
| 3 | Inside RA (stage 2 of section 11) as the last layer, with the V-REx term. | RA with SV beats RA without it at left-out stations, both seeds. | - | part of RA |

Nearest logged relatives: IL-207b (one number, one site), O3 (slow average), the rejected in-context
calibrator, GLOBAL_PLAN's "local adaptation". New: a prior from terrain with a measured scatter, an
exact update, site uncertainty as spread, one mechanism from zero readings to a full record.
Honest odds: stage 1 with readings, high (step 0 nearly shows it). Terrain-only guess, medium to low.

### 12.5 IT: instrument switches as free experiments

**The problem it solves.** RA and VS learn from balloons. A balloon reading is real air plus swing,
sensor lag and processing. Today we can bound that only at El Paso with the radar (C5: 80 hours).
Balloon models differ by country, so "instrument" and "climate" look like one thing.

**Where it comes from.** Biologists who read single cells in different labs have the same tangle
("batch effects") and remove it by giving the model the batch as an input, then asking for the answer
with the batch switched off. Economists separate a cause from a trend with before / after comparisons
against places where nothing changed.

| Version | Attack | Change |
|---|---|---|
| v0 | - | Give RA and VS the balloon model as an input; at run time set it to "none". |
| v1 | Balloon model and country are the same thing in the data; the input would soak up climate. | **Use only the switches.** Many stations changed their balloon model inside 2016-22. The air at a station does not change on that day. Compare the leftover (balloon minus forecast) before and after, against stations that did not switch in the same months. Only that contrast teaches the instrument input. |
| v2 | The input could still carry real effects. | It may change only two small things: the noise size and a bias by height. It never sees the weather inputs. |
| v3 | How do we know it is right? | Two outside checks: the El Paso radar bound (C5), and the known 2023 processing change (review trap 5), which the method must find by itself as a switch. If it does, low-level balloons after 2022 become usable again. |

Step 0 is a download of a few MB (the public IGRA station history file; not on disk) and a count.
Pass: at least 100 switches in 2016-22, and a noise estimate for the newest balloon model whose
interval excludes 0 and sits below the C5 upper bound. Kill: under 30 switches, or the estimate
changes sign between two halves of the stations: keep the radar bound only. Cost: 2 h CPU.
Nearest logged relatives: review Group 3 idea 1 patch ("give sonde type and year as inputs"), IL-67 / IL-72 (era
offsets). New: using the switch dates as experiments, and limiting what the input may change.
Honest odds: medium. It is cheap, and without it RA and VS inherit balloon noise as "real air".

### 12.6 DP: the drone profiler

**The problem it solves.** 87 % of the wind-driven apogee spread comes from 0-300 m and 53 % from
50-150 m (P6). There is no truth there at the pad: sodars need access, the taper data is blocked,
the pad has no tower (ASK_LATER 15, 20). Every ground-wind idea ended with "needs pad data".

**Where it comes from.** A hovering drone leans into the wind; the lean angle gives the wind. A fleet
calibrated this way matched a 99 m tower to under 0.3 m/s and 8 degrees (Lindenberg, 2021). The known
limit: the lean-to-wind curve belongs to one airframe and needs a tower to calibrate.

| Version | Attack | Change |
|---|---|---|
| v0 | - | Hover at 20, 40, 60, 80, 100, 120 m for 20 s each; read the lean from the flight log. |
| v1 | The curve needs a tower, which the pad lacks. | **Self-calibration by a cross pattern.** At one height fly straight out and back at three set speeds, on two crossing lines. Out and back, the wind adds and subtracts: half the sum of the two ground speeds is the airspeed, half the difference is the wind. That gives lean against airspeed for this airframe from the log alone (2 numbers). No tower. |
| v2 | A single profile is one moment. | It enters twice: as a reading for `observe` (a profile from 10 to 120 m with a stated error), and as readings for the site vector (SV), so each flight also improves the pad's long-term picture. |
| v3 | Rules and safety. | 120 m is the usual legal ceiling for hobby drones and it covers most of the 50-150 m layer. Flown well before the launch, never during. The tool only reads a log file; it never controls a drone. |
| v4 | Can we test it without a drone? | Yes: the 200 m tower data on disk (TTU, 131 hours). Replay: give `observe` the tower winds at 6 heights with 0.5 m/s error, score the 50-150 m layer 30 and 60 minutes later against the tower. |

Pass (set now, tower replay): CRPS of the 50-150 m mean wind 30 minutes later at least 40 % better
than the tool with only a 10 m report. Kill: under 15 %. Cost: 2 h CPU; then it waits for the user
(a drone and one flight log: new ASK_LATER item). Nearest logged relatives: none (no file mentions a
drone); limitation 5.2.5 idea 5 (an anemometer at the pad, parked). Honest odds: the replay passing,
medium to high (a measured profile where we have none); real use depends on the user owning a drone.

### 12.7 MF: two-speed Monte Carlo

**The problem it solves.** The tool's purpose is Monte Carlo. A full flight simulation is slow, so
users run a few hundred, and the error of a 1 % tail from 200 flights is large (IL-40, M18).
`montecarlo.py` has Latin hypercube, Sobol and importance sampling, but no way to use a cheap model.

**Where it comes from.** NASA's entry and landing studies ran thousands of cheap trajectories beside
a few full ones and combined them (multi-model Monte Carlo, control variates). The cheap model does
not have to be right. It only has to move the same way as the full one.

| Version | Attack | Change |
|---|---|---|
| v0 | - | Run the full simulator on n atmospheres and a cheap point-mass ascent on 50 x n. Correct the full result by how the cheap one differs between the small and the large set. |
| v1 | The gain depends on how alike the two are, which nobody knows beforehand. | A pilot of 50 paired flights measures it and gives the best split of the budget by a known formula. The tool prints "equal to N plain flights". |
| v2 | Writing a cheap flight model per rocket is work. | **Controls that need no flight model:** weighted layer winds with the P6 weights. Their exact mean over the pool costs nothing (100,000 draws, no flights). |
| v3 | Tails matter most and control variates help means most. | For tail odds the cheap model chooses which atmospheres the full model flies (the existing `run_importance`, steered by the cheap score, not by one fixed metric). |

Pass (set now): on the validation rocket, against a 5,000-flight reference, 200 full flights with MF
give an error of mean and spread of apogee and landing distance at least 5 times smaller (in variance)
than 200 plain flights, and at least 2 times for a 1 % tail; coverage of the printed intervals
0.90-0.98 over 100 repeats. Kill: under 2 times on the mean. Cost: 3 h CPU with the in-repo engine.
Nearest logged relatives: IL-34, M9 (importance sampling), IL-40. New: a second fidelity, and
controls with exactly known means taken from the pool. Honest odds: high for means and spreads
(v2 alone should do it, because apogee follows the low-level wind closely), medium for tails.

### 12.8 FF: the flow frame (reduced after its own check)

First form: turn every wind into "along the flow, across the flow" before any world model sees it,
and mirror southern-hemisphere rows, so a jet over New Mexico and a jet over Chile are one pattern
(the idea behind the local frames of protein-structure networks). Step 0 (12.2 c) does not support
turning everything: the gap is the same in both directions except in fast jets. Reduced form: keep
east / north, add three inputs (speed, and the along-flow part of the forecast shear and of the
terrain slope), and add mirrored southern rows. Test: the N2 "world as it is" arm, which missed by
1.2-3.7 %. Pass: the miss shrinks by a third at leads 1-3 d in both boxes and seeds. Kill: under a
tenth: closed. Cost: two Mode F runs per box (about 45 min CPU). Honest odds: low to medium.

### 12.9 Looked at and dropped in this round

| Candidate | Why dropped |
|---|---|
| Winds from airliner radio signals (ADS-B / Mode-S) near the pad | The open method was measured at 4.78 m/s error against 3.88 for a 6-hour forecast, so it would add noise to a forecast that is already better. US aircraft also do not send airspeed openly. |
| Prediction-powered inference (few true labels + many model labels give tighter intervals) | Needs many cases with no label. Our balloons exist at nearly every hour we can score, so there is nothing unlabeled of the same kind to add. |
| The 2026 "drifting" one-step generators as a new loss in the main network | A whole-profile loss in the main network has failed in every form (IL-47, IL-49, IL-62; pattern P7). Kept only as a second training rule for VS if the token version is too slow. |
| Ready-made table models that predict without training (TabPFN, TabICL) as the gap model | A real candidate for a zero-training bar in RA stage 2, but it needs a new package and model weights; installs need the user. Listed for ASK_LATER, not built. |
| Guidance, as in image generators, to strengthen the weak driver response | Drivers lift climate mode by about 3 % in all; nothing to amplify. |
| A reusable-holdout rule for the 30+ decisions made on 2024-25 | Sound, but it is a checking rule, not a change to the system (the reason the "referee network" was rejected). |
| Balloon tracks from the public tracking network as fine truth | Readings are uncalibrated and depend on volunteer receivers; the 1-second cadence could not be confirmed. Kept as a possible source for VS scale 3 only. |

### 12.10 How the pieces fit, and the order

```
pool member (today's tool, unchanged)
   -> RA  coarse real-air gap ........ section 11   } both trained on balloons with the
   -> VS  fine layers, u / v / T together .. 12.3   } instrument switched off (IT, 12.5)
   -> SV  the place: terrain guess, then readings (12.4)  <- drone profile (DP, 12.6)
   -> observe (unchanged), now on real-air members
   -> MF  two-speed Monte Carlo over the result (12.7)
```

Order, by cost and by what each one unlocks: (1) SV stage 1 and the VS library bar, side by side on
the CPU: both are simple, both ship something even if the networks fail. (2) IT step 0 (small
download) and the DP tower replay. (3) MF, any time; it touches nothing else. (4) RA stage 2 and VS
stage 2 on the GPU, after N1 / N6. (5) FF last.

Place in the overall work order (user, 2026-11-12): these six run at the very end, after sections
13 and 14; see step 8 of 13.5.

Sources checked on 2026-11-12 (searches; abstracts and summaries only, the papers were not read in
full): next-scale image generation and its reading as iterative refinement (arXiv 2510.02826; MVAR,
arXiv 2505.12742); drone wind from lean angle against a 99 m tower (Atmos. Meas. Tech. 14, 3795,
2021); aircraft-derived wind and its error (github.com/junzis/meteo-particle-model; PLOS ONE 2018
and 2022); multi-model Monte Carlo for entry and landing (NASA NTRS 20205002995; arXiv 2306.10800);
prediction-powered inference and its limits (arXiv 2311.01453, 2505.20178); table models for
distributions (arXiv 2603.08206, 2602.11139, 2601.22371); one-step "drifting" generators (arXiv
2602.04770); weather models trained on observations (GraphDOP, arXiv 2412.15687); balloon tracking
archive (registry.opendata.aws/sondehub-telemetry).

## 13. Variations of the near misses (added 2026-11-12; nothing here has been run)

Source: `Almost ideas.md` (experiments that failed by a small margin or on one clause, showed a
measured benefit, and were closed without a follow-up). Each row below is a VARIATION of one of
them, not a new idea. IDs are AV1 to AV21 ("almost, variation").

**Standing note for every row (user, 2026-11-12):** this is a variation. If it fails but still
shows potential (a benefit with an interval that excludes 0 somewhere, or a miss on one clause
only), log one more variation of it here as a new AV row before closing the parent. Close a parent
only when a variation shows no benefit at all.

Guards that stay in force while doing that:
- The pass and kill rules below are set now, before any run. A parent's old rule is not loosened
  after seeing its result; where a looser rule is the only change, the row says "user's call".
- The forking-paths rule (AUTOPILOT pitfall 14) applies per parent: with n variants tried, the gain
  needed to adopt one grows with n, and it must hold on both seeds.
- Where the split, band or threshold of a variation is already suggested by the parent's test-year
  result, it is fixed here in writing and confirmed on rows the parent was not scored on (stated
  per row). Otherwise the result is labelled "chosen on test" and cannot be adopted (pitfall 15).
- Defaults stay bit-identical, every switch is off by default, a trained model gets a new name, two
  seeds, never 2026, exports need the user's go.

### 13.1 Forecast mode (Mode F)

| ID | Variation of | What changes | Pass and kill rule (set now) | Cost | Note |
|---|---|---|---|---|---|
| AV1 | N6 big world-start Mode F (KILL: lead 1 d -4.7 to -5.8 %, lead 3 d -1.4 to -3.4 %, lead 7 d +2.2 to +4.0 % worse) | Lead split: the N6 model serves leads up to 3 d, the shipped small model serves 5 and 7 d. No training; the N6 networks exist. The split point (between 3 and 5 d) is fixed here | Confirm on the validation year first: the split picked there must be the same (N6 better at 1 and 3 d, not at 5 and 7 d). PASS: on 2022, leads 1 and 3 d at least 1 % better than shipped with an interval excluding 0, both boxes, both seeds, cov99 within 0.003; leads 5 and 7 d identical to shipped. KILL: the validation year picks a different split | 1 h CPU | VARIATION. If it still shows potential, try more (e.g. a smooth weight between 3 and 5 d, needs the IL-75 leads) |
| AV22 | AV1 lead split (KILL 2026-11-12 on a 0.1 % tie at NM/TX 5 d in 2021; 1 and 3 d better on 2021 and 2022) | Smooth blend by lead in place of a hard split: members drawn from the N6 model with share w(lead), from the small model with 1 - w, w = 1 at 1 d, 0 at 7 d, one free value at 3 d and at 5 d, both picked on 2021 (`--test-year 2021` tables, already on disk) on a 0 / 0.25 / 0.5 / 0.75 / 1 grid, then fixed | PASS: on 2022 every lead equals or beats the small model, 1 and 3 d at least 1 % better with the interval excluding 0, both boxes, both seeds, cov99 within 0.003. KILL: any lead worse than small by more than 0.5 % on 2022, or the 2021 pick differs between the boxes by more than one grid step | 1 h CPU (mixing only; needs per-row member draws saved, a small addition to `--save-rows`) | VARIATION of a variation (forking paths: second try on N6, so the gain to adopt grows; see pitfall 14). Logged by the loop 2026-11-12 after AV1's KILL |
| AV23 | AV2 long-lead use (MISS 2026-11-12: 7-22 % better than climate at days 8-10, cov99 0.978-0.983 vs 0.990) | Members beyond 7.5 d drawn from the N5 all-lead network with share w(day), from the climate generator with 1 - w (the IL-74 fade); one w per day 8 / 9 / 10 picked on a 0.5 / 0.6 / 0.7 / 0.8 / 0.9 grid on 2021 rows, then fixed. Needs a 2021 scoring of the N5 networks (`--test-year 2021`, N5 flags) and member-level rows | PASS: on 2022 at days 8, 9, 10 each better than climate and than the binned model with interval < 0, both boxes and seeds, cov99 within 0.003 of climate. KILL: cov99 still more than 0.003 below climate at w = 0.5, or worse than climate at any day | 2 h CPU (4 scorings on 2021 + mixing) | VARIATION of a variation (second try on N5; pitfall 14). Logged by the loop 2026-11-12 after AV2's MISS |
| AV24 | CHORUS stage 1 (MISS 2026-11-13: mix better at all leads in all 4 runs, 7 d interval < 0, 5 d interval crosses 0; network and calibration saw only newest-run inputs) | The same closed-rule mix (same 2018-20 weights, no new numbers) in EVERY year's rows (2016-2022): mode F retrained on mixed inputs with the shipped small recipe, PIT recal and range map on mixed 2021, judged on mixed 2022 against the stage 1 newest-run models (`models/chorus_new*`) | Stage 1's rule unchanged: PASS = interval < 0 at 5 and 7 d and mix / newest <= 1.005 at 1 and 3 d in all 4 box x seed; KILL = no lead better | 1 h CPU rows (older run for 2016-2021) + 8 CPU trainings/evals (~1.5 h) | VARIATION (first follow-up of CHORUS stage 1). Logged by the loop 2026-11-13 |
| AV25 | AV4 (MISS 2026-11-13: PIT -0.0019 [-0.0037, +0.0001], CRPS -0.48 % [-0.92, -0.13]; only 36 test init dates) | AV4 unchanged (factor in cells 0 1 2 6, fit 2016-2020) but tested on 2021 and 2022 rows together (about 72 init dates, 5000 test rows), the more-dates follow-up the AV4 row names; 2021 is outside the fit years | AV4's rule unchanged: PASS = PIT change interval below 0 and CRPS change <= +0.2 %; KILL = CRPS interval includes 0; else MISS | 1 h CPU | VARIATION of a variation (second try on C6). Logged by the loop 2026-11-13 |
| AV26 | AV24 (MISS 2026-11-13: mix retrained better at every lead in all 4 runs, 1 and 3 d intervals < 0, 7 d interval crosses 0 on one test year) | The same AV24 networks (no training) also scored on 2021 (`--test-year 2021`, range map on mixed 2022, AV1's protocol) against the newest-run networks' AV1 2021 scores; per-row scores of 2021 + 2022 pooled per lead (`new_plan_kit/b13_av26.py`, `scripts/cpu_av26.sh`) | AV24's rule on the pooled two years: PASS = interval < 0 at 5 and 7 d and mix / newest <= 1.005 at 1 and 3 d in all 4 box x seed; KILL = no lead better | 4 CPU evaluations, ~40 min | VARIATION (follow-up of AV24). Logged by the loop 2026-11-13 |
| AV2 | N5 all-lead network (KILL: leads 1-3 worse by +0.9 to +2.7 %; beyond 7.5 d -2.9 to -3.7 % better than binned and better than climate) | Long-lead-only use: the N5 network serves only leads beyond 7.5 d, where the tool now falls back to the climate generator. Leads up to 7.5 d untouched. No training | PASS: beyond 7.5 d better than the binned model and than the climate model with an interval excluding 0, both boxes, both seeds, at days 8, 9 and 10 each (not only pooled); cov99 within 0.003. KILL: worse than climate at any of days 8-10 in either box | 1 h CPU | VARIATION. If it still shows potential, try more (e.g. a blend weight toward climate by lead, the IL-74 idea) |
| AV3 | AV1 + AV2 | One router: N6 model up to 3 d, shipped model 5-7 d, N5 network beyond 7.5 d. Only if AV1 and AV2 both pass | PASS: every lead bin equals or beats what the tool serves today, no bin worse by more than 0.5 %, both boxes, both seeds. KILL: any bin worse by more than 1 % | 1 h CPU | VARIATION (combination). Opt-in only; export is the user's step |
| AV4 | C6 run-to-run disagreement spread (FAIL: PIT -0.0018 [-0.0051, +0.0007]; CRPS -0.69 % [-1.19, -0.24]) | Apply the factor only in the four cells where the premise held (wind 0-1, 1-5, 5-12 km; T 5-12 km; rho 0.30-0.38); the other four cells keep factor 1. Same fit years 2016-2020 | Same rule as C6, unchanged: PIT distance change with the whole interval below 0 on 2022, CRPS not worse. KILL: CRPS interval includes 0 | 30 min CPU | VARIATION. If it still shows potential, try more: more test init dates (2022 has 36), 12 h pairs if a refetch brings them. A CRPS-only rule is the user's call, not run on my own |
| AV5 | N2 world-start fine-tune (MISS on the "world as is within 1 %" clause; fine-tuned -0.8 to -2.7 %, 16 of 16 intervals below 0; control showed the gain is the world start) | No new model. Third training seed of own / own + 300 / fine-tuned on the 4-year box rows, judged on the fine-tuned model alone | PASS: fine-tuned better than own + 300 with an interval excluding 0 at 3 or more of 4 leads, both boxes, all three seeds (seeds 0 and 1 already show leads 1, 5, 7 d). KILL: the third seed fails at 2 or more leads in a box. Dropping the "world as is" clause is the user's call | 1.5 h CPU | VARIATION (confirmation). If it still shows potential, try more (500 or 1000 fine-tune steps; N2-B already passed for a data-poor box) |
| AV6 | G1-5 spread tracker (FAIL: TCS T CRPS +0.002 > 0.0009; coverage error fell in 4 of 4 cells; the factor sat at the 1.5 cap) | (a) One fixed widening factor per variable fitted on 2016-22, no tracking, wind only. (b) The same test on the tool's own forecast-mode output instead of the raw ensemble (the test G1-5 named as missing) | PASS: coverage error falls and CRPS not worse by more than 0.0009 in every site x variable cell tested, 2023-24. KILL: the tool's output already covers within 0.03 of 0.90 (nothing to fix) | 1.5 h CPU | VARIATION. If it still shows potential, try more (factor by lead; temperature with its own factor) |

### 13.2 Launch-day observations and ground wind

| ID | Variation of | What changes | Pass and kill rule (set now) | Cost | Note |
|---|---|---|---|---|---|
| AV7 | O1 two neighbours at once (FAIL: better in 4 of 4 runs, interval excludes 0 in 1 of 4) | Same method, 600 hours per target instead of 200, two new hour seeds | Same rule: interval excludes 0 at both targets in both seeds, coverage >= 0.80. KILL: interval includes 0 at both targets in both seeds | 3 h CPU | VARIATION. If it still shows potential, try more (a third target; three neighbours) |
| AV8 | S1 site map first, update second (FAIL: ONM coverage 0.78 vs 0.80 in one seed; cell factors differ 0.086 vs 0.05; CRPS better at 12 of 12 pair-seeds) | 120 prior hours per cell instead of 40 (steadier factors); neighbours outside the trained area (ONM, FST, ABQ; IL-209) are left out, stated here before the run | Same rule: coverage >= 0.80 at every servable pair, factor gap between seeds <= 0.05, CRPS better than B. KILL: factor gap still above 0.05 | 2 h CPU | VARIATION. If it still shows potential, try more (IL-208: height-difference term so ONM can come back in) |
| AV9 | O4 analog tail fix (FAIL: tail not halved; CRPS better at both sites with intervals below 0; TCS coverage 0.89 -> 0.83) | Shift the analog's upper tail as before but keep its spread (no narrowing), so the coverage loss is removed. Referee only, not a tool feature | PASS: CRPS interval below 0 at both sites on a second hour seed, coverage not lower by more than 0.02. Then it replaces the plain analog as the referee. KILL: coverage still falls by more than 0.02 | 1 h CPU | VARIATION. If it still shows potential, try more (K other than 40) |
| AV10 | O3 launch-week factor (FAIL: helps both sites in seed 1, neutral in seed 0; MAF coverage 0.91 -> 0.90) | Start from the IL-207b per-site factor instead of 1.0 (O3 ran without a starting shape because S2 was dropped) | Same rule: CRPS better at both sites in both seeds, coverage not lower. KILL: not better than the IL-207b factor alone | 1.5 h CPU | VARIATION. If it still shows potential, try more (alpha other than 1/30 per day) |
| AV11 | A2 past-mode spread x1.2 (FAIL: airports -8 / -13 %, both USCRN basin sites worse) | Switch by station type only: x1.2 when the target is an airport ASOS site, 1.0 elsewhere. No descriptor model (P7 was neutral) | PASS: no site worse by more than 0.0009, the airports better with an interval excluding 0, tested leave-one-airport-out over the airports on disk. KILL: any left-out airport worse | 1 h CPU | VARIATION. If it still shows potential, try more. A pad is not an airport, so the pad default stays 1.0 either way |
| AV12 | P2 gust as a mixed-layer wind measurement (-2.3 % MAE in mixed air, about 0 at night: "too small to wire") | Daytime gate: use the gust only at 10-18 h local solar time; no change at night by construction | PASS: at least 2 % MAE gain in the gated hours with an interval excluding 0, second station as a check. KILL: under 1 % | 1 h CPU | VARIATION. If it still shows potential, try more (gate by boundary-layer depth instead of the clock) |
| AV13 | Regional gust law (ties the built-in law; better above 5 m/s, worse below) | Switch by speed: regional law above 5 m/s model wind, built-in law below. The 5 m/s threshold is fixed here from the log | PASS: better than the built-in law overall with an interval excluding 0 and not worse below 5 m/s, tested across stations (fit one airport, test the other). KILL: the cross-station test loses the gain | 1 h CPU | VARIATION. If it still shows potential, try more (a smooth weight instead of a step) |
| AV14 | P6W wind loss term to 150 m (closed neutral: every 10-300 m wind column +0.001 to +0.0015, mean +0.0001) | The check IL-180 asked for and that was not found in the logs: a second TRAINING seed plus the night score | PASS: 10-300 m wind columns gain at least 0.001 in both training seeds, day and night, no other band worse beyond the paired tolerance 0.0009. Else closed for good | 40 min GPU, 1 h CPU | VARIATION (confirmation). If it still shows potential, try more; pad data (ASK_LATER 15) stays the stronger lever for the lowest 150 m |

### 13.3 Climate generator and shear

| ID | Variation of | What changes | Pass and kill rule (set now) | Cost | Note |
|---|---|---|---|---|---|
| AV15 | Shear target, forms "ratio" and "c1" (each passed one band: ratio 1.03 at 5-12 km but 1.22 at 1-5 km; c1 0.97 at 1-5 km but 0.82 at 5-12 km) | Hybrid fixed here: c1 at 1-5 km, ratio at 5-12 km. Because that choice comes from the test balloons, it is judged only on a balloon block neither form was scored on (refit with two fit years held out, or a third station) | PASS: p99 new / balloon within 0.90-1.10 in both bands on the fresh block, CRPS not worse by more than 0.1 %. KILL: either band outside 0.85-1.15 | 2 h CPU | VARIATION. Low priority: IL-201 showed 100-300 m shear does not move apogee; this matters for loads only. If it still shows potential, try more |
| AV16 | IL-103 balloon-fitted shear map (not adopted: CRPS unchanged, 12-18 km p99 24.6 -> 29.0 vs 28.5 for pre-2023 balloons; 5-12 km overshoots 22.8 vs 21.6; 0-1 km not fixable) | Aloft only: the balloon map acts at 12-18 km, every lower band keeps the shipped map | PASS: 12-18 km p99 within 10 % of pre-2023 balloons on 2021-22, bands below 12 km bit-identical, CRPS change within 0.1 %. KILL: 12-18 km CRPS worse by more than 0.1 % | 1 h CPU | VARIATION. Export needs the user. If it still shows potential, try more (add the 5-12 km band with a damped map) |
| AV17 | IL-10 trust layer refit on NM/TX (discarded: ERA5 +0.0008, balloons +0.0007 against a 0.001 margin; T 12-18 km -0.0043) | Same fit on the current l21 stack with the weights for T and u 12-18 km forced to zero (the band whose target changed around 2020) | PASS: paired gain above 0.0009 on ERA5 over 3 score seeds, balloons not worse by more than 0.0013, coverage error not worse by more than 0.0004, no band worse. KILL: paired gain under 0.0005 | 1 h GPU scoring | VARIATION. If it still shows potential, try more (surface and 0-1 km bands only, where it gained most: rh2m +0.0095) |
| AV18 | IL-54 shear-tail loss weight 2.0 (discarded: balloons +0.0010, at the margin; the 99.9th shear did not rise) | Two more training seeds on the current base, to see if the balloon gain is real. The weakest entry of the list | PASS: balloons gain at least 0.0013 in both new seeds with ERA5 not lower. Else closed for good | 1 h GPU | VARIATION (confirmation). Run last |

### 13.4 New-region transfer (Denver zero-shot)

| ID | Variation of | What changes | Pass and kill rule (set now) | Cost | Note |
|---|---|---|---|---|---|
| AV19 | L3-26 Student-t noise (rejected: NM/TX shape FAIL on vertical correlation 0.076 -> 0.109 and shear KS; Denver -0.1918 -> -0.1729 with better coverage) | Judge it inside the full stack (shuffle + shear map + lapse map), which re-imposes exactly the vertical correlation and shear that failed. No retrain; the model exists | PASS: NM/TX stack headline within the paired tolerance 0.0009 and shape not FAIL; Denver zero-shot gain over the base of at least 0.01 kept. KILL: event-coverage gap still worse beyond its tolerance | 1.5 h GPU scoring | VARIATION. If it still shows potential, try more (fewer Student-t noise numbers, 4 instead of 8) |
| AV20 | L3-4 SIREN location encoding (not adopted: NM/TX PASS + shape PASS, Denver 22 % of the gap, but Denver T 12-18 km -0.30 and 12x ERA5's surface jumps) | SIREN plus the climatology inputs of L3-7 (tropopause height, per-height mean and sd), which the log says carry the stratospheric temperature the coordinates drop. L3-7 was sidelined, never run | PASS: NM/TX within 0.0009 and shape not FAIL; Denver zero-shot better than SIREN alone (-0.156 on the fill-top set) with T 12-18 km not below -0.05. KILL: Denver T 12-18 km still below -0.15 | 40 min GPU, 1 h CPU, plus the L3-7 feature code | VARIATION. The log says single-box tests of location encodings are weak; if it still shows potential, try more once several boxes exist |
| AV21 | L3-34 / L3-48 climatology debias (works alone: Denver -0.1918 -> -0.0253 with the logit fix; redundant once the local trust blend is on) | Learn in anomaly space instead of correcting afterwards (L3-8, SAMOS targets: standardised by a smooth per-point climatology). Sidelined, never run; needs the dataset option | PASS: Denver zero-shot at or above -0.088 (half the gap) with NM/TX within 0.0009 and shape not FAIL. KILL: NM/TX worse by more than 0.0015 | 3 h code, 40 min GPU, 1 h CPU | VARIATION. The most expensive row; belongs with the global-mode work. If it still shows potential, try more (climatology smoothed in space, L3-9) |

### 13.5 Order

Cheapest and best-supported first; one heavy Mode F evaluation at a time (14-17 GB RAM).

1. AV1, AV2 (no training, 1 h each), then AV3 if both pass.
   Then the no-training first stages of section 14, one after the other: SIGMA stage 1 (bar B0,
   30 min CPU), CHORUS stage 1 (rebuild rows at fixed points, 1 h CPU), STRAND stage 0 (20 min CPU).
2. AV4, AV6 (CPU, under 2 h each). AV4's disagreement factor is also the starting point for
   SIGMA improvement 5; AV4 is still judged alone, by its own rule.
3. AV5 (third seed). Then SIGMA stage 2 (same world start as AV5; 1.5 h CPU per seed), judged by
   N5's rule; if AV3 passed, also reported against the AV3 router.
   Only if SIGMA stage 2 passes: SIGMA stage 3 (NEST, 30 min GPU), and CHORUS stage 2 (also needs
   CHORUS stage 1 to pass).
4. AV7, AV8, AV10, AV9, AV11 (observation lane, CPU, in this order).
5. AV17, AV19 (GPU scoring only), AV14.
6. AV16, AV15, AV12, AV13. STRAND stage 1 here (climate and past mode), only if its stage 0 did
   not stop it.
7. AV20, AV21 (new code and training), AV18.
8. At the very end, the six ideas of section 12, in the order of 12.10: (a) SV stage 1 and the VS
   library bar, side by side on the CPU; (b) IT step 0 (small download) and the DP tower replay;
   (c) MF; (d) VS stage 2 on the GPU; (e) FF last. RA (section 11) is not one of the six and keeps
   its own order in 11.6.

Steps 1-3, 6 and 8 were extended on 2026-11-12 (user: section 14 where it fits, section 12 last).
The rules of each idea are in its own section and are unchanged.

Not variations, so not listed here: the items that already passed but were never built or shipped
(`Almost ideas.md` part E: A1 persistence law, N1 cross-fit, N2-B, ENSF2 export, G2-2). They wait
for the user's go, not for a new test.

## 14. Three architecture ideas for the forecast engine (added 2026-11-12; step 0 measured, nothing trained)

Asked for: three ideas that are only about the AI architecture, each a new design for a major part,
taken from AI work elsewhere, checked against everything logged, then attacked and improved.

Why the forecast engine (Mode F and what surrounds it): it holds our largest skill (0.69 at one day),
and four of the last kills are about its design, not its data: N4 (one network for two input sets),
N5 (one network for all leads), N6 (a big network), C6 (run disagreement as spread). The climate
generator is input-limited (pattern P1), so a new body there has failed every time. Here the inputs
are rich and the design is the limit.

Rules as in sections 10-13: data on disk only, defaults bit-identical, a trained model gets a new
name, two seeds, fit years 2016-2020, test 2022, never 2026, pass and kill rules set now.

### 14.1 The three ideas

| Id | Idea in one line | Taken from | Part it replaces | Logged failure it answers | Nearest logged relative |
|---|---|---|---|---|---|
| SIGMA | Lead time is a noise level. The network gets a built-in shortcut (forecast pulled toward climate by a measured amount) and learns only what is left, scaled to size 1 at every lead | Image diffusion: the EDM recipe (Karras 2022), the reason one network works at every noise level | Mode F target and scaling, the four lead bins, the untuned ramp to climate in `router.py` | N5 KILL, N6 KILL, the routers AV1-AV3 | N5 (lead as an input, target unchanged) |
| CHORUS | Every forecast source is one token with its own measured error size. Tokens are mixed by a closed rule first; the network learns only the correction. A missing source is a missing token, never a row of zeros | Set and token models (Deep Sets, Perceiver), multi-source language models | Two separate networks (HRES-only, ENSF2) and the choice between them (ASK_LATER 21) | N4 KILL, C6 FAIL by rule | N4 (zeros plus a "present" bit) |
| STRAND | A member is one path through the launch window. Its random numbers age from hour to hour by a measured curve, and it keeps one real day as its template across the window | Video generation (noise linked between frames); Andrae et al. 2024 did it for a global diffusion model | The sampler: today every hour and lead is drawn on its own | none yet: the tool has no window product from the pool | review G3-2, patch line "same random numbers for all leads" |

### 14.2 Step 0, measured today (`new_plan_kit/b7_arch_step0.py`, log `kit_b7_arch_step0.log`)

Rows: `data/modeF_v2`, NM/TX box, 350,399 rows, fit years 2016-2019 (beta fitted on 2016-18, shown
on 2019). Truth is ERA5. Eight heights from 10 m to 15 km. Read-only, about one minute.

**(a) Size of today's training target, truth minus forecast, as a share of the climate spread
(variance; 1.0 = no better than climate):**

| Lead | 0.25-1 d | 1-2 d | 2-4 d | 4-6 d | 6-7.5 d | 7.5-10 d |
|---|---|---|---|---|---|---|
| Wind, today's target | 0.09 | 0.13 | 0.23 | 0.43 | 0.72 | 1.11 |
| Wind, after the shortcut | 0.08 | 0.12 | 0.21 | 0.38 | 0.57 | 0.77 |
| T, today's target | 0.05 | 0.08 | 0.15 | 0.30 | 0.60 | 0.93 |
| T, after the shortcut | 0.05 | 0.08 | 0.15 | 0.28 | 0.51 | 0.70 |
| Share of the squared wind loss | 0.02 | 0.02 | 0.08 | 0.16 | 0.20 | 0.51 |
| Share of the rows | 0.10 | 0.10 | 0.20 | 0.20 | 0.15 | 0.25 |

- The target grows 12.6 times (wind) and 18 times (T) from the first bin to the last. Half of the
  squared loss sits in the last bin; leads under 2 days hold 20 % of the rows and 4 % of the loss.
- Beyond 7.5 days the target is LARGER than the climate spread (1.11; 1.45 at 10 m). The network
  must first undo the forecast before it can add anything.
- The measured pull toward climate (beta; 1 = trust the forecast fully): 10 m wind 0.82 / 0.79 /
  0.75 / 0.61 / 0.46 / 0.30 by lead bin; 5 km wind 0.99 / 0.98 / 0.92 / 0.79 / 0.61 / 0.41. So
  even at day 1 the 10 m forecast should be pulled 18 % toward climate (target 0.28 -> 0.24).
- This fits N5: with all leads in one network the short leads lost 1-2.7 % and the leads beyond
  7.5 days won 3 %. The long leads own the loss.
- Limits: the training loss is absolute, not squared, so the imbalance there is about the square
  root (3.5-4 times). A network can learn the pull by itself; the table shows what it must spend
  its capacity on, not a gain. Climate means come from 26 rows per cell, so ratios are a bit high.

**(b) Two runs for the same hour and place (2,200-3,100 pairs per lead bin, older run 30-72 h older):**
their wind errors correlate only 0.37-0.53. The best fixed mix of the two cuts the squared error by
1-5 % up to 4 days and by 6-13 % at 4-7.5 days (0.5-3 km: 3.8 / 4.9 / 5.4 / 10.2 / 13.2 %). The
size of their disagreement ranks the newer run's error at 0.15-0.38 (C6 found 0.30-0.38).

**(c) One run alone:** its own change over the next 6 hours ranks its error at 0.25-0.39 for 0.5-9 km
at leads of 1-7.5 days (0.10-0.21 at 10 m). This needs no second run and no extra feed.

**(d) One run at two leads, same place, wind error correlation:**

| First lead | 6 h apart | 12 h apart | 24 h apart |
|---|---|---|---|
| 0.25-2 d | 0.16-0.28 | 0.02-0.11 | 0.02-0.13 |
| 2-4 d | 0.29-0.48 | 0.10-0.25 | 0.09-0.16 |
| 4-6 d | 0.42-0.69 | 0.18-0.50 | 0.06-0.31 |
| 6-7.5 d | 0.49-0.80 | 0.23-0.60 | 0.06-0.39 |

A pool that draws each lead on its own has 0.00 here. The truth itself, 6 h apart: 0.65-0.89.
Limit: the store has 6-hour steps, so nothing is known for 1-3 hours apart.

**(e) Memory of the place (a fourth candidate, ECHO, see 14.6):** subtracting the place's own mean
error changes the wind error by -2.2 to +1.7 %. The 20 most similar past forecasts of the SAME
place do worse than the 40 most similar of ALL places (10 m wind -7 to -15 % against -15 to -27 %;
aloft at short leads +1 to +4.5 %, i.e. worse than no correction).

### 14.3 SIGMA: lead time is a noise level

**Version 0.** A forecast is the truth with noise added, and the noise grows with lead. Image
diffusion networks face the same thing: one network, every noise level. What made that work is the
EDM recipe: output = shortcut x input + scale x network, with the shortcut and the scale set by the
noise level, so the network's own job has size 1 everywhere. Ours:

```
member = climate mean + beta x (forecast - climate mean) + s x F(inputs, noise draw)
beta, s : measured tables (how much to trust the forecast, how large the rest is)
F       : the engression network, target (truth anomaly - beta x forecast anomaly) / s, size 1 at every lead
```

**Improvements, in the order the flaws were found:**

1. *Flaw: beta and s by lead only.* They differ by height (10 m 0.82, 5 km 0.99 at day 1). Now one
   smooth curve per height and variable, two numbers each, so any lead works. No bins, no seam
   between routers, no ramp.
2. *Flaw: where does "climate" come from at a new place?* From the climate generator's own pool
   (mean and spread per height), which the tool has everywhere. At very long lead beta -> 0 and
   s -> 1: the forecast pool BECOMES the climate pool by the formula. That is N7's aim (one
   generator) without N7's training.
3. *Flaw: resampling noise.* With the same noise draw at every lead, a member moves smoothly from
   its climate value to its forecast value as launch day nears. The go / no-go number over the
   countdown then changes because the weather changed, not because the dice were rolled again.
4. *Flaw: N6.* A big network was best at 1-3 days (-4.7 to -5.8 %) and worse at 7 days (+2.2 to
   +4.0 %). Scaling the target does not stop overfitting on noisy rows. Fix (NEST, from nested
   "Matryoshka" networks): the units are ordered; rows with large s train and use only the first
   128, rows with small s use all 512. One network, large where there is signal, small where not.
5. *Flaw: s knows only the lead, not the day.* Three free signals rank the error inside a lead bin
   (14.2 b, c): run disagreement, the run's own 6-hour change, the spread of errors of similar past
   forecasts (0.20-0.44). s = table x g(signals), g a monotone rule with four numbers, held to
   0.8-1.5. This is the C6 factor (CRPS -0.69 % [-1.19, -0.24]) placed inside the target, so the
   network trains on what is left over.
6. *Flaw: a simple rule may tie (P4).* Arm B0 is the formula with F replaced by a plain bell-curve
   draw. SIGMA must beat B0 and the shipped model. B0 ships nothing, it is the bar.
7. *Later, not in the first test:* one noise level per height. A height with a radar reading gets
   the reading's s, the others keep the forecast's. Then `observe` is the same network (the
   any-sensor idea of the review, G3-5, given a concrete body). Only after stages 1-2.

**Stages.** (1) CPU, no training, 30 min: arm B0 on 2020, to fix the curves and see the bar.
(2) Train SIGMA at the shipped size (width 128, depth 2) on all leads to 10 days, world start as in
N2; 1.5 h CPU per seed. PASS = N5's own rule, unchanged: leads 1-7 within 0.5 % of the shipped
binned model, beyond 7.5 days better than the climate model and the router mix. KILL = N5's: worse
by more than 1 % at leads 1-3 in both seeds. (3) NEST at width 512, 30 min GPU. PASS = N6's rule,
unchanged: at least 1 % better at every lead, interval excluding 0, both boxes, both seeds, cov99
within 0.003. KILL: lead 7 d worse in both boxes.
Honest odds: stage 2 medium, stage 3 medium to low. What is new against the nearest work: N5 gave
the network the lead and changed nothing else; ERDM (2025) sets noise by lead inside a many-step
diffusion model; no logged idea and no source found reads a forecast as an already-noised truth
with a measured noise level in a one-step network.

### 14.4 CHORUS: every source is a token

**Version 0.** Sources: the newest run, older runs for the same hour, the same run 6 h before and
after, ensemble mean and spread, later an AI model. Each becomes a token (profile, source type,
lead). A query attends over whichever tokens exist and feeds the SIGMA body.

**Improvements:**

1. *Flaw: free attention over 3-5 tokens will tie a plain network (P4) and can overfit.* Start as
   the closed rule: weights from each token's own s and the measured error link between sources
   (0.37-0.53). This is the best fixed mix of 14.2 b, written as attention with no free numbers.
2. *Flaw: why would this survive where N4 died?* N4 fed zeros and a "present" bit; the trunk saw
   two different input worlds and lost 1.0-2.6 % in both. Here the trunk always sees ONE mixed
   profile with the same statistics; more sources only make its s smaller. A missing source cannot
   push the inputs off their range. That is the mechanism that differs.
3. *Flaw: what exists on launch day?* The same run's neighbours in time are always there (one
   download holds every lead). Yesterday's run is kept by the tool's own logger. The ensemble
   stays optional. So the smallest live set needs no new feed.
4. The weighted disagreement between tokens goes into SIGMA's g (improvement 5 there). One place
   for C6, the ENSF2 spread and the 6-hour change, in place of three separate attempts.
5. *Learned part, only after 1-4 pass:* small zero-started corrections to the weights by source
   type, lead and height band ("attention that starts as the closed rule").

**Stages.** (1) CPU, 1 h, no training: rebuild rows at fixed points from `data/raw/wb2_hres_v2`
(the random points of today's rows give too few pairs; 12 h pairs then exist too). Feed the shipped
Mode F the mixed profile against the newest run alone. PASS: CRPS better with an interval excluding
0 at 5 and 7 d, not worse by more than 0.5 % at 1 and 3 d, 2022, both seeds. KILL: no lead better.
(2) One network with 1 to K tokens. PASS = N4's rule, unchanged: with the ensemble within 0.5 % of
ENSF2, without it within 0.5 % of HRES-only, both boxes. KILL = N4's: either side worse by more
than 1 % in both seeds. Honest odds: stage 1 medium to high at 5-7 d, stage 2 medium.
Nearest published work: lead times as tokens for post-processing AI forecasts (Hua and Sobash,
arXiv 2505.11750); none found that treats lagged runs as tokens or starts attention as the closed
mix.

### 14.5 STRAND: a member is a path

**Version 0.** One noise draw for all hours and leads of a member (published for a global diffusion
model: Andrae et al., arXiv 2410.05431; logged as one patch line in the review, never run).

**Improvements:**

1. *Flaw: "same noise" means error correlation 1.0.* Measured 6 h apart: 0.16-0.28 at days 1-2,
   up to 0.80 at days 6-7.5 (14.2 d). Noise must AGE: next = r x previous + sqrt(1 - r x r) x new,
   r from the measured curve by lead and gap.
2. *Flaw: the network is not a straight line in its noise.* So r is tuned per lead bin until the
   OUTPUT errors show the measured correlation (5 numbers, fit years).
3. *Flaw: the stack order (trap 2).* The shuffle re-orders each lead on its own and wipes the link.
   Fix: a member keeps ONE real day as template across the window, with the template hour moving
   with the clock. Whole members only, ranks never mixed (trap 3).
4. *Flaw: where does it pay?* At day 1 the error part is 3-8 % of the climate spread aloft, so the
   window is carried by the forecast itself. The gain is at days 4-7 (planning a scrub day), at
   10 m, and in climate and past mode, where the truth 6 h apart correlates 0.65-0.89.
5. *Flaw: a launch window is 1-3 h, the forecast store has 6 h steps.* First target is therefore
   climate and past mode on the hourly ERA5 box store (33 years on disk).

**Stages.** (0) CPU, 20 min: real probability that 10 m wind stays under a limit for 3 hours in a
row, against the same from independent draws. STOP if they differ by under 0.02. (1) Aged noise plus
moving templates. PASS: that probability error halves, per-hour CRPS within 0.0009, both seeds.
KILL: any per-hour score worse beyond tolerance. Honest odds: low to medium; the premise holds
fully only beyond day 4. Its core is published; ours adds the measured ageing curve, the one-step
network and the pass through the shuffle.

### 14.6 Measured or weighed, then dropped

| Candidate | Why dropped |
|---|---|
| ECHO: the place's own past forecast errors as a prompt (in-context learning, as in table foundation models), to get the N2 fine-tune gain with no training | Measured (14.2 e): inside one box the place's own memory adds under 2.2 % for wind and same-place look-alikes do worse than all-place ones. What all-place look-alikes gain (10 m wind -15 %) is what SIGMA's beta already gives (-14 %). The regional form (world against box, the real N2 gap) is not tested |
| Network weights written by a second network from terrain (as "text to LoRA", 2025) | Terrain and climate descriptors have not predicted the local part so far (N2-C MISS, L3-5); overlaps SV (12.4) in aim |
| One latent "real air" with a small head per instrument (as in learning from many noisy labellers) | It is RA + IT + C5 trained as one object; nothing new to measure before RA stage 2 |
| A learned table of numbers per place (as node parameters in AIFS) | Same aim as SV; needs the global training run of `GLOBAL_PLAN.md` |
| One calibration network conditioned on season, hour, spread | Splitting calibration by season and by spread found nothing (IL-2, review "what failed" 3); the useful signals are forecast-side and now sit in SIGMA's g |

### 14.7 How the three fit, and the order

```
sources (runs, neighbours in time, ensemble)  -> CHORUS: one mixed profile + its error size s
mixed profile, s                              -> SIGMA : shortcut + s x network (NEST width by s)
noise draws that age, one template day        -> STRAND: members that are paths
-> range calibration, shuffle, maps (unchanged) -> pool
```

Each part can pass or fail alone. Order: SIGMA stage 1-2 first (it decides the body), CHORUS
stage 1 beside it (no training), STRAND stage 0 any time. One Mode F job at a time (14-17 GB).
Place in the overall work order: steps 1, 3 and 6 of 13.5.

Not checked: everything in 14.2 is one box (NM/TX), ERA5 as truth, 2019 as the shown year; the
lagged pairs are 30-72 h apart only; outside papers were read as search summaries, not in full.
Sources: EDM (arXiv 2206.00364); Elucidated Rolling Diffusion (arXiv 2506.20024); Continuous
Ensemble Forecasting (arXiv 2410.05431); leads as tokens (arXiv 2505.11750); Matryoshka
representation learning (arXiv 2205.13147).

---

## 15. STOP FIRST: code audit of 2026-11-12, to be fixed before any more trials (added 2026-11-12 evening; nothing here has been fixed)

Source: a read-through of the core code on 2026-11-12 (`tempest/generator`, `tempest/scoring`, `tempest/calibrate`,
`tempest/forecast`, `tempest/profiles`, the ingest parsers, `tempest_weather` and `tempest_weather_v2`). Three items were
reproduced with small scripts; the rest are from reading and say so. No code was changed by the audit.

### 15.0 The gate (user instruction, 2026-11-12: "to be done immediately, before any more trials")

1. **No new trial starts until 15.1 to 15.4 are done.** A trial = any training run, any scoring run whose number will
   be read as a verdict, any export. Sections 10 to 14 wait. Jobs already running may finish; their verdicts are
   **not read** until AU-1 is in and the run is rescored with it (or the verdict is of the kind AU-1 does not touch,
   see the table in 15.1).
2. Order: AU-1, AU-2, AU-3, AU-4 (the four that change numbers people read), then AU-5 to AU-7 (step 0 of each
   first, they may close with one line), then 15.3 (small defects, one sitting), then 15.4 (re-read of old verdicts).
3. The usual rules hold for every item: one change at a time; new behaviour behind a flag that is off until its
   check passes (a plain bug with one right answer may be on by default with a switch back to the old behaviour, as
   `OPTIONS["permute_blocks"]` was); a test for every fix; no pytest while a GPU score runs; `scripts/tool_audit.py`
   after anything that touches the shipped tool; commits as the standing rules say.
4. **The 2026 January-June final test is not rerun for any of this** (it was run once, lock `data/FINAL_TEST_DONE`).
   Where an item changes how its numbers should be read, the report gets a caveat line and the question goes to
   `docs/agent/ASK_LATER.md`.
5. Each item ends with one dated line in section 9 (result and what it changed) and one line in
   `docs/AI_MISTAKES_CHECKLIST.md` section B where it is a new class of mistake (AU-1 and AU-3 are).

Overview:

| Id | What is wrong | Status of the evidence | Changes old numbers? | Cost |
|---|---|---|---|---|
| AU-1 | The climatology baseline is scored from a thin pool with an estimator that punishes thin pools | measured | **yes: every "skill vs climatology" number** | 1 day, one GPU score per headline |
| AU-2 | Forecast mode moves samples to the site with the wrong grid heights | reproduced | forecast-mode t2m / pressure / density off the grid points | 1 h |
| AU-3 | Forecast mode very likely corrects surface values for height twice | from the Open-Meteo documentation, not yet seen live | forecast-mode pad pressure and temperature | 2 h, one live call |
| AU-4 | Bootstrap intervals resample single days although weather lasts several days | reasoning, size not measured | interval widths, so verdicts near zero | half a day |
| AU-5 | The ERA5 truth of the test years carries noise profiles the model was trained on | from reading | coverage on ERA5 (not relative skill) | step 0 half a day |
| AU-6 | Balloon scoring and the correction pool use complete soundings only | from reading | balloon scores, if the drop depends on the weather | step 0 2 h |
| AU-7 | The Earth-GRAM-style margin mixes shape and warming | from reading | how the 6.7 % is described | 2 h + one score |
| AU-8 .. AU-18 | eleven smaller defects | AU-8 and AU-13 measured, the rest from reading | small or none | 1 day together |

### 15.1 The four that change numbers

#### AU-1. The climatology baseline is handicapped by its pool size

**What is wrong.** `tempest/scoring/score.py` lines 187-197 build the two climatology sets (`clim`, `clim15`) by
drawing m = 199 samples **with replacement** from the real rows of the test row's group (grid point x month x 2-hour
bin). `crps_ensemble` (line 40) is the plain ensemble CRPS, not the fair one: an ensemble built from R distinct real
values is charged about `E|X - X'| / (2R)` on top of its true CRPS, roughly 1/R of the CRPS. The model draws 199 fresh
values, so it pays 1/199 only. The gap is credited to the model as skill.

**Evidence (2026-11-12, scratch scripts, nothing saved in the repo).** In `data/train/pilot80_dpd.npz` the test rows of
2024-25 have a median of **75** pool rows for `clim15` (10th to 90th percentile 61 to 86) and **221** for `clim`.
A synthetic model with **no skill at all** (199 draws from the true distribution) scored against such pools:
+0.0125 at R = 75, +0.0101 at R = 100, +0.0047 at R = 220, +0.0011 at R = 900. The README headline is +2.8 % against
the recent 15 years on ERA5 and +0.8 % on balloons, so a large part of the first number may be this effect.
Not measured: the real pools are not independent rows (same weather on neighbouring days), so the true size on our
data can differ from the synthetic one; the balloon pools (`sonde.py` lines 146-153) were not counted.

**What it does not touch.** A comparison of two models against the same baseline keeps its sign (both get the same
bonus). The Gaussian baseline draws fresh values from a fitted law, so "model minus Gaussian" is not inflated; but
"Gaussian vs climatology" was flattered by the same amount as the model.

**Fix.**
1. `score.py`: new flag `--fair-baseline` (off by default until step 4 passes; outputs get a `_fair` suffix).
   - Add `crps_fair(x, y)`: same sorted formula, spread term divided by `m (m - 1)` instead of `m^2`. Use it for
     every set when the flag is on.
   - Score `clim` and `clim15` from the **whole pool of the group, without replacement**: per group key, the sorted
     physical rows of the pool (cache per key, as `trust.ClimPool` already does), fair CRPS with m = R for that row.
     Rows whose pool has fewer than 20 rows fall back to the all-years pool and are counted in the log line.
   - Keep the 199-draw `clim` array for everything that needs an (N, 199, D) array (shuffle templates, variogram
     score, coverage, `--tail`, `--mc`, `--stress`); only the CRPS and MAE columns of the baselines change source.
   - `diag.headline`: accept ready per-row CRPS arrays for the baselines (`crps_override={"clim": ..., "clim15": ...}`)
     so the bootstrap uses the fair numbers.
2. Same change in `tempest/scoring/sonde.py` (balloon pools `r` and `r15` per station and month) behind the same flag.
3. Every other place that scores a climatology the same way: `grep -rn "crps_ensemble\|crps_sorted" tempest scripts new_plan_kit`
   and list each caller in the log with "pool with replacement: yes / no". Known ones: `scripts/il6_modeF.py` (mode F
   skill vs climate), `scripts/fv2_eval.py`, the kit scripts that print skill vs climate (b8 AV1 / AV2 among them),
   `tempest/calibrate/trust.py` (its w = 0 end is the pool's quantiles at 199 levels, so it is not affected: note it).
4. Tests (`tests/test_fair_baseline.py`): (a) the synthetic no-skill model gives |skill| < 0.002 with the flag and
   about +0.012 without (R = 75); (b) with a pool of exactly 199 distinct rows the fair pool score equals the fair
   score of those 199 as an ensemble; (c) flag off reproduces today's CSV byte for byte on a small fixture.
5. One GPU score of the shipped stack (`l3_c4w`, the exact flags of the last headline run) with `--fair-baseline`,
   and one `sonde` run. Write both headlines side by side into section 9.
6. Second step, only if step 5 shows the pool is still the limit: the dataset keeps about 8 % of the available
   point-hours, so a baseline built from the profile store itself would have about 900 hours per group. Measure first
   (`new_plan_kit`, CPU, between GPU steps: store read) how much the fair whole-pool CRPS still falls from R = 75 to
   the full store on 2,000 test rows; build the store-based baseline only if it moves skill15 by more than 0.003.

**Pass rule (set now).** The flag becomes the default when tests 4a-4c pass and the rerun is reproducible to 0.0005
on a second score seed. From then on every pass rule that names "skill15" means the fair number.

**After the fix.** Update the README status lines, `docs/results/FINAL_REPORT.md` (caveat only, no rerun, see 15.0
point 4), the Earth-GRAM comparison text, and re-read the verdicts listed in 15.4.

#### AU-2. Forecast mode moves samples to the site with the wrong grid heights

**What is wrong.** `tempest_weather/api.py` line 496: `dz_row = (elev - elev_row[:n]) if used != "past" else ...`.
`elev_row` is the height of the grid point each block of 199 samples was assigned to (right for the climate
generator, which runs at that point). In forecast mode the profile was built **once**, at the nearest grid point's
height (`_forecast_phys(..., elev_grid, ...)`), so every row needs the same shift `elev - elev_grid`.

**Evidence.** Canned forecast (the fixture of `tests/test_tool_forecast_mode.py`), Spaceport America (32.99, -106.97),
n = 1024, `elevation=1401`: 995 samples were moved by -94.5 m and 29 by -115 m, a 2 hPa split in surface pressure
inside one answer. Small here because the four neighbours are 1383 to 1516 m and the weights are lopsided; half-way
between two points 300 m apart it is several hPa and a few tenths of a kelvin, two-peaked.

**Fix.** One line: `dz_row = (elev - elev_row[:n]) if used == "ai" else np.full(n, elev - elev_grid)` (the fetch-failure
fallback sets `used = "ai"` before this line, so it stays right). Plain bug: on by default, with
`OPTIONS["forecast_single_shift"] = True` and the old line behind `False`.

**Test.** In `tests/test_tool_forecast_mode.py`: wrap `_core.site_shift`, call `atmosphere_set` in forecast mode at an
off-grid point with n = 1024, assert the `dz` it received has one value equal to `info["elevation_m"] - info["grid_elevation_m"]`.
Then `scripts/tool_audit.py`.

#### AU-3. Forecast mode very likely corrects surface values for height twice

**What is wrong.** `tempest_weather/sources/openmeteo.py` lines 21-24 send no `elevation`. The Open-Meteo
documentation says that by default 2 m temperature and surface pressure are downscaled to its own 90 m terrain height
at the requested point. The tool reads them as values at the ERA5 grid height (`forecast.py` line 113 keeps `sp` as
given; `forecast_profile` measures the pressure levels against `z_sfc_m` = the grid height) and then shifts them to
the site (`api.py` 496-498). With `elevation=1401` at Spaceport America (grid 1495.5 m) that second shift is about
+9.6 hPa and +0.6 K, about 1 % in pad density. Mode F was trained on grid-height fields (WeatherBench2 HRES against
the ERA5 grid), so the grid height is the consistent input.

**Not verified:** no live call was made in the audit. Step 0 settles it.

**Step 0 (one live call, minutes).** For one grid-misaligned point fetch the same hour three ways: default,
`&elevation=<ERA5 grid height>`, `&elevation=nan`. Print `doc["elevation"]`, `temperature_2m`, `surface_pressure` of
each. If the three agree, close AU-3 with one line. If they differ as the documentation says, do the fix.

**Fix.**
1. `openmeteo.url` / `fetch` take `elevation=None` and send it when given.
2. `_forecast_phys` calls the default fetch with `elevation=z_sfc` (the grid height). A user-supplied `fetch(lat, lon, day)`
   keeps its three-argument form: call it as today, then compare `doc.get("elevation")` with the grid height.
3. In both cases, if the response carries an `elevation` more than 5 m from the grid height, move `t2m` and `sp` from
   the response height to the grid height first (same lapse rate and hypsometric step as `_core.site_shift`) and add
   the flag `forecast-surface-values-moved-from-source-height`. No silent path.
4. The bias state (`tempest_weather/bias.py`, written by `scripts/update_bias.py` from the logger files): check which
   height its forecasts were fetched at. If the state was built from default (terrain-height) forecasts, its
   2 m temperature bias includes the height offset; rebuild the state from the same request the tool now makes, or
   apply the bias before step 3. Write down which.
5. `tempest/nearterm/ensemble.py` already uses `doc["elevation"]`: nothing to do there; say so in the log.

**Tests.** Unit test with a canned response that carries `elevation` 90 m below the grid: output `sp` and `t2m` at the
site equal the hand-computed single shift. Live check once (A13): the tool's forecast-mode pad pressure against the
nearest ASOS altimeter-derived station pressure on three days, before and after.

#### AU-4. Bootstrap intervals use one-day blocks

**What is wrong.** `tempest/scoring/diag.py` lines 140-143 (`headline`) and 85-102 (`block_bootstrap_ci`) resample
whole days. Score differences stay correlated over a weather system (several days), so the intervals are too narrow
and a result whose interval just clears zero may not be a result. The size is not measured.

**Step 0.** Scorer flag `--daily` writes `<stem>_daily.csv`: per day and band, the summed CRPS of each set and the
row count (cheap, the arrays are already there). From one existing-configuration run compute the lag 1 to 10 day
autocorrelation of the daily mean difference (model minus clim15) per band.

**Fix.** `block_days` argument in both functions (default 1 = today's numbers). Day ids become true day numbers
(`year * 1000 + doy` is not continuous across the year end: convert with `datetime64`), block id = day number
// block_days. Choose the block as the first lag where the autocorrelation is below 0.1 in every headline band,
rounded up, at least 3; print the intervals for 1, 3, 5 and 7 days side by side once.

**Pass rule.** The chosen block becomes the default for every interval a rule reads. Test: an AR(1) daily series with
rho = 0.7 gives a 95 % interval that holds the true mean in 93-97 % of 400 synthetic repeats with the chosen block and
clearly fewer with block 1.

### 15.2 Three that change how results are read (step 0 first; each may close with one line)

#### AU-5. The ERA5 "truth" of the test years carries noise the model has seen

**What is wrong.** `tempest/calibrate/station.py` `apply` (lines 154-172) adds one leftover balloon profile from a
fixed pool (fit years up to 2020, at most 3,000 per group and moisture class) to every corrected ERA5 row, training
years and test years alike. The scorer's truth for 2024-25 therefore contains the very leftover profiles the
generator was trained to reproduce. Relative skill is fair (the baselines get the same truth); **coverage and
calibration on ERA5 are flattered**, because the real 2024-25 departures are a fresh draw.

**Step 0.** Fit a second leftover pool from the 2021-23 balloon pairs with the existing a, b tables (rows the map
never used). Rebuild only the 2024-25 test rows with that pool (`build_dataset` gets `--leftover-pool FILE`
`--first-year 2024`), score the shipped stack against both truths with the same seed. If cov99, cov90 and CRPS differ
by less than the seed noise (0.003) in every band, close with one line.

**Fix if it matters.** Keep the fresh-pool test file as the standard truth for coverage claims; say in README and the
report that ERA5 coverage is "against a truth with an unseen noise pool"; balloon coverage stays the reference.
No retraining: the training targets are not wrong, only the test truth was too familiar.

#### AU-6. Balloon scoring and the correction pool use complete soundings only

**What is wrong.** `tempest/scoring/sonde.py` line 131 keeps a sounding only if all four variables are present at all
44 heights to 18 km plus the surface; `station.py` line 140 does the same for the leftover pool (and `modeP.load_pairs`
for mode P). Balloons that burst early or lose wind tracking are dropped. If that happens more on windy or stormy
days, the scores and the correction miss exactly those days.

**Step 0 (CPU, light).** For each station and test year: share dropped; then, using ERA5 at the launch hour, the
dropped share by class of 500 hPa wind speed (terciles) and by month, and which variable and height caused the drop
(humidity above 10 km is the likely main cause, which is not weather-dependent). If the dropped share does not rise
with wind by more than 5 points between the calm and the windy tercile, close with that table.

**Fix if it matters.** `sonde.py --partial`: keep a sounding when at least the lowest 5 km of wind and temperature
are complete; score per column with a validity mask (`diag.headline` already takes `valid`); baselines for a column
come from pool soundings valid at that column; whole-profile statistics stay on complete soundings and say so.
For the pool in `station.fit`: allow leftovers whose only gaps are humidity above 10 km, with those heights taken
from a complete leftover of the same group (flagged in the table as `n_patched`). Refit, compare the tables, and
retrain only if the windy-tercile correction changes by more than its own bootstrap noise.

#### AU-7. The Earth-GRAM-style margin mixes profile shape and warming

**What is wrong.** `score.py` lines 201-209 fit the Gaussian baseline on all training years, while the model has the
year as an input and `clim15` uses the last 15 years. "Beats the Earth-GRAM-style reference by 6.7 %" is true as
measured but part of it is the trend, not the non-Gaussian shape.

**Fix.** Add a second Gaussian set `gauss15` fitted on the same recent-15-year rows as `clim15` (thin groups: the
existing month-only fallback, threshold 300 rows instead of 600 for this set). Headline gets `margin_gauss15_*`
beside the existing columns (additive, nothing removed). One score. Report both: "against a fixed-climate Gaussian
(what such tools ship)" and "against a Gaussian of the recent climate (the shape part alone)". Do this together with
AU-1 step 5 so it costs no extra run. Keep `new_plan_kit/b9_gram_compare.py` (another session's, untouched) in mind:
its numbers need the same two labels.

### 15.3 Smaller defects (one sitting; each with its own test)

| Id | Where | What is wrong | Fix | Check |
|---|---|---|---|---|
| AU-8 | `tempest_weather/sources/indices.py` 34-37 vs `tempest/ingest/index_forecast.py` 28-35 | The tool's index forecast is called a copy of the tested ridge but lacks its three QBO-phase inputs (sin, cos of the phase angle, amplitude). Measured: QBO means differ by 1-3 m/s at 3, 6, 12 months; spreads agree. `--driver-mode ridge` therefore scores something slightly different from what ships. | First read `scripts/index_bakeoff.py` to see which design the 2012-25 hindcast tested. Port that one into `Indices._design` / `forecast` (QBO sd from the rows up to the last observed month). Code only, no export. | Parity test: tool mean and covariance equal `index_forecast.fit` at h = 1, 6, 12 to 1e-6 relative on the exported snapshot. |
| AU-9 | `tempest_weather/_core.py` 155, `tempest/generator/sample.py` 96 | Site shift of humidity: the new temperature already carries the height fade `w`; the humidity line blends with `w` again, so the change is under-applied aloft (about 1.5 instead of 4 points of RH at 1.5 km for a 500 m site offset). | Replace the blend by `rh * es(t_old) / es(t_new)` in both files in the same commit (the parity test ties them). | Hand value at one height; one `sonde` run (it uses `to_site`): RH 0-1 km and 1-5 km CRPS not worse than seed noise. |
| AU-10 | `tempest_weather_v2/readers.py` 299-314 | `above_top="climatology"` does exactly what `"hold"` does; the docstring promises standard-atmosphere T and p. | Correct the docstring ("alias of hold: T and p continue from the top value along the standard lapse rates"); a true switch to the standard atmosphere would put a jump at 18 km, so do not build it. | Test that the two policies return identical numbers, so the alias is deliberate. |
| AU-11 | `tempest/calibrate/spread.py` 30, `_core.py` 55 | The width floor of the range map is 10 % of the median half-width **of the batch**: thousands of rows in the scorer, one block of 199 in the tool (where it does nothing). Near-saturated or bone-dry humidity rows are treated differently in scoring and serving. | Step 0: count how often the floor binds in the scorer per column. If below 0.1 % of cells outside RH, close. Else store the per-column floor in the calibration file at fit time (`hw_floor`), use it in `apply` when present (old files unchanged), refit the shipped maps and re-export. | Parity test tool vs scorer on rows with RH pinned at 100 %. |
| AU-12 | `tempest_weather_v2/launch.py` 437 | A conditioned pool sets every sample's launch time to the first sample's, so a time window collapses silently after `observe()`. | Keep the base pool's times (cycled to n), evaluate the gust law per sample hour as `_regust` already can, add the flag `window-hours-not-used-by-conditioning`. | Test: windowed Launch + `observe()` keeps more than one distinct launch hour and carries the flag. |
| AU-13 | `tempest/calibrate/station.py` 55-79, `configs/region.toml` | Measured: 914 of 20,571 Santa Teresa soundings (all 1991-95, the El Paso site before the move) start about 60 m from the listed launch height and are paired with the present site's grid point. | `read_igra(..., launch_height=None, tol_m=30)`: with a height given, drop soundings whose first level is further away and print the count. Step 0: refit the station map with the filter and compare a, b and the pool sizes; adopt the filter for new fits; retrain nothing unless a table entry moves by more than its bootstrap noise. | Unit test with two synthetic soundings; the count line in the fit log. |
| AU-14 | `tempest/export_tool.py` 113-116 vs `score.py` 273 | Shuffle templates: the export uses years before 2021, the scorer years before the first test year. | No change to the shipped assets. Add `--template-before-year` to the scorer and use 2021 in runs that claim to score "as shipped"; `tool_audit.py` already scores the real assets. | The flag appears in the run header of the next as-shipped score. |
| AU-15 | `tempest/nearterm/ensemble.py` 66-72 | No 100 m anchor: wind between 10 m and the first pressure level above ground is linear in height above 100 m, which reads low at 100-300 m (a log profile gives 62 % of the step at 100 m between 10 and 400 m, the line 23 %). Not used by the shipped tool yet. | Interpolate in ln(height) up to the first level above ground (per column), or request the 80 / 120 / 180 m winds where the model serves them and use them as anchors. Before any calibration on the logger archive starts. | Synthetic log-profile test: error at 100, 150, 200, 300 m below 0.2 m/s. |
| AU-16 | `tempest/scoring/ridge_drivers.py` 34-35 | ONI and the 3-month lagged ONI are drawn independently although they move together; for leads under 3 months the lag is already observed but is drawn. Inactive today (no shipped model has the lag input). | When the lag month is observed, use it; otherwise draw both from one joint forecast (fit at h and h - 3 with a shared residual draw). Do it before any p2-feature model is scored in ridge mode. | Test: correlation of the drawn pair within 0.1 of the observed one at h = 6. |
| AU-17 | `tempest_weather_v2/launch.py` 1030-1033 | `stale(now)` fails on a naive `now`. | Treat a naive `now` as UTC, as the rest of the tool does. | One-line test. |
| AU-18 | `tempest/profiles/to_heights.py` 123 | A pressure level a few metres above the 100 m anchor sits next to the 100 m wind and can make a false shear step in the 100-150 m layer. | Step 0: share of rows with a level at 100-150 m above ground and the 99th-percentile shear of that layer with and without them. Only if it shows: use pressure-level winds from 150 m up. A store rebuild, so it waits for the next planned rebuild. | The step 0 table. |

Also noted, no action now: (a) the "unknown drivers" set keeps the smoothed global temperature as known; that only
matters for a p2-feature model at multi-year lead (the shipped models use `year`). (b) Mode F is tested on one year
(2022) against ERA5, an analysis of the same model family as the forecast; already stated in the tool's trust line.

### 15.4 Old verdicts to re-read once AU-1 and AU-4 are in

Do not rerun everything. Sort the verdict tables (section 9, `docs/logs/AUTOPILOT.md`, `To-do-Concise.md`) into:

| Kind of verdict | Touched by AU-1? | Touched by AU-4? | Action |
|---|---|---|---|
| Model A vs model B, same rows, same baseline (most KEEP / FAIL decisions) | sign no, size slightly | yes if the interval edge was within one interval-width of zero | recompute the interval from the saved per-row or daily files where they exist; else mark "interval to confirm" |
| "Beats climatology by x" (README, FINAL_REPORT, tool trust lines, mode F skill by lead, AV1 / AV2) | **yes** | yes | rescore the shipped stack once (AU-1 step 5); for the others state the pool size R of their baseline and the expected bonus 1/R until rescored |
| Rules with an absolute skill threshold ("skill15 >= ...", "above climate at day N") | **yes** | yes | re-read against the fair number; a pass within 1/R of the threshold is reopened |
| Coverage rules (cov99, cov90) | no | interval only | nothing, except AU-5 for ERA5 coverage |
| Earth-GRAM comparison | model-vs-Gaussian no; Gaussian-vs-climate yes | yes | AU-7 wording |
| 2026 Jan-Jun final test | yes (its climate skill) | yes | caveat line only; rerun is the user's decision (ASK_LATER) |

### 15.5 What the audit did not cover

Read in full: the generator (train, model, sample, features, dataset build), `score.py`, `sonde.py`, `diag.py`, the
calibration modules used by the shipped stack, the forecast modes, `to_heights`, the index code, `tempest_weather`
(`api`, `_core`, `engine`, `forecast`, `bias`, `coherence`, sources) and most of `tempest_weather_v2/launch.py`,
`readers.py`, `timeutil.py`, `weather_calc.py`. **Not read:** the 296 files in `scripts/`, `new_plan_kit/`,
`tempest_weather_v2/stats.py` and `montecarlo.py`, `tempest_weather/flight/dryden.py`, `tempest/output/`,
`tempest/ops/`, `scoring/mc.py`, `metrics_ext.py`, `extras.py`, `stress.py`. Verdicts that rest on those scripts
are unaudited. The test suite was not run (a GPU job was running). Checked and found sound: the year splits of the
generator, the range maps, debias, trust layer and mode F (no test-year leakage); the index order oni / wwv / qbo30 /
qbo50 across dataset build, scorers and tool; wind direction signs; the IGRA column positions; the altimeter and
density-altitude formulas; the shuffle cell indexing between export and tool.
