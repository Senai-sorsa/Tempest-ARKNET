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
