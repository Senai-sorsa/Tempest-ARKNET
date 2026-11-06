# HANDOVER: read this first (written 2026-11-04, about 20:30 CST)

This file is for a fresh Claude session, possibly in a different Claude account. That session will not have the
previous session's memory files, scratchpad or chat. Everything it needs is in this file plus the files it points to.

**Read in this order:**
1. This file, all of it.
2. `docs/plans/PHASED_PLAN.md`, the work plan: 3 phases, with a test at the end of each phase.
   - **Phase 4** (forecast and past-date correction) is a separate system with its own session and plan: `docs/plans/PHASE4_FORECAST.md`.
   - Its section 0 is the start prompt.
   - Its section 3 says which files belong to it.
3. `docs/plans/PLAN.md`, the project's full history:
   - the improvement log (rows 1-22, then E1-E13);
   - the "A6 and other drivers" section;
   - the blueprint review;
   - the evaluation review.
4. `docs/plans/TOOL_PLAN.md` (the planned query tool) and `docs/research/FUTURE_OPTIONS.md` (ideas parked as "mediocre").
5. Only when an item needs them: the other files in `Code-Modifications/`, which are the sources of the phased plan.
   - `review-triage.md`
   - `claude-recommendations-v2.md`
   - `atmosphere-outputs.md`
   - `coupled-atmosphere.md`
   - `operations.md`

---

## 1. First 15 minutes: checklist

Do these before anything else. They are safe, read-only checks, except for the restarts the checks call for.

1. **Which machine are you on?**
   - Check: `Test-Path C:\Users\Senai\Tempest-ARKNET\data\train\pilot80_smix.npz`.
   - `data/` (218 GB) and `models/` (965 MB) are **not in git**.
   - If you are on another machine, none of the trained models or data exist. Tell the user, then rebuild:
     1. Data: the ingest commands in section 5.
     2. E12: `handover_scripts/e12.sh`. It needs `models/station_map_mix.npz` first; see section 5.
2. **What is running?** Run in PowerShell:
   ```powershell
   Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'tempest\.|pipeline|e12|ablate' } |
     Select ProcessId,ParentProcessId,Name,CommandLine | Format-List
   ```
   At handover the following was running:
   - **One CDS downloader:** `python.exe -m tempest.ingest.fetch_cds`. It shows as two python.exe processes, PID 40856 (the venv launcher) and its child 35988. They are **one** job, not two.
   - **One `bash.exe` running `pipeline4.sh`** (PID 3172) from the old session's scratchpad. It waits for all CDS months, then builds, trains and scores. See section 8.
3. **If pipeline4 is gone** (it may die when the old Claude session closes), relaunch the handover copy. It is identical to the original, except that it calls `Code-Modifications/handover_scripts/mixmap.py` instead of the scratchpad copy:
   ```bash
   cd /c/Users/Senai/Tempest-ARKNET && OMP_NUM_THREADS=12 nohup bash Code-Modifications/handover_scripts/pipeline4.sh >/dev/null 2>&1 &
   ```
   - Start it only if **no** other pipeline4 is running. Two copies would run `to_heights` and the build in parallel and exhaust the RAM.
   - Every stage skips if its output already exists, so relaunching is safe.
   - It restarts `fetch_cds` itself if the downloader is not running. The ledger prevents duplicate CDS requests.
4. **The thermal limiter** (section 4.2) was a background PowerShell loop in the old session that ran for 6 h. Assume it is gone and start your own as a background task.
5. **Check CDS progress:**
   - Count the files: `ls data/raw/era5_cds/*.grib | wc -l`. The target is 420; there were 26 at handover.
   - Read `tail data/cds.log` and `data/raw/era5_cds/ledger.csv`.
   - At handover the rate was about one month per 40 min. The CDS queue is slow, so the rest will take **days**. That is normal. Don't "fix" it by launching more downloaders.
6. **Pipeline log:** `tail data/pipeline.log`.
7. **Git state:** `git status`. At handover these were uncommitted, on purpose (section 9):
   - edits to 9 tracked files;
   - the untracked folder `Code-Modifications/`.

   Don't commit unless the user asks.

---

## 2. The user and how to work with them

- **Background:** the user is not an ML or weather specialist (they asked "what does 99% range mean?").
  - Explain in plain language: short sentences, no jargon, or explain the jargon.
  - Give numbers with their meaning, for example: "the 99 % range caught the real value 98.6 % of the time; the target is 99 %".
- **What they want from the model:**
  - About 99 % accuracy "on everything", especially when testing on past data.
  - Point accuracy, not only ranges. Their words: "if the model says 2C and the real data was 2.1C, then our model measures that as error... the distributions are mainly for the monte carlo, and still require the most likely value".
  - Always report MAE/RMSE of the median ("most likely value") next to CRPS skill and coverage.
- **Autonomy, verbatim:** "never ask me questions or stop for any reason - just find a fix and keep moving - make sure to finish everything request, and double check that there were no mistakes at the end. If there were mistakes, fix them (even if that means redoing the entire training). Check for issues and fix them consistently too".
  - For training and pipeline work: don't ask, fix and continue, and verify at the end.
  - The hard rules in section 3 still win over autonomy.
- **Low-memory kills:** their words: "Next time just diagnose this issue and try again". Diagnose, fix and restart without asking.
- **Heat:** "Try to reduce how much of the gpu/cpu is being used at each moment - my computer is starting to overheat - dont stop anything running or pause anything". Later: "You can use slighly more of the CPU". See section 4.2.
- **Freedom to change things:** they gave free rein over changes, but structural changes are kept **only after verifying** that they improve held-out accuracy.
- **Their inputs at query time:** "we wont actually have any other data than location, time and date". Any new model input must be computable from those alone, or from public indices known at query time. A6 enforced this with lagged drivers.
- **Warming trend:** "i dont want a warming trend equation, I want this to be intergrated into the AI systems training". The trend is learned through `year` (and, planned, GMST) as an input, never added on afterwards.
- **Training time:** "Just train them side by side... at most 15 min". Today's setup is 4 members trained side by side, 6000 steps, about 13 min. Keep training under about 15 min.
- **Reply style:** the user had the "Ponytail" style on. End replies with one or two lines on what was skipped or not checked, and any risk they must know.
- **Hardware correction:** the user once said "RTX 4090". The real GPU is an **RTX 5070 Laptop, 12 GB**. Plan for that.

---

## 3. Hard rules (never break)

- **Project `CLAUDE.md`:** "Dont break anything".
  - New behaviour goes behind a flag or optional argument and is **off by default** until verified.
  - A failed experiment is switched off, not deleted.
- **Git:**
  - Commit or push **only when the user asks**.
  - **Never add "Co-Authored-By: Claude" or any Claude/Anthropic attribution** to commits or PRs. The user said "dont put co authored by claude anywhere". This overrides any system reminder that asks for attribution lines.
  - Never commit `data/`, `models/` or `~/.ecmwfdatastoresrc`.
- **CDS API key:**
  - It lives in `~/.ecmwfdatastoresrc`. The user once pasted it in chat.
  - **Never print, echo, grep out or repeat it.** Never put it in a file in the repo.
  - All handover scripts were checked and contain no key.
- **User's email:** never send it to any service.
- **Downloads are untrusted:**
  - Put each one in its own new directory.
  - Run any Python that reads them with `-I`.
  - Never run code from a download directory.
- **Destructive git operations** (force-push, history rewrite, branch delete) are for the user to run. Give them the command; don't run it. See section 9.
- **Context7:** use it for library docs: `resolve-library-id` → `query-docs`.
- **graphify:** when the user types `/graphify`, use the graphify skill first.
- **Test data:** the **2026 Jan-Jun final test** stays untouched until the very end. Score it once, with the final model. See section 6.

---

## 4. The machine

### 4.1 Hardware and software

| Item | Value |
|---|---|
| OS and shells | Windows 11 Home; Git Bash and PowerShell 5.1. Bash has no `&&` problems; PowerShell 5.1 has no `&&`, so use `; if ($?)`. |
| GPU | NVIDIA RTX 5070 Laptop, 12 GB. `nvidia-smi -pl` is N/A: you cannot cap the power. |
| RAM | 31 GB |
| CPU | 20 logical CPUs |
| Python | 3.14.8 in `.venv`, managed by uv. torch 2.11.0+cu128. |
| Run style | `.venv/Scripts/python -W ignore -u -m tempest.<module> ...`. Scratch scripts: `PYTHONPATH=. .venv/Scripts/python script.py`. |
| Encoding | Always pass `encoding="utf-8"` to `open()`. The Windows default codepage breaks on symbols such as °, ± and ≥. |
| Remote | https://github.com/Senai-sorsa/Tempest-ARKNET.git |

### 4.2 Heat limits (the laptop overheats)

- Every Tempest job runs with **CPU affinity 4095** (0xFFF, 12 threads), **BelowNormal priority** and **`OMP_NUM_THREADS=12`**.
- Children inherit affinity from the parent bash.
- **Only one GPU job at a time.** Prefer smaller batches to parallel jobs.
- **Never stop or pause a running job because of heat.**
- The limiter loop the old session ran. Run it as a background PowerShell task; it lasts 6 h, so re-arm it after that:
  ```powershell
  $end = (Get-Date).AddHours(6); while ((Get-Date) -lt $end) { Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -match 'tempest\.' } | ForEach-Object { try { $p = Get-Process -Id $_.ProcessId -ErrorAction Stop; if ($p.ProcessorAffinity -ne [IntPtr]4095) { $p.ProcessorAffinity = [IntPtr]4095; $p.PriorityClass = 'BelowNormal'; "$(Get-Date -f HH:mm) limited $($_.ProcessId)" } } catch {} }; Start-Sleep -Seconds 30 }
  ```

### 4.3 Memory and processes: lessons learned the hard way

- **Two trainings at once exhaust the 31 GB** and caused a low-memory kill of every background job.
  - Before starting any GPU job, check with Win32_Process that no other `generator.train`, `calibrate.spread` or `scoring` process is running.
  - e12.sh shows the "wait until none" loop.
- **Builds are heavy.** `build_dataset` holds about 11 GB, so don't start a training while a build runs.
- **Training memory:** training reads its dataset with `load_npz`, on demand from disk. Keep it that way; don't load the whole file into RAM.
- **The TaskStop / low-memory reaper kills only the bash wrapper.** The python child keeps running: about 7 GB of RAM plus the GPU.
  - To stop a job, find its `bash.exe` by command line and run `taskkill /PID <bash pid> /T /F` so the whole tree dies.
  - Killing only the python child lets retry loops relaunch it.
  - Afterwards, list `bash.exe`/`python.exe` processes matching the script names and `tempest`, and confirm there is **exactly one** of each job.
  - Stale copies of older `pipeline.sh` versions survived once and nearly ran `to_heights` twice.
- **The reaper struck once** at about 18:05 during an 11 GB build. It killed the bash wrappers of pipeline3 and E12 while their python children finished.
  - After any memory event, check which outputs exist and resume the scripts. They skip finished stages.
- **Never edit a bash script while it runs.** Bash reads the file as it goes, so an edit corrupts the running job. Copy it, edit the copy, and kill and relaunch only if needed.
- **Don't overlap tests and scoring.** Never run `pytest` while a scoring job runs: CPU, RAM and heat contend.
- **Long jobs** go in the background. Wait for the completion notification; don't poll in a tight loop.

---

## 5. Project overview

**Tempest-ARKNET** is a probabilistic generator of atmospheric profiles: wind u/v, temperature and relative humidity at 44 heights from the ground to about 30 km, plus t2m, surface pressure and rh2m. That is 179 outputs. It is for:

- month-ahead "what will the atmosphere look like" draws;
- identifying the profile on a past date.

It outputs many plausible profiles (a distribution) plus the most likely value. The pilot area is the box 31-34 N, 108-101 W (West Texas / New Mexico).

### 5.1 Pipeline stages (code in `tempest/`)

1. **Ingest** (`tempest/ingest/`):
   - ERA5 from the Earthmover icechunk store (anonymous access, 13 pressure levels).
   - CDS GRIB downloads for 8 extra boundary-layer levels: `tempest.ingest.fetch_cds` → `data/raw/era5_cds/*.grib` plus `ledger.csv`, log `data/cds.log`.
   - IGRA radiosondes (Santa Teresa, Midland; 00Z).
   - Climate indices: ONI, QBO30/50, WWV solar flux (`data/raw/indices`, `tempest/ingest/indices.py`). `indices.analog(...)` does the A6 analog draws.
2. **Profiles** (`tempest/profiles/to_heights.py`): pressure levels → 44 fixed heights.
   - Output: `data/pilot/profiles80.zarr`, or `profiles_bl.zarr` with the extra CDS levels.
   - Uses liquid-water RH.
   - Targets are stored as height-to-height steps (`to_diff`/`from_diff`).
3. **Station correction** (`tempest/calibrate/station.py`): a correction map that pulls ERA5 toward what the balloons measure.
   - E12 mix: T/u/v from the 1991-2020 fit, RH from 2022-23. The balloon RH sensor/processing changed in 2022.
   - `handover_scripts/mixmap.py` merges the two fits.
4. **Dataset** (`tempest/generator/build_dataset.py`) → `data/train/*.npz`.
   - Rows cover solar hours 06-21.
   - Conditions: time and space features plus the linear features year, oni, wwv, qbo30, qbo50.
5. **Generator** (`tempest/generator/{model,train,features,sample}.py`, config `configs/generator.toml`):
   - an engression network: 4 members, depth 4, width 512, noise 32, 2,881,074 params per member;
   - loss: afCRPS (alpha 0.95), plus energy score weight 0.1, plus step-CRPS weight 0.5 (vertical shape);
   - 6000 steps with the members side by side, about 13 min.
6. **Range calibration** (`tempest/calibrate/spread.py`): a per-column quantile map with m = 199 samples, fitted on 2021-23.
   - The file stores the model's `model_sha`; score and sonde refuse it if the model differs.
   - E12's older file has no hash, so it is not checked.
7. **Scoring:**
   - `tempest/scoring/score.py` scores against ERA5; `sonde.py` scores against balloons.
   - "Known" vs "unknown" drivers: whether the target month's index values are given or drawn.
   - Intervals come from a whole-day block bootstrap.
   - Every run is seeded (`--seed`).

### 5.2 Key commands

E12 / pipeline4 style; check `--help` before changing flags:

```bash
PY=.venv/Scripts/python
$PY -u -m tempest.generator.train --data D.npz --out models/X.part.pt --max-year 2023   # then mv X.part.pt X.pt
$PY -W ignore -u -m tempest.calibrate.spread --model models/X.pt --data D.npz --year 2023 --from-year 2021 --rows 60000 --m 199
$PY -W ignore -u -m tempest.scoring.score --model models/X.pt --data D.npz --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/X.calib2021.npz
$PY -W ignore -u -m tempest.scoring.sonde --model models/X.pt --data D.npz --profiles data/pilot/profiles80.zarr --m 199 --first-test-year 2024 --last-test-year 2025 --calib models/X.calib2021.npz
$PY -W ignore -u -m tempest.calibrate.station --profiles P.zarr --out models/station_map_A.npz                                       # 1991-2020 fit
$PY -W ignore -u -m tempest.calibrate.station --profiles P.zarr --out models/station_map_B.npz --first-year 2022 --last-year 2023     # RH fit
PYTHONPATH=. $PY Code-Modifications/handover_scripts/mixmap.py models/station_map_A.npz models/station_map_B.npz models/station_map_mix.npz
$PY -W ignore -u -m tempest.generator.build_dataset --profiles P.zarr --out D.npz --first-year 1980 --last-year 2026 --station-map models/station_map_mix.npz
.venv/Scripts/python -m pytest -q          # never while scoring runs
```

### 5.3 Data on disk at handover

| Folder | Size |
|---|---|
| `data/` total | 218 GB |
| `data/pilot` | 128 GB |
| `data/raw` | 56 GB |
| `data/train` | 35 GB |
| `models/` | 965 MB, 234 files |

Old experiments' files live in `models/`. Don't delete any without the user's consent.

---

## 6. How accuracy is measured (explain it this way to the user)

### 6.1 Metrics

- **CRPS skill vs climatology:**
  - CRPS measures how good the whole distribution is.
  - Skill = 1 - CRPS(model) / CRPS(climatology). 0 = no better than "what is normal for this date"; above 0 = better.
  - **skill15** uses the last 15 years as the reference. It is stricter and is the headline.
- **cov99:**
  - The fraction of real values inside the model's 99 % range. The target is 0.99.
  - The headline is mean |cov99 - 0.99|, where smaller is better.
  - Also reported: whole-profile coverage, and PIT per height.
- **MAE/RMSE of the median:** the point error of the most likely value. The user wants this, so always show it.
- **Intervals:** from a whole-day block bootstrap. A difference only counts if the intervals don't overlap.

### 6.2 Honest protocol

| Years | Use |
|---|---|
| ≤ 2020 | training |
| 2021-23 | validation and calibration fitting (train with `--max-year 2023`) |
| 2024-25 | **development** test. It has been used for more than 17 decisions, so it is no longer a clean test. Say so. |
| 2026 Jan-Jun | **final test**, touched once at the very end. It has no monsoon months; say so when reporting. |

### 6.3 Baseline

The current best is **E12**. Its exact numbers and file paths are in `PHASED_PLAN.md` §0.2. Headline on balloons 2024-25 with unknown drivers:

- mean skill15 **+0.0056**;
- mean |cov99 - 0.99| **0.0034**.

On ERA5:

- mean skill15 about +0.03;
- mean |cov99 - 0.99| about 0.003.

Weakest cells:

- rh2m skill15 -0.051;
- RH 0-1 km -0.025;
- T at 5-12 km cov99 0.984 on ERA5;
- extreme wind shear 16-22 % too weak above 1 km (the 99.9th percentile).

**Honest expectation:** month-ahead skill is close to climatology by nature. The 99 % range coverage is already near target. Big skill gains at month-ahead range are not physically likely; don't promise them.

---

## 7. Experiment verdicts: don't redo these blindly

Full details, with numbers, are in the `docs/plans/PLAN.md` improvement log.

### Kept
- 1: surface pressure as a departure from standard pressure.
- 2: step loss, which shapes the profile vertically.
- 3: range calibration.
- 6: liquid-water RH.
- 9: fixed validation noise (seeded).
- 10: station correction (st2).
- 19: station fit on 1991-2020, which fixed the test-year leak.
- 21: members side by side, 6000 steps.
- E11: RH station map from 2022-23.
- **E12:** the mixed-era map, current best.
- **A6:** analog index draws (K = 8) as the driver rule for the tool's "unknown future" mode.
  - Scores keep random draws as the headline so numbers stay comparable.
  - Not done: tuning K, and a paired difference interval.

### Rejected
- 4: extra balloon calibration.
- 6b: station fit on recent years only.
- 8: seasonal or spread-tercile calibration (one global map won).
- 11: moisture-tercile leftover pools (item 7 was later dropped here).
- 12: balloon calibration on 5 years.
- 13: afCRPS alpha 0.99.
- 14: per-column balloon calibration.
- 15 and 16: calibration on the last 3 years only, or on 150k rows.
- **22 (A5):** training on 1980-2020. Older years pull the learned trend down. Phase 3 retries it with GMST as an input.
- A6 candidates 1-2 for month-ahead: persistence of recent local departures, and soil moisture. Their correlation ceiling (r ≈ 0.1-0.15) gives under 1 % CRPS, below what the tests can detect. Persistence stays for the 0-7 day tool mode.
- E9: calibration with drawn drivers.
- E13: surface balloon map.

### Findings
- **Members ablation:** 2 members score the same as 4. 4 were kept, because they are cheap side by side.
- **E10 closed:** dropping incomplete soundings does not flatter the headline.
- **Speed:** inference time is dominated by numpy post-processing, not the GPU.
- **Cold T bias at 4-12 km (0.3-0.5 K):** year-to-year weather, not a trend error (`handover_scripts/yearbias.py`).

### Fixed bugs (to know about)
- **Station-apply memory:** it gathered the whole leftover pool per row, about 369 GB. Fixed.
- **Unseeded scoring noise:** scores from before the fix carry about ±0.001 of Monte-Carlo noise.
- **Overlap leak:** st2, a99 and mt were trained without `--max-year`, so validation overlapped the test years. The honest protocol fixed it.
- **yearbias.py:** an IndexError on names without "_". Fixed.
- **physics.py:** hit the calibration m-mismatch guard. Fixed: use m = 199.

### Still pending from the old list
- **PLAN row 20, block validation:** the code exists (`val_block_frac`, `configs/generator_blocks.toml`), but it was never run. Run it after Phase 2.
- **A2 go/no-go thresholds:** the user must supply them. Wind, shear, T and RH limits per vehicle.

---

## 8. What is running and what happens next on its own

**`pipeline4.sh`** is "full data v4". It runs in this order:

1. Wait until 420 CDS months are present (restarting `fetch_cds` if needed).
2. `to_heights` → `data/pilot/profiles_bl.zarr` (36 blocks, resumable through `done.txt`).
3. Station maps → `models/station_map_bl.npz` (the E12 mix).
4. `build_dataset` → `data/train/pilot_bl.npz`.
5. Wait for a free GPU.
6. Train `models/generator_pilot.pt`.
7. Calibrate on 2021-23.
8. Score ERA5 and balloons for 2024-25.

The log is `data/pipeline.log`.

- **When it finishes:**
  1. Compare `generator_pilot` (21 levels) with E12 (13 levels) using the phase-end test in `PHASED_PLAN.md` §0.3.
  2. Log the result as a new row in `docs/plans/PLAN.md`.
  3. Adopt it as the new baseline only if it passes.
- **Restarting the old copy:** the running copy lives in the old session's scratchpad and calls the scratchpad's `mixmap.py`. If that folder disappears before the station step, the old copy will fail with "FAILED: station" (exit 6). Then relaunch the handover copy (section 1, step 3); it resumes from what exists.
- **Timing:** CDS has 394 months left at about 40 min each, with several requests queued, so expect several days. Phase 1 of the plan needs no retrain and can run meanwhile.
  - Phase 1 still uses the CPU and GPU, so keep to one GPU job.
  - The pipeline only waits for the GPU right before its training step.

---

## 9. Git state at handover

- **Branch `main`** is at `ba2e2df`, the same as `origin/main`.
- **Uncommitted, on purpose** (the user didn't ask for a commit yet):
  - `docs/plans/PLAN.md`, `docs/plans/TOOL_PLAN.md`;
  - `tempest/calibrate/spread.py`, `tempest/generator/sample.py`, `tempest/ingest/indices.py`;
  - `tempest/scoring/score.py`, `tempest/scoring/sonde.py`;
  - `tests/test_calibrate.py`, `tests/test_data_pipeline.py`;
  - the new folder `Code-Modifications/`.

  Commit them only when the user asks. Use well-labelled commits with **no Claude co-author line**.
- **History split (the user asked for it; the user must run it):**
  - Branch `split-main` (`8ba300e`, 30 commits) rewrites the history as many small, well-labelled commits.
  - It lives in a worktree at the old session's scratchpad `.../scratchpad/splitwt`.
  - The user's command, which **you do not run**:
    ```
    git update-ref refs/heads/main split-main ba2e2df && git push --force-with-lease=main:ba2e2df origin main && git worktree remove <old scratchpad>/splitwt && git branch -D split-main
    ```
  - `split-main` holds only the commits up to `ba2e2df`. The uncommitted work above goes on top afterwards.
  - If the scratchpad worktree has vanished, run `git worktree prune`. The branch itself survives in `.git`.

---

## 10. What to do next

1. **Section 1 checks.**
2. **Keep the improvement loop going.** It was a standing `/loop` in the old session. Re-create it with the user's wording:
   > Continuous Tempest improvement loop: read the latest diagnostics (data/*.log, models/*_diag*.csv, training 'val by var' lines), find where 99%-range coverage or CRPS skill underperforms (ERA5 and balloons, 2024-2025 test years), research and try one improvement at a time, verify it genuinely improves held-out accuracy before keeping structural changes, keep only one GPU/training job at a time (check Win32_Process for orphans), log results in docs/plans/PLAN.md. Never stop or ask questions.

   About 30 min between checks is fine.
3. **Work through `PHASED_PLAN.md`**, Phase 1 → Phase 2 → Phase 3:
   - test only at the end of each phase, against E12;
   - if a phase fails, switch off half of its flags and rerun the test.
4. **Leftovers** (`PHASED_PLAN.md` §5):
   - pipeline4 monitoring;
   - E4 wording, plus a second walk-forward fold;
   - row 20 block validation;
   - the A2 thresholds;
   - commit when asked;
   - the user's force-push;
   - the final double-check;
   - the single 2026 H1 final test.
5. **Ideas discussed, not approved to build yet:**
   - an `update` script: fetch new months → rebuild → recalibrate → score, and swap only if not worse;
   - "recent-days tuning": the past 7 days plus the next 7 forecast days, extended to day 30, with the window to be experimented with;
   - `distribution(kind='predicted'|'uncertainty')`.

   They are in `docs/plans/TOOL_PLAN.md` as the query tool (modes past / 0-15 d / 15-60 d / AI; build order T1-T5). **Plan only.**
6. **Logging:** every experiment gets a numbered row in `docs/plans/PLAN.md` with:
   - what changed;
   - what it was tested on;
   - the numbers with intervals;
   - the verdict (kept or rejected).
7. **At the end:** double-check everything: pytest, a rescore with the final files, a check that the files' hashes match. Fix any mistakes, even if that means retraining.

---

## 11. Scripts in `Code-Modifications/handover_scripts/`

These are copies of the old scratchpad scripts. Temp-folder paths were replaced with repo paths.

| Script | What it does |
|---|---|
| `pipeline4.sh` | The full-data pipeline (section 8). Relaunch this copy if the original dies. |
| `mixmap.py` | Merges two station maps: T/u/v from map A, RH from map B. Usage: `mixmap.py A.npz B.npz out.npz`. |
| `e12.sh` | Rebuilds and retrains the E12 baseline from `profiles80.zarr` plus `station_map_mix.npz`, then calibrates and scores balloons. Waits for other GPU jobs. |
| `e12_resume.sh` | Waits, then runs e12.sh. |
| `ablate.sh` | Members ablation (1/2/4). Its outputs now go to `models/ablate_mem*`. Already done; for reference. |
| `e10.py` | The E10 check (do dropped soundings flatter the score?). Closed. |
| `boot.py` | Block-bootstrap helper used for interval comparisons. |
| `cmp.py` | Compares two score CSVs band by band. |
| `sfccmp.py` | Compares the balloon launch surface with the ERA5 grid surface at 00Z, per year (basis for E13, rejected). |
| `physics.py` | A3 physics check: shear and lapse-rate percentiles, samples vs truth, 2024-25 (m = 199, 4000 rows). |
| `yearbias.py` | Raw per-year mean bias for 2011-2025 (showed that the cold bias is weather, not trend). |

`PHASED_PLAN.md` §0.3 references `scripts/physics.py` and `scripts/compare_headline.py`. Phase 1.0 creates those in the repo, starting from `physics.py`, `cmp.py` and `boot.py` here.

---

## 12. The old session's memory notes (reproduced so nothing is lost)

- **Low-memory kills:** when jobs are killed for low memory, diagnose (free RAM, leftover processes), cut memory use, relaunch and keep monitoring. Don't ask.
- **TaskStop leaves python orphans:** kill the whole tree with `taskkill /PID <bash> /T /F`, then confirm exactly one of each job is running.
- **Thermal limits:** affinity 4095, BelowNormal, `OMP_NUM_THREADS=12`, one GPU job; never stop jobs for heat.
- **Training autonomy:** never ask or stop. Fix and continue, verify at the end, retrain if a mistake is found. Hard rules still apply.
- **Queue after A6:** done:
  - the GPT adoptables (block-bootstrap CIs, source-mask reporting, members in parallel, calibration provenance);
  - the inference speedups;
  - the members ablation;
  - A1 and A3.

  Remaining: E4, E6, block validation, A2 (needs thresholds), the final double-check. E10 is closed. All are carried into `PHASED_PLAN.md`.

**Suggestion for the new session:** save sections 2-4 of this file as memory notes in its own memory folder, so they survive future context resets.
