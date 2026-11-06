# Improvement loop 2 (user, 2026-11-06): synthesise hybrids from partial positives, test the best, keep going

Rule from the user: scrape the useful part out of past tests that had something positive but needed fine-tuning, combine or restrict them into better ideas, test the best of these together with the best of the existing not-yet-tested alternatives, and keep this as a standing loop. Same verdict rules as before (headline rule + shape rule with the seed spread as tolerance, `docs/results/APPLIED_STATUS.md`); every kept item stays an opt-in flag until the end; nothing touches 2026 January-June again (the final test is done; new keeps are judged on 2024-25 and described as such).

## How a round works
1. **Harvest:** list every earlier result with at least one clearly positive number (a metric better than the seed spread) next to a negative one.
2. **Synthesise:** for each, write the hybrid that keeps the positive and removes or softens the cause of the negative (restrict to the bands or variables that gained, damp the strength, combine with the partner that fixes the weak metric).
3. **Rank** by expected gain on the main target (distribution shape), cost and risk; add the best untested alternatives from `SIDELINED.md`.
4. **Test** the top ones (one GPU job at a time, CPU tests meanwhile), log each as an `L2-n` row in `AUTOPILOT.md`, then harvest again from the new results.

## Harvest of partial positives (round 1)
| Source | Positive | Negative | Hybrid |
|---|---|---|---|
| IL-86 PIT recalibration | per-level coverage error 0.0123 -> 0.0101, tail-rate error -26 %, skew and kurtosis better | PIT distance 0.0372 -> 0.0387 | **H1:** damped PIT map (half way) or tails only |
| Stack B (seasonal RH + surface widths) | cov error 0.0034 -> 0.0023, tail-rate -16 %, PIT better | event-coverage gap 0.059 -> 0.099 (rh2m surface) | **H1b:** seasonal widths for the RH profile only, no surface fields |
| F-15 (m = 8 final steps) | pre-clip RH share lower | vertical correlation slightly worse | **H4:** with F-19 at a milder dose |
| F-19 (RH in the loss) | PIT distance better | pre-clip share worse | **H4:** weight 0.1 plus final m = 6 |
| IL-101 (wind widening) | station-wind 90 % interval 59-80 % -> 88-89 % | wind only | **H3:** the same observed-spread widening for 2 m temperature at long leads (the tool's spread is narrow at 7 days) |
| IL-80 (network + ridge 50:50) | skill +0.005 ... +0.015, coverage at 7 d | one fixed weight | **H2:** weight per lead, and a third component (HRES + error pool) |
| IL-60 / IL-89 idea | shear gap strongest in winter | one map for all seasons | **H5:** shear map per season |
| F-20 station blend | temperature seam step 1.05 -> 0.78 | u 1-5 km 1.16 -> 1.31 | needs a retrain: parked |
| IL-10 trust layer | gains for u, v 0-1 km and surface | T 12-18 km lost | parked (already tried band-restricted) |

## Best existing untested alternatives taken in
- **IL-74 lead blending:** the tool switches from the forecast mode to the climate generator at 7.5 days; a smooth hand-over removes the jump in median and spread.
- **IL-79 mode F at any lead:** the tool uses the nearest of 1/3/5/7-day tables; lead as a continuous input.
- **IL-14 Chronos + ridge for ONI/WWV:** cheap, CPU.

## Round 1 order
H4 (GPU, running), H1 / H1b (diagnostics, CPU), H3 (backtest, CPU), H2 (mode F, CPU), H5 (shear map per season), IL-74, IL-79, IL-14.

## Round 2 harvest (2026-11-06 04:15)
- H1b (c4) beat c1 and c2/c3: seasonal widths work for RH above 1 km, fail only at 0-1 km. Next: **H1c** dose response of the PIT damp (0.75, 1.0 with the same seasonal) to see whether the gain keeps growing; **H1d** seasonal widths for T and wind profiles above 1 km (stack B only tried RH).
- H2 gave nothing; mode F is at its ceiling for mixing. No further mixtures.
- H4 (running/evaluating): if the milder RH loss improves PIT but not pre-clip, try RH loss weight 0.05 + 0.1 only in the last steps.

Round 2 results (04:55): H1b keep (opt-in); H4 rejected; H2 no gain; H5/IL-74/IL-79/IL-14 sidelined. Next candidates: H1c PIT-damp dose (0.75, 1.0) with the same seasonal; H1d seasonal widths for T and wind above 1 km.

## Round 3 close (2026-11-06 06:15)
H1 family closed with c4 kept; H6 monthly T shift: no gain. Gains in distribution shape from loop 2 are now saturating: every remaining hybrid moves metrics by less than the seed spread. What is left needs data or a retrain (F-17 CDS levels, R-8 night hours, R-3 more stations, IL-79 more forecast leads). The loop keeps harvesting after each of those lands.
