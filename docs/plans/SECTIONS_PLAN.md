# Sections plan: where each upgrade belongs (2026-11-07)

Source documents (in `Downloads/`, untouched): `tempest_weather_v2_master_upgrade_specification.md` (called **MASTER** below, item IDs F, S, R, N, I, M, C, U, T) and `validation_formatting_flight_sim_integration_spec.md`. The revised validation plan is `docs/plans/validation_formatting_flight_sim_integration_spec.md`.

**Status: plan only. Nothing here has been built or changed in code.**
**User decisions:** the usability design in MASTER Part 1 is **approved (2026-11-07)**. Any further change to it needs the user's confirmation first.

## The rule used to place items
- **Section 1 (finish building, make it correct):** things that are bugs or that change the numbers every later test depends on. Do them first, behind a flag that is off by default until verified (hard rule), so the frozen pilot model's results do not move.
- **Section 2 (make it flexible, fast, usable, proven):** capabilities, speed and the public interface, in this order: **flexibility, speed, usage, validation**. Anything that changes numbers comes before validation, or the validation has to be rerun.

## Section 1 additions (from MASTER)

| Item | What | Why it is Section 1 |
|---|---|---|
| **F3** | One sample schema for all producers and readers (`height_agl`, `height_asl`, `elevation_m`...) | Bug: readers raise `KeyError: 'height_asl'` on the tool's own output. Everything else reads this schema |
| **F1** | Key all engine and Dryden noise on a global `run_id` (counter-based RNG) | Bug: every batch reuses the same hidden noise (`seed + 31`, `seed + 47`, `turbulence_seed=0`). Any Monte Carlo run so far is affected |
| **F2** | Per-block seeds so `n=2048` starts with exactly the `n=1024` atmospheres | Same RNG rewrite as F1; results must not depend on batch size |
| **S1 + F9** | Exact AR(1)/AR(2) Dryden turbulence, no 4 km burn-in; run chunking in `float32` | Rewrites the same function as F1/F2 (`dryden.synthesize`), so do it once. It changes the random stream, so it must precede all validation. Verify variance and spectrum against the current Euler output first (the matrix algebra in MASTER is not yet checked) |
| **F6** | `eng.conditioned(obs)` returns a new engine instead of mutating `self._post` | State-mutation hazard when one engine is shared. The old method stays as it is; the new one is additive |
| **C3** | `check_outputs()` gate: no NaN/inf, RH 0-100, T 150-340 K, p > 0 and decreasing, rho > 0, a > 0, wind < 150 m/s | Cheap, protects every later test |

Flag handling: the new RNG streams, S1 and the schema are added behind a flag (default off) and the old behaviour stays selectable. Turn them on only after parity tests pass.

## Section 2, in order

### 2A. Flexibility (capabilities; several change numbers)

| Order | Items | Notes |
|---|---|---|
| 1 | **N1-N3, I1-I3** `_net.py` / `_files.py`: timeouts, retries, rate limits, offline mode, atomic writes, resumable downloads, cache self-repair | Foundation for elevation, forecasts and soundings, so it goes first. Single-process, no thread pools |
| 2 | **F7** reader `frame` / `units` / `reference` / `direction` | Applied once when the lookup tables are built. Sign errors are the top silent failure; the A3 test covers it |
| 3 | **F12** `above_top` policy | Make the top height a **parameter** (18 km now, 80 km after the A1 extension), not a constant |
| 4 | **R1** directional surface roughness z0 | Feeds Dryden and the sub-10 m wind. The NLCD map is US-only: add a default-z0 fallback and a "source" flag for other regions |
| 5 | **F13** engine over a `Window` | Needs the time-range design (Section 2C) but is built here |
| 6 | **F4** tail extrapolation | Use the **same** tail method as the model work (pooled EGPD, IL-103), not a second GPD on a 2,048-row pool. Applies when `n` exceeds the pool |
| 7 | **F5, R2** general observation operator and automatic morning sounding | Assumes Gaussian modes, so stays marked "not yet validated" until IL-33 passes. Test that strong observations do not collapse the spread |
| 8 | **F8, F10, F11** explicit columns / `k="auto"`, pad-elevation shift, Sobol stratification | Small, independent |
| 9 | **Region packs** | Move the pilot-only constants (solar-hours window, site list, time zones, DEM, roughness) into the asset pack manifest so the global stages can drop in |

### 2B. Speed (single process, no internal parallelism)

| Order | Items | Notes |
|---|---|---|
| 1 | **S2** 10 m `float32` lookup tables, vectorised lookups | Depends on F7 (frames and units baked in) and on the top-height parameter from 2A. Confirm every model height is a multiple of 10 m before relying on "zero interpolation loss" |
| 2 | **S3** cache the built engine on `Launch`; uncompressed `.npy` save/load | |
| 3 | **S4, S5** hash-check cache; partial final block | S5 only if it measurably costs time |
| 4 | **M1-M3** memory caps (`float32` pools, LRU cache limits) | Keep thermodynamic and hydrostatic maths in `float64` |
| 5 | **T1-T2** vectorised multi-query (`Launches`) | After S2/S3 |

Speed targets from MASTER: Dryden under 0.1 s per 64 runs (this lands in Section 1 via S1), 1,024 atmospheres cached after the first call, N = 10,000 under 1 GB peak.

### 2C. Usage (approved design; implement as written)

Implement MASTER Part 1 as approved: `Launch`, `Window`, `weather()`, `distribution()`, `couple()` (including `t_copula`), `atmosphere_set()`, the engine, result objects, plain names and units, local wall-clock time, helpful errors and trust line, provenance and save/load, the `tempest` CLI, the elevation lookup (`elevation.py`, with the tests in MASTER Part 4), the formatting rules and exports in the validation document Section 1 (RASAero, OpenRocket, CSV schemas), and packaging P-1 to P-11 plus versioning U1-U4.
Order inside 2C: elevation and time handling, then `weather()` and the exports, then `distribution()`/`couple()`, then `Launch` caching and the CLI, then packaging. **No usability behaviour is changed from what was approved without asking.**

### 2D. Validation (separate `Validation/` folder, touches nothing else)

The revised validation plan: formatting checks, RASAero and OpenRocket integration (RASAero through the user's hook), uniform-wind benchmark, sign/frame check, standard-atmosphere consistency comparison, and the Monte Carlo workflow at about 1,024 runs. Report goes to `Validation/out/`.

## Dependencies in one line
F3 -> F1/F2/S1 (+F9, F6, C3) = **Section 1**; then N/I -> F7 + top height -> R1/F5 -> S2/S3 -> usage -> validation.

## Not changed
`tempest/` (the research package), the trained models, the frozen pilot routing, and the gates in `docs/plans/fixing issues.md` are not touched by this plan.
