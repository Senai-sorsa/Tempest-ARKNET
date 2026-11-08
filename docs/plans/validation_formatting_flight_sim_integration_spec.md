# `tempest_weather` v2 — Output Formatting, Flight-Sim Integration & Monte Carlo Validation Plan

**Written:** 2026-11-07  
**Companion to:** `TEMPEST_MASTER_UPGRADE_SPEC.md`  
**Purpose:** Define exact data-formatting rules so human rocketeers and external flight simulators (RASAero II, OpenRocket, custom 6-DOF Monte Carlo engines) never misinterpret a unit, sign, or column; and provide an exhaustive, automated verification test suite for Claude to execute against RASAero, OpenRocket, and standard atmospheric baselines (ISA-1976, NRLMSISE-00, NOAA GFS/HRRR, and Uniform/Power-Law wind models).

**Revision 2026-11-07 (user decisions, applies to Section 2):** RASAero II automation is kept (the user supplies the hook). Observational truth and held-out-data requirements are removed: the tests are plumbing, consistency and plausibility checks, not skill claims. Monte Carlo scenarios are condensed to about 1,024 runs. Pass thresholds are initial values, frozen after a 20-case pilot. Dummy vehicles are used for sanity checks. All validation code lives in a separate `Validation/` folder that does not touch anything else. Section 1 (formatting) is unchanged from the original.

---

## Section 1: Data Formatting, Precision, Schemas & Human Readability

Rocketry flight software fails silently when given slightly malformed inputs: a wind direction off by $180^\circ$, sea-level altimeter pressure fed into a station-pressure field, altitude AGL fed into an ASL table, or floating-point noise (`14.000000000000002 mph`) cluttering a pad checklist. Every output from `tempest_weather` must obey the following strict formatting rules.

### 1.1 Display Rounding vs. Machine Export Precision

A core rule of `tempest_weather` is **Format for the Reader**:
* **Terminal Display (`print(r)`, `--format table`, `--format ras`, `--format openrocket`):** Round to the precision of real meteorological instruments and simulator GUI input boxes so launch crews can read and type numbers without visual noise.
* **Machine Exports (`--format csv`, `--format json`, `--format openrocket-csv`, `.nc`, `.parquet`):** Use **fixed scientific/engineering precision** (typically 4 to 6 decimal places, never unconstrained 17-digit IEEE 754 float noise, and never rounded so coarsely that numerical derivatives like wind shear $\partial \mathbf{u}/\partial z$ show stair-stepping).

| Variable | Plain Name | US Unit & Display Rounding | SI Unit & Display Rounding | Machine / CSV Precision (SI) | Physical / Instrument Basis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Elevation** | `elevation` | `1 ft` (`4,597 ft`) | `0.1 m` (`1401.3 m`) | `0.01 m` (`1401.27`) | USGS 3DEP vertical accuracy ($\sim 0.1\text{ m}$) |
| **Temperature** | `temperature` | `0.1 °F` (`84.2 °F`) | `0.1 °C` (`29.0 °C`) | `0.01 K` (`302.15`) | ASOS / radiosonde thermistor resolution ($0.1\text{ K}$) |
| **Dew Point** | `dew_point` | `0.1 °F` (`41.5 °F`) | `0.1 °C` (`5.3 °C`) | `0.01 K` (`278.45`) | Hygrometer resolution |
| **Altimeter Pressure** | `pressure` | `0.01 inHg` (`29.92 inHg`) | `0.1 hPa` (`1013.2 hPa`) | `0.1 Pa` (`101325.0`) | METAR `A2992` standard ($0.01\text{ inHg}$) |
| **Station Pressure** | `station_pressure`| `0.01 inHg` (`25.38 inHg`) | `0.1 hPa` (`859.5 hPa`) | `0.1 Pa` (`85946.5`) | Barometer transducer accuracy |
| **Wind Speed / Gust** | `wind_speed`, `gust`| `0.1 mph` (`12.4 mph`) | `0.1 m/s` (`5.5 m/s`) | `0.001 m/s` (`5.543`) | Smooth vertical derivatives $\partial u/\partial z$ |
| **Wind Direction** | `wind_from_deg` | `1°` (`245° (WSW)`) | `1°` (`245° (WSW)`) | `0.01°` (`245.18`) | Avoids stair-stepping in trajectory interpolation |
| **Relative Humidity** | `humidity` | `1 %` (`24 %`) | `1 %` (`24 %`) | `0.01 %` (`24.15`) | Bounded strictly to `[0.0, 100.0]` |
| **Air Density** | `density` | `0.00001 slug/ft³` (`0.00201`) | `0.001 kg/m³` (`1.036`) | `0.00001 kg/m³` (`1.03612`)| 4 significant figures required for aero $q = \frac{1}{2}\rho v^2$ |
| **Density Ratio** | `density_ratio` | `0.001` (`0.846` or `84.6%`) | `0.001` (`0.846`) | `0.00001` (`0.84582`) | $\rho / \rho_0$ where $\rho_0 = 1.225\text{ kg/m}^3$ |
| **Density Altitude** | `density_altitude`| `10 ft` (`7,840 ft`) | `1 m` (`2390 m`) | `0.1 m` (`2389.6`) | Aviation standard |
| **Speed of Sound** | `sound_speed` | `0.1 ft/s` (`1,142.3 ft/s`) | `0.1 m/s` (`348.2 m/s`) | `0.01 m/s` (`348.17`) | Mach number calculation $M = v / a$ |
| **Wind Shear** | `max_wind_shear` | `0.1 mph/1000 ft` (`8.4`) | `0.001 s⁻¹` (`0.012 s⁻¹`)| `0.00001 s⁻¹` (`0.01234`) | Structural bending-moment threshold |
| **Roughness Length** | `surface_roughness_m`| `0.001 ft` (`0.049 ft`) | `0.001 m` (`0.015 m`) | `0.0001 m` (`0.0150`) | Log-wind boundary layer scale $z_0$ |

---

### 1.2 Wind Direction, Coordinate Frame & Magnetic Bearing Formatting

Ambiguity in wind direction is the #1 cause of launch-rail azimuth setup errors and inverted trajectory dispersion ellipses.
1. **Meteorological ("From") vs. Vector ("To") Labelling:**
   * All scalar direction outputs (`wind_from_deg`, `wind_10m_from_deg`) use the **meteorological convention**: degrees clockwise from True North ($0^\circ \le \theta < 360^\circ$, with $0^\circ$ wrapped to $360^\circ$ or $0^\circ$ consistently, never negative) indicating the direction the wind is **blowing FROM**.
   * Terminal tables **must** append the 16-point cardinal compass rose in parentheses so a human cannot misread it:
     * Example: `248° True (from WSW)`
2. **True North vs. Magnetic North (Field Compass Helper):**
   * In `--all` and `--format openrocket`, print both **True** and **Magnetic** bearings using the site's magnetic declination $\delta$ (e.g., $\delta = +8.5^\circ\text{ E}$ at Spaceport America, where $\theta_{\text{mag}} = (\theta_{\text{true}} - \delta) \bmod 360^\circ$):
     * Example: `248° True / 240° Mag (from WSW, decl +8.5°E)`
3. **Vector Component Sign Conventions:**
   * In all CSV/JSON/NetCDF profile exports, vector components are explicitly suffixed with their positive axis:
     * `wind_u_east_ms`: positive toward **True East** ($+x$ in ENU, $+y$ in NED). Note: a wind *from* the West ($270^\circ$) has a **positive** `wind_u_east_ms` ($+u > 0$).
     * `wind_v_north_ms`: positive toward **True North** ($+y$ in ENU, $+x$ in NED).
     * `wind_w_up_ms`: positive **Upward** ($+z$ in ENU/UNE, $-z$ in NED).

---

### 1.3 Terminal Table & Copy-Paste Simulator Formats

#### A. Default Terminal Output (`tempest weather spaceport_america "2027-06-16 10:00"`)
Must fit cleanly in an 80-column terminal, use plain ASCII/Unicode box alignment, and separate the core pad numbers from the provenance/trust block:

```text
Tempest Weather — Spaceport America, NM (32.9900°N, 106.9700°W)
Valid: 2027-06-16 10:00 MDT (16:00 UTC | 09:12 Solar)
------------------------------------------------------------------------
  Launch Site Elevation :   4,597 ft   (1,401.3 m)  [usgs-3dep]
  Temperature (2 m)     :    86.4 °F   ( 30.2 °C)
  Barometric Pressure   :   29.98 inHg (1,015.2 hPa) [Altimeter Setting]
  Uniform Wind Speed    :    11.2 mph  (  5.0 m/s)  [10,000 ft drift eq]
  Density Altitude      :   7,410 ft   (2,259 m)    [rho/rho0 = 0.808]
------------------------------------------------------------------------
Trust: Climate estimate (mode: ai) — typical range for this date, not a forecast.
Note : High density altitude (7,410 ft); fin authority off the rail is reduced by 19%.
```

#### B. Multi-Percentile Coupled Table (`--percentile 10 50 90` or `--ras-profiles`)
Displays coupled scenarios side-by-side (lead variable marked with `*`):

```text
Tempest Weather — Spaceport America, NM | 2027-06-16 10:00 MDT
Coupled by lead variable: Uniform Wind Speed (*)
------------------------------------------------------------------------------
  Parameter                   P10 (Calm)       P50 (Median)      P90 (Windy)
------------------------------------------------------------------------------
  Elevation (ft)                   4,597              4,597            4,597
  Temperature (°F)                  84.9               86.4             88.1
  Altimeter Pressure (inHg)        30.04              29.98            29.91
  Uniform Wind Speed (mph) *         4.8               11.2             19.6
  Wind Direction (from)       215° (SSW)         242° (WSW)       258° (WSW)
  10 m Pad Wind / Gust (mph)   4.1 / 6.3         9.8 / 14.9      17.4 / 26.8
  Density Altitude (ft)            7,310              7,410            7,540
------------------------------------------------------------------------------
```

#### C. RASAero II Copy-Paste Block (`--format ras` / `r.to_ras()`)
RASAero II's `Launch Site` dialog requires **Launch Site Elevation (ft)**, **Temperature (°F)**, **Barometric Pressure (inHg, sea-level altimeter setting)**, and **Wind Speed (mph)**:

```text
=== RASAero II Launch Site Inputs (Spaceport America | 2027-06-16 10:00 MDT) ===
[P50 Median Coupled Day]
Launch Site Elevation (ft)    : 4597
Temperature (deg F)           : 86.4
Barometric Pressure (inHg)    : 29.98   # Sea-level Altimeter Setting (NWS std atm)
Wind Speed (mph)              : 11.2    # 10,000 ft AGL descent-weighted vector mean
```

#### D. OpenRocket Launch Conditions Block (`--format openrocket` / `r.to_openrocket()`)
**Critical Difference from RASAero:** OpenRocket's *Simulation Options -> Launch Conditions* tab uses **Station Pressure** (actual pressure at the pad, **not** sea-level altimeter setting) when the user unchecks "Use International Standard Atmosphere", and takes **10 m Pad Wind Speed + Turbulence Intensity (%) + Wind Direction (from)**:

```text
=== OpenRocket Launch Conditions (Spaceport America | 2027-06-16 10:00 MDT) ===
[P50 Median Coupled Day]
Launch Site Latitude (deg)    : 32.9900
Launch Site Longitude (deg)   : -106.9700
Launch Site Altitude (m ASL)  : 1401.3   (4597 ft)
Atmospheric Pressure (mbar)   : 859.8    (25.39 inHg)  # ACTUAL PAD STATION PRESSURE (Do NOT enter sea-level pressure!)
Atmospheric Temperature (C)   : 30.2     (86.4 F)
Average Windspeed (m/s)       : 4.4      (9.8 mph)     # 10 m pad wind (or use custom CSV profile for upper winds)
Turbulence Intensity (%)      : 14.2                   # sigma_u / U10 from site roughness z0 = 0.012 m
Wind Direction (deg from N)   : 242      (233.5 Mag)   # Blowing FROM WSW
```

---

### 1.4 CSV & Tabular File Schemas

Every CSV file generated by `tempest_weather` must follow four universal rules:
1. **Self-Documenting Header Comments (`#`):** Provenance, site coordinates, elevation, reference datum (`ASL` vs `AGL`), units, seed, and `tempest_weather` version are written as `# key: value` metadata lines at the top of the file. (Standard parsers like `pandas.read_csv(..., comment="#")`, `numpy.loadtxt(..., comments="#")`, and OpenRocket's CSV importer automatically skip `#` lines).
2. **Explicit Unit Suffixes in Column Names:** Every column header ends with its unit (e.g., `_m`, `_K`, `_Pa`, `_ms`, `_deg`), never ambiguous bare words like `alt` or `pressure`.
3. **Strict Monotonicity & No Missing Sentinels:** Height columns are strictly increasing (`height_agl_m[k+1] > height_agl_m[k]`). No `-9999`, `NaN`, or blank cells are ever written.
4. **LF Line Endings (`\n`) and UTF-8 Encoding (No BOM):** Ensures cross-platform compatibility across Windows, macOS, and Linux tools.

#### Schema 1: OpenRocket Custom Tabular Atmosphere (`--format openrocket-csv`)
Designed to import directly into OpenRocket's multi-level wind/atmosphere table:

```csv
# tempest_weather_version: 2.0.0
# site: spaceport_america (32.9900, -106.9700)
# pad_elevation_asl_m: 1401.27
# valid_time_local: 2027-06-16T10:00:00-06:00
# profile_type: P50_coupled_median
# wind_direction_convention: meteorological_degrees_from_true_north
altitude_asl_m,altitude_agl_m,temperature_K,pressure_Pa,density_kgm3,sound_speed_ms,wind_speed_ms,wind_from_deg,wind_u_east_ms,wind_v_north_ms
1401.27,0.00,303.35,85980.0,0.98762,349.12,0.000,242.10,0.000,0.000
1411.27,10.00,303.18,85882.4,0.98705,349.02,4.382,242.10,3.873,2.050
1451.27,50.00,302.79,85493.1,0.98384,348.80,5.114,244.30,4.608,2.218
...
```

#### Schema 2: Monte Carlo Parameter / Summary Table (`couple --out draws.csv` or `atmospheres --summary-csv`)
Designed for post-processing correlation and regression against flight simulation outcomes (`apogee`, `landing_lat`, `landing_lon`, `max_mach`, `rail_exit_v`). Every row has `run_id` matching the global deterministic counter (F1):

```csv
# tempest_weather_version: 2.0.0 | mode: ai | seed: 0 | n_samples: 1000
run_id,launch_time_iso,pad_temp_K,pad_pressure_Pa,altimeter_inHg,pad_rho_kgm3,density_alt_ft,z0_m,wind_10m_ms,wind_10m_from_deg,gust_10m_ms,uniform_wind_ms,uniform_wind_from_deg,wind_mean_0_3km_ms,max_shear_s1,max_shear_agl_m,jet_max_ms,jet_max_agl_m,mode_z1,mode_z2,mode_z3,mode_z4,mode_z5,mode_z6
0,2027-06-16T10:00:00-06:00,302.41,85912.3,29.96,0.98991,7342.1,0.0120,4.120,238.4,6.410,5.214,245.2,6.012,0.01420,450.0,24.110,11500.0,-0.4121,0.8832,-0.1104,1.2041,-0.0412,0.3319
1,2027-06-16T10:00:00-06:00,304.12,85840.1,29.93,0.98350,7560.4,0.0150,6.840,251.0,10.120,8.430,254.8,9.105,0.01980,300.0,31.450,12000.0,1.1204,-0.3410,0.5512,-0.7811,0.2190,-0.6012
```
*(Notice columns `mode_z1..mode_z6`: exporting the top 6 orthogonal latent principal-component scores of each atmosphere gives downstream Monte Carlo analysts a ready-made orthogonal basis for Sobol sensitivity indices and response-surface metamodeling!)*

---

---

## Section 2: Validation Plan (Flight-Sim & Monte Carlo Checks)

This section is the test protocol for **Claude** (with the user's RASAero II hook, and optionally OpenRocket) to run before v2 is cleared for flight-critical use. It checks **plumbing, units, signs, internal consistency and plausibility**. It does **not** make observational skill claims: calibration against balloons and the held-out scoring stay in the main model scoring (`docs/plans/PLAN.md`, `docs/logs/LOOP3.md`).

---

### Part 0: Where the validation code lives (isolation rules)

All validation code lives in one new folder, **`Validation/`** at the repo root, and touches nothing else.

1. **Contents:** dummy vehicles, the flight integrator, the RASAero adapter, the test scripts, the checks, and the outputs. Own `README.md`; runnable alone with `python -m Validation.run_all`.
2. **Read-only use of the tool:** `Validation/` reaches `tempest_weather` only through its public API (`Launch`, `weather`, `atmospheres`, the exports and the readers). It never imports private modules and never edits, writes into, or monkeypatches `tempest_weather/`, `tempest/`, `data/`, `models/` or `configs/`.
3. **One adapter file:** `Validation/adapters/tempest_api.py` is the only place that calls the tool. The v2 usability decisions are still pending the user's confirmation, so a later API change then means editing this one file, not the tests.
4. **Outputs:** only to `Validation/out/` (including the final report). Nothing is committed unless the user says so.
5. **Isolation guard:** `Validation/check_isolation.py` compares `git status` before and after a run and fails if any path outside `Validation/` changed.
6. **Own tests:** `Validation/tests/` runs the validation code itself (integrator conservation, sign checks on hand-made cases) so a broken validation tool cannot pass a broken weather tool.

#### Dummy vehicles (sanity checks only)

* `Validation/vehicles/` holds three **invented** vehicles as small TOML files (mass, reference area, Cd vs Mach table, thrust curve, stability margin, deploy altitudes): **V1** about 3,500 ft apogee, **V2** about 10,000 ft (dual deploy: 75 ft/s drogue, 20 ft/s main at 1,000 ft), **V3** about 30,000 ft.
* The integrator is a simple point-mass / 3-DOF model with a weathercocking approximation, labelled **"sanity-check integrator, not flight-accurate"**. The goal is to see that results *make sense* (directions, ordering, sensitivities), not to predict a real flight.

#### RASAero II automation (kept)

* `Validation/adapters/ras.py` exposes one function, **`run_ras(inputs) -> dict(pad_density, apogee, ...)`**. The user supplies its body (their own automation). The tests only call this function.
* If `run_ras` is not present or fails, every RASAero test is reported as **SKIPPED** (never as passed) and the report says so. OpenRocket is handled the same way through an optional `run_openrocket(...)`.

#### Reference atmospheres (no new data, no held-out claims)

* **Reference set:** 200 daytime cases taken from the ERA5 profile store already on disk, plus about 20 hand-built shear/turning-wind profiles. They stand in for "true days" in the sensitivity and plausibility comparisons.
* They are **development data** and are labelled so in the report. No test claims they are held out, and no new observations are collected for validation.

---

### Part A: RASAero II & OpenRocket Integration Tests

#### Test A1: Barometric pressure and pad air-density round trip ("altimeter vs station pressure" trap)
* **Why:** RASAero expects the sea-level altimeter setting (inHg); OpenRocket expects actual station pressure (hPa). Swapping them at 4,597 ft makes pad air density wrong by about 16%.
* **Run:**
  1. `tempest weather spaceport_america <time> --all` on 20 reference cases across winter and summer.
  2. Feed `r.to_ras()` (elevation, temperature, altimeter setting) into RASAero via `run_ras`; read RASAero's pad air density and apogee for one reference rocket of the user's choice.
  3. If OpenRocket is available, feed `r.to_openrocket()` (elevation, temperature, station pressure) and read its pad density and apogee.
* **Pass:** RASAero pad density within **0.2%** of tempest's; OpenRocket within **0.1%**. Feeding the wrong pressure type shifts apogee by more than **5%** (this proves `to_ras()` and `to_openrocket()` are separate for a reason). Station pressure to altimeter setting and back through the standard atmosphere round-trips within 0.01 hPa.

#### Test A2: Uniform drift-wind equivalence vs the full wind profile
* **Why:** RASAero takes one scalar wind for the whole flight. The spec defines `wind_speed` as the descent-time-weighted vector mean over a reference flight (10,000 ft, main at 1,000 ft, 75 ft/s drogue, 20 ft/s main). This test checks that it beats the usual rules of thumb.
* **Run:**
  1. Profiles: 100 from `launch.atmospheres(100)`, 100 from the reference set, and the 20 hand-built shear/turning profiles (for example southerly flow turning westerly with height).
  2. For each dummy vehicle V1, V2, V3, fly the full 44-level profile in the sanity-check integrator and record drift distance and landing point (the simulation reference).
  3. Re-fly with a constant wind set to: **A** the 10 m wind; **B** the unweighted scalar mean speed from 0 to apogee; **C** the unweighted vector mean; **D** tempest's descent-time-weighted vector mean.
* **Pass (initial, set after a 20-case pilot and then frozen):** D has the lowest median and 95th-percentile drift error for V2, and beats A and B by at least **20%** for every vehicle. Passing `--apogee 30000` for V3 lowers D's error compared with the default 10k assumption. RASAero drift (via `run_ras`) is compared for V2 where available and reported.

#### Test A3: Coordinate frame, azimuth and weathercocking sign check
* **Why:** A statically stable rocket weathercocks *into* the wind on ascent and drifts *with* it under parachute. An inverted sign makes it go the wrong way.
* **Run:** build a synthetic atmosphere with a pure west-to-east wind (`wind_from_deg = 270`, `u_east = +10 m/s`, `v_north = 0`) from 0 to 18 km. Export to OpenRocket CSV, RASAero, and all three reader frames (`une`, `enu`, `ned`). Fly a vertical launch (stability margin 2.5 cal) with and without parachute.
* **Pass:** at apogee the rocket is **west** of the pad; with a chute deployed at apogee the landing is **east** of apogee; the three reader frames give the same physical trajectory to within **1e-6 m**.

#### Test A4: Format and schema checks (added: the spec's Section 1 had no test for itself)
* **Run (automated, no simulator needed):** for every export (`table`, `ras`, `openrocket`, `csv`, `json`, `openrocket-csv`, `draws.csv`) check: no NaN or inf and no missing sentinels; height columns strictly increasing; every column header carries a unit suffix; `#` header lines present and parseable by `numpy.loadtxt(comments="#")` and `pandas.read_csv(comment="#")`; LF line endings; UTF-8 with no BOM; display rounding matches the Section 1.1 table; wind direction in [0, 360) with a cardinal label and the true/magnetic pair; RH in [0, 100].
* **Pass:** zero violations across 50 random queries. This feeds item 1 of the report checklist.

---

### Part B: Comparison with standard atmospheres (consistency, not skill)

Rocketry teams often use one of four legacy approximations. These tests compare `tempest_weather` (`ai`, `forecast`, `past` modes) with them on the **reference set** (Part 0). They show how the flight outcomes differ and whether the tempest atmospheres are physically plausible. They do **not** claim accuracy against observations.

| Baseline | How it works | What to look for |
| :--- | :--- | :--- |
| **1. ISA-1976 + uniform/power-law wind** | 15 °C sea level, -6.5 K/km, plus $U(z) = U_{10}(z/10)^{0.14}$ with constant direction | hot-pad density-altitude differences; no direction turning; no jet shear |
| **2. NRLMSISE-00 / US Standard supplements** | climatological mean T, rho by latitude and day of year | one deterministic profile; no spread; no wind profile |
| **3. Independent marginal Gaussian draws** | pad T, p and wind at each altitude perturbed independently | hydrostatic inconsistency; jagged shear; too-narrow joint extremes |
| **4. Raw deterministic NWP** (optional) | a single un-calibrated GFS/Open-Meteo profile from the forecast cache or live | terrain/elevation bias before Mode F; no spread. Skipped if offline |

**Run:** for the 200 reference days, fly V2 and V3 in the sanity-check integrator (and RASAero where available) with the reference profile, each baseline, and tempest P50 and a 1,024-run ensemble.
1. **Outcome difference from the reference day:** apogee (ft), max Mach, rail-exit velocity (ft/s), landing drift (m).
2. **Physical plausibility of the ensembles:** hydrostatic residual, superadiabatic-layer fraction, and wind-shear exceedance of the reference day's 99th percentile, for tempest vs Baseline 3.
3. **Where the reference outcome falls in the tempest ensemble:** the 50%, 80% and 95% intervals. **Reported only (no pass/fail)**, because the reference days are development data.
* **Pass (initial, frozen after a 20-case pilot):** tempest P50 median apogee difference is lower than ISA-1976's in every season, with the ratio reported (target at least **30%** lower); tempest ensembles show no hydrostatic violations and a shear-exceedance rate within **±25%** of the reference days; the ensembles are no narrower than Baseline 3 where physics demands coupling (landing drift and shear).

---

### Part C: Monte Carlo workflow, sensitivity and post-processing (about 1,024 runs per scenario)

Every scenario below uses **about 1,024 runs** (Saltelli runs are sized to fit that budget). With the sanity-check integrator this is minutes, not days; RASAero is used only for the small spot-checks in Part A and C5.

#### Test C1: Coupled P10/P50/P90 vs naive marginal P10/P50/P90 ("Franken-day" proof)
* **Run:** a 1,024-run Monte Carlo from `launch.atmospheres(1024)` gives the distribution of four outcomes (apogee, landing drift, rail-exit dynamic pressure, maximum angle of attack at max-q). Compare its 10th/50th/90th percentiles with single runs from `launch.weather(ras_profiles=True)` (coupled) and `launch.weather(percentile=[10, 50, 90], marginal=True)` (uncoupled).
* **Deliverable:** a table showing how closely 3 coupled runs approximate the 1,024-run percentiles, against the marginal version.
* **Pass (initial):** coupled errors are smaller than marginal errors for landing drift and apogee at P10 and P90.

#### Test C2: Sensitivity (Spearman, partial correlation, Sobol)
* **Run:** from the `draws.csv` schema (Schema 2), compute Spearman rank correlations and partial correlations between atmosphere features (`pad_rho_kgm3`, `wind_10m_ms`, `uniform_wind_ms`, `max_shear_s1`, `jet_max_ms`, `mode_z1..z6`) and the outcomes, on the 1,024 runs. For first-order and total Sobol indices use a Saltelli/Jansen design with base 128 and 6 inputs (128 × 8 = 1,024 runs), driven through `sample_sobol`.
* **Expected signs (plausibility):** apogee correlates with pad density/temperature and (negatively) pad wind; rail-exit stability with 10 m wind and gust; peak bending load with shear, gust and jet maximum near max-q; landing position with `uniform_wind_ms` and `uniform_wind_from_deg`.
* **Pass (initial):** the expected signs hold; `uniform_wind` terms explain at least **70%** of landing-position variance (R²) for V2 (raise the target after the pilot if it is easily met). Sobol indices are only reported for the orthogonal modes `mode_z1..z6` (they are invalid for correlated raw inputs).

#### Test C3: Convergence of pseudo-random vs Latin hypercube vs scrambled Sobol
* **Run:** reference = one 1,024-run set. For $N \in \{16, 32, 64, 128, 256\}$ over 10 replications (different seeds, using F1/F2 block seeds), estimate the mean landing point, the 95% ellipse area and the P99 apogee under (1) pseudo-random `atmosphere_set(N)`, (2) 1-D stratified whole-sample (`Batch.sorted_by("drift_proxy")`), (3) scrambled Sobol (`sample_sobol`).
* **Pass (initial):** error keeps shrinking across successive batches (no plateau; this checks F1), with fitted log-log slope at least **-0.4** for pseudo-random and a steeper slope for Sobol; report the sample-size reduction factor (e.g., "256 Sobol runs match about 1,024 random runs" if it holds).
* **Caveat in the report:** with a 1,024-run reference, errors below the reference's own error cannot be resolved; mark any such point as "at the noise floor".

#### Test C4: Launch-window uncertainty and morning conditioning (sharpness only)
* **Run:** for 10 reference days, 1,024-run landing ellipses at four stages: **1** climate mode over a 3-day `Window`; **2** climate mode at the exact launch hour; **3** forecast mode two days out; **4** conditioned mode (`observe(...)` with a supplied example sounding and pad observations taken from data already on disk, not newly collected).
* **Pass:** the 95% and 99% ellipse areas shrink in order Stage 1 > Stage 2 > Stage 3 > Stage 4 on at least **8 of the 10** days. Because the spec says conditioning is not yet validated, the report states that the stage-4 result is a plumbing check.
* **Removed:** the "true landing point lies inside the 90% ellipse" criterion, since it needs observational truth.

#### Test C5: Outlier forensics ("why did run #k fail?")
* **Run:** 1,024 trajectories; take the 5 worst runs by landing distance or by max-q times angle of attack. Using `run_id` alone, rebuild each atmosphere (`atms[k]` or `engine.sample_sobol(..., run_ids=[k])`), export it with `to_openrocket_csv`, and re-fly it.
* **Pass:** the rebuilt atmosphere reproduces the original outcome within **0.1%** in the sanity-check integrator (and in RASAero for the 5 runs where `run_ras` is available).

---

### Pass thresholds: how they are handled
Every number marked "initial" is set before the full run from a **20-case pilot** and then frozen; any later change is logged in the report with the reason. A test that fails is reported as failed, not retuned to pass.

### Summary checklist for Claude's validation report

When Claude finishes Section 2 it writes `Validation/out/FLIGHT_SIM_VALIDATION_REPORT.md` (nowhere else) containing:
1. **Format & schema table** (A4): zero NaNs, exact unit round trips, clean parses; plus the RASAero import check where `run_ras` is available.
2. **Pressure & density audit** (A1): `to_ras()` and `to_openrocket()` give matching pad air densities in the simulators that ran, and which tests were SKIPPED.
3. **Uniform wind drift benchmark** (A2): median and 95th-percentile drift error across A, B, C and D for V1, V2 and V3.
4. **Sign and frame check** (A3).
5. **Standard-atmosphere comparison** (Part B): outcome differences and plausibility rates on the reference set, clearly labelled development data.
6. **Monte Carlo results** (Part C): coupled vs marginal table, sensitivity table, convergence table with the reduction factor, the four-stage ellipse areas, and the forensics reproduction check.
7. **Isolation result:** the `check_isolation.py` output showing nothing outside `Validation/` changed.
