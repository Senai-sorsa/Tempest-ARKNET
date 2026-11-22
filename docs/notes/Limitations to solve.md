# Limitations to solve

Written 2026-11-10. Continues the numbering of the four limitations already listed (5.2.1 - 5.2.4). These are the largest simplifications and design choices that could make the output unrealistic, or make an engineer decide not to use the tool. Ordered by how much they can offset a flight result. Every number is taken from the repo's own reports (source in brackets); nothing was newly measured for this file.

**Read the audit below first.** It lists what was wrong in the first version of this plan, and the open defects found in the tool while checking it. The plan further down has been corrected to match.

# Bugs, mistakes and misunderstandings (audit 2026-11-10)

How it was done: every claim in the plan was checked against the code (`tempest_weather_v2/launch.py`, `obs.py`, `readers.py`, `radar.py`, `cli.py`, `montecarlo.py`, `tempest_weather/flight_sim_readers.py`, `flight/dryden.py`, `flight/engine.py`), the logs (`w6_observe_eval.log`, `p7_site_model.log`, `gw_conformal.log`, `LOOP3.md`, `AUTOPILOT.md`) and the data folders. No code was changed and no test was run. Severity: **high** = changes what should be built, **medium** = changes a number or a claim, **low** = wording or housekeeping.

## A. Open defects in the tool

| # | Severity | What is wrong | Evidence | What to apply |
|---|---|---|---|---|
| A1 | high | **`observe()` loses to plain persistence.** One hour after a wind report at the same station, tool + `observe` scores CRPS 1.140 (TCS) and 0.987 (MAF). A plain linear rule "next hour = a + b x this hour" scores 1.035 and 0.923. So the tool is 7-10 % worse than a two-number rule on its best case. The W6 update closed part of the gap (from 1.148 / 1.016) but not all. | `w6_observe_eval.log`; `scripts/w6_observe_eval.py` | (1) Rerun both on the same 300 hours so the comparison is paired (today the persistence number comes from another script, W3). (2) If the gap holds, make the 10 m speed follow the fitted persistence law (mean and spread by hour) when the report is from the site and under 3 h old, and keep the pool only for the profile above. Pass rule: tool + `observe` at or below persistence at both stations, 90 % coverage 0.86-0.92. |
| A2 | high | **Past mode is over-confident at 10 m by default.** The fitted widening x1.2 exists but is off: `past_wind_spread=1.0` is the default. Measured 90 % coverage in past mode is 0.80 (GW-1) and 0.73-0.81 (conformal log). The first version of this document said the widening "is applied in past mode". It is not. | `launch.py` lines 111, 127; `LOOP3.md` GW-1; `gw_conformal.log` | Test `past_wind_spread=1.2` with the ERA5 anchor on (the anchor became default after 1.2 was fitted) at TCS, MAF, USCRN on 2024-25. If coverage reaches 0.86-0.92 with CRPS not worse, propose it as the default. A default change: needs the user's yes. |
| A3 | medium | **`observe` has never been tested the way it is used.** Every score is for distance 0 (the report comes from the scored station). The real case is an airport 51 km away, where the fitted gain is 0.62 by day and 0.48 at night. No score exists for that case against any rival. The "(not yet validated)" label is therefore correct. | `w6_observe_eval.py` (`distance_km=0.0`); `obs.py` `REP_TABLE`; `launch.py` 631 | Leave-one-station-out test of the whole `observe` path: report from station S, score at station T, pairs 20-150 km apart, 2024-25. Rivals: no observation, and persistence of S scaled by the fitted gain. Remove the label only for the cases that pass. |
| A4 | medium | **Radar levels are treated as independent.** The error is 3.0 m/s per level (from radar-minus-balloon differences, so it includes the balloon's error), with no correlation between levels. With all radar levels the 90 % coverage fell to 0.49, which is why only 4 levels are used. | `radar.py` line 21; `launch.py` `_sensor_sigma`; review line 607-612 | Measure the error and its level-to-level correlation from the data (Desroziers). Keep 4 levels until then. |
| A5 | low | **Wind below 10 m: shape is rough.** A pad node already exists (see B1). Its limits: the factor 0.72 is the log-law value for 2 m but is placed at 0 m; it is fixed at roughness 3 cm even when `Launch(z0=...)` or the land-cover map says otherwise; the line between 0 and 10 m is straight. Result with z0 3 cm: 5 m is right (0.86 vs 0.88), 2 m is 8 % too strong (0.78 vs 0.72), 1 m is 24 % too strong (0.75 vs 0.60). If the samples have no `t2m`, `sp`, `rh2m` the node is skipped and the 10 m wind is held. | `flight_sim_readers.py` 63-72; `readers.py` 119-125, 165 | Optional `below_10m="loglaw"` in both readers (default unchanged), using the sample's own roughness. Small. Only matters for rails under about 3 m. |
| A6 | low | **Stale text in the code.** The module docstring (line 9) and a comment (line 90) of `tempest_weather/flight_sim_readers.py` still say the 10 m value is used below 10 m. This misled the first version of this plan. | same file | Fix the two lines. No behaviour change. |
| A7 | low | **Turbulence roughness may ignore the site.** The flight engine's default is `z0_roughness_m=0.03`. `Launch` has a land-cover roughness map (R1). Whether the map value reaches the turbulence step on every path was not traced. | `flight/engine.py` 277, 289; `launch.py` 675-694 | Trace it once; pass the sample's roughness if it is not passed. |
| A8 | low | **Sodar data is not ready to score against.** The ingest script says the time zone is not asserted, and the upper gates are often blank. | `scripts/a2e_sodar_ingest.py` | Confirm the time zone from the A2e metadata (or from the daily cycle against ERA5) before any comparison. |
| A9 | low | **Two different ideas share the id IL-192** in `AUTOPILOT.md` (line 205: SOWFA simulation idea; line 614: Denver ensemble features). | `AUTOPILOT.md` | Renumber one. |

## B. Mistakes in the first version of this plan

| # | Severity | What the plan said | What is true | Effect on the plan |
|---|---|---|---|---|
| B1 | high | "Below 10 m the 10 m wind is held. A 5 m rail gets a wind 12 % too strong, a 2 m rail 28 %." | Wrong. Both readers have added a pad node since 2026-11-08 (IL-131, on by default): 0.72 x the 10 m wind at the ground, straight line to 10 m. At 5 m the error is about 2 %. | 5.2.5 idea 2 is mostly built. It drops from step 1 to a small optional fix (A5). |
| B2 | high | "`observe` uses assumed scales. Fit `TAU_H` and `SIGMA_SCALE` on station pairs." | Wrong. There is no `SIGMA_SCALE`. The gains are already fitted on 9 station pairs, 2015-22, day and night (`scripts/obs_loso.py`, IL-156). `observe_latest()` already fetches the nearest METAR and weights it by age, distance and height. | 5.2.5 idea 1 and 5.2.17 idea 1 are replaced by A1 and A3 (the real gaps). The same stale text is in the To-do (C1). |
| B3 | high | "A wind report 1 hour old cuts 10 m CRPS by 41 %." | Misread. That is the station's own report against **climate** mode (1.125 vs 1.897). Past mode alone already scores 1.126. Adding the report to past mode gives 1.021 vs 1.151, so the real gain is **11 %**. And it is for a report from the same spot. For an airport 51 km away it is smaller, and not measured (A3). | The launch-day report is worth having but is not the big win the plan claimed. With no pad data, the same-spot case does not exist for this user. |
| B4 | medium | "Coverage after `observe` is 72 % / 86 % today." | Old run. After W6 (default since 2026-11-10) it is 0.81 (TCS) and 0.91 (MAF). TCS is still under 0.90. | Smaller gap than stated. Folded into A1. |
| B5 | high | "ERA5 model levels are on disk (`data/raw/era5_em`)." | Wrong. `era5_em` holds pressure levels and surface fields. Model levels are not on disk; the ARCO route was blocked (L5). | 5.2.5 idea 4 needs a model-level download first (now approved). |
| B6 | high | "Compare the sodars with ERA5 from the store on disk." | Not possible. `data/raw/era5_global` has **one hour per day** (rotating), 13 pressure levels, and wind at 10 m and 100 m only. The NM/TX stores stop at about 101 W; all five sodars are east of that (Colorado City is just outside, the others further east and south). | The sodar referee needs an hourly ERA5 point pull for the five sites, 2011-07 to 2012-09 (approved). It tests ERA5 against sodar, not the tool against sodar: the tool does not run there. |
| B7 | medium | "The sodars include vertical wind every 10 minutes: fit turbulence strength to it." | Wrong. The `W` column is the 10-minute **mean** vertical wind, not its scatter. It cannot give turbulence strength. | 5.2.11 fix (a) is withdrawn. Sodar speed scatter between 10-minute rows can check gustiness at hour scale only. |
| B8 | medium | "The Gaussian copula makes joint extremes too rare; a rebuilt copula inflated tail shear 3.6-4.8x." | The two halves disagree. The one check run (IL-128) found the rebuild makes tail shear too **high**, and only on a made-up pool. The direction on a real pool is unknown. | 5.2.12 text corrected. Idea 3 (rerun on a real pool) stands and comes before any copula change. |
| B9 | medium | "With the weight fitted on CRPS the blend cannot be worse" (5.2.6 idea 1). | True on the fit years only. On new years it is not guaranteed, and 2024-25 has been used for 30+ decisions. | Renamed "safe blend". Needs the paired test like any other change. Still a good bet (few numbers, many years). |
| B10 | medium | "Fallback with no hardware: regional factor (scale about 1.07, spread about 1.06). Small but free." | The two numbers have no source. The constant factor helps on average (0.960 -> 0.940) but **hurts** the two least airport-like sites (Monahans 0.615 -> 0.660, PEQ 0.974 -> 1.051). A remote pad is like those. | Do not apply the regional factor at the pad. With no pad data, 5.2.5 idea 5 has no fallback. |
| B11 | medium | "Then the adaptive (conformal) interval" as part of the default launch-day path. | In the log it equals a fixed x1.3 widening (0.83-0.88 vs 0.84-0.88). It also needs a running record of measurements at the site, which the pad does not have. | Dropped from the default path. The fixed widening is A2. |
| B12 | medium | "Turbulence on by default for load cases: the tool already has the missing tail." | IL-164's verdict was "no change". Turbulence fills the 0-1 km shear (0.46 -> 0.88 of balloon p99) but adds nothing above 1 km. The 2024-25 balloon shear in 0-1 km also rose because of an instrument change (IL-163), so the target itself moved. | Keep as a documentation step for 0-1 km only. Aloft the fix is the shear map (5.2.12 idea 2). |
| B13 | low | "Ensemble features -1.9 to -3.1 %, two seeds, both boxes." | That is NM/TX. Denver is -1.2 to -2.2 %. Test year 2022 only, 00Z runs every 8 days. IL-195: 75-90 % of the gain is the ensemble mean, not the spread. | Numbers corrected. |
| B14 | low | "Spread 15-25 % too narrow" (5.2.5) | That was against balloons for some seasons. At stations the climate-mode 10 m spread is about right (coverage 0.88, GW-1). The narrow one is past mode (A2). | Text corrected. |
| B15 | low | An earlier reply said 5.2.4 was rated the same as 5.2.18. | 5.2.18 is 6, 5.2.4 is 5. | Heading already fixed. |

## C. Already built, but presented as new work

| Plan item | What exists | What is really left |
|---|---|---|
| Auto-fetch the launch-day report (5.2.5 idea 1) | `Launch.observe_latest()` | A1, A3 |
| Inside / edge / outside (5.2.18 idea 2) | `Launch.domain()` (box and elevation test) | A climatology answer outside the boxes instead of a refusal; the dissimilarity test |
| Flag a report that does not fit (5.2.17 idea 4) | A "far outside the prior" flag (over 4 standard deviations) | Widening instead of pinning; a rule for far or high stations |
| Label the mode and "weather only" (5.2.13, 5.2.16) | `Launch.trust` says both | Check that saved files carry it (not checked) |
| Default vehicle dispersions (5.2.16) | `montecarlo.VehiclePriors`, used in `examples/monte_carlo_quickstart.py` | Nothing but README wording |
| `tempest doctor` (5.2.20) | `tempest doctor` in `cli.py` | Saving fetched inputs next to the output |
| Log law below 10 m (5.2.5 idea 2) | Pad node (B1) | A5 |
| HRRR anchor | `observe_hrrr` | Nothing |

## D. Stated as fact but never verified

- "The 1-second balloon archive includes El Paso / Santa Teresa and Midland." The station list was never opened. Check it before the download.
- The NASA poster link (20250003621) in the sources was not opened.
- The station coordinates in `obs.py` `STATIONS` are marked approximate in the code itself. Distances, and so the weights, inherit that.
- The persistence number in A1 and the tool number come from two scripts; they are on the same stations and years but not the same hours.

## E. What the audit did not cover

- No test suite was run and no number was recomputed. Everything above is read from code and logs.
- FINAL_REPORT numbers quoted in 5.2.6, 5.2.12, 5.2.14 and 5.2.19 were not rechecked line by line (radar +32 / +16 / +7 %, "35 of 38 flights", IL-164 and IL-128 were, and match).
- The training code (`tempest/`) and the forecast mode were not audited. Only the paths this plan relies on were.
- `docs/notes/Innovative idea review.md` ideas were not audited one by one.

---

## Short list

| # | Limitation | Why an engineer would hesitate | Fixable (1-10) |
|---|---|---|---|
| 5.2.5 | Wind in the lowest 300 m is the least accurate part | It is the part that moves apogee the most | 6 |
| 5.2.6 | Wind is no better than a simple statistical baseline | The main selling point is not shown for wind | 6 |
| 5.2.7 | No proof on real flights | Apogee error did not improve on the 3 testable flights | 3 |
| 5.2.8 | The model stops at 18 km | Above that the wind is frozen and the air is the standard atmosphere | 8 |
| 5.2.9 | It learns from a 31 km, hourly-average reanalysis, not from the real air | Real air is rougher, calmer at times and more local | 4 |
| 5.2.10 | Coarse height grid aloft (500 m steps) | Thin shear layers and jet edges are smoothed out | 6 |
| 5.2.11 | Turbulence, gusts and thermals are formulas, not learned or validated | Fine wind structure is a guess | 5 |
| 5.2.12 | Rare extremes are the weakest part of the distribution | Monte Carlo is run for exactly those cases | 5 |
| 5.2.13 | Beyond about 2 weeks it is climatology | A planned date gets "typical" weather, not that day's weather | 2 |
| 5.2.14 | Forecast mode is thinly tested | Tested on 2022 only, one forecast source | 7 |
| 5.2.15 | Truth data is thin and not fully independent | Two balloon sites, twice a day, none at the pad | 5 |
| 5.2.16 | The spread is weather only | Used as "the apogee range" it is badly over-confident | 9 |
| 5.2.17 | Launch-day measurements are folded in with an unvalidated method | The same measurement helped one flight and hurt another | 7 |
| 5.2.18 | Only two regions, and the model does not transfer | Anywhere else is refused | 6 |
| 5.2.19 | Upper-air temperature and humidity weak spots | 12-18 km temperature is worse than plain climatology | 7 |
| 5.2.20 | Depends on external data and local setup | Past mode and the 15-day mode need things that are not in the package | 9 |

Status of the four earlier items is at the end (two of them are partly built already). Ratings and fixes are in the section "Which of these can be resolved" near the end.

---

## 5.2.5 Ground wind (0-300 m): least accurate where the rocket is most sensitive

**The limitation:** The wind between the rail and about 300 m is the model's weakest output, and several simplifications stack up there:
- The lowest model height is 10 m. Below it the readers draw a straight line down to 0.72 x the 10 m wind at the ground (pad node, IL-131). That is right at 5 m and up to 24 % too strong at 1 m (audit A5, B1) [`tempest_weather/flight_sim_readers.py`].
- Only six heights describe the lowest 300 m (10, 50, 100, 150, 200, 300 m), with straight lines between them.
- The training data (ERA5) is an hourly average over a grid cell of about 31 km. It has calm air 1.2 % of the time; real stations have 6.1 % [handover, item W4].
- The 10 m wind has the least skill of any output [validation file, section 10]. In past mode its spread is too narrow (90 % range holds 80 %). A fitted x1.2 widening exists but is off by default (audit A2). In climate mode the spread is about right at stations (0.88).
- Every correction tested so far says the remaining error "is a property of the site": it needs a wind record from the pad itself, and none exists [FINAL_REPORT section 10].

**Why it matters:** For the test rocket, 87 % of the wind-driven apogee spread came from 0-300 m and 53 % from 50-150 m alone. Halving or doubling the wind below 200 m moved apogee by about 3 points; removing all wind above 200 m changed nothing [validation file, section 9]. Rail-exit crosswind also sets weathercocking and stability margin.

**Future improvement:** A real near-surface profile (log-law / stability-aware basis, levels down to 2 m, low-level-jet shape) trained on tower, sodar and mesonet data; a one-month pad anemometer record per site (gave -25 % error in tests).

## 5.2.6 Wind is not better than a simple Gaussian baseline

**The limitation:** On the untouched 2026 test the system beats an Earth-GRAM-style Gaussian baseline clearly for temperature (+13 to +16 %) but **not for wind**: u at 1-5 km is 3 % worse on both truths, and u/v at 5-12 km and v at 12-18 km are not better [FINAL_REPORT section 3]. Overall skill over a 15-year climatology is about +0.02 (2 %). The real NASA Earth-GRAM was never run; the comparison is against a stand-in built the same way.

**Why it matters:** Wind is what drives dispersion, loads and drift. An engineer who already has Earth-GRAM or a monthly wind table can fairly ask what they gain. The honest answer today is "coherent whole profiles and calibrated ranges", not "more accurate wind".

**Future improvement:** Obtain and score the real Earth-GRAM; put the training effort into wind (speed/direction targets, wind-specific loss) instead of temperature, which is already good.

## 5.2.7 No demonstrated benefit on real flights

**The limitation:** Of 38 flights with a measured apogee, only 3 are inside the trained regions. On those, replacing the standard atmosphere did **not** reduce apogee error: 5.21 % as filed, 5.7-5.8 % with the real-day atmosphere, 7.3 % with the climate mode [validation file, sections 4 and 14]. None of the three is an independent test of the climate generator (all are inside its training years). Landing position, drift and loads have never been validated at all: there is no landing data.

**Why it matters:** This is the end goal of the system. The simulator's own error (5-8 %) is two to three times the whole weather effect, so the result is "cannot be shown either way", which is not a reason to adopt a new tool.

**Future improvement:** 20-30 in-region flights from 2024 onward with published designs, pad weather and GPS logs; validate landing scatter, which depends on wind far more than apogee does.

## 5.2.8 The model stops at 18 km (59,000 ft)

**The limitation:** Profiles end at 18 km. Above that the reader holds the 18 km wind constant and continues temperature and pressure along the 1976 standard atmosphere [`tempest_weather_v2/readers.py`, option `above_top`]. No spread, no real stratospheric winds. The planned extension to 80 km is not built.

**Why it matters:** Any flight or descent from above 59,000 ft (the 100,000 ft case in 5.2.2) flies most of its coast and its whole high-altitude drift through air the model did not generate. Stratospheric winds can reverse direction with height and season; a held value can put the landing point on the wrong side.

**Future improvement:** The 18-80 km layer from MERRA-2 / balloon data (plan item A1), with its own spread and tied to the lower profile.

## 5.2.9 Trained on a smoothed reanalysis, not on the real atmosphere

**The limitation:** The generator learns ERA5 (about 31 km grid, hourly means, smoothed terrain), corrected toward two balloon stations. So "truth" is already a model. Known side effects: too few calms, smoother shear than balloons, co-occurring wind-shear extremes overstated against balloons [handover, mistakes B30], and the grid cell's terrain height differs from the pad (93 m at Spaceport America before the elevation fix). Everything between grid points is a straight (bilinear) blend.

**Why it matters:** Local effects the grid cannot see (valley channelling, drainage flow at dawn, sea breeze, lee waves) are simply absent, and no amount of calibration against the same reanalysis will reveal that.

**Future improvement:** Use a 3 km model (HRRR) or tower data as a teacher for the lowest 2 km; score against instruments that ERA5 never saw.

## 5.2.10 Coarse height grid above 2.5 km

**The limitation:** 44 heights: 500 m steps from 2.5 km to 18 km, linear interpolation in between. The source data has only 13-21 pressure levels.

**Why it matters:** Maximum dynamic pressure and the strongest jet-stream shear usually occur at 8-12 km. Real shear layers are often 100-300 m thick; a 500 m grid averages them, so peak shear (and bending load / angle of attack at max-q) is under-stated. The shear distribution is still off after correction (shear distance 0.027 vs goal; FINAL_REPORT section 4).

**Future improvement:** Finer grid in the jet layer, or a shear-detail layer fitted to high-resolution (1-second) radiosonde data.

## 5.2.11 Turbulence, gusts and thermals are textbook formulas

**The limitation:**
- Turbulence is a Dryden / von Karman field added afterwards. Its strength comes from a neutral log law with **no stability correction**, a default roughness of 0.03 m, and a clear-air mixing length of 20 m that the code itself calls "an assumption" [`tempest_weather/flight/dryden.py`]. It was never checked against measured turbulence.
- It is a **frozen pattern versus height**, not a wind that changes in time, because the simulator's wind interface takes altitude only [validation file, section 13].
- Vertical wind is the grid-scale value (centimetres per second). Desert thermals of several m/s are missing: the thermals module is off and unvalidated (its input data was never downloaded) [ASK_LATER 5].
- Gust and vertical wind are not part of the joint sampling; they are copied from the nearest pool member [`flight/engine.py`, marked shortcut].

**Why it matters:** Turbulence widened the apogee spread by 15-35 % in the trial, so it is not negligible, yet its size is a guess. Thermals change time under parachute and therefore drift. A parachute or slow rail exit feels gusts in time, not in height.

**Future improvement:** Fit turbulence intensity to tower / sodar data by stability class; time-varying gusts in the simulator interface; validate thermals against balloon rise rates.

## 5.2.12 Rare extremes are the weakest part of the distribution

**The limitation:** The tail-rate error is 3-4 times the nominal rate (goal 0.2) and the report says the goal is "probably unattainable at these sample sizes" [FINAL_REPORT section 4]. End-to-end, the shipped tool's 90 % ranges hold only 85-93 % of outcomes [section 11]. Time, distance and observation coupling all use **Gaussian copulas**, which do not keep the joint tails of the pool. The direction of the error is not known: the one check, on a made-up heavy-tailed pool, gave tail shear 3.6-4.8x too high, not too low [To-do, IL-128; audit B8]. Convective storms are not represented (5.2.3).

**Why it matters:** A Monte Carlo is run to find the 1-in-100 and 1-in-1000 cases: highest shear, strongest crosswind, furthest landing. Those come from the part of the distribution the model knows least. A range safety or structural engineer cannot take the tails at face value.

**Future improvement:** Heavy-tailed (t or empirical) copulas, extreme-value tails fitted per site, and scoring focused on the worst 1 % against balloons.

## 5.2.13 Beyond about two weeks the answer is climatology

**The limitation:** Measured forecast skill is zero beyond day 14-17 [To-do, L15]. For any later date the generator returns the typical spread for that place, season and hour, nudged by ENSO / QBO indices that are themselves unknown for future dates. It is also offered to year 2100 with a fitted trend that cannot be tested.

**Why it matters:** A real launch day can sit far out in that spread: Juno III's actual low-level wind was at the 99th percentile of the climate-mode distribution, and climate mode was the worst option for apogee (7.3 %) [validation file, section 12]. Users may read "weather for 16 June 2027" as a forecast. It is not.

**Future improvement:** Label the output mode loudly in every file; always re-run inside 7 days and again with pad observations.

## 5.2.14 Forecast mode is thinly tested

**The limitation:** The 0.75-7.5 day mode was trained and tested on archived forecasts that end in January 2023 (test year 2022 only); it was not in the 2026 final test. It uses one deterministic forecast (HRES) as input, covers 02-20 h solar time, and has no 0-18 hour "nowcast". Skill falls from about 0.69 at 1 day to 0.21 at 7 days. The 15-day ensemble route is not calibrated yet: it waits on 60-90 days of logged forecasts [FINAL_REPORT sections 5, 8].

**Why it matters:** This is the mode a launch team actually uses for go / no-go planning, and it has the least evidence behind it.

**Future improvement:** Rolling verification on logged live forecasts; HRRR for 0-48 h; calibrate on the ensemble archive when it is long enough.

## 5.2.15 Truth data is thin and not independent

**The limitation:**
- Real-profile truth is **two balloon stations**: Santa Teresa (about 120 km from the Spaceport America pad) and Midland (about 470 km). No balloon has ever been launched at the pad.
- Balloons fly at 00Z and 12Z only (about 5 pm and 5 am local). Midday profiles, when most launches happen, are checked against ERA5 only.
- ERA5 assimilates those same balloons, so past-mode balloon scores are not independent.
- The 2024-25 "development" years were used for 30+ accept / reject decisions; their numbers are optimistic. Coverage on the clean 2026 test was looser (average miss 0.0049-0.0064 vs 0.0032-0.0038) [FINAL_REPORT section 3].
- Denver has no balloons after mid-2022, so its two models (day and night) have no referee, and two of its correlation inputs are borrowed (18 km column copied from 16 km, nugget from NM/TX) [section 11].

**Why it matters:** The calibration claims ("a 99 % range holds 99 %") are proven for a grid-cell average near two airports at dawn and dusk, not for a pad at noon.

**Future improvement:** Pad soundings or a wind profiler at launch events; radar wind profiles (NEXRAD VAD) as an independent midday truth; a fresh untouched test window for every released model.

## 5.2.16 The spread is weather uncertainty only

**The limitation:** The pool of atmospheres gives an apogee range only 2-7 % wide, and the measured apogee fell **outside the whole sampled range** for all three flights (rank 0.00, 0.00, 1.00) [validation file, section 12].

**Why it matters:** Read as "the apogee range" it is badly over-confident. The vehicle uncertainty (drag, mass, impulse) is 2-4 times larger and must be added by the user. The same applies to landing ellipses.

**Future improvement:** State it in every output and the README; ship the Monte Carlo harness with vehicle dispersions as the default workflow, not atmospheres alone.

## 5.2.17 Launch-day observations: method unvalidated, proxy station far away

**The limitation:** `observe()` pins or nudges the profile with a linear Gaussian update. Its weights are fitted on station pairs, but the whole path was only ever scored with the report coming from the scored station itself, and there it still loses to plain persistence (audit A1, A3). The tool labels the result "not yet validated", correctly. The only available measurement is usually an airport 51 km away and 78 m higher. A morning sounding cannot be ingested automatically. Historically a missing data path made past mode fall back silently to climate mode (now warned).

**Why it matters:** Feeding the same kind of measurement moved Juno III from +4.7 % to +2.0 % but Prometheus from +8.8 % to +11.5 % [validation file, section 12]. An engineer cannot tell in advance whether adding an observation helps.

**Future improvement:** Learn station-to-pad relationships from station pairs (terrain, stability, age of the report); validate against pad anemometers; add the morning balloon.

## 5.2.18 Two regions only, and the model does not transfer

**The limitation:** Served areas are NM/TX (31-34 N, 108-101 W) and a small Denver box. Everything else is refused. This is more than the "less accurate at remote sites" of 5.2.4: the NM/TX model applied to Denver scored **below climatology** (-0.19), and the first shipped Denver model scored -0.115 before a locally trained one replaced it [FINAL_REPORT section 11, To-do]. Each new site currently needs its own training and its own calibration data. Denver also switches between two different models at 06 h and 21 h, so a sequence across those hours is not one consistent model.

**Why it matters:** 35 of the user's 38 validation flights, and every coastal range (Canaveral, Vandenberg, Wallops), are outside. A team that launches at more than one site cannot standardise on the tool.

**Future improvement:** The global model (G stages) with a leave-one-region-out test proving transfer before any new site is served.

## 5.2.19 Upper-air temperature and humidity weak spots

**The limitation:** Temperature at 12-18 km has **negative skill** against recent climatology (-0.030 ERA5, -0.039 balloons) because the tropopause-region data changed around 2020; humidity at 12-18 km covers only 0.958 of a nominal 0.99; the balloon sensor changed in 2022 [FINAL_REPORT section 3].

**Why it matters:** Tropopause temperature sets speed of sound and density where many rockets are near maximum Mach; errors there shift drag and Mach-dependent stability. Humidity aloft matters for icing and contrail / optical tracking, less for trajectory.

**Future improvement:** Retrain the upper levels on post-2020 data only, or blend toward climatology there until it beats it.

## 5.2.20 Depends on external services and local setup

**The limitation:** The 15-day mode needs live Open-Meteo downloads (past ensemble members are not kept by the provider, so results cannot be reproduced later). Past mode needs a local ERA5 store that is not in the package, plus a second store for night hours. Radar input needs an optional package. The asset bundle is about 211 MB per region.

**Why it matters:** A range or review board needs to re-run exactly what was used for a flight-readiness decision. Missing inputs or a changed upstream feed break that.

**Future improvement:** Archive every input with the output (hash-stamped), offline bundles per launch campaign, a `doctor` command that says which modes are really available.

---

# Which of these can be resolved

Added 2026-11-10. Sources: `docs/notes/Innovative idea review.md`, `docs/notes/Improvements-Concise.md`, `To-do-Concise.md`, `docs/logs/LOOP3.md`, `docs/logs/AUTOPILOT.md`, `docs/plans/FIVE_DAY_PLAN.md`, `docs/plans/LAUNCH_PLAN.md`, the result logs, and a short web search (links at the end). Nothing was run or measured for this section.

## How the rating was made

1 = cannot be resolved, 10 = very easy. Compute is treated as free (supercomputer). **Data is the scarce thing**, so the rating is mostly "can it be done with data already on disk, or with a small free download?" and "how many days of work?".

The project's own history gives a clear rule for what succeeds, and every fix below is picked to follow it:

- **Works here:** a simple statistical step placed after or beside the network (range calibration, Schaake shuffle, shear map, lapse map, 50:50 ridge mix, EWMA bias tracker, station-scale widening); fits with few free numbers on many years; real launch-day observations (radar +32 % aloft, a 1-hour-old wind report from the same spot -11 % on top of past mode); more training years (13 years +0.0050, 33 years +0.0277).
- **Fails here:** changing the network body; fits on few balloons with many free numbers; splitting calibration into small groups; site patches judged on pooled numbers; "better" high-resolution models used as truth (HRRR, WTK).

An honest note on "nearly 100 % chance": no experiment is certain. Below, an idea is marked **near-certain** only when (a) its core effect was already measured in this repo, or (b) it cannot be worse by construction (default off, or a weight that can fall back to zero). The size of the gain is still unknown until it is run on 2024-25.

## All ratings, easiest first

| # | Limitation | Rating | One-line reason |
|---|---|---|---|
| 5.2.16 | Spread is weather only | 9 | No data needed. Labels, docs and a default vehicle-dispersion harness; `montecarlo` already exists |
| 5.2.20 | External services and setup | 9 | Engineering only: archive inputs with a hash, a `doctor` command |
| 5.2.8 | Stops at 18 km | 8 | Design is written (A1), no retraining, data is 1-3 GB of ERA5 plus MERRA-2 (token in hand) |
| 5.2.14 | Forecast mode thinly tested | 7 | Ensemble features already confirmed on two seeds in both boxes; live verification only needs a logger and time |
| 5.2.17 | `observe()` unvalidated | 7 | Station pairs, one-minute ASOS and radar files are on disk; two numbers to fit |
| 5.2.19 | Upper-air T / RH | 7 | Two proven tools fit exactly (EWMA bias tracker, station-correction hybrid); balloons on disk |
| 5.2.5 | Ground wind 0-300 m | 6 | Four parts are easy and near-certain; the last part (the pad's own siting error) needs a pad record |
| 5.2.6 | Wind vs Gaussian baseline | 6 | Matching the baseline is near-certain; clearly beating it without launch-day data is limited by inputs |
| 5.2.18 | Two regions only | 6 | Compute-bound, not data-bound: global store and 6 new boxes are on disk; local recipe proven at Denver |
| 5.2.10 | Coarse grid aloft | 6 | Free 1-second US balloon data exists (a download); a detail layer after the network fits the "works here" rule |
| 5.2.1 | Downrange drift | 6 | Statistics are built; what is left is the simulator's wind interface (position, not altitude only) |
| 5.2.2 | Frozen snapshot | 6 | Same: hourly sequences are built; the simulator must accept time |
| 5.2.11 | Turbulence / gusts / thermals | 5 | Sodar data with vertical wind is on disk and unused; thermals have no truth data |
| 5.2.12 | Rare extremes | 5 | Aloft and near-ground gaps each have a measured partial fix; true 1-in-1000 events cannot be verified with this much data |
| 5.2.15 | Truth data thin | 5 | Radar, sodar, USCRN and one-minute data give new referees; a balloon at the pad at noon does not exist |
| 5.2.4 | Unseen sites | 5 | Same work as 5.2.18, plus a safe fallback |
| 5.2.9 | Trained on smoothed ERA5 | 4 | Inherent to the data source. Only the visible symptoms can be corrected (see 5.2.5, 5.2.10) |
| 5.2.7 | No proof on real flights | 3 | Needs in-box flights with GPS logs and pad weather. No amount of compute replaces them |
| 5.2.3 | Storms, microbursts | 3 | A storm-risk flag is easy; a microburst wind model has no training truth here |
| 5.2.13 | Climatology beyond 2 weeks | 2 | A limit of the atmosphere, not of the tool (measured skill zero past day 14-17). Only the labelling can be fixed |

Items rated 4 or below get no research section. Short notes for them: 5.2.9 is treated through 5.2.5 and 5.2.10; 5.2.7 improves only with data from the user (ASK_LATER 15); 5.2.3 could get a cheap CAPE-based "storm possible" flag from ERA5, nothing more; 5.2.13 needs a loud mode label in every output file and nothing else.

---

## 5.2.5 Ground wind: in-depth plan (rating 6, highest impact)

**What the logs already rule out** (do not repeat these):
- Extrapolating ERA5 50 / 100 / 200 m down with a log law does not beat raw ERA5 10 m (TCS 1.77-1.80 vs 1.73) [LOOP3 189].
- HRRR is no better than ERA5 at the independent USCRN station; its airport advantage is contamination. WTK is worse hour by hour (MAE 1.98 vs 1.65) [LOOP3 193, handover].
- Regime-dependent spread (P4), difference assimilation (P1), a terrain site model (P7), a Weibull head (W4): fail or neutral. The remaining gap is a property of each site.
- The calm gap (1.2 % vs 6.1 %) is in ERA5 itself, so no network change reaches it.

**What that leaves** is five ideas. They were corrected after the audit at the top of this file; the audit number is given where an idea changed.

### Idea 1. Make the launch-day wind report beat persistence (certain to measure, likely to fix)

- **What changed (audit B2, B3):** the weights are already fitted and the report is already fetched automatically (`observe_latest()`). The "41 %" was against climate mode. The honest numbers: the station's own 1-hour-old report improves past mode by 11 % (1.151 -> 1.021), and tool + `observe` still loses to a two-number persistence rule by 7-10 % (audit A1).
- **Work, step 1 (measure):** one script, `scripts/observe_vs_persistence.py`. Same hours for every rival. Rivals: tool alone, tool + `observe`, linear persistence, persistence scaled by the fitted distance gain. Cases: report from the scored station (TCS, MAF), and report from another station 20-150 km away (audit A3). Years 2024-25. CPU, 1 day.
- **Work, step 2 (fix, only if step 1 confirms the gap):** when the report is from the site and under 3 h old, take the 10 m speed distribution from the persistence law (mean and spread fitted by hour of day on 2015-22) and keep the pool's ranks and its profile above. Optional argument, default unchanged.
- **Kill rule:** tool + `observe` at or below persistence at both stations, 90 % coverage 0.86-0.92.
- **Not certain:** the pad has no station. The useful case is the airport 51 km away, where the gain is about half. Step 1 will say how much is left.

### Idea 2. Wind below 10 m at the rail (mostly built; small fix left)

- **What changed (audit B1):** the readers already bring the wind down to 0.72 x the 10 m wind at the ground. At 5 m the error is about 2 %. The earlier "12 % / 28 % too strong" was wrong.
- **What is left (audit A5):** a true log-law shape below 10 m using the sample's own roughness, as an optional argument. It matters only below about 3 m (2 m: 8 % too strong today, 1 m: 24 %). Also fix the stale docstring (A6).
- **Why near-certain:** textbook surface-layer physics, and the same factor was checked on real data: USCRN wind at 1.5 m scaled to 10 m (factor 1.48) lands between ERA5 and the airport [GW-C].
- **Work:** about 15 lines in each reader plus one test. Half a day. Low priority.
- **Not certain:** on calm stable nights the real profile is steeper than the log law. The Jornada 0.37-3 m masts would let us fit that.

### Idea 3. Use the five sodars on disk for the 30-200 m layer (measurement likely, fix uncertain)

- **What:** `data/raw/a2e/wfip1_sodar_*` holds five West / central Texas sodars: speed and direction every 10 m from 30 to 200 m, every 10 minutes, about 13 months each (2011-12). It is the only real truth on disk for the 50-150 m layer, which makes 53 % of the apogee spread.
- **What changed (audit B6, B7, A8):** the ERA5 on disk cannot be used (one hour per day, and no levels between 10 m and 100 m). The sodar sites are outside the trained box, so the tool itself cannot be scored there. The `W` column is a 10-minute mean and says nothing about turbulence. The time zone of the files must be confirmed first.
- **Step A (download, approved):** hourly ERA5 at the five sites, 2011-07 to 2012-09: 10 m and 100 m wind plus the lowest model levels (about 10, 30, 55, 80, 110, 140, 170, 205 m). Small.
- **Step B (referee):** ERA5 against sodar by local hour: speed ratio at 40 / 100 / 200 m, shear 50-150 m, night-jet height and strength.
- **Step C (fix, only if step B shows a gap that is the same at all five sites):** a rank-preserving shape map on the 30-200 m speed ratios per hour block, default off. If the gap differs by site, there is no general fix and this stops.
- **Not certain:** the sodars are 2011-12 and several hundred km east of Spaceport America. They test ERA5's low-level physics, not the pad.

### Idea 4. More real levels in the lowest 300 m (likely, supercomputer job)

- **What:** only six heights describe 0-300 m and most are interpolated from pressure levels. Add 20, 30, 40, 75, 125, 250 m from ERA5 model levels and retrain [IL-148].
- **What changed (audit B5):** model levels are **not** on disk. They need a CDS download for the box, 1991-2025 (approved; large, the lowest 10 levels are enough). The same download serves idea 3.
- **Cheap first check:** the 100 m wind (`u100`, `v100`) is already on disk. Check whether the height store uses it as a real level. If not, adding it costs nothing.
- **Why likely:** the same move one step earlier worked. Going from 13 to 21 source levels gave +0.0024 by day and +0.0056 at night [L3-45].
- **Not certain:** ERA5 model levels are still the smooth 31 km model. This sharpens the profile shape, not the siting error.

### Idea 5. One month of an anemometer at the pad (near-certain, parked: no pad data)

- **What:** every failed test points the same way: the last error is the site's own. One month of pad data with hour-of-day factors cut MAE by 21-25 % in the M6 test, and the site's own factors are the best case in P7 (-6.7 % CRPS). `Launch.calibrate_site()` is built and tested.
- **No fallback (audit B10):** the constant regional factor helps airports on average but hurts the two least airport-like sites (Monahans, PEQ). Do not apply it at a remote pad.

**Order:** 1 (measure first) -> past-mode spread (audit A2) -> 3 and 4 with the downloads -> 2 when convenient -> 5 when pad data exists. Honest expectation: without pad data the ground wind improves a little, not a lot. Ideas 3 and 4 are the only ones that can move what moves apogee.

---

## 5.2.6 Wind vs the Gaussian baseline: in-depth plan (rating 6, highest impact)

**Why the gap exists.** In climate mode the tool knows only the date, hour, place and a few climate indices. Given only that, wind at a point is close to unpredictable, so a well-fitted monthly mean and spread is already near the best possible. The model is input-limited (P-18). Network changes have failed to move this many times. The cells below the baseline are always the same: v at 5-12 km and 12-18 km in development, plus u at 1-12 km on the 2026 test, each by a small margin (about 0.003 skill, 3 % at worst).

So the fixes are: stop losing where there is nothing to win, win where there is information, and close the "real Earth-GRAM was never run" hole.

### Idea 1. A safe blend of the marginals (likely; never worse on the fit years only)

- **What:** for each variable and height band, pull the tool's marginal distribution toward the Gaussian baseline's by quantile averaging with one weight `w` (0 = today, 1 = baseline). Keep the tool's own ranks, so whole-profile coherence is untouched. This sits inside the range-calibration step, before the shuffle.
- **Why likely:** with the weight fitted on CRPS, the result cannot be worse than the better of the two on the fit years. On new years that is not guaranteed (audit B9), so it needs the paired test like any change. It is 19 numbers fitted on 18 years, which is the "few numbers, lots of data" pattern that has always held up here. The same idea already worked once: the 50:50 ridge mix (IL-80) and the column blend (IL-167, +0.0005 to +0.0013).
- **Trap respected:** never mix two sources of ranks (IL-161). Only the marginal values move.
- **Work:** `scripts/gauss_blend_fit.py` (fit 2005-2022, test 2024-25, paired seeds), then an optional asset key, default off. CPU, 1-2 days.
- **Kill rule:** every wind cell at or above the baseline within the paired tolerance (0.0009), no cell worse than today.
- **Honest limit:** this removes the "worse than a simple baseline" objection. It does not make climate-mode wind clearly better than the baseline. Nothing can, without new inputs.

### Idea 2. Show, and ship, the wind gain where information exists (near-certain, already measured)

- **What:** the tool's real wind advantage is that it can take in information a monthly table cannot. All of these are already measured: radar winds +32 % / +16 % / +7 % aloft (still +25 % from a radar 140 km away); past mode -11 % CRPS; forecast mode skill 0.69 at day 1; IFS-ensemble features a further -1.9 to -3.1 % in NM/TX and -1.2 to -2.2 % at Denver (two seeds, test year 2022 only, mostly from the ensemble mean); a 1-hour-old surface report from the same spot -11 % on top of past mode (not -41 %, audit B3).
- **Work:** (a) add a "launch-day" row to the headline table: tool + radar + surface report vs the Gaussian baseline, per wind cell, on 2024-25. (b) Make it a fair fight by also giving the baseline the same observations through the same Gaussian update (the code exists in `observe`), and add plain persistence as a rival at 10 m (audit A1). (c) Turn on the ensemble features as an opt-in (ASK_LATER 21 waits for the user).
- **Why near-certain:** every number above is on disk. Step (b) is new and is the honest part: the tool should still win there through its vertical structure, but that is not yet shown.

### Idea 3. Run the real Earth-GRAM once (near-certain to close the question)

- **What:** NASA's GRAM Suite (Earth-GRAM, version 2.1 from November 2024, with a Python API since 2.0) is requested through the NASA Software Catalog. Generate its dispersed profiles at the two balloon stations and score them with the same code as the stand-in.
- **Why it matters:** "we never ran the real thing" is the first question a reviewer will ask. The stand-in is fitted on local ERA5 per place and hour, so it is probably a harder rival than the real Earth-GRAM, whose climatology is global and coarser. That is likely, not certain.
- **Work:** the request is a user action (NASA account, release terms). Scoring is half a day once the software is here.

### Idea 4. Train on more wind data (likely, pure compute)

- **What:** the one training-side lever that always worked is more data: 13 years +0.0050, 23 years +0.0221, 33 years +0.0277, and a coarser lattice of points lost nothing [D1-D7]. The global store (7,483 points, 1991-2025) is complete on disk. The wind-specific loss term C4w was kept on two seeds (+0.0015 / +0.0032).
- **Work:** the G-stage training on the supercomputer, then the same per-cell baseline table. Wind cells are the gate.
- **Not certain:** gains have been monotone but may flatten before the wind cells turn positive.

### Idea 5. Score what a Gaussian table cannot do (likely)

- **What:** add the Gaussian baseline to the shape diagnostics (IL-45, G2-7): vertical correlation error, shear distribution, hour-to-hour change, co-extremes. A flight simulator feels these, and CRPS at single heights does not see them.
- **Not certain:** a Gaussian with a full covariance matrix does well on vertical correlation. The tool's edge should show in shear tails and time coherence. Run it before claiming it.

**Order:** 1 and 2 first (both CPU, both near-certain), 3 as soon as the software arrives, 4 with the global run, 5 alongside.

---

## 5.2.17 Launch-day observations: in-depth plan (rating 7, high impact)

### Idea 1. Validate `observe` the way it is used, and beat persistence (certain to measure)

Same work as ground-wind idea 1. The weights are already fitted (audit B2), so there is nothing to fit first. What is missing is the test: report from one station, score at another, against persistence (audit A1, A3). Coverage after `observe` is 0.81 (TCS) / 0.91 (MAF) today against a 0.90 target. Remove the "not yet validated" label only for the cases that pass (surface wind, age up to 3 h, distance up to the tested range).

### Idea 2. Measure the radar error from the data itself (near-certain)

`observe_radar` uses 3 m/s per level (taken from radar-minus-balloon differences, so it includes the balloon's own error) and treats the levels as independent (audit A4). The Desroziers method reads the real observation error from the differences "radar minus pool" and "radar minus updated pool", with no truth needed (review idea C4). Radar files are on disk (EPZ 611, FTG 485, HDX 127, MAF 133). Holloman is 75 km from the pad, closer than any balloon. Gain already measured with the assumed error: +32 % aloft. A correct error mostly fixes coverage (0.49 at radar levels in the review). CPU, 1 day.

### Idea 3. Take in the morning balloon (near-certain)

The sounding update is already validated on 100 held-out balloons: CRPS -6 to -20 % above the measured part, 90 % coverage 0.89-0.92 [Stage 6, module 2]. What is missing is the reader for a standard sounding file and the age handling (open item F5 / R2). About 1 day.

### Idea 4. Tell the user when an observation should not be trusted (near-certain)

The Prometheus case (+8.8 % -> +11.5 %) is what scares an engineer. Half of this exists: a report more than 4 standard deviations from the pool is already flagged (kept, not widened). What is left: widen instead of pinning in that case, and the same for a far or much higher station, and say so in `quality` (review items #13 and G2-2). The aim is "not worse than no observation"; that has to be shown in the test of idea 1, it is not automatic.

---

## 5.2.18 and 5.2.4 More regions: in-depth plan (ratings 6 and 5, high impact)

### Idea 1. Local packs for the six boxes already on disk (near-certain)

The local recipe has now worked twice: Denver went from -0.19 (borrowed model) to +0.0099 with its own training, and got full parity (forecast mode, vertical-wind head, correlation tables, gust law) within a day. Data for Vandenberg, Canaveral, Salt Lake, Lamont, Fairbanks and Hilo is in `data/raw/era5_g2_*`. With the supercomputer this is a batch job per box plus the standard checks. Limit: boxes without a balloon station get no balloon referee and no past mode.

### Idea 2. A safe answer everywhere instead of a refusal (near-certain)

`Launch.domain()` already answers inside / edge / outside with a box and elevation test, and outside is refused. What is left: outside the trained boxes, return the local Gaussian climatology from the global ERA5 store, labelled `domain: outside`, and replace the box test with the dissimilarity index from L3-28 (IL-150). Limit: the global store has one hour per day and 13 pressure levels, so this climatology has no real levels between 10 m and 100 m and a thin daily cycle. It is baseline-grade, not model-grade, but it is honest and it is what an engineer would otherwise build by hand. 35 of the 38 validation flights become runnable.

### Idea 3. The global model with a leave-one-box-out test (likely)

Train on the 7,483-point store and hold one box out at a time. The only proof of transfer that counts is a held-out box scoring above its own climatology. Evidence for: more data helped every time. Evidence against: one box could not teach place (spherical-harmonic test failed). Many boxes may; that is the open question.

---

## 5.2.12 Rare extremes: in-depth plan (rating 5, high impact)

First a correction that makes this smaller than it reads: the new tail score shows the 99th-percentile exceedance of the shipped model matches ERA5 at every height (10 m 0.0109 vs 0.0108) [IL-107]. The real gaps are against balloons: low-level shear p99 is 68 vs 100, and joint wind-shear extremes are 0.07 vs 0.17.

### Idea 1. Say that 0-1 km shear statistics need the turbulence step (documentation only)

Measured already: the profile alone has 0.82 / 0.66 / 0.46 of balloon shear at p50 / p90 / p99 in 0-1 km; with the default Dryden turbulence it is 1.08 / 1.12 / 0.88 [IL-164]. So for 0-1 km, "profile + turbulence" is the right thing to quote for shear and loads. Limits (audit B12): IL-164's own verdict was "no change"; above 1 km the turbulence adds nothing (idea 2 covers that); and the 2024-25 balloon shear in 0-1 km rose with an instrument change, so the target is not stable.

### Idea 2. Ship the balloon-fitted shear map aloft as an option (near-certain)

Measured: CRPS unchanged, p99 shear at 12-18 km 24.7 -> 29.1 (balloons 31.7), 5-12 km 19.2 -> 23.0 (balloons 24.6) [IL-103 log]. It was not adopted as a default because it changes shipped assets. As an opt-in "balloon-realistic shear" switch it is zero risk and directly answers a loads engineer.

### Idea 3. Check and fix the copula on the real pool (likely)

IL-128 was only run on a synthetic pool. Rerun it on a real conditioned pool. If tails move, select whole members by stratified sampling when unconditioned and apply the observation update as a residual on whole members. Also extend `_cdf` / `_ppf` past the pool minimum and maximum (IL-129). CPU, 1-2 days.

### Idea 4. Make the limits explicit

`Launch.stress()` and `montecarlo.run_importance` exist for tail probabilities. Document that 1-in-1000 values are extrapolations and report the effective sample size with them. Rating stays 5 because no dataset here can verify a 1-in-1000 event.

---

## Shorter fixes for the other items rated above 4

**5.2.16 Spread is weather only (9).** Mostly built (audit C): `Launch.trust` says it, and `examples/monte_carlo_quickstart.py` already uses default drag / impulse / mass dispersions (`montecarlo.VehiclePriors`). Left: check that saved output files carry the sentence, and say it in the README. Half a day.

**5.2.20 External services and setup (9).** `tempest doctor` already exists (audit C). Left: (a) save every fetched input (Open-Meteo members, METAR, radar file) next to the output with a hash; (b) make `doctor` list which modes work on this machine, if it does not already; (c) one offline bundle per campaign. 1 day.

**5.2.8 Stops at 18 km (8).** Build A1 as designed in `docs/plans/LAUNCH_PLAN.md`: ERA5 1-70 hPa to 48 km, MERRA-2 to 80 km, tied to each sample's own 12-18 km anomaly with the same Gaussian update `observe` uses, cosine blend over 18-20 km, 0-18 km bit-identical. Test: balloons at 18-30 km on 2024-25 against the standard-atmosphere hold, which it should beat easily since the hold has no season and no spread. Needs 1-3 GB of ERA5 and a few GB of MERRA-2 (downloads, ask first; the Earthdata token works until 2027-01-06). About 1 day of code. Limit: above 30 km there is no in-situ truth.

**5.2.14 Forecast mode thinly tested (7).** (a) Adopt the ensemble features as opt-in (confirmed twice). (b) Start the daily logger now so a live verification record builds itself (IL-78); every week of delay is a week of evidence lost. (c) Lead blending toward climate (IL-74) from `wb2_ifs_extended`, on disk. (d) A 0-18 h nowcast at 10 m is idea 1 of 5.2.5; today plain persistence wins there (audit A1). Limit: archived HRES ends January 2023, so 2024-25 scores need the logged record.

**5.2.19 Upper-air T and RH (7).** (a) T at 12-18 km: the target shifted around 2020. Use the EWMA bias tracker (IL-98 B, "never worse") on that band, or fit the band's calibration on the last 10-15 years (IL-121). (b) Until it beats climatology, blend the band toward the trend-aware climatology with one weight, the same safe-blend construction as 5.2.6 idea 1 (tested out of sample, audit B9). (c) RH at 12-18 km: the station-correction hybrid already cut CRPS 4.76 -> 3.70 (F-11); widen its range map to reach 0.99 coverage. CPU, 1-2 days.

**5.2.10 Coarse grid aloft (6).** Keep the 44 heights for the network. Add a detail layer after it: small-scale wind structure between the heights with the amplitude and vertical spectrum measured from 1-second US balloon data (NCEI "US Radiosonde BUFR High Resolution", free; download approved. Whether it includes El Paso / Santa Teresa and Midland was never verified: open the station list first, audit D). Review ideas G2-1 and C1 (wave law). The balloon shear map of 5.2.12 idea 2 already gives part of this with no new data.

**5.2.1 / 5.2.2 Downrange and time (6).** The statistics exist. The missing piece is in the simulator: a wind function of (altitude, downrange distance, time) instead of altitude only. Provide a small wind-object class the simulator can call (roadmap A3). Validate hour-to-hour change against 00Z / 12Z balloon pairs and one-minute ASOS. No new data.

**5.2.11 Turbulence, gusts, thermals (5).** (a) Withdrawn (audit B7): the sodar vertical wind is a 10-minute mean, so it cannot give turbulence strength. No turbulence truth is on disk. The 1-second balloons (5.2.10) give fine-scale wind scatter aloft; near the ground only a tower would do. Check that the site's roughness reaches the turbulence step (audit A7). (b) The one-minute gust law already works (unseen El Paso 0.70 vs 1.76); reuse it for the 10 m turbulence strength. (c) Put gust and vertical wind into the joint sampling. Thermals stay open: no truth data.

**5.2.15 Truth data thin (5).** New independent referees already on disk: radar wind profiles (any hour, including midday), five sodars (30-200 m), USCRN Monahans (non-airport), one-minute ASOS. Add the three-way referee C5 (triple collocation) so ERA5, balloon and radar errors are separated without calling any of them truth. Keep opening a fresh untouched window for each release. What cannot be fixed: no profile truth at the pad.

---

## What to do first

| Order | Work | Item | Cost | Confidence |
|---|---|---|---|---|
| 1 | `observe` against persistence, same hours, own station and distant station; then the persistence-law fix if the gap holds | 5.2.5, 5.2.17 (audit A1, A3) | 2 days | measurement certain, fix likely |
| 2 | Past-mode 10 m spread: test x1.2 with the anchor on, propose as default | 5.2.5 (audit A2) | half a day | likely |
| 3 | Start the downloads: ERA5 model levels (box, and the five sodar points), ERA5 1-70 hPa, MERRA-2; open the 1-second balloon station list | 5.2.5, 5.2.8, 5.2.10 | network | approved |
| 4 | Safe blend with the Gaussian marginals (wind cells, T 12-18 km) | 5.2.6, 5.2.19 | 2 days | likely |
| 5 | Launch-day row in the headline table, fair baseline and persistence included | 5.2.6 | 1 day | new comparison |
| 6 | 18-80 km extension (A1) | 5.2.8 | 1 day after the download | near-certain to 30 km |
| 7 | Sodar referee for 30-200 m (time zone first) | 5.2.5, 5.2.15 (audit A8, B6) | 2 days after the download | measurement likely, fix uncertain |
| 8 | Radar error and level correlation from data; morning balloon reader | 5.2.17 (audit A4) | 2 days | near-certain |
| 9 | Opt-in balloon shear map aloft; copula check on a real pool | 5.2.12 | 2 days | near-certain / unknown |
| 10 | Small items: log-law shape below 10 m, stale docstring, roughness into turbulence, labels in saved files, input archive, IL-192 id | audit A5-A7, A9; 5.2.16, 5.2.20 | 1-2 days | near-certain |
| 11 | Supercomputer: finer low levels (after step 3), local packs for six boxes, global model | 5.2.5, 5.2.6, 5.2.18 | compute | likely |

This table replaces the first version. Changes: the log-law step fell from first to "small items" (it was mostly built), the "fit the `observe` scales" step is gone (already fitted), and two real defects found by the audit (A1, A2) are now first.

**Update 2026-11-10 (user's answer):**
- **Approved:** the ERA5, MERRA-2 and 1-second balloon downloads (5.2.8, 5.2.10, and the ERA5 point pull for the sodar referee if needed).
- **Not available for now:** Earth-GRAM, pad data, GPS flight logs. So these are parked: 5.2.5 idea 5 (no fallback: the regional factor hurts non-airport sites, audit B10), 5.2.6 idea 3 (the report keeps saying the baseline is a stand-in), and all of 5.2.7. Nothing else in the order above depends on them.
- **Open, needs the user:** the free EDI account for the Jornada low masts (wind at 0.37 / 0.75 / 1.5 / 3 m). It would let us fit the wind shape below 10 m (audit A5), mostly for calm nights. Low priority now that the pad node exists. Steps are in `docs/agent/ASK_LATER.md` item 20.

## Outside sources used

- [GRAM Suite, NASA Software Catalog](https://software.nasa.gov/software/MFS-33888-1); [GRAM Suite 2025 poster (version 2.1.0, Python and MATLAB API)](https://ntrs.nasa.gov/api/citations/20250003621/downloads/GRAM%20Suite%202025%20Jamboree%20Poster.pdf); [Earth-GRAM 2026 User Guide](https://ntrs.nasa.gov/api/citations/20260004497/downloads/Earth-GRAM%202026%20User%20Guide.pdf)
- [NWS US Radiosonde BUFR High Resolution (1-second), NCEI](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C01630/html)
- [Probabilistic weather prediction with an analog ensemble (Delle Monache et al.)](https://opensky.library.ucar.edu/islandora/object/articles%3A12922)
- [NREL review: log and power laws cannot represent night low-level jets](https://nrel.gov/docs/fy20osti/78109.pdf); [Limits of Monin-Obukhov extrapolation under stable conditions](https://www.peeref.com/works/1477197)
- [ERA5 under-represents hourly wind variability at stations (Energy Reports 2023)](https://doaj.org/article/c2d7c314ea3f47d591acc7568e6b6f4c)
- [West Texas Mesonet](https://www.depts.ttu.edu/nwi/research/facilities/wtm); [NMSU ZiaMet](https://weather.nmsu.edu/); [WSMR surface data at NCAR EOL](https://data.ucar.edu/dataset/army-range-white-sands-missile-range-wsmr-surface-meteorological-data) (possible extra ground-wind truth; access terms not confirmed)
- Papers named in `docs/notes/Innovative idea review.md`: Desroziers 2005 (observation error from innovations), Houchi 2010 (balloon vs model shear), triple collocation, Schefzik (ensemble copula coupling).

---

## Status of the four earlier items (5.2.1 - 5.2.4)

- **5.2.1 Downrange drift: partly built.** `tempest_weather.api.atmosphere_downrange` returns linked columns along a bearing (default 0-60 km). But the link is a **statistical** distance correlation taken from ERA5, not physics: it knows nothing of coastlines or terrain, every point must lie inside the trained box, and the flight simulator's wind interface takes altitude only, so the simulator cannot use it yet.
- **5.2.2 Frozen snapshot: partly built.** Hourly sequences are tied together with a lag correlation (`tempest_weather/coherence.py`), so a sample can evolve hour to hour. It is hourly, not minute by minute, statistical (no sea-breeze front as an event), and again not consumed by the simulator during a descent.
- **5.2.3 Convective hazards: not addressed.** A `stress()` option draws rare storms / heat / freeze days from the existing distribution; there is no storm, microburst or lightning model.
- **5.2.4 Unseen sites: stronger than stated.** See 5.2.18: sites outside the two boxes are refused, and measured transfer between the two existing regions failed.
