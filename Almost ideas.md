# Almost ideas

Experiments that failed their rule by a small margin or on one clause only, still showed a measured benefit, and were closed without a follow-up variant being built. Written 2026-11-12.

**What was searched.** `docs/logs/AUTOPILOT.md` was read in full, `docs/logs/LOOP3.md` in full to line 124 and by keyword after that, and the result tables of `New_Plan.md` (section 9) and `To-do-Concise.md` by keyword. `PHASE4_LOG.md`, `LOOP2.md`, `SIDELINED.md` and `docs/plans/PLAN.md` were not read line by line, so an early-phase near miss could be missing.

**Follow-up.** Each near miss below now has a variation with a pre-set rule in `New_Plan.md` section 13 (AV1 to AV21).

**How to read it.** Every number is copied from the log. "Untried variant" means no run of it was found in the logs. None of these was re-run for this file.

---

## Short list: the six most worth a second look

| # | Idea | Benefit that was measured | Why it failed | Untried variant |
|---|---|---|---|---|
| 1 | N6 big world-start Mode F | lead 1 d CRPS -4.7 to -5.8 %, lead 3 d -1.4 to -3.4 % | lead 7 d +2.2 to +4.0 % worse | use it for leads 1-3 only |
| 2 | N5 all-lead Mode F network | beyond 7.5 d: -2.9 to -3.7 % vs binned, beats climate at days 8-10 | leads 1-3 worse by +0.9 to +2.7 % | use it beyond 7.5 d only |
| 3 | C6 run-to-run disagreement spread | CRPS -0.69 % [-1.19, -0.24] | PIT interval [-0.0051, +0.0007] touches 0 | wind bands only; CRPS rule; more test dates |
| 4 | G1-5 spread tracker | coverage error down in 4 of 4 cells, CRPS better in 3 of 4 | one cell +0.002 over a 0.0009 limit | fixed widening; test on the tool's own forecast output |
| 5 | O1 two neighbours at once | better than the best single neighbour in 4 of 4 runs | interval excludes 0 in 1 of 4 only | more hours per target |
| 6 | N2 world-start fine-tune | -0.8 to -2.7 % vs own model, interval below 0 at 16 of 16 | the un-tuned world model missed the 1 % clause | adopt the fine-tuned model on its own evidence |

Items 1 and 2 fit together: one router with the big model at leads 1-3, the shipped model at 5-7 and the all-lead network beyond 7.5 d. Neither half was built.

---

## A. Forecast mode (Mode F)

### A1. N6, full-size world-start Mode F (KILL, 2026-11-12 02:45)
- **Result:** against the small shipped model, lead 1 d -4.7 to -5.8 % (interval below 0 in all 4 box x seed cases), lead 3 d -1.4 to -3.4 %. Lead 7 d +2.2 to +4.0 % worse everywhere, Denver lead 5 d +1.5 / +1.6 % worse.
- **Rule that failed:** not better at 2 or more leads in a box x seed.
- **What the log says:** "best lead 1-3 Mode F seen so far; a lead-split is a possible new item for the user".
- **Untried variant:** a lead split (big model at 1-3 d, shipped model at 5-7 d). N7 was never started because it depended on N6 passing.
- Log: `docs/results/logs/kit_b5_modeF_big.log`.

### A2. N5, one network for all leads (KILL, 2026-11-11 23:56)
- **Result:** beyond 7.5 d the all-lead network beats the binned model by -2.9 to -3.7 % (NM/TX -0.139 [-0.193, -0.097], Denver -0.167 [-0.218, -0.121]) and beats the climate model at days 8, 9 and 10 in both boxes. At lead 1 d it is +2.4 to +2.7 % worse, at lead 3 d +0.9 to +1.1 % worse.
- **Rule that failed:** worse by more than 1 % at leads 1-3.
- **What the log says:** "a long-lead-only network is a possible later item".
- **Untried variant:** serve this network only beyond 7.5 d, where the tool now falls back to the climate generator.
- Log: `docs/results/logs/kit_b5_modeF_alllead.log`.

### A3. C6, widen by run-to-run disagreement (FAIL by rule, 2026-11-12 09:50)
- **Result:** CRPS -0.69 % [-1.19, -0.24] (u 2.301 -> 2.287, v 2.386 -> 2.369, T 0.890 -> 0.883). PIT distance 0.0545 -> 0.0527, change -0.0018 [-0.0051, +0.0007].
- **Rule that failed:** the whole PIT interval had to be below 0.
- **Premise step:** passed narrowly, 4 of 8 cells (wind 0-1 / 1-5 / 5-12 km rho 0.30 / 0.37 / 0.38, T 5-12 km 0.33; the other four 0.18-0.27).
- **Untried variants:**
  - apply the factor only in the four cells where the premise held;
  - a CRPS-only rule (the log leaves this to you);
  - a larger test set: 2022 had only 36 init dates;
  - 12 h lagged pairs: only 36 h pairs are on disk.
- Script: `scripts/c6_lagged_spread.py`.

### A4. N2, world-trained Mode F fine-tuned on the box (MISS, 2026-11-11 17:00)
- **Result:** world model + 300 box steps vs the box's own model: -0.8 to -2.7 %, interval below 0 at all 16 lead x box x seed checks. The control (own model + 300 steps) moved only -1.1 to +1.1 %, so the gain is the world start.
- **Rule that failed:** the world model *as is* had to be within 1 % of the own model at every lead; it was +0.2 to +3.7 % worse.
- **Variants that were run:** B (one fit year only) PASSED, -1.9 to -5.1 %, 16 of 16; C (place descriptors) MISSED.
- **Still open:** nothing was adopted from any of the three; the log marks it as your decision.
- Logs: `kit_b5_modeF_world.log`, `kit_b5_modeF_scarce.log`, `kit_b5_modeF_place.log`.

### A5. G1-5, forecast spread tracker (FAIL by rule, 2026-11-12 07:30)
- **Result:** coverage error falls in 4 of 4 site x variable cells (MAF wind 0.27 -> 0.14, TCS T 0.17 -> 0.06). CRPS better at TCS wind, MAF wind, MAF T (MAF wind 1.315 -> 1.273).
- **Rule that failed:** TCS T CRPS 1.290 -> 1.292, +0.002 against 0.0009 allowed.
- **Caveat in the log:** the factor sat at its 1.5 cap almost always, so this was a fixed widening, not tracking.
- **Untried variants:** a plain fixed widening factor; wind only; and the test the log itself names as missing, on the tool's forecast-mode output instead of the raw ensemble.
- Script: `new_plan_kit/b3_g15_spread_replay.py`.

### A6. N3 step 0, more fit years (closed, 2026-11-11 14:58)
- **Result:** going from 3 to 4 fit years gained +0.66 % (seed 0) and +0.34 % (seed 1) against a 0.5 % rule: one seed each side.
- **Untried variant:** none obvious; listed because the two seeds straddle the line.

---

## B. Launch-day observations and ground wind

### B1. O1, merge two neighbour stations (FAIL, 2026-11-11 12:25)
- **Result:** merged report minus best single neighbour: TCS -0.043 [-0.096, +0.013] and -0.019 [-0.104, +0.066]; ELP -0.105 [-0.153, -0.053] and -0.038 [-0.089, +0.008]. Better in all 4 runs, coverage 0.84-0.89.
- **Rule that failed:** interval must exclude 0 at both targets in both seeds; it did once.
- **Untried variant:** more than 200 hours per target. The intervals are about +-0.06 m/s wide, the same size as the effect.

### B2. S1, site map first, then the observation update (FAIL, 2026-11-11 11:25)
- **Result:** map + B beat B on CRPS at all 12 pair-seeds (-0.007 to -0.063 m/s).
- **Rule that failed:** ONM coverage 0.78 in seed 1 (floor 0.80), and the cell factors differed by 0.086 between seeds (limit 0.05).
- **Untried variants:** more prior hours per cell (40 per cell now) to steady the factors; dropping ONM, which lies outside the trained area (IL-209). IL-208 (a height-difference term for ONM) is logged as an idea with no result found.

### B3. O4, analog tail fix (FAIL, 2026-11-11)
- **Result:** CRPS better at both sites with intervals below 0 (TCS -0.010 [-0.017, -0.004], MAF -0.027 [-0.033, -0.019]). Strong-wind under-prediction TCS 2.44 -> 2.11, MAF 1.87 -> 1.37 m/s.
- **Rule that failed:** the under-prediction had to halve. TCS coverage also fell 0.89 -> 0.83.
- **What the log says:** "a better analog overall, but not the fix the rule asked for".
- **Untried variant:** use it as the referee analog anyway. This is a referee, not a tool feature.

### B4. O3, launch-week factor (FAIL, 2026-11-11 12:55)
- **Result:** k = 7 vs no factor: seed 1 helps both sites (TCS -0.044 [-0.070, -0.018], MAF -0.029 [-0.047, -0.013]); seed 0 is neutral (TCS -0.016 [-0.039, +0.007], MAF +0.008). MAF coverage 0.91 -> 0.90.
- **Rule that failed:** both sites, both seeds, coverage not lower.
- **Untried variant:** start from the IL-207b per-site factor instead of 1.0. The planned starting shape (S2) was dropped, so O3 ran without one.

### B5. A2, past-mode wind spread x1.2 as default (FAIL)
- **Result:** airports better (TCS / MAF -8 / -13 % vs -5 / -11 % without). Both USCRN basin sites worse (Las Cruces 0.744 -> 0.750, Monahans 0.604 -> 0.634).
- **Status:** exists as the opt-in `Launch(past_wind_spread=1.2)`.
- **Untried variant:** an automatic airport-or-basin switch. The one attempt to predict the factor from site descriptors (IL-168 / P7) was neutral on 8 sites.

### B6. Smaller ones
- **P2, gust as a mixed-layer wind measurement:** -2.3 % MAE in mixed air, about 0 at night, "too small to wire". A daytime-only gate was not tried.
- **Regional gust law:** ties the built-in law overall, better above 5 m/s and worse below. A switch by wind speed was not tried.
- **P6W, wind loss term up to 150 m:** every 10-300 m wind column +0.001 to +0.0015, mean +0.0001; closed neutral on two score seeds. The second training seed that IL-180 asked for was not found.

---

## C. Climate generator and shear

### C1. Balloon shear target, two forms (both FAIL, closed 2026-11-11 03:50)
- **Result:** each form passed one band and failed the other. Form "ratio": p99 new / balloon 1.03 at 5-12 km, 1.22 at 1-5 km. Form "c1": 0.97 at 1-5 km, 0.82 at 5-12 km. CRPS unchanged in both.
- **Untried variant:** c1 at 1-5 km with ratio at 5-12 km. The log refused it on purpose, because choosing per band on the test balloons would be fitting the test set. It needs a balloon block that neither form has seen.
- **Related:** IL-103 balloon-fitted shear map brought 12-18 km p99 from 24.6 to 29.0 against 28.5 for pre-2023 balloons with CRPS unchanged, and was not adopted. An aloft-only version was not run.
- **Weight against it:** IL-201 showed 100-300 m shear does not move apogee or landing for the trial rocket.

### C2. IL-10, trust layer refit on NM/TX (discarded by rule, 2026-11-05)
- **Result:** ERA5 skill15 +0.0277 -> +0.0285, balloons +0.0083 -> +0.0090. Gains at u, v 0-1 km, T 5-12 km and rh2m (+0.0095).
- **Rule that failed:** gains of 0.0008 and 0.0007 against a 0.001 margin; balloon coverage error 0.0039 -> 0.0045; T 12-18 km lost 0.0043 because that band's target changed around 2020.
- **Untried variant:** the same fit with T and u 12-18 km switched off. The trust layer was later used at Denver, never again on NM/TX.

### C3. IL-54, shear-tail loss weight 2.0 (discarded, 2026-11-05)
- **Result:** balloons +0.0083 -> +0.0093, exactly at the 0.001 margin; ERA5 coverage error 0.0034 -> 0.0030.
- **Why dropped:** its purpose, the 99.9th-percentile shear, did not rise. Single seed, and the balloon seed spread is 0.0013, so this is the weakest entry here.

---

## D. New-region transfer (Denver zero-shot)

### D1. L3-4, SIREN location encoding (not adopted, your decision 2026-11-06)
- **Result:** the only coordinate encoding that passed both NM/TX rules (+0.0278, shape PASS). Denver -0.176 -> -0.138, 22 % of the gap.
- **Why dropped:** Denver T 12-18 km fell to -0.30, and it made 12x ERA5's surface jumps.
- **Untried variant:** SIREN plus climatology inputs (L3-7), which the log says carry the stratospheric temperature. L3-7 was sidelined and never run. The log also says to retest once several boxes exist.

### D2. L3-26, Student-t noise (rejected for NM/TX)
- **Result:** Denver -0.1918 -> -0.1729 with better coverage (error 0.0167 -> 0.0111) and no tropopause collapse.
- **Why dropped:** NM/TX shape FAIL (vertical correlation error 0.076 -> 0.109).
- **Status:** labelled "transfer-only candidate for the global model"; not used since.

### D3. L3-34 / L3-48, climatology debias (works alone, redundant in the stack)
- **Result:** the largest gain without retraining: Denver -0.1918 -> -0.0313, and -0.0253 with the logit humidity fix (RH 12-18 km coverage 0.47 -> 0.86).
- **Why dropped:** adds nothing once the local trust blend is on (+0.0099 -> +0.0094).
- **Untried variant:** the log reads this as evidence for learning in anomaly space (L3-8, SAMOS targets). L3-8 was sidelined and never run.

---

## E. Passed, but never built or shipped

Not near misses, but the same kind of unused value.

| Item | Result | What is missing |
|---|---|---|
| A1 persistence law for `observe` | MAF gap +0.037 m/s [+0.007, +0.067], build rule met | judged too small; never built |
| N1 cross-fitted members | ERA5 skill15 +0.0020 / +0.0026, balloons +0.0030 / +0.0037 | not exported (ASK_LATER 26); part of the gain may be the extra 2021-23 years |
| N2-B world start for a data-poor box | -1.9 to -5.1 %, 16 of 16 | no adoption |
| ENSF2 ensemble features | -1.9 to -3.1 % NM/TX, -0.7 to -2.2 % Denver, three seeds | opt-in code exists; shipped assets not re-exported |
| G2-2 Student-t widening | surprising 10 %: cov90 0.85 -> 0.92 | flag off; radar path not evaluated |
| IL-167 wind / temperature column blend | +0.0012 in-box, Denver equal to base | parked as the recipe for one model over several regions |

---

## F. Already rescued (left out on purpose)

These near misses did get a variant that was kept:
- IL-86 full PIT recalibration -> damped version, L2-H1 c1 / c4.
- IL-16 B seasonal widths -> above-1 km version, c4.
- C4b near-ground loss -> C4w, wind term only.
- A3-fix B neighbour rho, failed at the 0.81 floor -> adopted with a cap (ASK_LATER 23).
- F-14 driver interactions -> IL-97 restricted version (also failed).
- IL-207 TCS spread -> IL-207b per-site factor (opt-in).

M4 ECC ordering looked like a near miss on 2022 (-2.5 % variogram score) but the replicate on 2023-24 (O5) was worse at leads 3-7, so it is not listed.
