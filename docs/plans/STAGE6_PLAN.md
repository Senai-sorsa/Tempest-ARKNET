# Stage 6: tools for the flight simulator (blueprint adjusted and built, 2026-11-06)

Source: `C:\Users\Senai\Downloads\tempest_arknet_flight_sim_expansion_blueprint.md` (read after the final model, group E and group C were finished, as the user asked). Rules from the user: tools only, nothing vehicle-specific is trained into the weather model, no retraining, `observe()` by conditioning at sampling time, tail-directed importance sampling and the vehicle-sensitivity loss are discarded. Code: `tempest_weather/flight/` (numpy only). Tests: `tests/test_flight_engine.py`, `tests/test_flight_tools.py`. Evidence: `scripts/s6_condition_eval.py`, `data/s6_condition_eval.txt`.

## What was built, what changed against the blueprint, and why
| Module | Built | Changes against the blueprint |
|---|---|---|
| 1. Quasi-Monte Carlo sampler | `TempestFlightSimEngine.sample_sobol(u)`; pool of coupled atmospheres for one place and time, empirical marginals, eigen-ordered Gaussian copula | (a) The leading k modes take the simulator's uniforms; the **remaining modes get a seeded pseudo-random draw** so the full covariance is exact. The blueprint rescaled a truncated sum per column, which distorts the correlations between heights. (b) **Importance weights and tail stretching dropped** (the user discarded tail-directed sampling). (c) Marginals come from the pool itself (empirical), not from fitted parametric families, so the generator's calibrated tails are kept. (d) scipy is not used (`norm_ppf` / `norm_cdf` of the tool) so the folder stays numpy only. |
| 2. Measurement conditioning | `condition_on_observations(obs, sensor_sigma, inflate=1.5)`, `observe_by_weights(...)`; `u=None` gives the conditional median profile | Two methods were built and **tested on real balloons** (below): the closed-form Gaussian-copula (Schur) update wins; the pool-weighting version (the user's first idea) collapses. The Schur posterior is **inflated by 1.5** because the pure version was too sharp. Sensor noise is given in physical units, not as a latent number. |
| 3. Turbulence and gust | `dryden.synthesize(...)`, `dryden.envelopes(...)`, `dryden.one_minus_cos(...)` | (a) For a **vertical** path the component along the path is w (first-order filter, correlation exp(-d/L)); u and v are transverse (second-order filter, correlation (1 - d/2L) exp(-d/L)). The blueprint had it the other way round. (b) The second-order filter is integrated as a proper stochastic differential equation with sub-steps and its state is rescaled when the scale length changes with height (the blueprint's recurrence did not reproduce the Dryden spectrum). (c) The clear-air-turbulence term had the unit 1/s in the blueprint; here sigma_cat = shear x mixing length (20 m, an assumption) x (0.25 - Ri) / 0.25. (d) Gust peak 3-15 m/s from a fourth uniform instead of a fixed 8 m/s. Tested: variance and autocorrelation against the closed forms. |
| 4. Acoustic ray tracing | `acoustics.AcousticRayTracer.trace_ray_fan(...)` | Effective-sound-speed approximation with a conserved ray parameter cos(theta) / c_eff; turning rays are flagged as shadow zone; cross-wind advection added at first order. The blueprint's ray parameter and vertical-slowness formulas did not conserve the parameter in a wind-free medium. Tested: straight rays in still air, shadow zone for a ground-level jet downwind, cross-wind drift. Not modelled: absorption, boom steepening, ground reflection, 3D refraction, turbulence scattering. |
| 5. Avionics and radio | `avionics.compute(...)` | Barometric altitude by ISA inversion (troposphere and above 11 km), pad-zeroed AGL, altimeter bias, refractivity N, its gradient, effective-Earth-radius factor k, radio horizon. Sign convention tested: warm day = altimeter reads low, cold day = reads high. **ITU-R P.676 gaseous attenuation is not implemented** (it needs the line tables; guessing them would be worse than leaving it out). |

One call for a simulator: `eng.sample_sobol_batch(u_matrix, k_atmo=6, dz_fine_m=2.0)` returns the coarse batch (u, v, T, RH, p, rho, a on the 44 heights), `fine` (Dryden fields) and `avionics`. Columns 0..k_atmo-1 drive the atmosphere, four more columns (if present) place the 1-cos gust.

## Evidence for module 2 (real balloons, held-out)
Setup: 2024-25 00Z soundings at Santa Teresa and Midland; for each, a pool of 1,024 atmospheres from the climate generator for that place and date (no forecast); measurements taken from the balloon with sensor noise added: 2 m temperature, 10 m wind, surface pressure and a partial sounding of u, v, T at 500, 1000, 1500, 2000 m. Scored above 2.5 km, where nothing was measured. The inflation factor was chosen on one subset (60 soundings) and the numbers below are from another (100 soundings).

| Variable, band | CRPS vs unconditioned | 90 % interval coverage |
|---|---|---|
| T 2.5-12 km | -16.8 % | 0.889 |
| T 12-18 km | -8.5 % | 0.905 |
| u 2.5-12 km | -13.6 % | 0.905 |
| u 12-18 km | +2.1 % (worse; no information reaches it) | 0.888 |
| v 2.5-12 km | -20.2 % | 0.922 |
| v 12-18 km | -5.7 % | 0.913 |

Pool weighting (the user's first idea): with eight to fifteen measurements the effective sample size is 1 of 1,024 and the result is far worse than no conditioning (CRPS worse by 34 % to 80 %), so it is kept only as a documented alternative for one or two soft measurements. The pure Schur update (no inflation) improved CRPS as much but its 90 % interval held only 80-86 % of the balloons.

## Limits and open points
- The pool is the climate/forecast mixture the tool already serves; conditioning improves a **climatological** atmosphere with measurements. If the forecast mode is available (0.75-7.5 days) the pool is already forecast-centred and the gain from the same measurements will be smaller (not measured).
- Turbulence intensity uses the neutral log law and a mixing length (assumptions); it is not validated against tower or aircraft data (none available here).
- Acoustic rays and the altimeter bias are physics-checked, not checked against flight data (no simulator or flight logs in the repo).
- Hours outside 06-21 solar are refused by the tool, so pad conditioning at night is not possible.
- Group C (hourly and downrange coherence) is separate: `api.atmosphere_sequence` / `api.atmosphere_downrange`. The engine does not use them yet (a trajectory that crosses hours or distance would need the two combined).
