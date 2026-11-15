# new_plan_kit: code and step-by-step instructions for `New_Plan.md`

Read this file from top to bottom once before you run anything. It is written so that a model with
no memory of the earlier work can continue. When this file and your own guess disagree, this file wins.

- **Part 1** rules you must follow.
- **Part 2** how to run a kit script (one pattern for all of them).
- **Part 3** what is built, in the order to run it, with the results already measured.
- **Part 4** what the results changed in the plan.
- **Part 5** items that are NOT built: how to build each one, step by step.
- **Part 6** how to write a new kit script (template).

Nothing in this folder edits the shipped tool (`tempest/`, `tempest_weather/`, `tempest_weather_v2/`).
Scripts that need a different setting change it **in memory only** and put it back. Every script only
measures and writes a log. Putting a result into the tool is always a separate task: report it.

---

## Part 1. Rules (hard; do not trade them for speed)

1. **Never use 2026 data. Never run `scripts/final_test_2026h2.sh`.** Fit on 2005-2022 (2021 for map fits), test on 2023-2025.
2. **Python:** never type `python` or `python3`. Always `PYTHONPATH=. .venv/Scripts/python -W ignore <script>` from the repo root (`C:\Users\Senai\Tempest-ARKNET`), in the Bash tool.
3. **CPU:** at most 12 threads in total. Before each run: `export OMP_NUM_THREADS=3` and `. scripts/cap_cpu.sh`. At most three kit scripts at the same time.
4. **RAM:** 31 GB. Scripts that build sample sets refuse to start under 8 GB free (`K.ram_gate`). If one refuses, wait for another job to end. Do not lower the gate.
5. **GPU:** one job at a time. All kit scripts run on the CPU (`--device cpu`). Do not run the test suite (`pytest`) while a GPU job runs.
6. **Do not delete anything.** A hook blocks `rm`, `del`, `rmdir`. A leftover file stays where it is.
7. **Do not kill jobs**, except a job you started yourself that is running out of memory or disk; then `taskkill //PID <n> //T //F` with the exact PID.
8. **Git:** commit only when the user asks. Stage files by name (never `git add -A`). Never commit `data/`, `models/`, `flight_sim_trial/`. No "Co-Authored-By" line. Never push.
9. **Do not touch:** files of other sessions (`SECTIONS_PLAN`, `docs/plans/fixing issues.md`, `scripts/ap_l3_fixes.sh`, Colab notes), a bash script while it runs, the two forecast loggers, security or registry settings, SSH keys.
10. **Downloads:** allowed by the user (see `New_Plan.md` section 8). Each one into its own new folder under `data/raw/`, add a line to `data/download_ledger.txt` (date, folder, size, why). Total budget 50 GB; stop if the disk has under 10 GB free.
11. **Changes to the tool itself** (anything outside this folder and `scripts/`): new behaviour behind a switch that is off by default, output without the switch identical to before, one small test, and the full test suite before you say "done".
12. **Noise sizes:** a CRPS change under 0.0006 (standardised headline) is noise; for two runs with the same seeds, under 0.0009. Intervals come from resampling whole days (`K.block_boot`).
13. **Fixed order of the calibration stack:** range map -> shuffle -> shear map -> lapse map. If you change one, refit every later one.
14. Report what really happened: copy the numbers from the log. If a run failed or was skipped, say so.

---

## Part 2. How to run a kit script

Every script has the same shape. Open it and read the text at the top first: it states the purpose,
the PASS / KILL rule, the exact command, the smoke-test command and the log file.

```bash
cd /c/Users/Senai/Tempest-ARKNET
export OMP_NUM_THREADS=3 PYTHONPATH=.
. scripts/cap_cpu.sh
# 1. smoke test first (seconds to 2 minutes; KIT_SMOKE=1 means: write no log)
KIT_SMOKE=1 .venv/Scripts/python -W ignore new_plan_kit/<script>.py <the smoke options from its header>
# 2. real run. Under 9 minutes: run it directly. Longer: in the background, then look at the output file.
nohup .venv/Scripts/python -W ignore new_plan_kit/<script>.py <options> > "$TEMP/kit_<name>.out" 2>&1 &
tail -5 "$TEMP/kit_<name>.out"
```

- The result is appended to `docs/results/logs/kit_<script name>.log`. The last line always starts with `VERDICT:` and says what to do next. **Do what the verdict line says.**
- If a script stops with `AssertionError` at once, a self-check failed: the code around it changed. Read the message; do not remove the check.
- `data/kit/` holds files the scripts pass to each other (it is not committed).

---

## Part 3. What is built (run order) and what it found

Status words: **DONE** = real run finished, result below. **READY** = smoke-tested, real run not finished when this was written (look for its log; if there is none, run it).

| # | Script | Plan item | Time | Status and result |
|---|---|---|---|---|
| 0 | `kit_common.py` | shared helpers (`K.tool`, `K.balloon`, `K.radar_uv`, `K.block_boot`, `K.report`, ...) | - | not run by itself |
| 0 | `b1_build_pool.py` | shared sample sets per stage (`stages(...)`), imported by the others | - | imported; needs no GPU (1500 rows take about 5 min on the CPU) |
| 1 | `b1_c5_triple.py` | C5 three-way referee (balloon, radar, forecast) | 5 min | **DONE.** 80 common hours. ERA5-to-real shear ratio: lower bound **1.33** [1.14, 1.53], upper 1.63. Usable (biased high). |
| 2 | `b1_c1_wave_law.py` | C1 step 1 wave law | 5 min | **DONE. PASS.** c per band 0.12 / 0.31 / 0.33 / 0.27, saved in `data/kit/c1_wave_law.npz`. |
| 3 | `b1_c2_premise.py` | C2 premise: shuffle or network? | 10 min | **DONE.** The shuffle makes all of the excess (share 1.00 / 1.00), even on real rows. The shipped maps already bring the rates to 0.213 / 0.0066 (truth 0.206 / 0.0031). **-> no GPU fine-tune.** |
| 4 | `b1_quick_checks.py trend` | G1-7 trend input | seconds | **DONE.** The network has a `year` input. G1-7 needs only the replay. |
| 5 | `b1_quick_checks.py il128` | IL-128 on real pools | 3 min | **DONE.** No inflation (worst ratio 0.84). The copula sampling LOSES 16-34 % of the p99.9 shear. G3-3 not triggered. |
| 6 | `b1_quick_checks.py oracle` | G1-4 oracle templates | 15 min | see RESULTS BLOCK below |
| 7 | `b1_observe_loso.py` | A3 observe from a neighbour station | 40 min | **DONE. All 7 neighbours FAIL on coverage** (0.67-0.82; wanted 0.85-0.95). CRPS improves for 5 of 7 (by 0.13-0.29 m/s). TCS with no report covers only 0.80. Fix = wider error for distant stations (`obs.py REP_TABLE`), Part 5 item A3-fix. |
| 8 | `b1_shape_scores.py` | G2-7 shape scores per stage | 30-40 min | **READY.** Only a 12-case trial is in the log. Run: `... new_plan_kit/b1_shape_scores.py` (options in its header). |
| 9 | `b2_group_rank_shuffle.py` | C2 fallback | 30 min | **DONE. KILLED.** New shuffle: unstable 0.262 (limit 0.26), shear rate 0.0099 against 0.0197 (not halved), CRPS +0.0022 (limit 0.0006). C2 is closed. |
| 10 | `b2_shear_target_fit.py` | shear target, `--form ratio` and `--form c1` | 25 min each | see RESULTS BLOCK below |
| 11 | `b2_c4_innovation_fit.py` | C4 radar error | 30-60 min | see RESULTS BLOCK below |
| 12 | `b2_g16_observe_fit.py` | G1-6 observe numbers | 1 h | see RESULTS BLOCK below |

**RESULTS BLOCK** (state on 2026-11-11)
**Row 6, oracle (DONE, 600 rows):** perfect templates change the score by u -3.0 %, v -10.1 %, T -0.3 %, mean -4.5 % (worse, not better). **Close G1-4 and G3-4.**

**Rows 10, 11, 12 were still RUNNING when this session stopped (2026-11-11, about 01:30 local).** They were left running on purpose. Do this first in the next session:

1. Look for the three logs in `docs/results/logs/`: `kit_b2_shear_target_fit.log` (two entries: form ratio, then form c1), `kit_b2_c4_innovation_fit.log`, `kit_b2_g16_observe_fit.log`. A log that exists = that run finished; read its VERDICT line and write it into this block and into `New_Plan.md` section 9.
2. No log: check whether the run is still alive (PowerShell: `Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId, CommandLine`). Alive -> wait, do not start a second copy. Not alive -> read the end of its output file (`$TEMP/kit_shear.out`, `$TEMP/kit_c4.out`, `$TEMP/kit_g16.out`) for the error, then run it again with the command in its header.
3. Order they were started in: C4 (`--max-per-site 700`) and shear target `--form ratio` in parallel; shear target `--form c1` starts after `ratio`; G1-6 starts by itself once the C4 log exists.
4. If C4 is still running after 2 hours it is too slow at 700 per site: let it finish if RAM is fine, or next time use the default `--max-per-site 150`.

**Update 2026-11-11 02:10 (collected):** shear `ratio` FAIL (p99 new / balloon 1.22 in 1-5 km); `c1` and G1-6 started by themselves (02:00) and are running. C4 measured: one-level sd 2.37 m/s (95 % [2.57, 3.55]), engine-equivalent 3.02 / 4.16; next = `scripts/p3_vad_condition.py --sigma` 3.0 / 3.02 / 4.16 (its VERDICT lists the commands). New: A3-fix v2 `b3_a3fix_neighbour_rho.py` (the speed-space rho ignored distance): variant B fails only at LRU by rounding (0.81 vs 0.81); a replicate on new hours (`--seed 1`) is running.

**Update 2026-11-11 03:10:** A3-fix v2 replicate (`--seed 1`): B fails at ONM (0.75 vs 0.80), C passes there but failed FST in run 1 -> no variant passes both runs, shipped kept (B is better than shipped almost everywhere: ASK_LATER 23). `b2_c4_innovation_fit.py` bug, minor: its 95 % interval bootstraps the uncentred d^2 - B while sd uses the centred R, so the interval sits above sd; centre `per` on the per-level mean before a re-run. C4 sigma sweep running (`c4_vad_sigma_*.log`).

**Update 2026-11-11 03:50:** shear `c1` FAIL (5-12 km p99 x0.82) -> shear target CLOSED. C4 sigma sweep: no sigma beats 3.0 -> C4 CLOSED. A2 x1.2 FAILS from existing USCRN logs (CRPS worse at both non-airport sites) -> no new run needed. G2-7 full run started 03:42 (`$TEMP/kit_g27.out`).

**Update 2026-11-11 04:45:** G2-7 full run done (1600 cases x 3 seeds; report only): '+ shuffle' is the stage closest to balloons; shear and lapse maps cost 0.01-0.02 of Ri<1 share (below noise); all stages miss Ri<1 at 12-18 km and over-produce low-level T-rises. IL-207 (new `b3_il207_site_spread.py`): the TCS coverage shortfall is a one-sided BIAS (tool too calm, +1.44 m/s, spring/summer afternoons), not a too-narrow spread; MAF fine. IL-207b (new `b3_il207b_site_shift.py`, per-site factor fit 2021-22, test 2023-25) running.

Smoke-test numbers (tiny samples, NOT verdicts, only what to expect): shear target ratio form p99 new / balloon 1.28 and 1.22 (too much shear -> FAIL), c1 form 1.03 and 0.97 with CRPS +0.02 % (PASS); C4 killed (R negative above 2.5 km: the tool's spread of 6-9 m/s is already wider than the radar mismatch of 5-6 m/s; positive below 2 km); G1-6 closed (fitted plain update not better than the shipped speed-space default; fit coverage 0.71-0.80).

Things found while building (each one was checked by a run or a self-check):

1. The switches the plan named (`shuffle_train`, `day_code`, `target_shear`, `group_rank`, `t_update`, `SIGMA_SCALE`) **do not exist** in the tool. The kit gets the same effect from outside (pseudo-truth for the shear map, in-memory change for `observe`).
2. The group-rank recipe as written ("order members by the rank fraction in the whole group") changes nothing: the order by fraction is the order by value. The kit uses the fraction as a position instead. That is what was tested and killed.
3. The shear target needs no change in `shear_map.py`: `shear_map.fit` reads only the truth's layer shear, so a truth with scaled wind steps gives the same table.
4. The raw network stage cannot be switched on alone in the installed tool, so G2-7 has 4 stages, not 5.
5. `data/raw/wb2_hres_v2` already holds the 00Z + 12Z forecasts 2016-22: C6 needs no download.
6. G2-1 (detail between heights) cannot be checked from disk: `data/igra_heights` holds only the 44 model heights.
7. The cached radar files are one volume per day-hour (near 23 and 11 UTC). G2-4 (pairs 15 min to 6 h apart) needs a radar download first.
8. `scripts/p3_vad_vs_balloon.py fetch` takes the FIRST volume of the hour, 51-60 min before the balloon; `K.radar_uv` therefore allows 65 min.
9. CRPS against balloons is in m/s, not standardised: the kit uses 0.15 % relative as the stand-in for 0.0006.

---

## Part 4. What this changes in `New_Plan.md` (already written into the plan)

- Block 2 GPU: the C2 fine-tune is **skipped** (premise says shuffle; fallback killed). The GPU goes straight to the seed-1 base and C3 stage 1.
- Block 3 CPU-A "refit maps on the C2 output": **dropped** (no C2 output).
- A1 was already measured (`scripts/w6_observe_eval.py`); A3 is measured now. The block-3 fix is the neighbour error (A3-fix), not the same-station law.
- G3-3 stays unbuilt. G1-7 = replay only.

---

## Part 5. Items NOT built: how to do each one

Read this before each item:
- "Recipe" = the numbered steps in `Innovative idea review.md` (repo root). The line numbers below point at them. Read the recipe, then the files it names, then write code.
- Start a new script from the template in Part 6. Put it in `new_plan_kit/`, name it `b<block>_<short name>.py`.
- First write the PASS / KILL rule into the script header. Then code. Then smoke test. Then real run. Then copy the verdict into `docs/logs/AUTOPILOT.md`.
- "Core change" means a file outside `new_plan_kit/` and `scripts/`: rule 11 of Part 1 applies.

### 5.1 CPU items (no training)

**A3-fix: neighbour reports are over-trusted (found by `b1_observe_loso.py`).** Core change, `tempest_weather_v2/obs.py`.
1. Cause: coverage 0.67-0.82 with a neighbour's report means the answer is too narrow, so the gain in `REP_TABLE` is too high for the spread it leaves, or the spread after the update is too small.
2. Measure before any edit: copy `b2_g16_observe_fit.py`; change `report(...)` to send a neighbour's report (`distance_km`, `elevation_diff_m` from `b1_observe_loso.neighbours`); keep only the `scale` axis (0.8 ... 3.0); fit 2015-22, test 2023-25 at TCS and MAF.
3. PASS: coverage 0.85-0.95 for every neighbour and CRPS not worse than today's by more than the day-block interval.
4. If one scale passes: report it. The edit (a factor on the error for `distance_km >= 5`) is behind a switch, default off.
5. Also report: TCS with no report covers 0.80. That is the tool's own spread at TCS, not `observe`.

**A2 past-mode spread x1.2.** `scripts/gw_past_anchor.py` already has the two numbers `w` (re-centring on ERA5) and `s` (spread scale). Run it for TCS, MAF and the USCRN site with `s` 1.0 and 1.2 (read its header for the options). PASS: coverage nearer 0.90 at all three sites and CRPS not worse by more than 0.0009 at any. Then the default change 1.0 -> 1.2 is permitted (plan section 8): core change, back up first.

**G1-5 spread tracker and G1-7 drift replay.** Recipe lines 165-169. Extend `scripts/bias_backtest.py` (read it first; it already replays day by day). G1-5: the formula in recipe step 1, as a second running number next to the bias. G1-7: a new script; monthly mean of (ERA5 minus climate-mode pool mean) per band and variable 2015-25 with `K.tool` and `K.era5_at`, 20 hours per month are enough; the network has a `year` input, so expect a small drift: if the mean absolute monthly bias is already under the day-block interval, write "no tracker needed" and stop. PASS rules: recipe steps 2 and 4.

**G2-4 two-scale persistence aloft.** Recipe lines 176-181. Needs a download first (finding 7): NEXRAD level-3 NVW volumes for EPZ and MAF at more hours. Use `fetch(day, radar, hour)` in `scripts/p3_vad_vs_balloon.py` as the fetcher, with a NEW target folder (`data/raw/nexrad_nvw_hourly/`), hours 18-23 UTC, 120 days of 2021-23, one volume per hour; add the ledger line. `fetch` writes to the fixed folder `p3_vad_vs_balloon.OUT` (`data/raw/nexrad_nvw`): set it in memory first (`import p3_vad_vs_balloon as p3; p3.OUT = "data/raw/nexrad_nvw_hourly"`), do not edit the script. Then pairs of volumes 1-6 h apart, split into column mean (0.5-5 km) and departures, fit the two decay laws, test on every fifth day. PASS: CRPS aloft better than the single rate 0.72 per hour beyond the day-block interval.

**G1-3 radar + station score.** Recipe lines 183-186. Report only. Use `K.radar_uv`, `K.asos_speed`, `K.balloon`, and `coext` in `scripts/a3_coextremes.py`. For "C4's sd" use the result of `b2_c4_innovation_fit.py`; if C4 was killed use 3.0 m/s.

**G2-2 Student-t widening + fault gate.** Recipe lines 171-174. Core change in `tempest_weather_v2/launch.py` (after `_conditioned_pool`), switch `t_update=False` on `observe`. Write the test first with `scripts/w6_observe_eval.py` and `scripts/p3_vad_condition.py`. PASS: coverage on the 10 % most surprising cases moves toward 0.90, CRPS on the rest inside noise.

**C6 run-to-run disagreement.** Recipe lines 198-202. No download (finding 5). `from tempest.forecast import modeF; modeF.load_year_v2(year, ds, starts=("00z", "12z"))` (read its docstring for `ds`; `scripts/fv2_eval.py` shows how to open it). KILL first: rank correlation of the disagreement with the error under 0.3 on 2016-2020.

**Safe Gaussian-marginal blend.** `scripts/gauss_blend_fit.py` does not exist. Look at `scripts/ap_l3_blend.sh` (do not edit it) and the functions `gauss_skill` / `fit_factor` in `scripts/` (`grep -l "def gauss_skill" scripts/*.py`). Per cell (variable x band): weight in 0-1 between the tool's values and a normal curve with the same mean and sd, fitted on 2021, tested on 2024-25. KILL: any wind cell worse than baseline by more than 0.0009.

**18-80 km extension.** Design A1 in `docs/plans/LAUNCH_PLAN.md`. Needs the ERA5 1-70 hPa download (plan preflight step 5). Off by default; check against held-out levels.

**Launch-day row.** One more row in the headline table: the tool with a 1 h old own-station report against (a) the tool alone and (b) linear persistence, same hours. The numbers exist: `scripts/w6_observe_eval.py` (TCS 1.636 / 1.140 / persistence 1.035; MAF 1.480 / 0.987 / 0.923) and `kit_b1_observe_loso.log`. Reporting only: write the row into `docs/FINAL_REPORT.md` when the user asks for the docs update.

**Sodar referee 30-200 m.** Fix A8 first (sodar time zone, `scripts/a2e_sodar_ingest.py`; check one day by eye against ASOS at the same site). Needs the ERA5 point pull for the five sodar sites. Measurement only: CRPS and coverage of the tool at 30-200 m.

**Step-6 small checks.** Recipe lines 213-217, one paragraph each: G2-3 gust factor, G2-6 blend check (read the mode F score logs; nothing to build if coverage is 0.88-0.92), G1-2 mixed pool, G2-5 double jets. G1-4 is built (`b1_quick_checks.py oracle`).

**Small fixes of plan block 5** (A5 `below_10m="loglaw"` opt-in, A6 stale docstring in `tempest_weather/flight_sim_readers.py` lines 9 and 90, A7 roughness into turbulence, A9 duplicate IL-192 id, IL-129 `_cdf` / `_ppf`): each is a core change of a few lines. One at a time: read `Limitations to solve.md` for the item, make the edit, add one test, run the full suite with the GPU idle. A6 and A9 are text only.

### 5.2 GPU items (need training; NOT built, by decision)

These need edits in `tempest/generator/train.py` / `model.py` and a full training run. They were not
written, because code for a training loop that was never run would be untested guesswork.

| Item | Do it? | Recipe |
|---|---|---|
| C2 fine-tune through the shuffle | **No.** The premise check says the shuffle is the cause and the shipped maps already repair it. | lines 119-126 |
| Seed-1 base of the shipped stack | Yes, first GPU job. Copy the newest `scripts/gpu_direct_*.sh` that trains `l3_c4w` (`gpu_direct_c4w_replicate.sh`), change only the seed and the output name. Read the runner header for the exact command. | - |
| C3 day-coded generator, stage 1 then 2 | Yes, after the base. Switch `day_code` (default 0 = today's behaviour, output identical). KILL stage 1 under 40 % skill. | lines 157-163 |
| G3-5 learned update | Only if C4 and C3 stage 2 passed and 6 h are left. First to drop. | lines 190-196 |

For any GPU run: one runner script `scripts/gpu_direct_<name>.sh`, exact command in its header,
`&&` before every "done" line, started with `nohup bash scripts/gpu_direct_<name>.sh > /dev/null 2>&1 &`,
progress in `data/l3.log`, compared with `scripts/compare_headline.py OLD NEW` against the base of the SAME seed.

---

## Part 6. Template for a new kit script

```python
"""<ITEM>: <one sentence: what is measured>. PASS RULE BELOW.
<3-10 lines: the idea in plain words, the data used (years!), what is compared with what.>
PASS: <numbers>.   FAIL / KILL: <numbers> -> <what to do>.

    PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/<name>.py            # <time>, <RAM>, 3 threads
    KIT_SMOKE=1 PYTHONPATH=. .venv/Scripts/python -W ignore new_plan_kit/<name>.py --n 5      # smoke test
Result: docs/results/logs/kit_<name>.log
"""
import argparse
import numpy as np
import kit_common as K            # read kit_common.py once: most helpers you need are there

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=300); a = ap.parse_args()
    K.ram_gate(6.0)
    lines = ["<title line with the sizes used>"]
    # ... measure; every test time must pass  assert K.day_ok(t)  (never 2026)
    # ... m, lo, hi = K.block_boot(values, days)   -> interval from whole days
    lines.append("VERDICT: ...")   # last line: PASS / KILLED / what to run next
    K.report("<name>", lines)      # prints, and appends to the log unless KIT_SMOKE is set

def _selfcheck():                  # runs at import: a tiny made-up case with a known answer
    assert True

_selfcheck()
if __name__ == "__main__":
    main()
```

Good examples to copy from: `b1_observe_loso.py` (station reports, paired verdict),
`b2_c4_innovation_fit.py` (radar files, a made-up case that recovers known numbers),
`b2_g16_observe_fit.py` (changing a core number in memory and putting it back).

## New_Plan section 17 (UR1-UR15)

Scripts `b24`-`b37` plus `ur_common.py` (shared helpers: member files, scoring as `il6_modeF.py`, pooled 2021 + 2022 rows). What each needs
first, its runner and its cost are in the table of `New_Plan.md` 17.5; the rule of each is in its own header. Unit tests: `tests/test_ur_kit.py`.
