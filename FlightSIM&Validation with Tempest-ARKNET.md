# FlightSIM & Validation with Tempest-ARKNET

Working log, started 2026-11-08. Question: **does replacing the flight simulator's standard atmosphere with Tempest-ARKNET's atmospheres bring the simulated apogee closer to the true measured apogee?** That is the end goal of the system: a more accurate overall flight simulator.

Everything below is written as the work happens; the last section is always the current verdict. Nothing here changes the flight simulator or the user's repo: the simulator code was copied into a deletable folder.

## 1. What the flight-sim branch contains

Local repo `C:\dev\flight_sim`, branch **JARVIS-TRUE-VALIDATION** (checked out; its `main` is older than GitHub's). The branch adds `validation/` ("fsval" harness) with **38 flights that have a measured apogee**: 23 development flights (RASAero's published validation set) and 15 held-out flights (RASAero `.alx1` files plus RocketPy's example flights, IREC / EuRoC / Spaceport America Cup entries).
Its own report (`validation/REPORT.md`, `validation/JARVIS-improvment-From-True-Validation.md`, 2026-11-01): the simulator (called JARVIS or FS there) **ties RASAero II on the development flights and is slightly worse on the held-out ones; the largest errors are shared by every tool and come from inputs none of them is given: real wind, real air, rail guides, as-flown weights and delivered impulse.** That is exactly the part Tempest-ARKNET can supply.

Their earlier "real weather" test (ERA5 profiles plus IGRA balloons) on the 10 flights with a known site and date (all in Nevada): signed error fell from +2.58 % to +0.26 %, the mean absolute error did not improve overall (6.75 % -> 6.98 %), better on 8 of 10 flights' tiers A and B, much worse on two accelerometer-truth flights (Qu8k, Proteus 6).

## 2. Where did each flight fly? (site, elevation, date)

Tempest-ARKNET's models are trained for **two boxes only**: NM/TX (31-34 N, 108-101 W, includes Spaceport America and Midland) and a Denver box (38-40 N, 106-104 W). A flight can only be served by the tool if it launched inside one of them. Sites below come from the files (filed launch elevation), from the branch's notes, and from web look-ups; items marked (?) are inferred and need a second source.

| Flight | Launch elevation (filed) | Site / event | Date | Inside the Tempest box? |
|---|---|---|---|---|
| Heart of Steel (Stanford SSI) | from IREC_Current.CDX1 | IREC, Spaceport America, NM | 2017-06-22 | **yes** (hour not known) |
| Prometheus (Western Univ., London ON) | 1401 m | Spaceport America Cup 2022, NM | 2022-06-24 09:17 local (the RocketPy notebook's `set_date` says 2023: a typo in their example, the flight card says 2022) | **yes** |
| Juno III (Projeto Jupiter, Univ. of Sao Paulo) | 1480 m (RocketPy notebook value; the pad is about 1401 m) | Spaceport America Cup 2023, NM | 2023-06-23 about 17:00 local | **yes** |
| Andromeda, Astra, Cavour, Genesis, Lince, Erebus | 150-160 m | EuRoC (Portugal) | not yet looked up | no |
| BellaLui | 407 m | ? (Europe) | ? | no |
| Valetudo | 668 m | ? | ? | no |
| PSAS Launch 10 | 1390 m | Pacific Northwest (?) | 2013 | no |
| CalIsp1-3 / CalIsp4-5 | 2302 / 2848 ft | California desert (?) | ? | no |
| Byrum, CancerDescending, EZI65-1, Gibb, IonDrive, Raven, Thunder&Lightning | 2750 ft | Jean dry lake NV, LDRS-26 | 2007-07-12..17 | no |
| Qu8k, DontDebate, Proteus 6, Full Metal Jacket 1/2, Kinsel P4935 | 3750 / 3933 ft | Black Rock desert NV | various | no |
| Blister, Rabia, Torrent (2400 ft), Rabia-ShortFinCan (3400 ft) | 2400-3400 ft | ? | ? | no (?) |
| EZI65Hist-1, Hubbub, McGarvey, L500Roc | 2848 ft / ? | ? | ? | no (?) |

**Consequence:** only three of the 38 flights (Heart of Steel, Prometheus, Juno III) can be flown through Tempest-ARKNET today. That is a very small test; any conclusion must say so. The other 35 would need the global extension of the tool (not built yet).

Elevation clues from the files: 2750 ft = Jean dry lake NV (the branch names it), 3750 / 3933 ft = Black Rock desert NV, 2302 / 2848 ft = a California desert site (CalIsp, not named in the files), 2400 / 3400 ft = not identified. The six EuRoC rockets and BellaLui / Valetudo / PSAS are in Europe, South America or the Pacific Northwest. None of these is inside either Tempest box, so the tool cannot serve them.

## 3. Method (what was run)

- **Code:** a copy of the branch (`git archive JARVIS-TRUE-VALIDATION`) in `flight_sim_trial/true_validation/` (deletable; untracked; own virtualenv). The branch was not modified; the user's repo was only read.
- **Rockets and true values:** the branch's own frozen setup (`sea_re2_po1_w0_linear`: sea-level drag table, built-in Reynolds correction, power-on table, linear nozzle), run folders copied from `validation/results/matrix`. I reproduced its published simulator numbers to the foot (Prometheus 13776.1 ft, Juno III 11117.0 ft, Heart of Steel 29663.6 ft). True value = the measured apogee in the branch's table, assumed above the pad (feet).
- **Location, date, hour (looked up):** Prometheus: Spaceport America Cup 2022, 24 June 2022 09:17 local (flight card in RocketPy's notebook; its `set_date` says 2023 by mistake). Juno III: Spaceport America Cup 2023, 23 June 2023 about 17:00 local. Heart of Steel: IREC 22 June 2017, hour not published, so a uniform 09:00-14:00 local window (flagged). Site: lat 32.939, lon -106.912, pad 1401 m, time zone America/Denver. The branch's Juno III run used pad 1480 m (the RocketPy notebook's number, which is the nearby airport, 79 m above the pad) and all of them used latitude 35 deg (a guess in the branch); the Tempest scenarios use the true latitude and pad.
- **Scenarios** (everything except the atmosphere and wind is identical):
  - **S0** the branch's own run (its filed air: ISA temperature for Prometheus and Juno III, 95 degF from the file for Heart of Steel; no wind or the file's wind).
  - **S1** a plain standard atmosphere at the true pad and latitude, no wind (the "basic standard atmosphere").
  - **S2** Tempest climate mode for that date and hour (the generator's distribution; 100 atmospheres).
  - **S3** Tempest **past** mode: ERA5 for that exact hour corrected to balloons (100 atmospheres). This is the mode that uses the real weather of the day.
  - **S4** S3 then conditioned on the surface temperature and 10 m wind actually measured that hour at the nearest ASOS station, Truth or Consequences (a proxy: 78 m higher than the pad and tens of km away; its temperature was moved to the pad with the standard lapse rate). This is the "adjust to the actual values at the time" mode (`Launch.observe`).
- **Tempest side:** `tempest_weather_v2.Launch` (pool of atmospheres, `observe`), generated in the project environment (`tempest_run/gen_atmospheres.py`), flown in the simulator's environment through the new `Atmosphere` reader (`tempest_run/fly.py`). ERA5 store: `data/pilot/profiles.zarr` via `TEMPEST_ERA5_STORE`. No 2026 or holdout data was read (the dates are 2017, 2022, 2023).

## 4. Results: apogee error vs the measured apogee (median of the 100 sampled atmospheres; the number after the plus-minus sign is the standard deviation in ft)

| flight | truth (ft) | S0 branch as filed | S1 standard air, true pad | S2 Tempest climate | S3 Tempest past | S4 past + measured values | RASAero | RocketPy (plain) |
|---|---|---|---|---|---|---|---|---|
| Prometheus | 12789 | 13776 (+7.7 %) | 13778 (+7.7 %) | 14248 (+11.4 %) ±233 | 13916 (+8.8 %) ±182 | 14211 (+11.1 %) ±68 | 13505 (+5.6 %) | 13840 (+8.2 %) |
| Juno III | 10541 | 11117 (+5.5 %) | 11065 (+5.0 %) | 11217 (+6.4 %) ±107 | 11033 (+4.7 %) ±89 | 10835 (+2.8 %) ±64 | 10914 (+3.5 %) | 11167 (+5.9 %) |
| Heart of Steel | 30411 | 29664 (-2.5 %) | 28667 (-5.7 %) | 29107 (-4.3 %) ±166 | 29210 (-4.0 %) ±162 | 29139 (-4.2 %) ±70 | 29964 (-1.5 %) | 28685 (-5.7 %) |

| scenario | mean abs error (3 flights) | mean signed error | flights closer than S0 |
|---|---|---|---|
| S0 branch as filed | 5.21 % | +3.57 % | - |
| S1 plain standard atmosphere, true pad, no wind | 6.15 % | +2.32 % | 1 of 3 |
| S2 Tempest climate | 7.37 % | +4.51 % | 0 of 3 |
| S3 Tempest past (ERA5 + balloons) | 5.81 % | +3.18 % | 1 of 3 |
| S4 Tempest past + measured surface values | 6.03 % | +3.24 % | 1 of 3 |

Reading it: S0 vs S3 is the question "does the real-weather mode beat what the simulator used before": **5.21 % -> 5.81 %**, no. Against the plain standard atmosphere at the true pad it is slightly closer (6.15 % -> 5.81 % past, 6.03 % past plus measured values). The Tempest climate mode alone is worse (7.37 %): a typical hot afternoon is thinner air than the standard day, and these simulations already read high.

Pad air and wind along the climb (mean over the sampled atmospheres): Prometheus: standard 5.9 degC / 1.069 kg/m3 / no wind, Tempest past 26.3 degC / 0.996 / up to 10 m/s; Juno III: standard 5.4 degC / 1.060 (branch) vs past 36.2 degC / 0.964 / up to 18 m/s; Heart of Steel: filed 35 degC / 0.968 vs past 34.2 degC / 0.968 / up to 12 m/s.

### Air versus wind (`tempest_run/decompose.py`, 40 atmospheres, past mode)

| flight | truth | standard air, no wind | Tempest air only | standard air + Tempest wind | Tempest air + wind |
|---|---|---|---|---|---|
| Prometheus | 12789 ft | 13778 (+7.7 %) | 14166 (+10.8 %) | 13501 (+5.6 %) | 13883 (+8.6 %) |
| Juno III | 10541 ft | 11065 (+5.0 %) | 11226 (+6.5 %) | 10881 (+3.2 %) | 11057 (+4.9 %) |
| Heart of Steel | 30411 ft | 28667 (-5.7 %) | 29244 (-3.8 %) | 28658 (-5.8 %) | 29225 (-3.9 %) |

- The real air (a 26-37 degC pad against the standard 6 degC at 1400 m, density 0.96-1.00 against 1.07 kg/m3) raises apogee by **1.5-3.1 %**; the real wind (8-19 m/s aloft on those days) lowers it by **about 2 %**. They partly cancel, so the net change is small. Both signs are physically right.
- **For Prometheus and Juno III the simulator already reads 5-8 % high with standard air, and RASAero (+5.6 %, +3.5 %) and RocketPy (+8.2 %, +5.9 %) read high too.** Tempest's more realistic air does not remove that, because it comes from elsewhere (drag, as-flown mass, impulse, rail guides, as the branch's own report concludes). The Tempest atmosphere effect (about 3 % each way) is smaller than that shared error, so with three flights it cannot show a gain.

## 5. Do the Tempest results make sense?

- **Past-mode air matches an independent reanalysis.** RocketPy's own notebooks print the reanalysis surface values for these launches: Prometheus 26.8 degC, 862 hPa, 0.2 m/s; Juno III 33.8 degC, 850 hPa, 10.8 m/s from 244 deg. Tempest past mode gave Prometheus 26.3 degC, 861.7 hPa, light wind and Juno III 36.2 degC, 858 hPa, 8-9 m/s from the west-southwest. Heart of Steel: 34.2 degC against the 35 degC filed in the team's own file. Same weather, to within the expected difference between a reanalysis and a balloon-corrected product.
- **The simulator responds correctly to the air** (hotter, thinner air: higher apogee; wind: lower apogee), matching the earlier flight-sim trial (apogee vs pad air density correlation -0.8).
- **Consistent with the branch's own "real weather" finding** (ERA5 + balloons on ten Nevada flights): the signed error moves toward zero but the mean absolute error does not improve, because the remaining error is not in the air.

## 6. Is the "adjust to actual values" mode built right?

Yes, in two forms, both exercised here end to end:
1. **`past` mode:** ERA5 for the exact hour, corrected to balloons. Works for any date 1990-2025 inside the NM/TX box once the ERA5 profile store is configured. *Flaw found and fixed during this work:* without the store path the tool silently returned the climate estimate. `Launch` now has `era5_store=`, warns loudly ("fell back to the climate generator") and says so in the trust line.
2. **`Launch.observe(wind_10m=, wind_from_deg=, temperature=)`:** conditions the whole atmosphere on launch-day measurements (Schur-complement update: the observed values are pinned and the rest moves with the learned vertical correlations). Here it was fed the ASOS values. **Limits:** it takes only 10 m wind, direction and 2 m temperature (not pressure yet, not a morning balloon: `sounding="auto"` is the R2 module, not built), and it is marked "not yet validated". Result: for Juno III it brought the apogee error from +4.7 % to +2.8 %; for Prometheus and Heart of Steel it changed little (+8.8 % -> +11.1 %, -4.0 % -> -4.2 %). Three flights and a proxy station: no conclusion.

## 7. Flaws and limits found

1. **Coverage is the main limit.** 35 of the 38 flights in the branch are outside the two trained boxes, so this validation set cannot be used at scale until the global extension exists. Only three flights are testable today.
2. **Three flights cannot show an accuracy difference.** The branch's own estimate is about 140 flights to resolve a 0.35-point gap; the atmosphere effect here is about 3 points per flight but with both signs.
3. **The largest error is not the air.** For these rockets the simulator's over-prediction (5-8 %) is two to three times the whole air-and-wind effect. Making the air more accurate cannot fix it; the aerodynamic, mass and impulse inputs (and rail guides) need to improve first. This is the main finding for the overall goal.
4. **Hidden inputs.** Heart of Steel's launch hour is unknown; Prometheus's flight card and notebook disagree on the year; Juno III's pad elevation is wrong in the notebook by 79 m (it changes apogee by about 0.5 %); the truth is assumed to be above the pad and the sensors differ.
5. **The surface-value proxy is weak.** ASOS at Truth or Consequences is not at the pad. IREC publishes its own weather observations, which would be the right values to feed `observe`.
6. **`observe` is limited** (no pressure, no sounding), and **past mode needed manual setup**; fixed by `era5_store` and the loud fallback warning (in `tempest_weather_v2`).
7. **A pad elevation error matters in the simulator.** The branch's Juno III run used 1480 m; the real pad is about 1401 m. The new elevation lookup (Section 2C) exists for exactly this.

## 8. Verdict so far

On the three in-domain flights, replacing the standard atmosphere with Tempest-ARKNET's real-day atmospheres **did not make the flight simulator measurably more accurate** (mean absolute error 5.21 % as filed vs 5.81 % past mode, 6.03 % past plus measured values; against a plain standard day 6.15 %). It did make the inputs physically correct and moved the signed bias slightly (+3.6 % to +3.2 %). The reason is that the simulator's error on these rockets is dominated by things the atmosphere does not control. The honest statement of the end goal: the atmosphere is now the better-known input; the next accuracy gains for the whole system must come from the rocket side, and a decisive test needs many more in-domain flights with documented inputs (for example Spaceport America Cup rockets with published designs and official apogees) and, for the other flights, the global extension.

## 9. Why did Prometheus move so much? (follow-up 2026-11-08)

Prometheus went from +7.7 % (standard air) to +8.8 % (Tempest past), +11.4 % (climate) and +11.1 % (past + measured values). Four separate things explain it, each checked:

1. **The standard air was the wrong air, and the right air makes this rocket's error larger, not smaller.** The branch's Prometheus run used the standard-day temperature at 1401 m (5.9 degC). On 24 June 2022 at 09:17 the real surface was about 26 degC. Thinner air (density 0.996 against 1.069 kg/m3) raises the apogee by **+3.1 %** (decomposition table: 13778 -> 14166 ft with no wind). The simulator was already reading high, so the correct air moves it further from the measured 12789 ft.
2. **The simulator reads high for reasons outside the atmosphere.** RocketPy's own published run for this very flight, using the reanalysis weather of the day, also over-predicts: 4190 m simulated against 3898 m official (+7.5 %). Our past-mode run, +8.8 %, is in the same place. Two independent tools with real weather land at +7.5 % and +8.8 %: the shared error is in the rocket inputs (drag, mass, impulse, rail guides), not the air.
3. **Only the wind in the lowest 200 m matters for Prometheus's apogee** (`tempest_run/why_prometheus.py`, past-mode atmospheres, median of 25 flights):

   | wind change | apogee error |
   |---|---|
   | as generated | +8.8 % |
   | calm below 200 m, rest unchanged | +10.6 % |
   | below 200 m x 0.3 | +10.0 % |
   | below 200 m x 2 | +7.2 % |
   | no wind above 200 m, ground wind unchanged | +8.9 % |
   | no wind at all | +10.8 % |

   The rocket leaves a 5 m rail slowly, so a crosswind there tips it into the wind (weathercocking) and costs altitude. Everything above 200 m is irrelevant for this rocket's apogee.
4. **That is why the "measured values" run (S4) went up 2.3 %.** The Truth or Consequences ASOS station reported a near-calm (0.9 m/s) at 09:17; conditioning on it pinned the 10 m wind to 0.9 m/s instead of the 3.2 m/s of the unconditioned past mode, and the air was 2.6 K cooler (which alone would lower apogee about 0.4 %). Light wind at the rail wins: +8.8 % -> +11.1 %. The conditioning did exactly what it was told; the *measurement* (a station tens of km away, 78 m higher, one hourly report) is a poor stand-in for the pad's rail-exit wind.

The climate run (+11.4 %) is the same story: a typical hot morning (28.8 degC) is thin air with a spread of 233 ft (standard deviation) from the wind draws.

## 10. Is the tool actually useful? And how to make it more useful

**What this test says, plainly.** For *apogee*, the atmosphere is a second-order input: about 3 % from temperature and density, about 2 % from the ground wind at the rail, 0.5-1 % scatter from everything else it models. The simulators' own errors on these rockets are 5-8 %. So today Tempest-ARKNET cannot be shown to make the apogee more accurate, and with three flights that was never going to be shown either way. Where it is clearly useful already:
- **It removes a systematic bias.** A standard-day run for a hot New Mexico afternoon is 3 % high on apogee from the air alone (28 K too cold at the pad). The tool gives the real day's air (past mode) or the typical air for a planned date (climate mode), checked against balloons and against an independent reanalysis.
- **It gives uncertainty, not one number:** a pool of coherent atmospheres (density, wind, shear, jet) for Monte Carlo of landing dispersion, rail-exit wind, shear loads and recovery drift, which a single standard atmosphere cannot do. Those quantities depend on the wind much more than apogee does, and the true landing positions needed to prove it are not in this validation set.
- **It speaks the users' formats:** RASAero and OpenRocket launch inputs (altimeter setting, drift-equivalent wind), OpenRocket profile CSV, a drop-in reader for the flight simulator.

**What would make it more useful (ordered by the evidence above):**
1. **Get the ground wind right (0-200 m).** It is the one atmospheric input that moves apogee as much as the air. The tool's wind spread was 15-25 % too narrow against balloons (IL-144), and the 10 m wind has the least skill. Work: wind-spread calibration at the lowest levels, and a station-aware near-surface wind (the pad's own anemometer, IREC on-site weather, nearby mesonet stations) instead of a distant airport.
2. **A launch-day mode that takes real observations easily.** `observe()` works but needs typed numbers. Add `observe_metar("KTCS 241553Z 19002KT ... 23/12 A3012")` (METAR parser; built next), a one-command live fetch of the nearest METAR / mesonet reading and the morning sounding (R2), and put the observation's age and distance in the trust line.
3. **Coverage.** 35 of the 38 flights in your validation set are outside the two trained boxes. Nothing else matters as much for using it on your real flights. The global extension (G stages, on the supercomputer) is the prerequisite for a meaningful validation.
4. **A plug-in for the simulator and EDITH.** `Launch.atmospheres()` already returns drop-in readers, but your sim and the EDITH dispersion framework are driven by TOML. A small adapter class (`type = "tempest_weather_v2...TempestAtmosphere"` with a `.tempest` file and an index) and a `couple()` bridge for EDITH's dispersion classes would let a Monte Carlo draw its atmospheres from the tool with no code.
5. **Tell the user which inputs matter for their rocket.** The sensitivity table above (3 % per 20 K, 2 % per 3 m/s of ground wind for a 14 kg, 5 m-rail rocket) is exactly what a user needs to decide whether the weather is worth refining. A documented recipe, or a helper that flies the user's sim at a few perturbations, would turn the tool from "numbers" into "decisions".
6. **Test the forecast mode, the real use case.** Everything here used the real day's analysis. A launch team decides days ahead; the test that matters is "atmosphere forecast 1-5 days ahead vs standard day, scored on the apogee". It needs archived forecasts for the flight dates (Open-Meteo's historical forecast archive covers recent years) and more flights.
7. **More in-domain flights with published designs.** Spaceport America Cup teams publish designs and official apogees every year; Midland-area launches too. 20-30 flights would resolve effects of 1-3 %.

## 11. Files

`flight_sim_trial/true_validation/` (deletable): the branch copy, `tempest_run/gen_atmospheres.py`, `fly.py`, `decompose.py`, `analyze.py`, `inputs/` (atmospheres per flight and scenario), `flights.csv` (every flight), `summary.md`. Reproduce: step A in the project venv with `TEMPEST_ERA5_STORE=data/pilot/profiles.zarr`, then `fly.py`, `decompose.py`, `analyze.py`.
