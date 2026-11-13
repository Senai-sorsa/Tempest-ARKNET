# Secondary ideas (working file, 2026-11-11)

Purpose: the long list behind section 10 of `New_Plan.md`. About 20 ideas were written down, attacked
three times, and cut to 3 structural ideas and 5 others. Nothing here was run. Every number is from an
existing log (named beside it) or from the code.

## 1. What the logs say

**What worked (and why)**

| Result | Numbers | Common cause |
|---|---|---|
| Own-station report (`observe`) | CRPS -0.48 / -0.52 | a real measurement on launch day |
| Radar 0.5-2 km (`observe_radar`) | +31 % at 2.5-5 km, +16 % at 5-12 km | a real measurement, new information |
| Sounding update, schur x1.5 (`g1_localize_eval.log`) | +15-17 % at 2.5-12 km | same |
| IL-207b site factor at TCS | CRPS -0.079 and -0.075, coverage 0.81 -> 0.85 | simple statistic beside the network |
| Site quantile map, past mode (`gw_tool_calibrated.log`) | 1.079 -> 1.031, coverage 0.78 -> 0.89 | same, fitted on many hours |
| A3-fix variant B (distance gain) | neighbour coverage 0.69-0.76 -> 0.81-0.92 | uses a law the tool already measured |
| Ensemble inputs, mode F | -1.9 to -3.1 % at 1-7 days | new inputs |
| Analog ensemble (`gw_analog.log`) | 1.010 at TCS vs tool past 1.133 | plain statistics on a long record |

**What failed (and why)**

| Result | Common cause |
|---|---|
| Shear target (both forms), group-rank shuffle, oracle templates | changes to the shuffle / template stage |
| C2 GPU fine-tune | the network was not the cause |
| Spread x1.2 (A2), regime spread (`p4_dynamic_spread.log`), per-height T spread (`il166`) | spread fixes pooled over sites: helps one site, hurts the next |
| Neighbour treated as own station (A3) | too much trust in a distant report |
| Sector x stability factor (`gw_downscale_station.log`), regime HRRR fit | small-group fits |

**Three facts that point to the next step**

1. The speed-space update (`launch._speed_space_update`) maps the report through the PRIOR pool's own
   speed distribution. If the prior is too calm, the report lands in its far tail and the result is too
   narrow. TCS covers only 0.82 with its own report. This is why variant B misses the floor exactly when
   TCS is the target (LRU 0.81, ONM 0.75).
2. The TCS error is a too-flat day / night cycle, not an offset. Over all hours the quantiles are right
   (`e1_extremes_coverage.log`: q50 0.533, q75 0.747, q95 0.929), but the 08-20 h bias is +1.44 m/s (IL-207).
   Inference, not yet measured: the tool is too windy at night by a similar amount.
3. A factor borrowed from other sites helps on average (`p7_site_model.log`: 0.960 -> 0.940, 6 of 8 sites
   better) but hurts two sites (PEQ +0.077, MONAHANS +0.045). The LEVEL of the factor is site specific
   (0.92 to 1.20).

## 2. The long list (20 ideas) with the first attack

| # | Idea | For | Attack | Verdict |
|---|---|---|---|---|
| 1 | Apply the site map BEFORE the observe update, then use the variant B gain | fact 1; the hook `site_cal` already runs at the end of `_ensure_pool`, before observe reads the prior | the coverage floor moves when the prior moves | KEEP (S1) |
| 2 | Fit the site map on all ASOS years by matching distributions, not on 300 paired hours | IL-207b factors differ between seeds (1.20 vs 1.38 in one cell); `sitecal.py` has a quantile method | mode ai is a climate estimate, so pairs are noisy; unpaired matching is the right tool | MERGE into 1 |
| 3 | Regional day / night map by leave-one-station-out, for the pad | facts 2 and 3; settles the ASK_LATER 24 caveat | PEQ and MONAHANS got worse with a constant | KEEP (S2), shape only |
| 4 | Launch-week factor from a few days of pad anemometer (decaying average) | NCEP has used this since 2006; `tempest_weather/bias.py` does it for mode F | a week is weather, not bias | KEEP (O3) |
| 5 | Persistence law as the centre at short age | persistence beats tool + observe at MAF by 0.037 | this is the running G1-6 | DROP (duplicate) |
| 6 | Use two or three neighbour stations together | `observe_latest` stops at the first usable station; one neighbour gave 1.437 -> 1.313 (`p1_diff_assim.log`) | neighbours are correlated; over-trust is the A3 failure | KEEP (O1) |
| 7 | Remove the radar bias by height | C4: bias -0.6 m/s low, +1.3 at 5 km | bias 0.6 against rms 6-9: gain under 1 % | DROP |
| 8 | Condition on the full radar profile with an honest error model | "radar+all" gives +17-20 % at 5-12 km but covers 0.49-0.61 at 2.5-5 km | the sigma sweep changed nothing; the fitted R is negative above 3.5 km | KEEP (S3), thinning not a full R |
| 9 | Radar transfer over distance (HDX radar scored at EPZ balloons) | the pad has no radar; 127 common hours on disk | 127 hours is small | KEEP (O2) |
| 10 | Fit the 10 m -> 300 m taper (`SPEED_TOP_M`) on tower / sodar data | 0-300 m holds 87 % of apogee variance | sodars are outside the trained box, ingest not ready; SWiFT is 5 days | DROP (data blocked) |
| 11 | Radar and station report together (G1-3) | both work alone | low risk, low news; follows from S1 and S3 | DROP as its own item |
| 12 | Analog ensemble beside the tool at station sites | in-house -11 to -23 % vs tool past; solid literature | needs a station record; under-predicts strong wind (7.71 vs 10.16) | KEEP (O4) |
| 13 | Continuous spread tracker (G1-5) | exists in `bias.py` | same thing as 4 | MERGE into 4 |
| 14 | Ensemble spread as a spread signal | - | already inside the 24 ensemble inputs | DROP |
| 15 | Fewer T rises below 3 km (0.52 vs 0.318) | G2-7 shape score | post-stack change = the failing class; apogee does not feel it | DROP |
| 16 | More unstable layers at 12-18 km | G2-7 shape score | same class; above what the rockets feel | DROP |
| 17 | Spread factor per hour block | TCS coverage is low by day | `p4`: fails when pooled; spread is short BECAUSE the centre is off | DROP (measure spread again after S1) |
| 18 | Quantile-map form of the site factor | `gw_tool_calibrated.log` coverage 0.89 | same as 2 | MERGE into 1 |
| 19 | Run-to-run disagreement as an error signal (C6) | - | literature: jumpiness is a poor predictor of error (Richardson 2024) | DROP |
| 20 | Physical gust law after a measured wind | `gust_1min.log` 0.61 vs 1.73 | already shipped: `MEASURED_GUST_LAW = True` (`launch.py:62`) | DROP (done) |
| 21 | ECC ordering for mode F | `m4_ecc_test.log`: variogram score 1-3 % better at leads 1-7; per-height CRPS cannot change | "shuffle change" class | KEEP (O5), see round 2 |

## 3. Attack rounds

**Round 2: does it fit the system?**

- S1: no core change needed. `Launch(site_cal=...)` exists and the map is applied before observe takes
  the prior. Problem found: `sitecal.fit_site` wants paired speeds (>= 100). Patch: the kit builds the map
  itself per season x hour block and passes it in the format `apply_site` reads.
- S2: p7 shows a constant fails at 2 of 8 sites. Patch: transfer only the SHAPE (each station's factors
  divided by their all-hours mean), never the level. The level stays 1 at a site with no record.
- S3: the core takes one sigma for all radar levels (`obs["_radar_sigma"]`), so a full error matrix would
  need a core change. Patch: the standard cure for correlated observation errors is to thin and inflate
  (NMC Office Note 175). Use one level per error length (C4: L = 901 m, so every 1000 m) and sweep sigma.
  All through the existing `levels_m` and `sigma_ms` arguments.
- O1: `observe()` holds one wind report. Patch: the kit merges the neighbours into one pseudo-report
  (weights = variant B gains, second gain cut by the between-station correlation) and calls `observe` once.
- O5: ECC only reorders members per height, so per-height CRPS is unchanged by construction. This is the
  reason it is not in the failing class (those changed the marginals or the template source). It needs the
  ensemble members, so it depends on ASK_LATER 21.
- 12 (analog): cannot work at the pad (no record). Reduced to a referee row and a tail fix at station sites.

**Round 3: can the test fool us?**

- S1: de-biasing also changes the own-station coverage, which defined the floor. Patch: the floor is fixed
  before the run at 0.80 (the value the A3-fix runs used). Two seeds, both must pass.
- S1 / S2: the map and the test must not share hours. Fit <= 2022, test 2023-25, never 2026.
- S2: a shape fitted on airports may be an airport effect (open, flat, 10 m mast). Check: USCRN Monahans
  and Las Cruces (not airports) are scored as held-out sites too. `wtk_pad_factors.log` (pad / airport ratio
  0.83 at night, 0.98-1.00 by day) says the pad's night wind is LOWER than the airport's, which agrees
  with the direction of the map.
- S3: picking the best sigma on the test hours is tuning on the test. Patch: choose on EPZ 2021-22, score
  on EPZ 2023 and on MAF (never used for the choice).
- O2: all 127 common hours are at 23 UTC (evening balloon). The result holds for that hour only; say so.
- O3: a decaying factor in a climate-mode pool partly measures the weather of the week. That is allowed
  (it is information the user has), but it must beat the static map, not the raw tool.

**Round 4: honest odds**

| Idea | Chance it passes its rule | Why |
|---|---|---|
| S1 map first, update second | high | mechanism read in the code; each half already passed alone |
| S2 regional shape for the pad | high for "better on average", medium for "no site worse" | p7 already shows the average gain |
| S3 thinned radar profile | medium to high | the gain exists (+17-20 %); only the coverage has to be repaired |
| O1 two neighbours | medium | gain is bounded by station correlation |
| O2 radar over distance | measurement: any outcome is useful | |
| O3 launch-week factor | medium to high | long operational record at NCEP |
| O4 analog referee + tail fix | high (already measured), small value | |
| O5 ECC for mode F | high for the variogram score, unknown for flight outcomes | |

## 4. Final set

Structural: **S1** (ideas 1 + 2 + 18), **S2** (3), **S3** (8).
Other: **O1** (6), **O2** (9), **O3** (4 + 13), **O4** (12), **O5** (21).
Full text with tests and kill rules: `New_Plan.md` section 10.

## 5. Outside sources

| Topic | Source | Used in |
|---|---|---|
| Decaying-average bias correction (NCEP) | ams.confex.com/ams/94Annual/webprogram/Manuscript/Paper232884/bias_annual%20upload_1_19_14.pdf | O3 |
| Kalman-filter correction of 10 m wind (Crochet 2004) | openpolar.no/Record/crwiley:10.1017%2Fs1350482704001252 | O3 |
| Decaying-average BMA (Veenhuis) | ams.confex.com/ams/94Annual/webprogram/Handout/Paper231690/Veenhuis_AMS_2014.pdf | O3 |
| Station bias moved to points with no station (kriging, terrain) | doaj.org/article/43085e4b3e144e1ea87ae7045283b46d ; html.rhhz.net/qxxb_en/html/20170412.htm | S2 |
| Latest observation as an extra predictor (Schulz and Lerch) | arxiv.org/pdf/2401.14393 | S1, idea 5 |
| Adaptive conformal inference (Gibbs and Candes 2021; Zaffran 2022) | arxiv.org/abs/2106.00170 ; arxiv.org/pdf/2202.07282 | idea 17 (dropped; `gw_conformal.log` equals fixed x1.3) |
| Run-to-run jumpiness does not predict error | centaur.reading.ac.uk/120888/11/wefo-WAF-D-24-0115.1.pdf ; nhess.copernicus.org/articles/25/2613/2025/ | idea 19 (dropped) |
| Correlated observation errors, few neighbours are enough | repository.library.noaa.gov/view/noaa/12742/noaa_12742_DS1.pdf ; apps.dtic.mil/sti/tr/pdf/ADA248384.pdf | S3, O1 |
| Analog ensemble (Delle Monache 2013; Alessandrini 2019 tail bias) | opensky.library.ucar.edu/islandora/object/articles%3A12922 ; data.ucar.edu/dataset/e53a880f-c911-473a-b987-574c248de728 | O4 |
| VAD wind profile limits (Holleman 2005) | cdn.knmi.nl/system/data_center_publications/files/000/066/932/original/holleman2005jaot.pdf | S3, O2 |
| Post-processing review | arxiv.org/pdf/2410.11916 | general |

---

## 6. Five more ideas: change how the AI system works (added 2026-11-11, nothing run)

Asked for: five new ideas, mostly about the AI system itself, at least one changing a core AI part,
none tested before, built on what worked, then attacked as a senior AI developer and refined.

Honest note first: no idea can be guaranteed. What can be guaranteed is that none of them can make the
shipped tool worse and that a bad one dies cheaply. So every idea in 6.3 has a cheap first step that
can stop it, a pass rule and a kill rule set before the run, and today's model as the thing to beat.
The first set of five was rejected by the user; 6.3 holds the second set and says why the first went.

### 6.1 Why earlier AI ideas failed (patterns read from the logs)

| # | Pattern | Evidence | Rule taken from it |
|---|---|---|---|
| P1 | Changing the network to get more out of the SAME inputs gives nothing | w768, conv refinement (+0.0281 -> +0.0284), m = 8, Sobol noise, Student-t noise, fill mask: all inside noise. The model is input-limited (P-18) | No idea here asks the network to be smarter on the same inputs. Each adds new information or a new way to combine sources |
| P2 | What helps at home hurts away, and the reverse | no-lat/lon: NM/TX -0.010, but Denver u 0-1 km -1.76 -> -0.14 and T 12-18 km -0.006 -> -0.57. ctxsep, terrain, SIREN: same kind of split | Never one switch for all outputs. Decide per output band (N4) |
| P3 | Fits on little data fail; fits on lots of data work | few-balloon fits, small-group calibration, regime fit worse than pooled (0.766 vs 0.763) | Learn across many sites, few numbers per site (N1) |
| P4 | A fancy model ties the simple rule | Chronos 0.337 vs regression 0.342; analog beats tool past by 11-23 % | Start AS the simple rule and learn only the difference (N1, N3) |
| P5 | A verdict on a checkpoint, not on the shipped tool | audit: shipped Denver model was below climatology (-0.115) and nobody saw it | A standing automatic check on the shipped output (N2) |
| P6 | Gains vanish in the stack, or break its order | shuffle changes, oracle templates worse, train-through-shuffle killed | No idea touches the templates. Any change before the stack refits the range calibration |
| P7 | Extra loss terms and extra heads | shear tail, jump head, tail head | No new loss terms |

### 6.2 Candidates dropped in this round (already tested or already planned)

| Candidate | Why dropped |
|---|---|
| Anomaly generator, climatology as input | Already in `GLOBAL_PLAN.md` (standardised anomalies); L3-7 clim inputs sidelined, L3-1 no-lat/lon failed, "climatology inputs barely move the Denver u bias" (LOOP3) |
| HRRR as teacher for a low-level head | Already planned (AUTOPILOT C3, FIVE_DAY L12); no HRRR archive on disk |
| LoRA packs, mixture of experts, distilling the 4 members | Already in `GLOBAL_PLAN.md` |
| Shared noise across hours, day code, any-sensor input, select-then-nudge | Already in the review (G3-2, C3, G3-5, G3-3) |
| Whole-member weights from a classifier | Entropy pooling was already discarded; weights also shift the per-height calibration (P6). Kept only the classifier as a checker (N2) |
| Flight-outcome score (apogee wind) | 50-150 m carries 53 % of apogee variance (`p6_apogee_sensitivity.log`) but there is no truth there (taper data blocked) |
| Time-series foundation model for the nowcast | Chronos tied regression on the indices; `il122`: no usable trend in 1-minute wind; G1-6 already tests persistence (P4) |
| Loss weights by flight sensitivity | The network is not capacity-limited (P1), so reweighting the loss cannot add skill |

### 6.3 The five ideas (second set, 2026-11-11; the first set was rejected)

The first set (in-context site calibrator, referee network, online committee, input dial, language
sensor) was rejected by the user: N5 not realistic, the others more name than mechanism. Why each
went, after checking:

| First set | Why dropped |
|---|---|
| In-context site calibrator | Needs airports beside ERA5 points. Checked: only 66 of the 200 airports on disk are within 30 km of an ERA5 global point (median 70.8 km). Would need new data. |
| Referee network | A checker, not a change to the system. No measurable gain by itself. |
| Online committee | Generic. Works only where a station record exists, so not at the pad. |
| Input dial | The useful part is transfer to other regions; the G2 test regions are not processed. A reduced, concrete form survives as N4 below. |
| Language sensor | Needs a text download and paid model calls. Not realistic here. |

Rules for the new set: data already on disk only; one laptop GPU or CPU minutes to hours; each idea
has a mechanism with a number behind it from our own logs; each has a cheap step that can kill it
before anything is built. No idea can be guaranteed. What is guaranteed: defaults stay bit-identical,
new models get new names, and a bad idea dies in under an hour.

Facts the set rests on (all read from the repo on 2026-11-11):

| Fact | Where |
|---|---|
| The generator trains on years <= 2020. 2021-23 are used for early stopping and for calibration and are never trained on. | `configs/generator.toml` `val_years = 3`; `models/<name>.calib2021.npz` |
| Two recent training years are worth about 0.003 skill15: p2fv (train <= 2018) +0.0243 against p2f +0.0277; noise 0.0006. | AUTOPILOT F-7, IL-92 |
| Holding out 14-day blocks inside <= 2020 lost 0.0023 (p2fb). | AUTOPILOT F-7b |
| Mode F: width 128, depth 2, 1500 steps, 2 members, CPU. Fit 2016-20, range map 2021, test 2022 only. ENSF2 (-1.9 to -3.1 %) was judged on that one year. | `scripts/cpu_fv2_train.sh`, HANDOVER line 263 |
| Mode F is trained per box (NM/TX; Denver separately). | `[FDEN]` runs |
| `data/raw/wb2_hres_global`: 85 monthly files 2016-2022, HRES at 7483 points worldwide, 13 levels. Read by no model code. ERA5 truth at the same points is in `data/raw/era5_global`. | `points.npz` in both folders |
| Leads beyond 7.5 days in the v2 rows are thrown away. | `modeF.lead_bin` returns 0 |
| Lead as a continuous input (IL-79), stand-in forecasts from ERA5 (PHASE4_FORECAST line 281), per-input dropout (IL-9): planned, never run. Out-of-fold training, a global Mode F, a source mask: not found anywhere. | AUTOPILOT, SIDELINED, PHASE4 |

---

**N1. Cross-fitted members** (core change: how the 4 members are trained and calibrated)

| | |
|---|---|
| What | Each of the 4 members holds out a different set of years: member k leaves out the 2-year blocks with (year // 2) % 8 == k, about 4 of 33 years. It trains on all other years, the newest included. Its range map is fitted on its own held-out years. Pooling as today (row i -> member i % K). |
| Mechanism | (1) Every member now trains on the newest years; today none does. F-7 puts about 0.0015 skill15 on each recent year. (2) Calibration comes from honest output on 16 different years instead of 3. (3) The held-out years are a second test bed; 2024-25 has been used for 17+ decisions. |
| Where in the code | `tempest/generator/train.py` `split`: one option `holdout_fold = [k, n]`, default off. Calibration scripts run per member from the kit (`b5_crossfit.py`). Same training cost as today: 4 members, about 13 min GPU. |
| Mode F part | Leave one year out over 2016-2022: 7 small CPU trainings. Every year becomes a test year; ENSF2 is re-scored on 7 years instead of 1. The final model trains on all 7. |

| Attack (senior AI developer) | Refinement |
|---|---|
| F-7b held out blocks and lost 0.0023. This is the same thing. | Not the same: F-7b still stopped at 2020. But the risk is real, so step 1 isolates it. Whole 2-year blocks, not 14-day blocks, so weather does not leak across the cut. No early stopping on the held-out years: a fixed step count taken from p2f's own stopping point. |
| A map fitted on one member's output is applied inside a 4-member pool. Spread will not match. | One map per member, applied to that member's rows before pooling. The pooled coverage on 2024-25 is in the pass rule. |
| 4 years per member is no more than today's 3. | True per member, so a second arm fits one map on all 16 held-out years. The better arm is chosen on 2021-23 rows held out, not on the test years. |
| The held-out years are older than the launch day; the climate drifts (`ap_bias_by_year.log`, +0.24 m/s per year at 5-12 km). | If coverage on 2024-25 misses, fit the maps on held-out years >= 2010 only. Decided now, not after the run. |
| p2f is a lucky seed (IL-92). | Compare with the mean of the three p2f seeds, +0.0275, with two new training seeds. |
| The verdict needs years no member saw. | Verdict run: years <= 2023 only, test 2024-25, as today. A shipped version would add 2024-25 to the folds; its score is then the held-out score, and that is said in the report. |

Step 1 (13 min GPU): arm A = today's data (<= 2020), fixed steps, no validation set. It must
reproduce p2f within 0.0006. If not, the fixed-step rule is wrong and is fixed before going on.
PASS (set now): on 2024-25, both seeds, ERA5 skill15 >= +0.0287 (mean p2f + twice the tolerance),
balloons not worse by more than 0.0013, coverage error not worse by more than 0.0004.
KILL: gain under 0.0006 in either seed. The Mode F leave-one-year-out part is kept either way; it is
a better test, not a model change.
Cost: about 1 h GPU and 3 h CPU for both arms and seeds; Mode F part 1 h CPU.
Honest odds: test bed and Mode F part near certain; skill gain medium to high (rests on F-7).

---

**N2. One forecast-error model for the whole world** (what Mode F is trained on)

| | |
|---|---|
| What | Train Mode F on HRES / ERA5 pairs from the 7483 world points in `data/raw/wb2_hres_global`, with no lat / lon inputs: forecast profile, lead, season, hour, surface height only. Then two arms: use it as it is, and use it as the starting point for 300 steps on the box rows. |
| Mechanism | Climate depends on the place, and that is why networks moved between regions failed (pattern P2). The error of a forecast, given the forecast profile, depends far less on the place. Pooled fits on much data are what worked here (P3). The world set is 100 times the box set and nothing reads it. |
| Where in the code | New build script from the kit, reusing `modeF.forecast_profiles` (it already takes pressure levels) and `scripts/il6_modeF.py`. No core change. |

| Attack | Refinement |
|---|---|
| ERA5 global holds one hour per day; most HRES valid times will have no truth. | Step 0 counts the matched pairs. Under 300,000 -> stop. |
| 13 levels are coarser than the box files. | Step 0 also converts the box HRES through the same 13 levels and checks that Mode F loses under 1 % with the coarse input. If it loses more, the idea stops there. |
| Without lat / lon the home score dropped before (L3-1, -0.010). | That was the climate network, which has nothing else to tell it the place. Check in 5 CPU minutes: today's Mode F retrained without lat / lon must lose under 0.5 %. |
| The world truth is plain ERA5; the box truth carries the balloon leftover (F-24). | Score only on the box truth. The fine-tune arm exists for exactly this gap. |
| Leakage. | Year 2022 and all points within 500 km of both boxes are kept out of the world training. |

PASS (set now): as it is, within 1 % CRPS of each box's own model at every lead, at NM/TX and at
Denver; fine-tuned, better than the box's own model with an interval that excludes 0 at 3 of 4 leads,
cov99 within 0.003; two training seeds.
KILL: as it is, worse by more than 3 % at both boxes.
Cost: 2 h CPU to build rows, 20 min to train. Honest odds: "works anywhere within 1 %" medium;
beating the box model after fine-tune medium.

---

**N3. Pre-training on stand-in forecasts** (core change: how the Mode F network starts)

| | |
|---|---|
| What | Make stand-in forecasts for 33 years of ERA5 rows: forecast = truth minus a real error profile, drawn whole from the real pairs of the same lead, season and hour bin. Pre-train Mode F on these, then fine-tune on the real pairs at a low learning rate. |
| Mechanism | Mode F learns from 5 fit years and two start hours. Rare states (strong jet, monsoon bursts) are few. The stand-in rows show it every state of 33 years at every hour. Drawing whole real error profiles keeps the vertical structure of the error real. The plan wrote this down (PHASE4_FORECAST line 281); it was never run. |
| Where in the code | Kit build script; `scripts/il6_modeF.py` needs one new option to start from a saved model. |

| Attack | Refinement |
|---|---|
| The model is limited by inputs, not by data (P1). More rows will do nothing. | Step 0 answers this before anything is built: fit on 1, 2, 3 and 5 real years, test 2022. If 3 -> 5 years gains under 0.5 %, closed. |
| The drawn error does not depend on the weather state, the real one does. | So it is only the start. The state dependence is learned in the fine-tune. The pass rule compares with training from scratch at the same total steps. |
| Leakage. | Error pool from fit years only; ERA5 rows of 2021-22 are not used for pre-training. |

PASS (set now): both seeds, CRPS better than from-scratch at leads 5 and 7 with an interval that
excludes 0, not worse by more than 0.5 % at leads 1 and 3, cov99 within 0.003.
KILL: step 0 flat, or no gain at lead 7.
Cost: step 0 20 min CPU; full run 2 h CPU. Honest odds: low to medium; step 0 makes a miss cheap.

---

**N4. One Mode F network with optional sources** (core change: the input layer)

| | |
|---|---|
| What | Train the ensemble-feature model (ENSF2) with its 24 ensemble inputs set to zero on a random 30 % of rows, plus one input bit that says "ensemble present". One network then serves both cases. |
| Mechanism | ENSF2 is confirmed (-1.9 to -3.1 % CRPS) but needs the ensemble feed at launch time, so ASK_LATER 21 is a choice between two models, and a missing feed on the day breaks the better one. A whole-source mask with an explicit bit removes the choice. |
| Where in the code | Rows on disk (`data/modeF_ens`). One option in a kit copy of the training script. |

| Attack | Refinement |
|---|---|
| The fill mask failed before (P1). | It failed as a way to gain skill. Here the aim is no loss on either side. |
| Zero is a legal value for a wind mean. | That is what the bit is for. Inputs are standardised first, so zero is the mean. |
| Width 128 may be too small for both jobs. | If either side loses more than 0.5 %, one extra arm at width 192, then stop. |

PASS (set now): with the feed, within 0.5 % of the ENSF2 model at every lead; without it, within
0.5 % of the HRES-only model; both seeds, both boxes, cov99 within 0.003.
KILL: either side worse by more than 1 % in both seeds.
Cost: 30 min CPU. Honest odds: high.

---

**N5. One network from day 1 to climate** (core change: the network replaces the lead router)

| | |
|---|---|
| What | Lead becomes a continuous input. Train on the real rows at all leads, the ones beyond 7.5 days included. Add rows where the forecast input is a random profile of the same season with the lead set to its cap, so the network learns what "the forecast says nothing" looks like. It then decides itself how far to trust the forecast at each lead. |
| Mechanism | Today leads are put in four bins, rows beyond 7.5 days are dropped, and the hand-over to the climate model is a fixed cosine ramp in `router.py` whose limits were never tuned. A network that has seen the whole range can learn the fade from the data. |
| Where in the code | Kit copy of the Mode F training; `router.py` untouched. The continuous-lead half is IL-79 (planned, never run). |

| Attack | Refinement |
|---|---|
| Are there enough rows beyond 7.5 days? Not checked. | Step 0 counts them. Under 20,000 -> only the continuous-lead half is run. |
| A general model loses to the binned one at short leads. | In the pass rule: leads 1-7 must stay within 0.5 %. |
| Extra heads and loss terms failed (P7). | None here: same loss, same output, only the training rows change. |

PASS (set now): leads 1-7 within 0.5 % of the binned model; beyond 7.5 days better than both the
router mix and the climate model with an interval that excludes 0; never worse than the climate model
at any lead; both seeds.
KILL: worse than the binned model by more than 1 % at leads 1-3.
Cost: 1.5 h CPU. Honest odds: continuous lead medium to high; beating the router at long leads medium.

---

**GPU ideas looked at again (user question 2026-11-11: why is everything CPU?)**

Answer: four of the five ideas work on Mode F, and Mode F was cut to a CPU-size network (width 128,
depth 2, every 4th height) because it overfitted within 250 steps on the box rows (IL-77: validation
0.53 -> 0.64 while train fell to 0.27). The ideas were sized to that network. That was too timid:
N2 and N3 remove the cause of the cut. Two GPU ideas come back; the rest stay dropped.

| GPU candidate | Verdict | Reason |
|---|---|---|
| **N6. Full-size Mode F** (width 512, depth 4, 4 members, all 44 heights) on the N2 world pairs, then 300 steps on the box rows | **Kept** | The small size was a cure for too little data, measured in IL-77. With 100 times the rows the cure is no longer needed. Attack: a big net on the same information gave nothing in climate mode (P1) -> here the information grows too (all heights, world rows). Step 0 stops it if validation rises again. |
| **N7. One generator for climate and forecast**: forecast profile as an optional input group of the main generator | **Kept, after N6** | Gives forecast mode the 33 years, the shear loss and the calibration stack. Attack: must not cost climate mode anything -> pass rule 0.0006. L3-21 (one model for two boxes) was sidelined, never run; this is a different join (two modes, not two places). |
| Input groups switched off at random in the main generator, with a dial | Stays dropped | Honest test needs other regions; only Denver is processed. One site cannot carry a verdict. |
| Pre-train the main generator on the 7483 world ERA5 points, then fine-tune on the box | Stays dropped | The main net is limited by its inputs at home (P-18), not by rows. It is also the user's own global run. |
| Train the 4 members jointly on a pooled loss; more members; snapshot members; weight soups | Stays dropped | m = 8 and antithetic noise gave nothing (F-15); extra loss terms failed (P7). |
| Loss weights by flight sensitivity (0-300 m = 87 % of apogee variance) | Stays dropped | Wider nets gave nothing, so capacity is not short; weights only move capacity. |
| Fine-tune the generator on balloons | Stays dropped | Only local balloon stations on disk; the target already carries the balloon leftover (F-24). |

N6 pass rule: at least 1 % better than the shipped small model at every lead, interval excluding 0,
both boxes, both seeds, cov99 within 0.003. Kill: not better at 2 or more leads.
N7 pass rule: climate mode within 0.0006 skill15 of p2f and forecast mode not worse than the better
of N6 and the shipped model at any lead. Kill: climate mode worse by more than 0.0015.
Honest odds: N6 medium to high (the overfitting evidence is direct); N7 medium.

### 6.4 Order and what each depends on

1. Free or near-free first: N3 step 0 (learning curve), N2 step 0 (pair count, coarse-level check,
   no-lat/lon check), N5 step 0 (row count), N4 (whole run, 30 min). All CPU.
2. N1 step 1 when the GPU is free, then the two arms. N1's Mode F part can run any time on CPU and
   should come before N2-N5 are judged: they all gain a 7-year test from it.
3. N2 and N5 full runs. N3 only if its step 0 passes.

Nothing here touches the running jobs, the 2026 data or the shipped models. Adoption follows
ASK_LATER 22 (pass rule met -> backup, `tool_audit.py`, `shipped_check.py`).

### 6.5 Where the methods come from

| Idea | Method it borrows |
|---|---|
| N1 | Cross-fitting / stacking (out-of-fold predictions for the second stage); CV+ calibration. |
| N2 | Train one model on pooled data from many places, then a short fine-tune per place. |
| N3 | Pre-train on synthetic data, fine-tune on real; noise drawn from real residuals instead of a formula. |
| N4 | Modality dropout with a presence flag. |
| N5 | Conditioning on the noise level, as in denoising models: lead plays the part of the noise level. |
