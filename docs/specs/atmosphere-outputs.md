# New atmosphere outputs: density, pressure, speed of sound, vertical wind, soak temperature

Build spec, 2026-11-04, against commit `ba2e2df`. Adds five outputs for the flight sim, for **every mode, including
past dates**. Same rules as `claude-recommendations-v2.md`: honest split (train <= 2020, fit 2021-23, test 2024-25),
one change at a time, log every result in PLAN.md.

## Summary

| Output | Key | Units | How | Retrain? |
|---|---|---|---|---|
| Pressure at each height | `p` | Pa | derived: hypsometric integration up from surface pressure | no |
| Air density at each height | `rho` | kg/m3 | derived: ideal gas with virtual temperature | no |
| Speed of sound at each height | `a` | m/s | derived from virtual temperature | no |
| Vertical wind, resolved | `w` | m/s, + up | ERA5 vertical velocity, new 5th profile variable | yes |
| Vertical wind, thermals | `w_sigma`, `w_turb` | m/s | convective boundary-layer scaling, per sample | no (new surface targets, see 4) |
| Soak temperature | `soak` block | K, W/m2, m/s | 24 h of pad weather before launch + a lagged soak temperature | no |

**Key rule:** every output is computed **from the same sample profile**, never drawn on its own. A hot afternoon
must come with lower density, more thermals and warmer propellant in the same sample. That is what makes the Monte
Carlo realistic.

## 1. Pressure, density, speed of sound (derived)

New module `tempest/profiles/thermo.py`, copied into `tempest_weather/profiles.py` with the other copied functions
(TOOL_PLAN). It is covered by the parity test, so the two copies cannot drift.

**Inputs per sample:** surface pressure `sp`, `t2m`, `rh2m` at the site (after `sample.to_site`), and profile
`T`, `RH` at the 44 heights above ground. Site elevation `z0`.

**Steps (vectorised over samples):**
1. Saturation vapour pressure over liquid water (same formula as `to_heights.liquid_rh`; RH is over liquid since
   log item 6): `es(T) = 611.21 * exp(17.502 * (T - 273.16) / (T - 32.19))` Pa.
2. Vapour pressure `e = RH/100 * es(T)`; specific humidity `q = 0.622 e / (p - 0.378 e)`.
3. Virtual temperature `Tv = T * (1 + 0.608 q)`.
4. Gravity at geometric height (heights are geometric, `to_heights.geometric_height`):
   `g(z) = 9.80665 * (R / (R + z0 + z))**2`, `R = 6,371,000 m`.
5. Integrate from the ground (level 0 = surface: `sp`, `t2m`, `rh2m`) up through the 44 heights:
   `p[k+1] = p[k] * exp(-g_mid * dz / (Rd * Tv_mid))`, `Rd = 287.05 J/(kg K)`, `Tv_mid` = mean of the two levels.
   `q` depends on `p`: do one fixed-point pass (compute `p` with `q` from the previous pass); one pass is enough.
6. Density `rho = p / (Rd * Tv)`.
7. Speed of sound `a = sqrt(1.4 * Rd * Tv)`. The moist-air correction to gamma is under 0.3 %; ignore it unless
   the test below says otherwise.

**Decision change:** design review item 12 planned pressure-at-height as a learned 5th profile variable. Deriving it
instead is hydrostatic by construction, needs no retraining, and makes recommendation A6 (hydrostatic penalty)
unnecessary for pressure. Record this in PLAN.md. Surface pressure stays the only learned pressure.

**By mode:**
- Mode 1 (past): apply `thermo` to the ERA5 profile at that hour. Check value: ERA5's own pressure at each height
  (interpolate ln p against geometric height from the pressure levels).
- Mode 2 (0-15 days): Open-Meteo members come on pressure levels, so pressure is native. Still compute `rho` and
  `a` with the same functions, so all modes agree.
- Modes 3-4: apply `thermo` to every generated sample.

**Tests:**
- Unit: a dry isothermal column matches the exact exponential; the US Standard Atmosphere 1976 T profile reproduces
  its tabulated p and rho to < 0.1 % up to 18 km.
- ERA5 2024-25: derived p vs ERA5 interpolated p, error per height (expect well under 1 hPa near the surface,
  growing slowly with height).
- Balloons 2024-25: IGRA reports p, geopotential height, T and humidity, so compare derived `p` and `rho` at the
  balloon's heights. Report bias and spread per height band.
- Distribution: rank histograms of `rho` per height band against balloons (same checks as recommendation A1).

## 2. Vertical wind, resolved part (`w`, learned)

ERA5 gives grid-scale vertical motion (pressure velocity `w`, Pa/s, on pressure levels). It is small (centimetres
to decimetres per second) but organised: terrain-forced flow, monsoon convection, fronts.

**Data changes:**
- `fetch_earthmover.py`: add `"w"` to `PRESSURE`. Earthmover's `pressure/temporal` group lists it (PLAN *Data*).
  For the CDS boundary-layer fill, add vertical velocity to the request in `fetch_cds`.
- `to_heights.py`: interpolate `w` like the other profile variables, then convert to m/s:
  `w_z = -omega / (rho * g)`, with `rho` from section 1 at that level. Add `w` to `PROFILE`.
- `build_dataset.py`: `w` as a 5th profile variable (surface value + 43 neighbour differences, like the others).
  Outputs grow from 179 to 223.

**Training:** retrain B0 settings with `w` added (~13 min for 4 members on the laptop). Watch for harm to the
other variables: `w` is noisy and could pull capacity. If they get worse beyond the intervals, give `w` a smaller
loss weight (a per-variable weight is already discussed in design review item 6).

**Past mode:** the ERA5 `w` profile at that hour, plus the station-error treatment of the other variables. IGRA has
no `w`, so the error part is from the turbulence term in section 3.

**Tests:** on ERA5 2024-25, CRPS skill of `w` against recent climatology per height band, and no other variable's
skill or coverage gets worse. Expect `w` skill near zero at long leads; its value is a correct, coherent spread.

## 3. Vertical wind, thermals (`w_sigma`, `w_turb`)

Desert afternoon thermals reach several m/s, far more than ERA5's grid-scale `w`. They change time under the
parachute, and so drift. They are sub-grid, so they come from **convective boundary-layer (CBL) scaling**, applied
per sample, not from a network.

**Inputs per sample:** boundary-layer height `zi` (ERA5 `blh`) and surface sensible heat flux `H` (ERA5 `sshf`,
accumulated J/m2; divide by the accumulation period and flip sign so upward heat is positive).
- Add `blh` and `sshf` to `SINGLE` in `fetch_earthmover.py` (check both are in `single/temporal`; `blh` is listed in
  PLAN *Data*; if `sshf` is missing, take it from CDS).
- Modes 3-4 need them per sample: add `blh` and `H` as two extra **surface targets** at the same retrain as section
  2, so they stay consistent with the sample's temperature and wind.

**Model:**
1. Convective velocity scale `w* = (g / T * (H / (rho * cp)) * zi) ** (1/3)` when `H > 0`, else 0 (stable: no
   thermals). `cp = 1004 J/(kg K)`.
2. Standard deviation of vertical wind inside the boundary layer, from the published CBL profile shape (Lenschow
   et al. 1980 form): `w_sigma(z) = w* * 1.8 * (z/zi)**(1/3) * (1 - 0.8 z/zi)`, for `0 < z < zi`; a small floor
   above `zi`. **Verify the coefficients against the source and refit them on the test data below before use.**
3. Thermals are skewed: narrow strong updrafts, broad weak downdrafts. Sample `w_turb` from a skewed distribution
   with that standard deviation (start with a two-Gaussian mixture, updraft area ~40 %), skewness fitted on data.
4. Output per sample: `w_sigma` (44,) and one `w_turb` draw (44,) that is correlated in height (thermals span the
   boundary layer: use one random thermal phase per sample through the depth, not independent draws per height).

How the sim should use it (for the `dynamics` side, later): add `w + w_turb` to the vertical wind. A parachute
falling at ~5-10 m/s drifts through thermals of size ~`zi`, so the sim can hold one draw over that size of altitude
change.

**Truth and tests:** NWS high-resolution (1-second) radiosondes at Santa Teresa and Midland. A balloon's rise rate
minus its expected rise rate is an established estimate of vertical air motion. On 00Z soundings (~17-18 h local,
still convective in summer), in the boundary layer: compare the variance of rise-rate anomalies with
`w_sigma(z)` by season, and refit the coefficients and skewness on 2021-23, test on 2024-25. Keep the term only if it
matches better than "no thermals" and better than a constant.

## 4. Soak temperature (pad weather before launch)

Propellant and tank temperature depend on the hours before launch, not the launch moment. Tempest supplies the pad
weather history; the propulsion team's thermal model turns it into grain or tank temperature.

**Output (`soak` block) per sample:**
- `t2m_hist` (24,): hourly 2 m temperature for the 24 h before launch;
- `ssrd_hist` (24,): hourly surface solar radiation (sun on the pad, W/m2);
- `wind10_hist` (24,): hourly 10 m wind speed (convective cooling of the vehicle);
- `T_soak`: a convenience value, the exponentially weighted mean of `t2m_hist` with time constant `tau` (a setting
  for the propulsion team to choose; no default is invented here), plus the 24 h min and max.

**Data changes:** add `"ssrd"` to `SINGLE` in `fetch_earthmover.py`. Note that `to_heights` keeps only UTC 12-04
(daytime) hours, but the raw pull in `data/raw/era5_em/` keeps all hours. Write a small
`tempest/profiles/surface_hourly.py` that writes `data/pilot/surface_hourly.zarr` (t2m, ssrd, u10, v10, all 24 hours,
per grid point) from the raw files. It is small.

**By mode:**
- Mode 1 (past): read the 24 h directly from `surface_hourly.zarr` (or Open-Meteo's archive after the store's end),
  moved to the site elevation like `t2m` (`sample.to_site`).
- Mode 2 (0-15 days): each ensemble member's hourly t2m, shortwave radiation and 10 m wind for the 24 h before
  launch (Open-Meteo ensemble API; confirm the radiation variable is served for the chosen models, else use
  ERA5 climatology of `ssrd` for that day and cloud-free fraction).
- Modes 3-4: the generator gives only the launch hour. Use a **diurnal history library**: for each sample, take real
  ERA5 24 h histories from the same grid point, within +/-15 days of the season, from training years only; pick one
  at random among the K whose launch-hour `t2m` is closest to the sample's `t2m`; shift its `t2m_hist` by the
  difference; keep that day's `ssrd_hist` and `wind10_hist` unchanged. The shapes stay real (night cooling, sunrise,
  clouds), and they match the sample.

**Tests (2024-25 held out):** for each test day, build `soak` from the method and score against ERA5's real 24 h
history: CRPS and 90/99 % coverage of `T_soak` (for a few `tau` values) and of the overnight minimum. Mode 1: compare
`t2m_hist` with the nearest ASOS station's hourly temperatures. Choose K on 2021-23.

## 5. Output format

`distribution()` gains (n = samples, 44 heights):

| Key | Shape |
|---|---|
| `p`, `rho`, `a` | (n, 44) |
| `w`, `w_sigma`, `w_turb` | (n, 44) |
| `soak.t2m_hist`, `soak.ssrd_hist`, `soak.wind10_hist` | (n, 24) |
| `soak.T_soak`, `soak.t2m_min24`, `soak.t2m_max24` | (n,) |

Mean, std, p005 and p995 per height for each, as for the existing variables. `values()` returns the same keys, as
the per-height median (past mode: the actual values). The `dynamics` TOML gains `[atmosphere_profile]` (mean/std of
`p`, `rho`, `a`, `w` per height) and `[soak]`.

Out of scope here, needed later on the `dynamics` side: a sim atmosphere model that reads `rho`, `p` and `a`
profiles instead of `StandardAtmosphere1976`, a vertical-wind term, and the propulsion thermal model that reads
`[soak]`.

## 6. Build order

| Step | Content | Retrain? | Check |
|---|---|---|---|
| 1 | `thermo.py` (p, rho, a) + unit tests; apply in score/sonde and mode 1 | no | section 1 tests |
| 2 | `surface_hourly.zarr` + `ssrd` pull; soak for mode 1, then the diurnal library for modes 3-4 | no | section 4 tests |
| 3 | Pull `w`, `blh`, `sshf`; rebuild profiles and dataset; retrain with `w`, `blh`, `H` | yes, one | section 2 tests; no other variable worse |
| 4 | Thermal term (`w_sigma`, `w_turb`); fit on high-res soundings 2021-23 | no | section 3 tests on 2024-25 |
| 5 | Mode 2 versions of all five, in the tool | no | coverage on the logger archive |

Steps 1 and 2 need no new model and can start now. Step 3 should share its rebuild with the CDS boundary-layer merge
(design review item 2), so the dataset is rebuilt once.
