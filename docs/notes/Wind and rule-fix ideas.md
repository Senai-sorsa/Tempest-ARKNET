# Rule-excluded items (C) and wind ideas (B)

Written 2026-11-14. Numbers are copied from `docs/notes/fixing final issue.md`, `docs/notes/Useful results.md`, `New_Plan.md` and `To-do-Concise.md` as read in this session. Nothing here was re-run. Items marked (unverified) rest on outside research or on a file I did not open. Every pass rule below is a proposal; the rule changes are the user's call.

---

## PART C. What the rules excluded that should still be considered

### C-1. Just add (the evidence is already in hand; only the wording blocked it)

| # | Item | Why it was excluded | Why it should go in | Remaining step |
|---|------|---------------------|---------------------|----------------|
| C1-a | **UR5 calm-window map and link** | Killed by "u/v 10 m cov90 must not move > 0.01" | 3 h calm error 0.237 -> 0.036; per-hour gap 0.12-0.19 -> about 0.03; CRPS better. Shipped cov90 was over-covered (0.93-0.97), so a move toward 0.90 is an improvement, not a harm | Re-score with the rule `abs(cov90 - 0.90)` not worse, then refit spread. No new run of the map |
| C1-b | **SIGMA and NEST cov99** (AV2, NEST, AV30) | "cov99 within 0.003 of binned" | They cover 0.976-0.984 (0.99 without PIT); binned covers 0.958-0.963 at 7 days. They beat the baseline on the very clause that killed them | Adopt proposed rule: cov99 within 0.005 of 0.99, CRPS not worse by more than 0.2 % |
| C1-c | **AV28 / AV29, O1 / AV7, AV8 / AV31** | MISS at small sample, later PASS | Already passed at a larger sample. Keep them as passes, and record that the first MISS was sample size | Log only |
| C1-d | **AV24 / AV26 mix** | No clean third test year (ASK_LATER 29) | Better at every lead, 14 of 16 intervals below 0 | Accept pooled years, then confirm on UR15 (2023-24) |
| C1-e | **TAILCAL on the shipped binned model** | Held up behind the column question | No training, about 1 h CPU, fixes a 0.958 -> 0.99 gap | C5 step 0 identity check, then run |

### C-2. Needs more testing (a real signal, but a rule did not decide it)

| # | Item | Open point | Test |
|---|------|------------|------|
| C2-a | **C6 / AV4 / AV25 calibration line** | CRPS -0.33 to -0.48 %, but PIT got worse | Check whether the PIT loss is in tails only; if so, TAILCAL on top. Test on UR15 |
| C2-b | **AV9 strong-wind cut (15-27 %)** | Spread narrowed too far (TCS cov 0.89 -> 0.84 / 0.85) | Move-then-respread: refit sigma after the centre change, then score cov90 |
| C2-c | **Near-misses in `docs/notes/Useful results.md` Part 1B** | Not re-opened by me | Re-score each under the new rule and sort into C-1 or C-2 (unchecked) |
| C2-d | **Past-mode airport wind (cov 0.71-0.82)** | Centre fault, widening hurts | Becomes B-ideas 1-4 below |
| C2-e | **Column choice (PIT vs no-PIT)** | Shipped column unconfirmed | C5 step 0; fix the column in the headers once; UR15 gives the clean word |

---

## PART B. Wind: what has worked, what is missing

> Superseded 2026-11-14: the 30 ideas below were attacked against the logs; the 14 survivors (WD1-WD14) are in New_Plan.md section 19, with the reasons the rest were dropped.

### What made progress so far (from the logs read)
- **Site-specific correction with shrinkage works**: IL-207b per-site factor, AV7 (two neighbours), AV31 site map all passed.
- **Fixing the link, not the marginal**: UR5 cut the 3 h calm error 0.237 -> 0.036. Nothing else in wind moved this much.
- **Centre fixes without a spread refit lose coverage** (AV9). This applies to every idea below.
- **ERA5 is the weak proxy**: calm 11.0 % vs real 17.3 %; SWiFT 200-10 m speed difference 5.9 real vs 4.1 ERA5; aloft bias -2 to -4.5 m/s.

### Design rules for every idea (so Part C does not repeat)
1. Pass rule written in the script header before the run, with the sample size that can resolve the gain.
2. Coverage rule is `abs(cov90 - 0.90)`, never "does not move".
3. Every centre change comes with its own spread refit.
4. Score the shipped column only.

### Data inventory
**Local, not yet used (or barely used)** (all under `data/raw/`):
| Data | Size | Use |
|------|------|-----|
| `a2e/ttu_swift_200m` 50 Hz, 131 hourly files, 0.9-199.9 m | 31 GB | Shear, turbulence, gust factor, calm-spell structure at 8 heights |
| `a2e/wfip1_sodar_*` (brady, cleburne, colorado_city, jayton, ozona) | small | Wind profile to 200 m at 5 sites, needs the time-zone fix and ERA5 point pulls |
| `wtk` MAF/SAF 2010-12 | small | 100 m model wind, a second shear reference |
| `nexrad_nvw` (EPZ) | small | VWP wind aloft |
| `merra2` | small | Second reanalysis, ensemble-of-proxies |
| `asos1min` (ALM, ELP, LRU, MAF, PEQ, TCS) and `asos1min_denver` | small | Real 1-min speed, gust, calm windows |
| `asos_global` (201 stations) | small | Global calm/gust climatology for the generator |
| `om_previous_runs`, `wb2_hres_v2`, `wb2_ifs_ens`, `opendata_hres_nmtx` | mixed | Lead-specific wind errors |
| `data/ops/raw` | small | Logger archive, real pad weather if any |

**New data, total at most about 10 GB, well under the 30 GB cap:**
| Data | Size (estimate, unverified) | Use |
|------|------|-----|
| HRRR 10/80 m wind at the pilot sites, Zarr point extract | MB | Grid-to-point at 3 km, 80 m shear |
| ERA5 single-level 100 m wind at the sodar/tower sites | MB | Closes the sodar pairing |
| WIND-Bench / MADIS 2021-25 for NM/TX | about 1-5 GB | Many more point stations as truth |
| West Texas Mesonet recent + UCAR 2009-10 | about 1 GB | Real 10 m wind, dense network |
| NOAA PSL 915 MHz profilers (Lubbock/TexAQS) | about 1 GB | Real profiles to 2-3 km |

---

## The 30 ideas

Legend: **Tier 1** = best expected gain per cost; **Tier 2** = good, needs more build; **Tier 3** = speculative. Cost: CPU/GPU hours and GB.

### Group 1. Fix the near-ground bias and calm spells (the floor)

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 1 | **UR5 re-scored with the fixed cov rule + spread refit** | repo (UR5, C1-a) | local | 1 h CPU | **1** |
| 2 | **Measured check of the climate-mode 10 m bias** (+0.67 m/s, P<5 m/s low by 0.06-0.14); find the cause, then a bias map by hour and season | repo (B2) | local ERA5 + ASOS 1-min | 2 h CPU | **1** |
| 3 | **Calm-fraction correction**: quantile-map the generator's speed marginal near zero to real 17.3 % (ERA5 11.0 %) | repo + quantile mapping | asos1min, asos_global | 2 h | **1** |
| 4 | **Persistence kernel for calm spells**: fit a two-state (calm/not) Markov or copula on ASOS 1-min and use it as the link | repo (STRAND) + research | asos1min | 3 h | **1** |
| 5 | **Gust factor from the SWiFT tower** by height, speed, stability, applied to gust laws | SWiFT processed 10-min | local | 3 h | 1 |
| 6 | **Calm-window gate**: instead of the independent hours, sample whole 3 h windows from real ASOS 1-min analogues | repo | asos1min | 4 h | 2 |

### Group 2. Height structure and shear (the 47-200 m coverage gap)

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 7 | **Height-dependent shear law** fitted on SWiFT: real 200-10 m difference 5.9 vs ERA5 4.1, so a power-law exponent by stability | repo + SWiFT | local 31 GB (reduce to processed 1/10 min) | 3 h | **1** |
| 8 | **Sodar-calibrated per-height factor** at 5 WFIP1 sites, shrunk to the pooled mean (IL-207b logic) | repo + WFIP1 | local + ERA5 points | 4 h | **1** |
| 9 | **WTK 100 m as second shear anchor** (MAF/SAF) for the 100 m level | WTK | local | 2 h | 2 |
| 10 | **Stability-conditional spread**: widen near the ground at night (stable) where ERA5 is least reliable | research (profile stability) | SWiFT + ERA5 | 4 h | 2 |
| 11 | **Low-level jet flag** from sodar and SWiFT, used to raise the 100-500 m spread when ERA5 shows a jet signature | research | sodar, SWiFT | 5 h | 2 |
| 12 | **Spread refit at 47-200 m** after idea 7/8 (move-then-respread) | repo lesson | local | 1 h | **1** |

### Group 3. Station and grid-to-point representativeness

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 13 | **UR3 grid-to-point and UR4 FIRST-10 shrinkage**: confirm whether they ran; if not, run with the fixed rule | repo | local | 2 h | **1** |
| 14 | **HRRR quantile mapping to the pad**: 3 km model, quantile or quantile-delta mapping with a short site record, shrunk to the regional map | research | HRRR point Zarr, MBs | 4 h | **1** |
| 15 | **Representativeness error term**: add the sub-grid variance (known from dense mesonet pairs) to sigma as a separate component | research | WTMesonet / MADIS | 5 h | 2 |
| 16 | **Dense-station kriging of the bias** over NM/TX using MADIS truth, replacing the 2-station anchor | research + WIND-Bench | MADIS 1-5 GB | 8 h | 2 |
| 17 | **Pad-node (IL-131) learned from first 10 days of logs** with shrinkage | repo | data/ops/raw | 1 h | **1** (if logs exist) |

### Group 4. Forecast-mode strong wind and spread

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 18 | **AV9 + spread refit** (centre right, spread not) | repo | local | 2 h GPU | **1** |
| 19 | **Quantile regression forest / distributional forest** for station wind with HRRR/ECMWF predictors, as a spread model | research | om_previous_runs | 6 h | 2 |
| 20 | **EMOS on wind speed with a truncated or censored shape**, a cheap spread baseline, not a replacement | research | local | 2 h | 2 |
| 21 | **Student-t widening by lead, tuned only on the |cov90 - 0.90| rule** | repo (Student-t) | local | 1 h | 2 |
| 22 | **Two-reference blend (IFS ENS + HRRR) for the centre** | repo + wb2_ifs_ens | local | 5 h | 2 |

### Group 5. Truth, validation and rules

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 23 | **Real pad weather comparison** with `scripts/atmosphere_check.py` | repo | data/ops/raw | 1 h | **1** |
| 24 | **NEXRAD VWP and PSL profilers as independent aloft truth** to score the aloft bias (-2 to -4.5 m/s) | local + new | nexrad_nvw + 1 GB | 5 h | 2 |
| 25 | **MERRA-2 as second proxy**: check whether the calm/shear bias is ERA5-specific | local | merra2 | 3 h | 2 |
| 26 | **Pass-rule template for wind**: one sentence per script: sample size, `abs(cov90-0.90)`, CRPS 0.2 % | Part C | none | 0 | **1** |

### Group 6. Bigger or more speculative

| # | Idea | Source | Data | Cost | Tier |
|---|------|--------|------|------|------|
| 27 | **Autoregressive multivariate post-processing** (Schaake shuffle already in; try AR copula over height) | research | local | 10 h | 3 |
| 28 | **Fine-tune on 50 Hz turbulence** to learn a gust and turbulence head | SWiFT 50 Hz | 31 GB local | 15 h GPU | 3 |
| 29 | **Learned dynamic range map** replacing the static one in UR5 | repo | local | 8 h | 3 |
| 30 | **Wind atlas prior (E1)** combined with the generator in climate mode | repo | local | 6 h | 3 |

---

## Best combination (my recommendation)

Run in this order; each step is one small script with its rule fixed beforehand:

1. **#26** rule template and **#1** UR5 re-score (cheap, and the biggest known gain: 3 h calm error 0.237 -> 0.036).
2. **#2 + #3 + #4**: explain and remove the 10 m bias and calm-fraction gap as one block.
3. **#7 + #8 + #12**: shear law on SWiFT and sodars, then the spread refit. This addresses 47-200 m coverage 0.51-0.60.
4. **#14 + #13 + #17**: HRRR quantile mapping and grid-to-point, with the pad node when logs exist.
5. **#18**: AV9 with spread refit for strong wind.
6. **#23 and #24**: independent truth, to know if any of it is real.

Total new data for steps 1-6 is about 1-3 GB; the 30 GB cap is not needed unless #16 or #28 is tried.

## Where this is weakest
- The research found no source on calm-wind underestimation specifically, no EMOS-for-HRRR material, and nothing specific to NM profilers. Ideas 4, 14, 15, 19 and 20 borrow from general downscaling and post-processing literature.
- Cost and size figures for new data are estimates.
