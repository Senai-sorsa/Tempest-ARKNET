# JARVIS improvements from True Validation

Results from branch `JARVIS-TRUE-VALIDATION`, as of 2026-11-01. The final results section replaces the earlier conclusions. "How to redo and implement everything" comes next. The sections after it keep the history, so where they mention `surface_re1_po1_w0_linear_fc`, that is the older setup.

## Final results

**JARVIS ties RASAero II on the 23 development flights and is slightly worse on the 15 held-out flights. It has not been shown to be more accurate than RAS.** The recommended setup stays `sea_re2_po1_w0_linear_fc`: sea-level table, built-in Reynolds correction, power-on table, linear nozzle, fin can reference. No other setup in the matrix beat it by more than the noise.

Error is mean absolute percent error, then median, then mean signed error.

| Flights | RAS | RocketPy, plain | RocketPy, helped | JARVIS frozen |
|---|---|---|---|---|
| Development, 23 | 5.41 / 4.67 / +1.76 | 6.30 / 6.02 / +1.43 | 5.54 / 5.22 / +1.80 | 5.49 / 5.78 / +1.19 |
| Development above 20,000 ft, 7 | 5.23 / 4.19 / +2.49 | 7.94 / 6.72 / +2.98 | 5.08 / 4.39 / +1.93 | 5.57 / 6.10 / +0.35 |
| Held-out, 15 | 11.11 / 7.54 / +10.48 | 11.99 / 8.22 / +11.04 | 11.52 / 7.90 / +11.01 | 11.78 / 7.82 / +11.26 |
| All, 38 | 7.66 / 6.07 / +5.20 | 8.55 / 7.46 / +5.22 | 7.90 / 6.65 / +5.44 | 7.97 / 6.69 / +5.17 |

| Flights | JARVIS minus RAS, mean error [95 %] | Closer than RAS | JARVIS minus plain RocketPy [95 %] | Closer than plain RocketPy |
|---|---|---|---|---|
| Development, 23 | [−0.41, +0.63] | 15 | [−2.40, +0.63] | 14 |
| Above 20,000 ft, 7 | [−1.13, +2.05] | 4 | [−6.40, +1.57] | 5 |
| Held-out, 15 | [+0.20, +1.10] | 4 | [−1.49, +1.33] | 10 |
| All, 38 | [−0.05, +0.69] | 19 | [−1.67, +0.47] | 24 |

- **Plain RocketPy** is what an ordinary user would get: body diameter reference, standard atmosphere, no wind, no nose or fin objects, and default nozzle behaviour. Its code was not changed; only the flight list was.
- **Helped RocketPy** used the fin can reference, the site's air, wind, and nose and fin objects. It went from 6.30 % to 5.54 % on development flights, and from 7.94 % to 5.08 % above 20,000 ft.
- **The inputs matter more than the simulator.** Given the same fixes, RocketPy matches JARVIS within about 0.1 % on many held-out flights and scores about the same. That agreement between two independent integrators is good evidence that JARVIS's flight mechanics are sound.
- **The held-out result is weak.** All four tools read about 11 % high because those flights assume standard air, no real wind and no rail guides. RAS's lead there is statistically real, but it comes from a set that was seen before this matrix.

### Which setup is best

The matrix flew 720 setups over 38 flights. That is 27,360 cells and 5,550 real flights after removing duplicates, with no failures.

| One change from the frozen setup | Development change | 95 % range | Held-out mean error (frozen 11.78) |
|---|---|---|---|
| Altitude drag surface | −0.08 | [−0.24, +0.05] | 11.75 |
| Constant gravity (diagnostic only) | +0.02 | [−0.02, +0.07] | 11.81 |
| Reynolds correction off | +0.06 | [−0.50, +0.58] | 11.99 |
| 1/7 wind | +0.07 | [−0.12, +0.29] | 11.99 |
| Kalt-Badal nozzle | +0.12 | [−0.04, +0.33] | 11.27 |
| RAS power-on change in base drag model | +0.29 | [+0.03, +0.55] | 11.94 |
| Mid-altitude table | +0.33 | [−0.76, +1.68] | 11.66 |
| Power-off drag only | +0.35 | [−0.42, +1.31] | 11.60 |
| No nozzle exit area | +0.68 | [−0.24, +1.82] | 9.98 |
| Blended base drag | +0.78 | [−0.17, +1.68] | 15.60 |
| Body diameter reference | +0.89 | [−0.57, +2.66] | 11.96 |
| AP02 base drag | +5.62 | [+1.62, +10.04] | 12.43 |

- **The top setup is not reliably better.** `surface_re2_po1_w0_linear_fc` scored 5.41 % against 5.49 % for the frozen setup, a gap within the noise. About two thirds of that win comes from one flight, DontDebate.
- **Picking the best setup does not carry over.** With leave-one-flight-out selection, picking the best setup scores 6.14 % against 5.49 % for the frozen setup, range [−0.06, +1.83]. The winner changes with the flights left out.
- **Only two changes are clearly different, and both are worse:** AP02 base drag and RAS's power-on change in the base drag model.
- **Reynolds barely changes mean error.** It does cut the bias above 20,000 ft from +2.44 % to +0.35 %.
- **Removing the nozzle exit area looks better on held-out flights.** It is probably cancelling the shared high bias, because it lowers thrust. It is worse on development flights and should not be chosen.

### Run time

Each flight was run one at a time for the same 38 flights.

| Simulator | Total | Median per flight | Slowest flight |
|---|---|---|---|
| RAS | 11.2 s | 0.045 s | 5.81 s |
| JARVIS, warm flight server | 15.8 s | 0.362 s | 1.93 s |
| RocketPy, helped | 10.3 s | 0.244 s | 0.84 s |
| RocketPy, plain | 2.68 s | not recorded | 0.11 s |

- A fresh JARVIS process takes 1.91 s for one flight.
- Plain RocketPy is fast because it has no aero surfaces.
- RAS's time covers only the fly call, not loading the file. JARVIS's time includes building the case and writing its table, so the comparison slightly favours RAS.
- The matrix ran at 13.7 flights/s on 20 threads and 11.0 to 11.5 flights/s on 10.

### What is left

The largest errors are shared by every tool. JARVIS and RAS correlate at about 0.97 on the development flights, so their errors come mainly from what none of them is given: real wind, real air, rail guides, as-flown weights and delivered impulse. Better inputs are likely to gain more than further physics. Showing a small accuracy gap would also need many more flights, about 140 for a gap of 0.35 points.

### Faults and limits

- **Matrix bug, fixed:** fin can runs kept the centre of pressure in body calibers after the reference changed, which moved it aft. 764 fin can runs were deleted and reflown, along with 23 stale Reynolds runs.
- `weather_run` still has that old behaviour, and its cached fin can results were not reflown.
- The first RocketPy numbers were overwritten by the helped run. The plain numbers here come from a rerun of the original fly code.
- Held-out flights were seen before this matrix, so they are reported but not used for selection.

## How to redo and implement everything

This section lets you repeat the final trials by hand: RAS in its own window, FS from one command, RocketPy from one short script, and the statistics in a spreadsheet. It covers only the final 38-flight comparison. JARVIS and FS are the same program here.

**What was checked:** all 38 FS runs were repeated with the plain command below, and every result matched to 0.0 ft. The RocketPy script matched DontDebate exactly (67,470.665 ft). The statistics in Step 5 reproduce the tables above. **I can't click through RAS's window, so nobody has yet run the RAS steps as written.** The button names were checked against the labels inside the program, and its engine matched the RAS window within 0.19 ft on 10 flights on 2026-09-16.

### What we used

| Item | Used |
|---|---|
| RAS | RASAero II 1.0.2.0 |
| FS | Branch `JARVIS-TRUE-VALIDATION`, Python 3.11, **plus the uncommitted Reynolds change** in `src/flight_sim/vehicle/reynolds_correction.py` |
| RocketPy | 1.13.0, Python 3.12, in `validation/.venv` |
| Flights | 23 development and 15 held-out, all with published apogees and none from our team |
| Aero data | RAS's tables, for all three simulators. This does not test FS as a drag predictor |
| FS setup | `sea_re2_po1_w0_linear_fc`, frozen before scoring new flights |

What the frozen setup means:

| Setting | Value |
|---|---|
| Drag table | RAS's sea-level table |
| Altitude drag | Built-in Reynolds correction |
| During burn | RAS's power-on drag |
| Wind | The filed speed, constant with height |
| Nozzle | Exit area with pressure thrust, where the exit is known |
| Gravity | WGS84 |
| Reference diameter | The fin can's, where it is wider than the body |

Each flight uses one saved folder:

| Flight | Folder |
|---|---|
| Blister, DontDebate, both Full Metal Jackets, Kinsel, Rabia-ShortFinCan, Rabia, Torrent, Hubbub | `sea_re2_po1_w0_linear_fc` |
| Byrum, CancerDescending, EZI65-1, Gibb, IonDrive, Raven, Thunder&Lightning, McGarvey, Genesis, PSASLaunch10 (exit 0) | `sea_re2_po1_w0_none` |
| All others | `sea_re2_po1_w0_linear` |

**Flights left out:**

| Flight | Why |
|---|---|
| Valkyrie | RAS flight error |
| NDRT2020 | Transition format could not be read |
| LOC2P1-1, LOC2P1-2, EZI65Hist-2 | J125 Hist motor has only 0.0016 kg of propellant in its file |
| Camoes | Air brakes |
| Hedy | Liquid motor |
| Defiance, Halcyon | Hybrid motors |
| AeroPac104K | Two stages |
| Stanford test flights | Could not tell which row was flown |

**Keep a copy of `validation/results/`.** Git ignores it, along with `validation/data/` and `validation/third_party/`, so a fresh clone won't have the saved folders. The tables here are enough to rebuild the settings and geometry. The thrust curves for the X motors are in `results/extra/designs/rocketpy.eng`, and the tool's `fsval.extra` step writes them again.

### Step 1: Write down the truth

The Truth column in the results table below is the measured apogee in feet above ground. Rounded values are fine by hand. `validation/results/final_flights.csv` holds them to 3 decimals, with every simulator's result.

| Flights | Where the truth comes from |
|---|---|
| Development | The comments in each RAS file. Lines containing "predict" are skipped |
| Held-out | Published values, listed in `validation/src/fsval/extra.py` |
| PSAS Launch 10 | Mean of TeleMetrum 15,091.3 ft and ARTS 15,484.9 ft |
| Heart of Steel | Strato altimeter, 30,411 ft above ground, 2017-06-22 |

Never change a truth value or a setting because of the error it gives.

### Step 2: Run RAS by hand

**RAS version:** the demo allows 5 simulations, has no export and stops at Mach 3, so the full version is needed for all 38 flights. Licence state on this machine is unknown.

1. Install `RASAero II Setup Version 1.0.2.0.msi`.
2. Open the flight's file with **File > Open** (`*.CDX1`):

   | Flights | File |
   |---|---|
   | Development | `~/Rocket-Profile-Analysis/vendor/rasaero/examples/<name>.CDX1` |
   | Held-out | `validation/results/extra/designs/<name>.CDX1` |
   | Heart of Steel | `validation/data/ssi/IREC_Current.CDX1`, first simulation row |

3. Open **Flight Simulation**, then **Select Motor File** and load `vendor/rasaero/rasp.eng`. For motors named `X… (RPY)`, also load `validation/results/extra/designs/rocketpy.eng`.
4. Check every box against the settings table below:

   | RAS box | Table column |
   |---|---|
   | `Sustainer Motor` | Motor |
   | `Weight (lb)` | Launch wt lb |
   | `CG (in)` | CG in |
   | `Nozzle Exit Diameter (in)` | Nozzle exit in |
   | `Temperature (deg F)` | Temp F |
   | `Launch Site Barometric Pressure (in-hg)` | Pressure inHg. **0 means leave the file's value alone** |
   | `Launch Site Elevation (ft)` | Elev ft |
   | `Wind Speed (mph)` | Wind mph |
   | `Launch Rail Length (ft)` | Rail ft |
   | `Launch Angle - degrees from Vertical` | Rail angle deg |
   | `Surface Finish` | Surface |
   | `All Turbulent Flow` | Turb |

5. Click **Rerun All Simulations**. Each development file has one row. Heart of Steel has 7, so use the first.
6. Open **View Data** and read the maximum altitude above ground. Write it in the RAS column.

**Expected:** the RAS column below. The altitude saved in all 23 development files already rounds to that column. The held-out files have no saved result, so they must be run. Heart of Steel's saved 30,005.98 ft is out of date, so use the rerun; ours was 29,964 ft.

**Rebuilding a held-out rocket:** only needed if its file is lost. Use **Add Nose Cone**, **Add a Body Tube Section**, **Add a Fin Canister** and **Add a Boattail**, in the order listed under "Geometry of the held-out rockets". The inputs we assumed for the RocketPy flights were 5 mm rounded fins, Smooth Paint, standard air (59 − 3.566 × elevation in ft / 1000 °F), no wind and no rail guides. A nozzle exit above 85 % of the base was dropped, which affected Genesis. PSAS gave no nozzle size, weighed 33.742 kg, and its canards weren't modelled.

**Exporting the aero table for FS:** only needed for a rebuild, because each saved folder already has `aero.csv`. Use **Aero Plots > Export > To CSV File**:

| Setting | Value |
|---|---|
| Stage | Sustainer |
| Altitude | 0 |
| Mach | 0.01 to 5, step 0.01 |
| Alpha | 0, 2 and 4 |
| Nozzle | The flight's exit diameter |

You should get 1,500 rows plus a header. The header must read:

`Mach,Alpha,CD,CD Power-Off,CD Power-On,CA Power-Off,CA Power-On,CL,CN,CN Potential,CN Viscous,CNalpha (0 to 4 deg) (per rad),CP,CP (0 to 4 deg),Reynolds Number`

The saved exports are `results/ras_cases/<case>/ras_aero.csv` and `results/extra/<case>/ras_aero.csv`.

### Settings for each rocket

Sizes are in inches. FS ref dia is the wider of body and fin can.

| Flight | Motor | Launch wt lb | CG in | Nozzle exit in | Temp F | Pressure inHg | Elev ft | Wind mph | Rail ft | Rail angle deg | Surface | Turb | Body dia in | FS ref dia in | Length in |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Blister | K1075GG (AMW) | 17.81 | 55.25 | 1.3125 | 80 | 30.05 | 2400 | 8 | 10 | 0 | Smooth (Zero Roughness) | No | 3.0000 | 3.1250 | 94.6250 |
| Byrum | J570W (AT) | 7.75 | 56 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 3.0000 | 3.0000 | 84.7500 |
| CalIsp1 | I205 (CTI) | 3.41 | 40 | 0.63 | 77 | 0 | 2302 | 0 | 10 | 3 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 59.2500 |
| CalIsp2 | I205 (CTI) | 3.25 | 40 | 0.63 | 78 | 0 | 2302 | 0 | 10 | 3 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 59.2500 |
| CalIsp3 | I205 (CTI) | 3.4 | 40 | 0.63 | 76 | 0 | 2302 | 0 | 10 | 3 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 59.2500 |
| CalIsp4 | I285 (CTI) | 3.36 | 40 | 0.63 | 62 | 0 | 2848 | 0 | 10 | 3 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 59.2500 |
| CalIsp5 | I285 (CTI) | 3.55 | 40 | 0.63 | 64 | 0 | 2848 | 0 | 10 | 3 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 59.2500 |
| CancerDescending | M1297W (AT) | 49.84 | 74 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 6.0000 | 6.0000 | 109.0000 |
| DontDebateThisN5800MinDia | N5800-CS (CTI) | 48.19 | 64.69 | 2.488 | 80 | 0 | 3750 | 5 | 10 | 2 | Smooth Paint | Yes | 3.9173 | 4.1500 | 98.2500 |
| EZI65-1 | J450ST (AMW) | 10.06 | 59 | 0 | 70 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 4.0000 | 4.0000 | 85.0000 |
| Full Metal Jacket1 | O10000 (Hist) | 70 | 86 | 2.5 | 80 | 0 | 3933 | 0 | 12 | 0 | Smooth (Zero Roughness) | No | 4.0000 | 4.2500 | 132.3125 |
| Full Metal Jacket2 | O10000 (Hist) | 65 | 85 | 2.5 | 80 | 0 | 3933 | 0 | 12 | 0 | Smooth (Zero Roughness) | No | 4.0000 | 4.2500 | 123.5625 |
| Gibb | I284W (AT) | 6.16 | 50.5 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 3.0000 | 3.0000 | 70.7500 |
| IonDrive | K550W (AT) | 11.37 | 39.5 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 4.0000 | 4.0000 | 70.0000 |
| Kinsel_P4935_A-601_Rocket | P4935 (LR-EX) | 154.46 | 113.2 | 3.09 | 80 | 0 | 3933 | 0 | 14 | 0 | Smooth Paint | Yes | 6.1250 | 6.5000 | 169.0000 |
| L500Roc | L500 (Hist) | 8.5 | 42.6 | 1 | 80 | 0 | 2848 | 0 | 8 | 0 | Smooth (Zero Roughness) | No | 2.2600 | 2.2600 | 62.0000 |
| Proteus6 | P9381 (LR-EX) | 186.7 | 111 | 4.8 | 80 | 0 | 3933 | 0 | 18 | 2 | Smooth (Zero Roughness) | No | 6.0000 | 6.0000 | 171.0000 |
| Qu8k | Q18000 (DEAP-EX) | 314.5 | 110 | 6 | 80 | 0 | 3750 | 0 | 16 | 2 | Smooth Paint | Yes | 8.3750 | 8.3750 | 167.1000 |
| Rabia-ShortFinCan | L730 (CTI) | 17.68 | 51.75 | 1.187 | 85 | 29.92 | 3400 | 14 | 10 | 0 | Smooth (Zero Roughness) | No | 3.1260 | 3.1900 | 97.2500 |
| Rabia | L1080BB (AMW) | 18.44 | 61.5 | 1.188 | 80 | 30.05 | 2400 | 8 | 10 | 0 | Smooth (Zero Roughness) | No | 3.0000 | 3.1250 | 111.7500 |
| Raven | J570W (AT) | 5.44 | 54.9 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 1.7500 | 1.7500 | 73.5000 |
| Thunder&Lightning | I284W (AT) | 6.17 | 51.5 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 3.1000 | 3.1000 | 75.7500 |
| Torrent | M1850GG (AMW) | 29.13 | 66.5 | 1.625 | 80 | 29.85 | 2400 | 10 | 10 | 0 | Smooth (Zero Roughness) | No | 4.0000 | 4.1250 | 109.5000 |
| Hubbub | L1080BB (AMW) | 22.61 | 48.38 | 1.25 | 85 | 29.92 | 3400 | 14 | 10 | 0 | Smooth (Zero Roughness) | No | 4.0240 | 4.1490 | 114.0000 |
| McGarvey | J350W-L (AT) | 6.53 | 42.52 | 0 | 100 | 0 | 2750 | 0 | 10 | 0 | Smooth (Zero Roughness) | No | 3.0000 | 3.0000 | 67.5000 |
| EZI65Hist-1 | J100 (Hist) | 4.9 | 37.17 | 0.4 | 70 | 0 | 2848 | 0 | 8 | 0 | Smooth (Zero Roughness) | No | 3.9980 | 3.9980 | 59.0000 |
| Prometheus | XPrometheu (RPY) | 45.521 | 58.8807 | 2.126 | 42.61 | 0 | 4596.5 | 0 | 16.995 | 10 | Smooth Paint | No | 5.5000 | 5.5000 | 87.7559 |
| Andromeda | XAndromeda (RPY) | 55.83 | 50.2258 | 2.2146 | 57.13 | 0 | 524.9 | 0 | 39.37 | 6 | Smooth Paint | No | 5.9331 | 5.9331 | 98.4094 |
| Astra | XAstra (RPY) | 27.935 | 47.0751 | 2.2146 | 57.13 | 0 | 524.9 | 0 | 39.37 | 6 | Smooth Paint | No | 3.7008 | 3.7008 | 71.1338 |
| Cavour | XCavour (RPY) | 22.339 | 67.0729 | 2.6378 | 57.25 | 0 | 492.1 | 0 | 39.37 | 6 | Smooth Paint | No | 4.0945 | 4.0945 | 107.1811 |
| Genesis | XGenesis (RPY) | 24.226 | 62.295 | 0 | 57.13 | 0 | 524.9 | 0 | 39.37 | 6 | Smooth Paint | No | 3.7008 | 3.7008 | 93.3858 |
| Lince | XLince (RPY) | 30.356 | 47.9943 | 2.6378 | 57.15 | 0 | 518.4 | 0 | 39.37 | 6 | Smooth Paint | No | 4.0945 | 4.0945 | 83.9140 |
| Erebus | XErebus (RPY) | 15.425 | 51.2632 | 1.5945 | 57.13 | 0 | 524.9 | 0 | 39.37 | 6 | Smooth Paint | No | 3.6024 | 3.6024 | 85.5288 |
| Juno3 | XJuno3 (RPY) | 71.034 | 66.9185 | 2.6378 | 41.68 | 0 | 4855.6 | 0 | 17.06 | 5 | Smooth Paint | No | 5.1575 | 5.1575 | 109.0945 |
| BellaLui | XBellaLui (RPY) | 43.38 | 63.165 | 3.5 | 54.24 | 0 | 1335.3 | 0 | 13.78 | 1 | Smooth Paint | No | 6.1417 | 6.1417 | 105.4173 |
| PSASLaunch10 | N2500 (CTI) | 74.388 | 93.0339 | 0 | 42.74 | 0 | 4560.4 | 0 | 11.975 | 1 | Smooth Paint | No | 5.5000 | 5.5000 | 139.2126 |
| Valetudo | XValetudo (RPY) | 21.311 | 48.6663 | 1.7039 | 51.18 | 0 | 2191.6 | 0 | 18.701 | 5.3 | Smooth Paint | No | 3.1850 | 3.1850 | 84.9606 |
| HeartOfSteel | N2900-CL (CTI) | 72.49 | 75.91 | 2 | 95 | 0 | 4596 | 8 | 18 | 5 | Rough Camouflage Paint | No | 4.0400 | 4.0400 | 131.6200 |

### Geometry of the held-out rockets

Lengths and diameters are in inches. `loc`, `fx1`, `fx3` and `LE` are stored values from the file's fin fields (`Location`, `FX1`, `FX3`, `LERadius`). We didn't confirm which RAS box each one fills, so open the saved file when you can.

- Hubbub: NoseCone L 16.75 D 4.024 at 0 Shape Tangent Ogive BluntRadius 0.063 | BodyTube L 97.25 D 4.024 at 16.75 RailGuideDiameter 0.375 RailGuideHeight 0.5 | FinCan L 8.25 D 4.149 at 114.0 InsideDiameter 4.024 ShoulderLength 0.125 Offset -8.25; fins n 3 root 8.25 tip 3.25 span 5.0 sweep 5.0 t 0.125 loc 26.0 Rounded fx1 0.0 fx3 0.0 LE 0
- McGarvey: NoseCone L 13.0 D 3.0 at 0 Shape Tangent Ogive | BodyTube L 54.5 D 3.0 at 13.0; fins n 3 root 8.75 tip 2.0 span 4.0 sweep 6.25 t 0.0625 loc 10.5 Square fx1 1.5 fx3 1.25 LE 0
- EZI65Hist-1: NoseCone L 16.5 D 3.998 at 0 Shape Tangent Ogive | BodyTube L 42.5 D 3.998 at 16.5; fins n 3 root 5.5625 tip 3.75 span 5.0 sweep 0.5938 t 0.125 loc 5.5625 Hexagonal fx1 0.3 fx3 0.3 LE 0
- Prometheus: NoseCone L 29.2126 D 5.5 at 0 Shape Von Karman Ogive | BodyTube L 58.5433 D 5.5 at 29.2126; fins n 3 root 10.5512 tip 5.3543 span 5.1181 sweep 2.5984 t 0.1969 loc 10.748 Rounded fx1 0.1969 fx3 0 LE 0
- Andromeda: NoseCone L 11.811 D 5.9331 at 0 Shape Von Karman Ogive | BodyTube L 86.5984 D 5.9331 at 11.811; fins n 3 root 9.0551 tip 4.3307 span 7.2835 sweep 2.3622 t 0.1969 loc 13.9606 Rounded fx1 0.1969 fx3 0 LE 0
- Astra: NoseCone L 10.6299 D 3.7008 at 0 Shape Von Karman Ogive | BodyTube L 60.5039 D 3.7008 at 10.6299; fins n 4 root 7.874 tip 4.6457 span 4.6063 sweep 1.6142 t 0.1969 loc 7.874 Rounded fx1 0.1969 fx3 0 LE 0
- Cavour: NoseCone L 20.4724 D 4.0945 at 0 Shape Von Karman Ogive | BodyTube L 86.7087 D 4.0945 at 20.4724; fins n 4 root 7.874 tip 2.7559 span 3.937 sweep 2.5591 t 0.1969 loc 8.2835 Rounded fx1 0.1969 fx3 0 LE 0
- Genesis: NoseCone L 10.6299 D 3.7008 at 0 Shape Von Karman Ogive | BodyTube L 82.7559 D 3.7008 at 10.6299; fins n 4 root 7.874 tip 4.3307 span 4.1339 sweep 1.7717 t 0.1969 loc 9.8425 Rounded fx1 0.1969 fx3 0 LE 0
- Lince: NoseCone L 11.0236 D 4.0945 at 0 Shape Von Karman Ogive | BodyTube L 72.0243 D 4.0945 at 11.0236; fins n 4 root 6.6929 tip 1.6732 span 3.248 sweep 2.5098 t 0.1969 loc 6.6929 Rounded fx1 0.1969 fx3 0 LE 0 | BoatTail L 0.8661 D 4.0945 at 83.0479 RearDiameter 3.8205
- Erebus: NoseCone L 15.3981 D 3.6024 at 0 Shape Von Karman Ogive | BodyTube L 67.0157 D 3.6024 at 15.3981; fins n 4 root 4.7244 tip 1.9685 span 3.1496 sweep 1.378 t 0.1969 loc 4.7244 Rounded fx1 0.1969 fx3 0 LE 0 | BoatTail L 3.1149 D 3.6024 at 82.4139 RearDiameter 2.815
- Juno3: NoseCone L 22.2441 D 5.1575 at 0 Shape Von Karman Ogive | BodyTube L 84.1732 D 5.1575 at 22.2441; fins n 4 root 7.874 tip 4.7244 span 5.1181 sweep 1.5748 t 0.1969 loc 11.7323 Rounded fx1 0.1969 fx3 0 LE 0 | BoatTail L 2.6772 D 5.1575 at 106.4173 RearDiameter 4.2126
- BellaLui: NoseCone L 9.5276 D 6.1417 at 0 Shape Tangent Ogive | BodyTube L 93.9213 D 6.1417 at 9.5276; fins n 3 root 11.0236 tip 4.9213 span 7.874 sweep 3.0512 t 0.1969 loc 13.2126 Rounded fx1 0.1969 fx3 0 LE 0 | BoatTail L 1.9685 D 6.1417 at 103.4488 RearDiameter 5.315
- PSASLaunch10: NoseCone L 41.0157 D 5.5 at 0 Shape Tangent Ogive | BodyTube L 98.1969 D 5.5 at 41.0157; fins n 3 root 14.5669 tip 7.9449 span 5.9449 sweep 3.5906 t 0.1969 loc 14.5669 Rounded fx1 0.1969 fx3 0 LE 0
- Valetudo: NoseCone L 10.7874 D 3.185 at 0 Shape Tangent Ogive | BodyTube L 74.1732 D 3.185 at 10.7874; fins n 3 root 2.2835 tip 0.7087 span 3.0315 sweep 0.7874 t 0.1969 loc 4.6457 Rounded fx1 0.1969 fx3 0 LE 0
- HeartOfSteel: NoseCone L 15.52 D 4.04 at 0 Shape Parabolic BluntRadius 0.0625 | BodyTube L 116.1 D 4.04 at 15.52; fins n 3 root 10 tip 2 span 3.2 sweep 7 t 0.25 loc 10 Double Wedge fx1 1 fx3 0 LE 0.125

### Motors made for the held-out flights

Each line reads: name, diameter mm, length mm, delay, propellant kg, total kg, maker. The stock motors are in RAS's `rasp.eng`: L1080BB (AMW), J350W-L (AT), J100 (Hist), N2500 (CTI) and N2900-CL (CTI). Where a RocketPy notebook's grains differed from the `.eng` header by more than 20 %, we used the notebook's propellant mass.

```text
XPrometheu 98 548 0 3.7370 6.7180 RPY
XAndromeda 105.49 749.88 0 4.3463 4.3473 RPY
XAstra 75 486 0 2.0238 2.0248 RPY
XCavour 75 486 0 1.9130 1.9140 RPY
XGenesis 75 486 0 1.7735 1.7745 RPY
XLince 72.8 639.425 0 3.0830 3.0840 RPY
XErebus 64.05 651.73 0 1.1757 1.1767 RPY
XJuno3 91.7 831.3 0 8.1694 8.1704 RPY
XBellaLui 54 579 0 1.4500 1.4510 RPY
XValetudo 56.63 647.4 0 1.4087 1.4097 RPY
```

### Step 3: Run FS by hand

**Quick route, using the saved folders:**

1. Copy `sim.toml`, `aero.csv` and `motor.eng` from `validation/results/matrix/<flight, spaces as _>/<folder from the first table>/` to a new folder.
2. Run this from that folder:

   ```powershell
   $env:PYTHONPATH = "C:\dev\flight_sim\src"; $env:MPLBACKEND = "Agg"
   C:\dev\flight_sim\.venv\Scripts\python.exe -m flight_sim sim.toml --no-show --output-dir out --overwrite
   ```

3. Open `out/telemetry.csv` and go to the last row. Column `state.position_x [m]` is apogee above ground in metres.
4. Divide by 0.3048 and write the result in the FS column.

Don't use the `apogee_m` value printed in the console, because it is rounded.

**From scratch, for a new rocket:** make the same three files. This is DontDebate's real `sim.toml`, so you can check your working against it:

```toml
name = "DontDebateThisN5800MinDia"
stop_event = "apogee"
max_time = "400 s"

[properties.aero_table]
type = "flight_sim.utilities.data_loader.aero_table_from_csv"
filepath = "aero.csv"
reference_area = "0.008726770 m**2"
reference_length = "0.105410 m"
reference_point = { value = [0, 0, 0], units = "m" }
frame = "missile"
extrapolation = "clamp"

[properties.dry_mass_properties]
mass = "7.0326 kg"
cg_location = { value = [-1.15208, 0, 0], units = "m" }
inertia = { diag = [0.00977, 3.6498, 3.6498], units = "kg*m**2" }

[properties.engine]
type = "flight_sim.vehicle.engine.SolidEngine.from_eng"
motor_file_path = "motor.eng"
forward_end_location = { value = [-1.25655, 0, 0], units = "m" }
nozzle_exit_area = "0.003137 m**2"
reference_pressure = "101325 Pa"

[properties.reynolds_correction]
type = "flight_sim.vehicle.reynolds_correction.ReynoldsCorrection"
reference_area = "0.008726770 m**2"
body_length = "2.49555 m"
body_diameter = "0.10541 m"
body_wetted_area = "0.715171 m**2"
roughness = "0.000006350 m"
all_turbulent = true

[[properties.reynolds_correction.fins]]
wetted_area = "0.110322 m**2"
mean_chord = "0.18097 m"
thickness = "0.00480 m"

[config.truth]
launch_latitude = "35.0 deg"
launch_elevation = "1143.00 m"

[config.truth.atmosphere]
type = "flight_sim.environment.atmosphere.StandardAtmosphere1976"
launch_temperature = "80 degF"

[config.truth.gravity]
type = "flight_sim.environment.gravity.WGS84Gravity"

[config.truth.wind]
type = "flight_sim.environment.wind.UniformWind"
speed = "2.2352 m/s"
from_azimuth = "0 deg"

[config.truth.launch_rail]
length = "3.048 m"
friction_coefficient = 0.0
elevation = "88 deg"
azimuth = "0 deg"

[[events]]
ref = "flight_sim.events.APOGEE"
```

Compare your layout with a saved `sim.toml` before relying on it. To work out each value, use the DontDebate numbers below as a check. Motor length and total mass come from the first line of the `.eng` file (`N5800-CS 98 1239 P 9.425 14.826 CTI`).

| Value | Rule | DontDebate |
|---|---|---|
| `reference_length` | FS ref dia | 4.15 in = 0.10541 m |
| `reference_area` | π d² / 4 | 0.0087268 m² |
| Dry `mass` | Launch weight − motor total mass | 21.8586 − 14.826 = 7.0326 kg |
| Engine forward end | Rocket length − motor length, entered negative | −(2.49555 − 1.239) = −1.25655 m |
| Motor CG | Forward end + motor length / 2, as a distance from the nose | 1.25655 + 0.6195 = 1.87605 m |
| Dry CG | (launch weight × CG − motor mass × motor CG) / dry mass, entered negative | (35.9165 − 27.8143) / 7.0326 = 1.15208 m |
| Roll inertia | 0.5 × dry mass × (d / 2)² | 0.00977 |
| Pitch and yaw inertia | dry mass × length² / 12 | 3.6498 |
| `nozzle_exit_area` | π × exit² / 4. Use 0 when the exit is 0 | 0.003137 m² |
| `launch_elevation` | Elev ft × 0.3048 | 1143.00 m |
| Rail `elevation` | 90 − Rail angle | 88 deg |
| Wind `speed` | mph × 0.44704 | 2.2352 m/s |
| `barometric_pressure` | Add under `[config.truth.atmosphere]` only when pressure isn't 0, for example `"30.05 inHg"` | Not set |

Reynolds values use the widest diameter, including the fin can.

| Value | Rule |
|---|---|
| `body_wetted_area` | Sum of the parts below |
| Nose | π × d / 2 × √(L² + (d/2)²) |
| Tube | π × d × L |
| Fin can | π × (d − inside d) × L |
| Boattail or transition | π × (d + rear d) / 2 × √(L² + ((d − rear d) / 2)²) |
| Fin `wetted_area` | Count × (root + tip) × span |
| Fin `mean_chord` | (root + tip) / 2 |
| Fin `thickness` | Fin thickness |
| `all_turbulent` | The Turb column |

DontDebate's wetted area is 0.07188 (nose) + 0.63716 (tube) + 0.00613 (fin can) = 0.71517 m².

| Surface finish | Roughness, inches | Multiply by 0.0254 for metres |
|---|---|---|
| Smooth | 0 | 0 |
| Polished | 0.00005 | 0.00000127 |
| Sheet Metal | 0.00016 | 0.00000406 |
| Smooth Paint | 0.00025 | 0.00000635 |
| Camouflage | 0.0004 | 0.00001016 |
| Rough Camouflage | 0.0012 | 0.00003048 |
| Galvanized | 0.006 | 0.00015240 |
| Cast Iron | 0.01 | 0.00025400 |

**`aero.csv`** has the header `Mach,Alpha,Phi,Cx,Cy,Cz,CMx,xCP,CxPowerOn,CxViscous`. Make two rows for each RAS row, one with Phi 0 and one with Phi 360:

| Column | Value |
|---|---|
| `Cx` | −CA Power-Off |
| `Cy`, `CMx` | 0 |
| `Cz` | −CN |
| `xCP` | −CP in inches × 0.0254 / reference diameter in metres. Alpha 0 uses `CP (0 to 4 deg)` |
| `CxPowerOn` | −CA Power-On |
| `CxViscous` | Blank |

Add a Mach 0 row for each alpha and Phi by copying the lowest Mach row. DontDebate's first row is `0.00,0,0,-0.671215,0,-0.000000,0,-17.98850,-0.651555,`.

On a fin can rocket, don't rescale `Cx`, because RAS's coefficients already use the fin can reference. Dividing `xCP` by the fin can diameter is the part that matters: using the body diameter here caused the 764-run bug.

### Step 4: Run plain RocketPy

Save this as a `.py` file beside `motor.eng` and `ras_aero.csv`, then run it with `validation\.venv\Scripts\python.exe`. Change lines 5 to 8 for each flight. It is set for DontDebate and should print 67470.66. Use body diameter here, not fin can diameter. Temperature, pressure and wind are left out on purpose, because this is what an ordinary user would get.

```python
import csv
from rocketpy import Environment, Flight, GenericMotor, Rocket

IN, FT, LB = 0.0254, 0.3048, 0.45359237
weight, cg, length, dia, exit_d = 48.19 * LB, 64.69 * IN, 98.25 * IN, 3.9173 * IN, 2.488 * IN  # Launch wt, CG, Length, Body dia, Nozzle exit
elev, rail, angle = 3750 * FT, 10 * FT, 2  # Elev, Rail, Rail angle
motor_kg, motor_len, motor_rad = 14.826, 1.239, 0.049  # from the motor's .eng header
ENG, AERO = "motor.eng", "ras_aero.csv"

rows = [r for r in csv.DictReader(open(AERO)) if float(r["Alpha"]) == 0]
off = [(float(r["Mach"]), float(r["CA Power-Off"])) for r in rows]
on = [(float(r["Mach"]), float(r["CA Power-On"])) for r in rows]
dry = weight - motor_kg
cg_dry = (weight * cg - motor_kg * (length - motor_len / 2)) / dry
motor = GenericMotor.load_from_eng_file(ENG, nozzle_radius=exit_d / 2, chamber_radius=motor_rad, chamber_height=motor_len,
                                        chamber_position=motor_len / 2, center_of_dry_mass_position=motor_len / 2,
                                        reference_pressure=101325, dry_inertia=(0, 0, 0))
iyy = dry * length**2 / 12
rocket = Rocket(radius=dia / 2, mass=dry, inertia=(iyy, iyy, 0.5 * dry * (dia / 2) ** 2), power_off_drag=off,
                power_on_drag=on, center_of_mass_without_motor=length - cg_dry)
rocket.add_motor(motor, position=0)
env = Environment(latitude=35, longitude=-100.0, elevation=elev)
env.set_atmospheric_model("standard_atmosphere")
flight = Flight(rocket=rocket, environment=env, rail_length=max(rail, 0.1), inclination=90 - angle, heading=0,
                terminate_on_apogee=True, max_time=400)
print((flight.apogee - elev) / FT)
```

The motor sizes come from the `.eng` first line: radius is diameter / 2000, length is length / 1000. Helped RocketPy is in `validation/src/fsval/rpy_helped.py`.

### Step 5: Compare the results

**In a spreadsheet:** one row per flight, starting at row 2. Do the 23 development and 15 held-out flights as separate blocks. Column A is the flight, B truth, C RAS and D FS. Fill these down:

| Column | Name | Formula |
|---|---|---|
| E | RAS error % | `=100*(C2/B2-1)` |
| F | FS error % | `=100*(D2/B2-1)` |
| G | RAS size | `=ABS(E2)` |
| H | FS size | `=ABS(F2)` |
| I | FS − RAS | `=H2-G2` |

Then, for development (rows 2 to 24):

| Result | Formula |
|---|---|
| Mean error | `=AVERAGE(G2:G24)` and `=AVERAGE(H2:H24)` |
| Median error | `=MEDIAN(G2:G24)` and `=MEDIAN(H2:H24)` |
| Mean signed error | `=AVERAGE(E2:E24)` and `=AVERAGE(F2:F24)` |
| Mean gap | `=AVERAGE(I2:I24)` |
| 95 % half-width | `=T.INV.2T(0.05,COUNT(I2:I24)-1)*STDEV.S(I2:I24)/SQRT(COUNT(I2:I24))` |
| Flights closer than RAS | `=COUNTIF(I2:I24,"<0")` |

The range is the mean gap ± the half-width. The critical t values are 2.0739 for 23 flights, 2.4469 for 7, 2.1448 for 15 and 2.0262 for 38. "Above 20,000 ft" is the 7 development flights with truth of 20,000 ft or more, and "All" is all 38.

**How to read it:** a negative gap means FS is better. If the range includes 0, the two are not shown to differ. Check one row by hand first. Qu8k: truth 121,478, RAS 119,684.039, FS 115,299.795 gives RAS −1.48 %, FS −5.09 %, and a gap of +3.61.

**The bootstrap ranges** in the tables above resample the flights. They can't be done sensibly in a spreadsheet, so use this script from `validation/`:

```python
import csv, numpy as np
r = list(csv.DictReader(open("results/final_flights.csv")))
v = lambda k, s: np.array([float(x[k]) for x in s])
for name, s in (("dev", [x for x in r if x["group"] == "dev"]), ("held", [x for x in r if x["group"] == "held"])):
    t = v("truth_ft", s)
    a, b = 100 * (v("fs_ft", s) / t - 1), 100 * (v("ras_ft", s) / t - 1)
    d = abs(a) - abs(b)
    picks = np.random.default_rng(1).integers(0, len(d), (20000, len(d)))
    print(name, round(abs(a).mean(), 2), round(abs(b).mean(), 2), np.percentile(d[picks].mean(axis=1), [2.5, 97.5]).round(2), (d < 0).sum())
```

It prints mean FS error, mean RAS error, the 95 % range and flights closer than RAS. You should get `dev 5.49 5.41 [-0.41 0.63] 15` and `held 11.78 11.11 [0.2 1.1] 4`. Typing rounded results by hand can move a range's last digit.

| Flights | FS − RAS, mean | Spreadsheet t range | Bootstrap range | Closer than RAS |
|---|---|---|---|---|
| Development, 23 | +0.08 | [−0.48, +0.64] | [−0.41, +0.63] | 15 |
| Above 20,000 ft, 7 | +0.34 | [−1.92, +2.59] | [−1.13, +2.05] | 4 |
| Held-out, 15 | +0.66 | [+0.15, +1.17] | [+0.20, +1.10] | 4 |
| All, 38 | +0.31 | [−0.08, +0.70] | [−0.05, +0.69] | 19 |

Both methods reach the same conclusions. The error columns should match the Final results tables above.

**The one test you can't do by hand** is leave-one-flight-out selection, because it needs the full 720-setup matrix. Each flight is scored on the setup with the lowest summed error on the other flights. It is `final_score.leave_one_out`.

### Expected results

Feet above ground, rounded. `validation/results/final_flights.csv` has the same numbers to 3 decimals.

| Flight | Set | Truth | RAS | RocketPy plain | RocketPy helped | FS |
|---|---|---:|---:|---:|---:|---:|
| Blister | dev | 9026 | 8301 | 8505 | 8367 | 8336 |
| Byrum | dev | 5732 | 5281 | 5112 | 5310 | 5284 |
| CalIsp1 | dev | 3964 | 3876 | 3778 | 3886 | 3876 |
| CalIsp2 | dev | 3837 | 3948 | 3839 | 3958 | 3948 |
| CalIsp3 | dev | 3710 | 3876 | 3782 | 3887 | 3877 |
| CalIsp4 | dev | 5085 | 4847 | 4781 | 4866 | 4851 |
| CalIsp5 | dev | 4930 | 4836 | 4760 | 4854 | 4838 |
| CancerDescending | dev | 6188 | 6328 | 6452 | 6348 | 6325 |
| DontDebateThisN5800MinDia | dev | 56573 | 61982 | 67471 | 62254 | 60864 |
| EZI65-1 | dev | 3965 | 4214 | 4333 | 4237 | 4227 |
| Full Metal Jacket1 | dev | 37981 | 38772 | 40534 | 38999 | 38238 |
| Full Metal Jacket2 | dev | 30038 | 32548 | 33722 | 32551 | 32075 |
| Gibb | dev | 3913 | 4205 | 4204 | 4230 | 4218 |
| IonDrive | dev | 8027 | 8642 | 8659 | 8675 | 8616 |
| Kinsel_P4935_A-601_Rocket | dev | 42771 | 41098 | 41860 | 40537 | 40164 |
| L500Roc | dev | 24771 | 26509 | 24676 | 25625 | 26170 |
| Proteus6 | dev | 85067 | 81499 | 77650 | 81335 | 79036 |
| Qu8k | dev | 121478 | 119684 | 114031 | 119750 | 115300 |
| Rabia-ShortFinCan | dev | 10584 | 10225 | 9947 | 9956 | 10269 |
| Rabia | dev | 12745 | 12197 | 12493 | 12296 | 12226 |
| Raven | dev | 8815 | 9332 | 8935 | 9383 | 9325 |
| Thunder&Lightning | dev | 3577 | 3989 | 3969 | 4013 | 3999 |
| Torrent | dev | 12807 | 13717 | 13765 | 13798 | 13735 |
| Hubbub | held | 10750 | 10646 | 10791 | 10770 | 10763 |
| McGarvey | held | 4246 | 5139 | 5129 | 5173 | 5152 |
| EZI65Hist-1 | held | 5671 | 7887 | 7393 | 7540 | 7870 |
| Prometheus | held | 12789 | 13505 | 13840 | 13790 | 13776 |
| Andromeda | held | 11296 | 13200 | 13320 | 13338 | 13320 |
| Astra | held | 10663 | 11393 | 11495 | 11505 | 11497 |
| Cavour | held | 9150 | 10303 | 10404 | 10422 | 10404 |
| Genesis | held | 9567 | 10030 | 10328 | 10140 | 10127 |
| Lince | held | 11768 | 13285 | 13440 | 13444 | 13431 |
| Erebus | held | 9908 | 9675 | 9764 | 9781 | 9768 |
| Juno3 | held | 10541 | 10914 | 11167 | 11134 | 11117 |
| BellaLui | held | 1506 | 1619 | 1622 | 1622 | 1622 |
| PSASLaunch10 | held | 15288 | 17358 | 18158 | 17386 | 17338 |
| Valetudo | held | 2822 | 3318 | 3357 | 3357 | 3352 |
| HeartOfSteel | held | 30411 | 29964 | 28685 | 29653 | 29664 |

### Running it all with the tool instead

From `validation/`, using `$env:PYTHONPATH="src"` and `.venv\Scripts\python.exe -m`, run these in order: `fsval.run_ras_cases`, `score`, `surface`, `extra`, `extra prepare`, `exhaust`, `throat`, `matrix`, `final_score`, `matrix_score`, `tiers`, `rpy`, `rpy_helped`, `timing`, `builtin`. Prefix each module with `fsval.`. `matrix` can resume if stopped, and uses every core (`WORKERS = os.cpu_count()`, 20 here, at `matrix.py:26`). Lower that number to keep the computer usable.

The matrix tag is `{table}_re{re}_po{po}_w{wind}_{nozzle}[_gras][_fc]`:

| Part | Options |
|---|---|
| table | `sea`, `mid`, `surface` |
| re | 0, 2 (surface runs are tagged 1) |
| po | 0, 1, `ap02`, `blend`, `ras` |
| wind | 0, 1 (1 is the 1/7 law) |
| nozzle | `none`, `linear`, `kb` |
| `_gras` | RAS's constant 9.786 gravity |
| `_fc` | Fin can reference |

### Implementing it all in FS

In priority order. After each change, rerun the FS tests and the 38 flights in Step 3. Results should stay the same unless the change is meant to move them.

**Needed now**

1. **Commit the built-in Reynolds correction.** It is only in the working tree, in `src/flight_sim/vehicle/reynolds_correction.py` and `tests/test_reynolds_correction.py`. The frozen setup can't run without it.
2. **Add a RAS importer.** FS has none, and `data/aero/Convert_RASAERO_To_CSV.py` isn't on `main` or this branch. Move the rules from Step 3 into FS, starting from `validation/src/fsval/aero.py` (`to_fs_table`), `fsrun.py` (`build`) and `cdx1.py` (`skin`, line 27).
3. **Use the fin can diameter by default in that importer.** The cleanest fix is adding the fin can to the diameter calculation at `cdx1.py:91`, which removes the separate `matrix.fincan_design` step. Reference area and length, the Reynolds area, base diameter and `xCP` all need the same diameter.
4. **Require a real nozzle exit.** Decide what happens to RAS files with an exit of 0. A warning is the smallest option, because 10 of our 38 flights have one.

**Worth doing next**

5. **Add delivered-impulse uncertainty to Monte Carlo.** FS has no Monte Carlo yet, so it needs building first. Scale the thrust curve per run at `SolidEngine.get_thrust` (`engine.py:373`). The size of that scatter should come from motor test data, not from these flights.
6. **Add batch running.** `validation/src/fsval/flight_server.py` and `fs_worker.py` show the idea: one process stays loaded and reuses it for each flight. The check is that 400 repeat flights matched the saved results exactly. Memory use over long runs hasn't been checked.

**Optional, off by default**

7. **Profile atmosphere.** Start from `profile_air.py` and `weather.air_profile`. Retest on new dated flights before relying on it.
8. **Altitude drag surface.** Start from `surface.py`, `surface_lookup.py` and `surface_worker.py`. Its gain is within the noise, so this is the lowest priority. It would have to become a real input, not a runtime patch.
9. **Kalt-Badal nozzle.** The spec is `tasks/nozzle_separation.md`, and the working code is `kb_worker.py`. Change `SolidEngine.get_thrust`, and add optional `throat_area` and `gamma` inputs. It should act whenever a throat is known. The recovery constant is 0.08. The spec's gamma is 1.25 but the harness used 1.22, so settle this first. Throats came from `throat.py` and `exhaust.py`, key `c*1500_g1.22`. The jump near 1.8 bar should also be smoothed.
10. **Base drag modes.** These are already in FS and stay off. Turn one on with `[config.physics]`: `type = "flight_sim.phases.PowerOnBaseDrag"`, `model` of `ap02`, `blend` or `ras`, plus `throat_diameter`, `base_diameter` and `exhaust_gamma`. Keep `base_diameter` at the fin can diameter. How AP02 works is deliberately not covered here.

**Harness only**

11. **Fix `weather_run.fly_one`** the way `matrix.py` handles `xCP` (lines 83 and 116), then refly its fin can results.

### What can't be repeated exactly

- **Weather runs:** ERA5 and sonde downloads go through `weather_run` (`fetch`, `sondes`, `fly`, `ras`, `score`), and its fin can results are old.
- **First RocketPy numbers:** these were overwritten, and the plain numbers here come from a rerun of the original code.
- **Stanford data:** it has no licence, so keep it local and don't redistribute it.
- **Timing:** speeds depend on the machine.
- **Held-out independence:** those flights have now been seen, so a future clean test needs new flights.

## Earlier bottom line, before the held-out flights and full matrix

**The changes below cut JARVIS's mean apogee error from 7.37 % to 5.41 %, which ties RASAero II on the mean but not on the median.** On flights above 20,000 ft, the mean error fell from 11.98 % to 5.39 %.

| Setup, 23 flights | Mean error | Median error | Mean signed error | Within 5 % | Above 20,000 ft (7 flights) | Below 20,000 ft (16 flights) |
|---|---|---|---|---|---|---|
| Original JARVIS | 7.37 % | 6.44 % | +1.97 % | 11 | 11.98 % | 5.35 % |
| **Improved JARVIS** | **5.41 %** | **5.55 %** | **+1.03 %** | **9** | **5.39 %** | **5.41 %** |
| RASAero II | 5.41 % | 4.67 % | +1.76 % | 12 | 5.23 % | 5.50 % |

- **Most of the gain came from better inputs, not new physics.** The largest gains came from using the right reference area and giving JARVIS the nozzle exit area.
- **JARVIS is not yet shown to be better than RAS.** The gap in mean error is −0.01 points, with a 95 % range of −0.60 to +0.64.
- **Some gains may not hold up.** The improved setup was chosen using these same 23 flights, so its score is probably a little optimistic.

## How to read the numbers

- **Error** is the absolute percent difference between predicted and measured apogee.
- **Original JARVIS** is `sea_re0_po0_w0_none`: RAS's sea-level drag table, power-off drag only, no nozzle exit area, and the filed launch-site temperature.
- **Improved JARVIS** is `surface_re1_po1_w0_linear_fc`, the older setup, not the frozen one.
- **Effect** is the change in mean error from using that option, with the other settings held the same. Negative is better. Each range is a 95 % bootstrap interval across flights. The Reynolds row compares on and off on the sea-level table.
- **Better and worse** count flights. A change can help a few flights by a lot and still leave most unchanged.
- All engines used RAS's aerodynamic data, so this doesn't test JARVIS as a drag predictor.

## Summary

| Change | Requested by you? | Where it lives | Effect on mean error | Better / worse flights | Verdict |
|---|---|---|---|---|---|
| Fin can reference area | No, found while tracing the gap | Harness | −0.90 [−2.75, +0.60] | 4 / 4 | **Adopt** |
| Nozzle exit area and pressure thrust | No, found in setup | JARVIS supports it; the harness supplies it | −0.71 [−1.88, +0.22] | 9 / 7 | **Adopt** |
| Power-on drag table during burn | Yes | JARVIS (`CxPowerOn`) | −0.37 [−1.33, +0.40] | 9 / 7 | **Adopt** |
| Altitude drag surface | Yes | Harness, through JARVIS's Reynolds hook | −0.14 [−0.78, +0.51] | 12 / 11 | **Optional, within the noise** |
| Real weather profiles | Yes | Harness | +0.23 on 10 flights | See below | **Optional, unproven** |
| Reynolds correction alone | Yes | JARVIS; test data built by the harness | +0.14 [−1.11, +1.41] | 12 / 11 | **Old CSV version; the built-in version is in the frozen setup** |
| Kalt-Badal nozzle | Yes | Harness | +0.12 [−0.04, +0.33] | 2 / 5 | **Physically justified, extreme case untested** |
| 1/7 power-law wind | Yes | Harness | +0.07 [−0.13, +0.30] | 2 / 3 | **Not needed** |
| RAS's power-on change in the base drag model | Yes | JARVIS (`PowerOnBaseDrag`) | +0.28 [+0.03, +0.55] | 8 / 15 | **Do not use by default** |
| Blended base drag | Yes | JARVIS (`PowerOnBaseDrag`) | +0.82 [−0.10, +1.71] | 8 / 15 | **Do not use by default** |
| AP02 base drag | Yes | JARVIS (`PowerOnBaseDrag`) | +5.63 [+1.60, +9.93] | 5 / 18 | **Do not use yet** |
| Flight server | Yes | Harness | No accuracy effect; about 4.8 times faster | n/a | **Bring into JARVIS** |

The full package beats original JARVIS by 1.96 points [0.09 to 4.06]. No single change is clearly positive on its own, because 23 flights are too few to show it. The harmful options are clearer: the AP02 and RAS-mode ranges exclude zero.

## Changes to adopt

### 1. Use the fin can diameter for reference area

RAS calculates drag from the fin can diameter, and our CDX1 reader was ignoring it. Eight flights changed, and they are the ones with a wider fin can.

- **Help:** mean error fell from 6.30 % to 5.41 %, and error above 20,000 ft fell from 9.19 % to 5.39 %. Signed error fell from +3.28 % to +1.03 %.
- **Catch:** four flights improved and four got worse, so the gain comes mostly from a few large corrections. This is a correct reading of RAS's data, not a new JARVIS model.
- **JARVIS change:** any RAS import must set `reference_area` from the wider fin can. It is not yet part of JARVIS itself.
- **Knock-on:** if base drag is used later, its base diameter must also become the fin can diameter, or fin can rockets get a false boattail.

### 2. Always give JARVIS the nozzle exit area

Without it, JARVIS's thrust comes out about 5 % low against RAS, which includes pressure thrust.

- **Help:** mean error fell from 6.12 % to 5.41 %, and error above 20,000 ft fell from 7.35 % to 5.39 %. Sixteen flights changed.
- **Catch:** our own team enters a nozzle exit diameter of 0 in RAS files. Those files need a real exit area, or a rule for how to handle them, before JARVIS uses them this way.

### 3. Use power-on drag during burn

This uses RAS's power-on drag while the motor burns. JARVIS already supports it through the `CxPowerOn` column.

- **Help:** mean error fell from 5.78 % to 5.41 %, and error above 20,000 ft fell from 6.56 % to 5.39 %.
- **Catch:** its benefit is uneven. Averaged across all combinations, it helped the 5 indirect-truth flights by 1.93 points and hurt the 15 best flights by 0.14.

### 4. Use drag from a RAS altitude surface

**Update:** not adopted. The final matrix puts its gain within the noise, so it stays optional.

You asked for this because RAS's drag rises with altitude and JARVIS's sea-level table did not. The surface gives JARVIS RAS's drag at each altitude a flight reaches, up to 200,000 ft.

- **Help:** mean error fell from 5.55 % to 5.41 %, and error above 20,000 ft fell from 5.61 % to 5.39 %. Before the fin can fix, its gain looked larger (6.67 % to 6.30 %).
- **Catch:** median error rose from 5.24 % to 5.55 %, and Qu8k went from −1.4 % to −5.6 %. Twelve flights improved and 11 got worse.
- **Verdict:** the physics is right, but the measured gain is small and could be noise.
- **JARVIS change:** the surface is applied through a runtime patch in the harness. It should become a proper input.

## Keep as options, off by default

### Real weather

ERA5 profiles and IGRA sondes were run for the 10 flights with a known site and date.

| Mean error, 10 flights | RAS | JARVIS with filed weather | JARVIS with real weather |
|---|---|---|---|
| All 10 | 6.42 % | 6.75 % | 6.98 % |
| Tier A (6) | 8.09 % | 7.50 % | 6.39 % |
| Tier B (2) | 4.96 % | 4.81 % | 3.48 % |
| Tier C (2) | 2.84 % | 6.45 % | 12.26 % |

- **Help:** it removed nearly all the signed error, from +2.58 % to +0.26 %. It also improved the Tier A and B flights.
- **Catch:** the overall mean didn't improve (p = 1.00). The two accelerometer flights (Qu8k and Proteus 6) fell to about −12 %.
- **Unknown:** the tier split was written after the errors were known, so it's a lead, not a finding. Launch hour is assumed, except for Qu8k, and Proteus's dates are weak.
- **Wind detail:** using real wind profiles changed apogee by 0.5 % or less.
- **JARVIS change:** a profile atmosphere is worth adding as a replicable option. It should not become the default until more flights support it.

### Reynolds correction

This section tests the old CSV version. The built-in version further down replaced it and is on in the frozen setup.

- On the sea-level table, it raised mean error from 5.55 % to 5.69 %.
- It over-corrected the highest flights: Qu8k went from −1.4 % to −11.4 %, and Proteus 6 from −4.4 % to −7.6 %.
- This is a test of the viscous drag data I built from RAS altitude scans at Mach 0.5, not a verdict on your JARVIS code. A better viscous drag source could change this result.
- The altitude surface runs through the same hook and remains an optional alternative.

### Kalt-Badal nozzle

It raised mean error by 0.12 points on the 7 motors first tested, using estimated throats because no certification letter gave a confirmed one.

A follow-up flew all 16 flights with a nozzle exit, using estimated throats at 0.8, 1.0 and 1.2 times their size:

- **Size of the effect:** it lowers apogee on nearly every flight. Proteus 6 moved −2.00 % and Qu8k −1.36 %, L500 −0.43 %, and the other 13 flights 0.21 % or less.
- **Accuracy:** mean error on those 16 flights rose from 4.75 % to 4.93 %. That cost is almost all Proteus 6 and Qu8k, which already read low.
- **Throat sensitivity:** Proteus 6 stays between −1.82 % and −2.21 %. Qu8k depends on the estimate, from −0.66 % to −1.91 %.
- **Why it matters here:** none of these motors separate during their main burn. The change comes from low-pressure start-up and tail-off, where the linear model gives too much pressure thrust at altitude.
- **Where it would matter more:** at 35 bar, separation starts near an expansion ratio of 12, and the sea-level thrust change reaches 13.9 % at a ratio of 20. Our flights have ratios of 9.2 or less, so the extreme case this model is built for is untested.
- **How to apply it:** it should be on whenever a throat is known, and the physics decides when it acts. Choosing flights by whether it lowers their error would be tuning to truth.
- **Smoothing:** the separation switch is continuous. There is a small jump near 1.8 bar chamber pressure, of about 8–40 N on motors up to 12.8 kN, which should be fixed when it moves into JARVIS.

### Base drag modes

The `ras` and `blend` modes should stay available but off. Both scored worse than the plain power-on table.

## Do not use yet

### AP02 base drag

Selecting AP02 raised mean error from 5.41 % to 11.04 %. The damage is concentrated on low flights: 13.27 % below 20,000 ft, against 5.94 % above it.

- **Worst flights:** the CalIsp flights fell to about −26 % to −29 %. Burn-phase Cd on those flights reached about 2.2, against 0.46 power-off.
- **Likely cause:** low subsonic flight, below the range of its table, where it is used by clamping. The drag swings are far larger than RAS's change at the same Mach numbers.
- **Inputs:** the result barely moved with throat size (4.7 to 12 mm). No subsonic scale beat the plain power-on table, and the boattail scale only mattered on IonDrive.
- **Open question:** throats and exhaust values are estimates, so this doesn't prove AP02 itself is wrong. It does show the current setup shouldn't fly subsonic flights.
- **Limited use:** it may suit supersonic burns, but this hasn't been shown. An AP02 check limited to its valid Mach range would be the next test.

## Tested and not worth changing

| Idea | Result | Decision |
|---|---|---|
| 1/7 wind law | Mean error +0.07; only 5 flights changed | Not needed for apogee |
| RAS's constant gravity | Mean error +0.02; apogee moves 0.4 % at most | Keep WGS84 |
| RAS's density | Matches RAS closely, but helps some flights and hurts others | Keep 1976 or real air |
| Hydrostatic hot-day air | Mean error rose to 5.59–5.68 % | Real issue, but no evidence for this fix |
| Surface roughness | Best case 5.41 % to 5.36 %; most options gave no real gain | Not a remaining fix |
| Inertia ±30 % | Negligible on apogee | Not a priority |
| Wind and tilt direction | Negligible on apogee | Not a priority |

The `Differing_Physics_Models` merge left all 1,104 comparable runs unchanged, so its effect on apogee accuracy here is zero.

## Biggest error still left

JARVIS and RAS mostly miss in the same way. Their errors correlate at 0.975, and 98 % of the squared error is shared. Better physics in JARVIS alone is unlikely to remove that.

1. **Measurement noise:** sensors alone contribute about 3–4 %, or 25–45 % of the squared error. Part of the error can't be fixed.
2. **Delivered motor impulse:** this is the biggest untested input. A 3 % impulse increase raises apogee by a median of 3.1 %, and up to 7.8 % on Qu8k.
3. **Experimental motors:** all 3 experimental-motor flights read low in both simulators, which points to impulse. This is mixed up with altitude, so it isn't proven.
4. **Mass and drag:** a 1 % change moves apogee by about −0.41 % for mass and −0.51 % for drag.
5. **No global fix:** 13 flights read high and 10 read low, so no single scale factor would help. Impulse, mass and drag also can't be separated using apogee alone.

**JARVIS change:** add delivered-impulse uncertainty to Monte Carlo runs. It costs little, and it's the input most likely to matter.

## Faster runs

The flight server keeps one JARVIS process running, so each flight skips about 0.76 s of imports. It reached about 15.2 flights per second against about 3.2 before, and 400 repeat flights matched the saved results exactly.

The speed comparison isn't exact, because the flight mix differed from the old benchmark. Memory growth over long runs is unchecked. This matters most for Monte Carlo and large test matrices, and JARVIS should have its own batch mode.

## Recommended order

1. Freeze `sea_re2_po1_w0_linear_fc` before scoring any new flight.
2. Add fin can reference area to the RAS import path.
3. Require a real nozzle exit area, and settle how to handle RAS files with a value of 0.
4. Keep the altitude drag surface optional, because its gain is within the noise.
5. Add delivered-impulse uncertainty to Monte Carlo.
6. Add batch running to JARVIS.
7. Add a profile atmosphere as an option, then retest it on new dated flights.
8. Leave AP02 off until it has been tested within its valid Mach range.

## Not tested

- **Datcom drag data:** you chose to skip this.
- **Gusts, 3D wind and updrafts:** not built, though direction and wind profile effects on apogee were small.
- **Misalignment:** not tested as a Monte Carlo input.
- **Descent:** every run stopped at apogee.
- **JARVIS's own drag prediction:** RAS supplied the aerodynamic data throughout.

## Limits of this evidence

- The 23 development flights all come from RAS's own validation set.
- Only 7 flights are above 20,000 ft, which is where JARVIS and RAS really differ.
- In a random-split check, choosing the best of all 720 setups on half the flights beat RAS on the other half in about 8 % of splits.
- The improved setup was picked before the tiers were written, but after the 23 flights had been seen. The frozen setup has since flown the held-out flights, but those had been seen too, so truly new flights are still needed.
- RAS's lead over JARVIS on the median isn't shown to be real: +0.88 points [−1.16, +1.97].

## Where the numbers come from

- `validation/results/matrix.json`, `matrix_scores.json` and `tiers.json`
- `validation/results/weather/scores.json`
- `validation/src/fsval/tiers.py`, `matrix_score.py` and `flight_server.py`

## Built-in Reynolds correction

JARVIS no longer needs a `CxViscous` column or RAS altitude scans. `ReynoldsCorrection` now computes the change in skin friction drag from sea-level air to the flight's air, using only the rocket's geometry and surface finish. No drag data goes in, and no constant was fitted to RAS or to measured flights. `from_csv` is gone.

| Piece | Law | Source of the value |
|---|---|---|
| Turbulent plate | Schultz-Grunow | published correlation |
| Laminar plate | Blasius | theory |
| Transition | Prandtl's allowance at Re 5e5 | RAS manual gives the flat plate value |
| Compressibility | Van Driest II, adiabatic wall, r = 0.89 | published transform |
| Roughness | Hoerner's fully rough limit, 0.032 (k/L)^0.2 | published correlation; k from RAS manual Table 1 |
| Body and fin shape | Barrowman form factors | published |
| Tripped flow | the file's All Turbulent Flow setting | the design itself |

These are empirical correlations from the literature. "Without empirical data" here means no data about this rocket and no RAS output. RAS does not publish its own friction law, so this reproduces its behaviour without being its method.

Fixed setup on all 23 flights, power-on Cx, linear nozzle, fin can reference:

| Mean abs. error to truth, % | RAS | RAS surface in FS | Built-in | Built-in vs surface, mean / max |
|---|---:|---:|---:|---:|
| All 23 flights | 5.41 | 5.41 | 5.49 | 0.27 / 1.17 |
| 7 flights over 20,000 ft | 5.23 | 5.39 | 5.56 | 0.39 / 1.17 |

Median error is 5.78 % for the built-in law, 5.55 % for the surface and 4.67 % for RAS. RAS's drag change with altitude stays larger than the built-in one: the median RAS-to-built-in ratio is 1.15 at Mach 0.3, 1.10 at Mach 0.8, 1.23 at Mach 1.5 and 1.22 at Mach 3, up to 60,000 ft. This gap is left in rather than scaled away. The largest apogee difference from the surface is DontDebateThisN5800MinDia at +1.17 %.

## Held-out flights (fsval.extra)

Setup fixed before any was flown: built-in Reynolds, power-on table, linear nozzle where the exit is known, fin can reference. 15 flights: 3 RASAero .alx1 files, 10 RocketPy flights, PSAS Launch 10, Stanford SSI Heart of Steel. Results in results/extra/scores.json.

| | mean abs err % | median % | bias % |
|---|---|---|---|
| RAS | 11.11 | 7.54 | +10.48 |
| FS, no Reynolds | 11.99 | 7.88 | +11.49 |
| FS, built-in | 11.78 | 7.82 | +11.26 |

Built-in closer than RAS on 4 of 15. All three read about 11 % high, so the set is weak at ranking them: RocketPy flights carry assumed air, no wind, no rail guides, and a lower simulator scores better whatever its physics. Only Heart of Steel exceeds 20,000 ft or Mach 1.1, and its unpublished launch weight moves it by about 4.5 %. FS is not shown to beat RAS.
