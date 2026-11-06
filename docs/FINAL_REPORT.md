# Final report: Tempest-ARKNET pilot-box system (2026-11-06)

Plain-language summary of the finished system, the single 2026 January-June test and what is still open. All numbers are from files in the repo (`docs/final_test/`, `docs/APPLIED_STATUS.md`, `Code-Modifications/AUTOPILOT.md`).

## 1. What the system is
A probabilistic atmosphere generator for the pilot box (31-34 N, 108-101 W). For a date, hour and place it returns many whole, physically coherent profiles (wind u/v, temperature, humidity at 44 heights up to 18 km, plus 2 m temperature, surface pressure and 2 m humidity) whose ranges are calibrated so that a 99 % range holds about 99 % of outcomes. Three sources are blended by lead time: the climate generator (any date to 2100), a forecast-conditioned network on the live ECMWF forecast (about 0.75-7.5 days, afternoon and evening hours), and a past-date mode (ERA5 plus learned balloon corrections). Hours served: 06-21 local solar time. Other places are refused.

## 2. How it was tested (and what is NOT clean)
- **Final test:** 2026 January-June, run once (`scripts/final_test.sh`, lock file). Nothing was chosen, tuned or calibrated on these rows (training ended 2020, calibration 2021-23, checked by `scripts/e3_checks.py`).
- **Truth:** (a) ERA5-type targets of the dataset (85,734 rows) and (b) real radiosondes, Santa Teresa and Midland, 2026 January-June (about 290 and 264 soundings, only those with an ERA5 pair).
- **Baselines scored with the same code:** E12 (the earlier adopted model), a 15-year recent climatology, and a Gaussian baseline built the way Earth-GRAM builds a dispersion (monthly mean and spread per place and hour). **Real Earth-GRAM was not available.**
- **Not clean:** the 2024-25 development years were used many times to accept or reject changes, so their numbers are slightly optimistic. The seed-to-seed spread was measured late (ERA5 skill15 0.0006, balloons 0.0013) and used for the later decisions. Two balloon stations are the only independent truth.
- **Not tested on 2026:** the forecast-conditioned mode (the archived forecasts used to train and test it end in January 2023; its test year is 2022). Its numbers below are from 2022.

## 3. The 2026 January-June result (drivers unknown, as a real query would be)
Tables with intervals, cell by cell: `docs/final_test/tables.md`.

| | ERA5-type targets | Balloons |
|---|---|---|
| Skill vs the recent 15-year climatology (mean of 19 variable x height cells) | **+0.0209** (E12 +0.0204; development years +0.0278) | **+0.0187** (E12 +0.0160; development +0.0084) |
| Mean distance of the 99 % range from 99 % coverage | **0.0049** (E12 0.0047; development 0.0032) | **0.0064** (E12 0.0063; development 0.0038) |
| CRPS skill vs the Gaussian (Earth-GRAM-style) baseline | **+5.6 %**, better in 13 of 19 cells (E12 +5.5 %) | **+2.2 %**, better in 12 of 19 cells (E12 +2.0 %) |

What this says, honestly:
1. **The final system is not clearly better than E12 in any cell on 2026.** All 38 cells are statistical ties. Mean skill is slightly higher (balloons +0.0027) but inside the intervals.
2. **It beats the Gaussian baseline on average**, by a lot for temperature and surface (T 0-12 km +13 to +16 %, 2 m temperature +25 % on ERA5, +9.5 % on balloons) and not at all for wind (u 1-5 km -3 % on both truths). Cells where it is NOT better than the Gaussian: ERA5 u 1-5 km, u 5-12 km, v 5-12 km, v 12-18 km, T 12-18 km, RH 5-12 km; balloons u 0-1, 1-5, 5-12 km, v 5-12, v 12-18, T 12-18, RH 12-18 km.
3. **Temperature at 12-18 km has negative skill against recent climatology** on 2026 (-0.030 ERA5, -0.039 balloons), on E12 as well. The tropopause-region target changed around 2020 (found earlier, IL-67); this is the known weak spot.
4. **Coverage is looser than in development:** the 99 % ranges hold, but the average miss is 0.0049 / 0.0064 instead of 0.0032 / 0.0038. Weakest cells: balloons RH 12-18 km (0.958), balloons v 12-18 km (0.977), ERA5 T 0-5 km and 2 m temperature (0.978-0.980).
5. 2026 is a harder half-year than 2024-25 for both models and the Gaussian baseline alike; six months of data is also a small sample.

## 4. Distribution shape (the main target)
Metrics: PIT distance, coverage error at all levels, skew, kurtosis, tail rates, event-conditional coverage, vertical correlation of the profile, shear distribution. Files: `docs/final_test/*.txt`, `final_shape.csv`.
- **The shape stack helps, also on 2026:** against the plain p2f generator on the same 2026 rows, the shuffle with 2-degree templates plus the refit shear map gives shear distance 0.0333 -> 0.0274, vertical correlation error 0.0697 -> 0.0606 and a smaller event-coverage gap; nothing worse (descriptive ablation, not used for any choice). In the development years the gain was larger (shear 0.0196 -> 0.0090, vertical correlation 0.076 -> 0.039).
- **Against E12 on 2026** (each on its own dataset's truth, so only indicative): vertical correlation error better (0.061 vs 0.073), pre-clip humidity out-of-range share better; shear distance worse (0.027 vs 0.019) and the tail-rate error worse (3.9 vs 2.1, driven by RH at 12-18 km).
- **Standing weaknesses:** tail-rate error is about 3-4 nominal rates (goal 0.2), PIT distance 0.037 in development (0.09 on 2026 for both models), coverage error per level above its goal. The tail-rate goal is probably unattainable at these sample sizes.

## 5. Forecast-conditioned mode (tested on 2022, not 2026)
CRPS skill vs a short-record climatology at 1 / 3 / 5 / 7 days: raw HRES profile 0.57 / 0.34 / 0.08 / -0.21; network 0.69 / 0.54 / 0.35 / 0.20; final tool mixes network and ridge 50:50: 0.691 / 0.539 / 0.350 / 0.209. The Schaake shuffle brings the vertical correlation error from 0.3-0.5 down to 0.05-0.12.

## 6. What the tool adds beyond the generator (all opt-in assets, built by `scripts/export_final.sh`)
Surface values with spread for past dates (CRPS 2 m temperature 1.16 -> 0.68 K, surface pressure 48.8 -> 25.9 Pa); calibrated vertical wind (99 % coverage 0.984 -> 0.991); station-correction hybrid for humidity at 12-18 km in past mode; online bias tracker for the live feed (MAE lower in almost every site / lead / variable cell, never worse); station-scale widening of the 10 m wind (90 % interval of station wind 59-80 % -> 88-89 %); shape stack in the tool.

## 7. What was tried and did not help (kept off, code stays)
Seasonal width factors beyond RH/surface (event-coverage gap worse), median shifts (IL-13, IL-72), trust layer, shear patches, shear-loss variants, 8-seed ensembles, token generator (too slow), driver interactions (F-14, IL-97: far worse), final-m=8 and RH-in-loss training (F-15, F-19), trajectory-aware first guess (F-10), post-2022 indicator (F-11 part 2), split validation windows (F-7, F-7b), gust stability inputs and soak-library wind matching (F-25, F-26), station-blend dataset (F-20), PIT recalibration alone (IL-86: mixed), Chronos-2 for the climate indices. Full list: `Code-Modifications/SIDELINED.md` and `AUTOPILOT.md`.

## 8. What is open
- **Needs you** (`Code-Modifications/ASK_LATER.md`): pushing the latest local commits to GitHub; the Colab pulls (forecast archive with 00Z and 12Z starts, IFS ensemble, optional ARCO) for night hours, 8-10 day forecasts and ensemble calibration; North America (data and compute); real Earth-GRAM; stage 6 (tools for the flight simulator only).
- **Waiting on data:** the 8 near-ground ERA5 levels (CDS download in progress) and the retrain on them; the daily ensemble logger needs 60-90 days.
- **Group C (next):** hourly and downrange coherence, then stage 6.
- **Sidelined ideas:** `Code-Modifications/SIDELINED.md`.

## 9. Bottom line
A well-verified pilot-box system whose calibrated ranges hold on an untouched half-year and which clearly beats an Earth-GRAM-style dispersion for temperature and surface fields, but only ties it for wind. It does not clearly beat the previous model E12 in skill; its gains over E12 are in vertical coherence, shear distribution, surface spread, forecast blending and the tool, not in per-variable CRPS. Skill over a recent climatology is small (about +0.02 on 2026).
