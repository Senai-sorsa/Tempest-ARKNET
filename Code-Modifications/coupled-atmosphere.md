# Coupled atmosphere for Monte Carlo

Spec, 2026-11-04. Covers two repos:
- **Tempest-ARKNET** (commit `ba2e2df`): what it writes.
- **tamusrt/flight_sim** (commit `8b828a3`): how EDITH, the Monte Carlo campaign runner, and the sim read it.

Builds on `claude-recommendations-v2.md` (gusts) and `atmosphere-outputs.md` (p, rho, a, vertical wind, soak).

## The problem

In the real atmosphere, the quantities a rocket feels move together:
- wind at one height goes with wind at the next (shear is limited);
- temperature goes with density, pressure and speed of sound;
- hot afternoons come with deeper thermals, gustier surface wind and warmer propellant;
- the jet stream's speed goes with the temperature structure around it.

A Monte Carlo is only accurate if every run gets a set of values that **really occurred together**.

Two places in the current plans would break that:

1. **Tempest's `dynamics` TOML** stores a mean and standard deviation per variable and height. Drawing from those independently is the zig-zag problem again, across variables as well as heights.
2. **EDITH's sampler** (`src/edith/sampler.py`) is planned as "Latin hypercube samples per variable". If launch temperature, pressure, humidity and wind speed each become separate dispersion variables, every run gets a combination that did not happen together. Example: a cold-day density with a hot-day thermal and a mild-day wind.

## The rule

**The coupled unit is one whole Tempest sample.** One Monte Carlo run draws one sample index `k`, and **every** atmospheric quantity in that run comes from sample `k`:
- wind and vertical wind at every height;
- temperature, pressure, density and speed of sound at every height;
- surface values;
- the gust distribution;
- thermals;
- the soak history, which also feeds the motor model.

Nothing atmospheric is dispersed on its own. Vehicle dispersions (mass, drag coefficient, thrust tolerance, rail angle) stay independent, as they really are.

The samples themselves are coupled already. The generator produces whole columns, range calibration keeps each sample's rank order (ensemble copula coupling), and the derived outputs are computed from the same sample (`atmosphere-outputs.md`). This spec makes sure that coupling survives into the sim.

## Part 1: what Tempest writes

### 1a. The samples file (the thing the Monte Carlo uses)

`atmosphere_samples.npz` (numpy only, so the portable tool needs no extra dependency). Every array has the sample as its first axis, so index `k` is one coupled atmosphere.

| Key | Shape | Units | Notes |
|---|---|---|---|
| `height_agl` | (44,) | m | heights above ground |
| `height_asl` | (44,) | m | `site_elevation + height_agl`; flight_sim works in geometric altitude above sea level |
| `u`, `v`, `w` | (n, 44) | m/s | east, north, up (`w` = resolved part) |
| `T`, `p`, `rho`, `a` | (n, 44) | K, Pa, kg/m3, m/s | p, rho, a derived from the same sample |
| `RH` | (n, 44) | % | over liquid water |
| `w_sigma`, `w_turb` | (n, 44) | m/s | thermals: spread and one height-correlated draw |
| `t2m`, `sp`, `rh2m` | (n,) | K, Pa, % | surface |
| `gust_mu`, `gust_beta` | (n, g) | m/s | Gumbel parameters of the largest 3-s gust at the g near-ground heights |
| `gust_heights` | (g,) | m AGL | |
| `soak_t2m`, `soak_ssrd`, `soak_wind10` | (n, 24) | K, W/m2, m/s | 24 h before launch, hourly |
| `T_soak` | (n,) | K | lagged soak temperature (tau from metadata) |
| `weight` | (n,) | - | sample weights; all 1 unless conditioning or tail oversampling is used |
| `member` | (n,) | - | which of the 4 trained copies made it |
| `drivers` | (n, 5) | - | the ONI, WWV, QBO30, QBO50 and warming values this sample used |
| `stratum_key` | (n,) | m/s | see 2b |

Metadata (a JSON string inside the file):
- query: lat, lon, valid time, site elevation;
- answer: `mode`, `kind`, source line;
- provenance: model hash, calibration fit years, Tempest version;
- settings: `tau` for the soak value;
- `"coupling": "whole-sample"`.

### 1b. Coupling values (to inspect and to check)

Written next to the samples as `atmosphere_coupling.npz`, plus a readable summary in the TOML. Every value is computed **from the samples**, so it describes exactly what the Monte Carlo will see.

| Name | Shape | What it says |
|---|---|---|
| `corr_vars_at_height` | (44, V, V) | correlation between variables at each height, V = u, v, w, T, p, rho, a, RH |
| `corr_heights[var]` | (44, 44) per variable | how each variable at one height moves with itself at others (vertical coupling, shear) |
| `corr_full` | (8·44, 8·44) | all variables at all heights at once |
| `corr_surface` | (S, 8·44) | surface and scalar quantities against every profile value; S includes t2m, sp, rh2m, gust_mu, T_soak, the boundary-layer w_sigma maximum |
| `spearman_*` | same shapes | rank correlations of each of the above; these capture non-straight-line dependence, such as humidity capped at 100 % |
| `eof_modes` | (K, 8·44) | principal patterns of joint variation (standardised), K reaching 99 % of variance |
| `eof_variance` | (K,) | share of variance per mode |
| `eof_scores` | (n, K) | each sample's amount of each pattern |
| `shear_stats` | per variable | quantiles of height-to-height steps (50, 90, 99, 99.9 %) |

The TOML gets a short `[coupling]` table with three things:
- the first 3 modes, as plots-worth of numbers per height;
- the key correlations: u at 1 km vs 10 km, T vs rho per height band, t2m vs T_soak, t2m vs gust_mu, t2m vs boundary-layer w_sigma;
- the samples file name, n, and its sha256.

**These numbers are for checking and understanding, not for drawing new atmospheres.** Rebuilding atmospheres from correlations loses the non-bell-curve shapes and the extremes. The Monte Carlo draws whole samples.

The existing mean/std tables stay, labelled `display_only = true`, with a comment that sampling them independently breaks coupling.

## Part 2: how EDITH and flight_sim use it

### 2a. New flight_sim models

Both read one sample from the file and are built per run.

- **`TempestWind(WindModel)`**: `velocity(altitude_m)` returns `(u, v, w + w_turb)` interpolated in height. Interpolate linearly in height. Below the first height (10 m), use the 10 m value. Above 18 km, hold the 18 km value and blend to zero difference from the top over 2 km (document it; it matters only for vehicles above 18 km). Gusts are added near the ground by the gust model (2c).
- **`TempestAtmosphere(AtmosphereModel)`**: `conditions(altitude_m)` returns temperature, pressure, density and speed of sound. Rules:
  - interpolate T linearly and p in log space;
  - recompute rho and a from the interpolated T and p (and the interpolated humidity), so all four stay consistent between grid heights;
  - above 18 km, continue with `StandardAtmosphere1976` scaled to match T and p at the top height, so there is no jump.
  - `anchor(launch_altitude_m)` checks that the sim's launch elevation matches Tempest's site elevation within 10 m, and raises an error otherwise. A mismatch would shift every height.

Both models take the sample index in their configuration, so a run's TOML records exactly which atmosphere it flew.

### 2b. EDITH: one dispersion dimension for the whole atmosphere

- The atmosphere is **one** dimension of the Latin hypercube, not one per variable.
- To keep the Latin hypercube's even spread, the samples are sorted by `stratum_key`, a single number per sample that tracks how hard the atmosphere pushes the rocket. Default: the mean wind speed over 0–3 km above ground, a setting. Later, once the decision layer is built, it can be the vehicle's own sensitivity-weighted wind.
- The hypercube value `x` in [0, 1) for run `i` picks the sample at rank `floor(x * n)`. Calm, typical and windy atmospheres are then each covered in proportion, and every run still gets a whole real sample.
- If the campaign has more runs than samples, ask Tempest for more samples (it makes 1,024 in milliseconds). Reusing a sample would count one atmosphere twice.
- If `weight` is not all 1, EDITH uses the weights in every statistic it reports. This happens with launch-commit conditioning or tail oversampling.

### 2c. Gusts, thermals and soak inside a run

- **Gust:** run `i` draws its gust from sample `k`'s Gumbel (`gust_mu[k]`, `gust_beta[k]`) using the run's own random stream. This is the only fresh randomness, because a gust is short-lived turbulence within that atmosphere. Its strength still comes from sample `k`, so a calm sample cannot produce a storm gust. Apply it in the wind's direction, over the rail and first seconds of flight.
- **Thermals:** use `w_turb[k]` as given (it is already one height-correlated draw). For a parachute descent, hold each value over an altitude change about the size of the boundary layer, as `atmosphere-outputs.md` describes.
- **Soak:** the motor model takes `T_soak[k]` (or the full `soak_*[k]` history, for the propulsion team's own thermal model) from the **same** sample. So the warm-day thrust curve flies through the warm-day air. A thrust tolerance stays a separate vehicle dispersion on top.

## Part 3: tests

Hold-out years as in the other specs (fit 2021–23, test 2024–25).

**Tempest side, coupling accuracy:**
1. **Cross-variable:** `corr_vars_at_height` from the samples vs the same correlations in real held-out cases (ERA5, and balloons for u, v, T, RH, p) for the same season and hour. Report the largest differences per height band, with bootstrap intervals.
2. **Vertical:** `corr_heights` vs real cases; shear quantiles (99, 99.9 %) vs balloons.
3. **Surface to aloft:** t2m vs boundary-layer w_sigma, t2m vs gust, t2m vs T_soak, all against observations (ASOS, high-resolution balloons, ERA5).
4. **Physical consistency, per sample:** hydrostatic check (p vs T), `rho = p / (Rd Tv)`, and `a` from T. These should hold to rounding.
5. **Joint scores:** energy score and variogram score, already in the scorecard, reported for the new variables too.

**Sim side, coupling survives:**
6. **Unit test in EDITH:** every model in run `i` reports the same sample index and the same file hash.
7. **Interpolation test:** `TempestAtmosphere` at the 44 grid heights returns the file's values exactly. Between heights, rho and a stay consistent with T and p.

**End to end, the point of all this:**
8. For a set of held-out real days, take the real profiles (ERA5 corrected toward balloons) and fly the vehicle through them. That gives the "true" landing scatter. Then run three campaigns for the same days:
   - **(a)** whole-sample coupling;
   - **(b)** per-variable independent draws from the same samples' means and stds;
   - **(c)** standard atmosphere plus uniform wind.

   Compare the landing scatter's size, shape and 99 % ellipse with the true scatter, using the energy score on landing points. Coupling (a) must beat (b). The size of that gap is the evidence for doing it this way.

## Build order

| Step | Repo | Content |
|---|---|---|
| 1 | Tempest | samples file with the current variables + metadata + `stratum_key`; display-only flag on mean/std |
| 2 | Tempest | coupling file and `[coupling]` summary; tests 1, 2, 4, 5 |
| 3 | flight_sim | `TempestWind`, `TempestAtmosphere`; tests 6, 7 |
| 4 | flight_sim | EDITH single atmosphere dimension with stratified rank selection |
| 5 | both | new outputs as they land (p/rho/a first, then w, gusts, soak); test 3 |
| 6 | both | end-to-end test 8 |

Steps 1–2 can start now with the outputs that exist. Steps 3–4 should be agreed with whoever owns EDITH before its sampler is written, so the atmosphere is not split into separate dispersion variables.
