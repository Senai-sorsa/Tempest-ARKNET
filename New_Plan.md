# New_Plan: everything before global mode, in about 2 days

Written 2026-11-10. Sources merged: `Innovative idea review.md` (run list C1-C6, G1-G3 ideas),
`Limitations to solve.md` (audit defects A1-A9, "what to do first" table), and the open list in
`docs/HANDOVER_2026-11-10b.md` section 14.4 plus the unticked boxes of `docs/plans/FIVE_DAY_PLAN.md`.
The global track (G0-G6, supercomputer) is not in this plan.

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
| A7 (Limitations to solve): does the site roughness reach the turbulence step? Traced: `Launch.engine()` built the engine with no roughness and `TempestFlightSimEngine.sample_sobol_batch` used `z0_roughness_m=0.03` unless the caller passed `launch.z0()` by hand; it was not passed on any path | DONE behind a flag, default unchanged: `Launch.engine()` now puts the site roughness (median of the land-cover map values, = `Launch.z0()`) in `engine.info["z0_m"]`, and `sample_sobol_batch(z0_roughness_m="site")` uses it (a bad string or a missing value raises). New tests: default unchanged, 'site' = the info value and differs from 0.03, errors; Launch test checks info z0_m = Launch.z0(). Full suite 396 passed | making 'site' the default for Launch engines is the user's call (changes Dryden strength near the ground at rough sites) | `docs/results/logs/tests_after_A7.log` |

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
rated 6, parked) and the C5 referee. RA grows from both. New: (a) the finding that the data for it is
already on disk at 986 stations; (b) learning it from forecasts, so the truth is independent; (c) the
measured rule that the gap does not depend on lead, which makes it one added layer for all modes and
leaves every ERA5 score alone; (d) the ground, the 24 hours and the pad inside the same world model;
(e) a 6-number version that ships if the network fails.

Risks: balloon noise counted as real air (stage 3); hour and region tied together (stage 4); low
levels in the balloon files partly interpolated; the post-2022 change in balloon processing (review
trap 5: fit on 2016-22 only, year as an input); a gap added to a member can break the limits the
lapse map enforces (check the superadiabatic share in stage 5).
