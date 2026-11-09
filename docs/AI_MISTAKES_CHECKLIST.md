# Common AI / ML mistakes and our own past mistakes: the checklist

Use: after every 3 trials (a trial = one experiment, fix or idea that produced a verdict), run section C on the last three and add one dated line to section D. If an item fails, fix the claim or the work before moving on.

## A. Common mistakes (any AI-assisted or ML work)
1. **Truth contamination / leakage.** The reference data was already used by the thing being tested (assimilated, trained on, or tuned against). Ask: did the model or the comparison source ever see this truth?
2. **Fit and test overlap.** Anything fitted (weights, scales, thresholds, gates) must be fitted on years or cases that are not the scoring cases. Count the years.
3. **Reusing the dev test set** for many decisions: its scores drift optimistic. Note how many decisions have used it.
4. **Single seed, tiny gain.** A change smaller than the seed-to-seed spread is not a result. Compare with the measured noise (paired day-block sd), not with zero.
5. **Several changes in one run.** The gain or loss cannot be attributed. Say so, or run them one at a time.
6. **Wrong or weak baseline.** Compare with the strongest simple baseline (climatology, persistence, the previous best), on exactly the same rows.
7. **Averages hiding the damage.** A mean gain can hide a loss in one band, variable, regime or tail. Look at every band and at the tails.
8. **Metric not matching the goal.** Skill on levels is not skill on apogee, shear or the 10 m wind. Say which metric answers the real question.
9. **Silent fallback.** A path quietly does something else (climate instead of past, default instead of measured). Every fallback must be loud (warning, flag, trust line).
10. **Units, signs, frames.** Scale factors (0.1 m/s), wind "from" vs "to", feet vs metres, geometric vs geopotential height, UTC vs local, ASL vs AGL. Check one number by hand.
11. **Overclaiming.** "Done", "validated", "better" without the run, the numbers or the caveat. State what was tested and what was not.
12. **Stale or wrong memory of the code.** Re-read the file before editing or describing it; a summary can be wrong.
13. **Untested edge path.** The tests pass but never reach the new code path (a flag that is never switched on, a fake fetch that hides the live format). Run the real path once.
14. **Confusing a lab condition with the real use.** Near-analysis is not a day-ahead forecast; station sites are not the launch pad; 21 levels are not 44.
15. **Optimising what is easy to measure.** More samples, more weight on a loss term, a different threshold: ask whether the mechanism of the error was found first.
16. **Hidden randomness.** Seeds, draw order of sampled cases, hash-ordered sets. Reproduce a number before trusting it.
17. **Data quality.** Missing values encoded as numbers, NaN holes, duplicates, partial downloads, wrong time stamps. Count them before use.
18. **Scope creep and collateral damage.** Changing unrelated code, committing data or models, touching files that belong to another session. Read `git diff` before every commit.
19. **Extrapolating beyond the domain.** Applying a fit outside the years, stations, heights or regimes it was fitted on.
20. **Treating absence of evidence as evidence.** "No effect seen" with a test that could not have seen one (too few cases, wrong layer).

## B. Mistakes we have made in this project (so far)
1. "Wind spread too narrow" was true for balloon/season-specific cases but not at ASOS: climate mode is calibrated there (corrected, IL-144).
2. Past mode silently fell back to climate when the ERA5 store was missing (fixed: loud warning, `era5_store`).
3. Observation weights were assumed, not measured (replaced by weights fitted on station pairs, L2).
4. The engine pinned the observed column so the weights had no effect (found by test; soft conditioning added).
5. Tests for a standard day assumed the wrong height convention (geometric vs geopotential).
6. A PIT test used the wrong default ordering (keep_order).
7. Floor / age model: a single exponential did not match the measured age table (replaced).
8. Shell scripts: a function named `tr` called `tr` and recursed (about 1,300 processes); heredoc quoting broke several scripts; a queue waited for a RAM threshold that was never met; Smart App Control blocked the venv Python.
9. `.gitignore` `data/` hid the package data files (added a negation).
10. Benchmark script first included hours outside the tool's solar window (filter added).
11. The 3-flight / branch validation: only 3 of 38 branch flights are inside the domain; the mean error did not improve, so "validated" is not claimable (stated in the validation file).
12. C4b (L8) changed three things in one single-seed run: attribution impossible, gain within a plausible noise range.
13. IL-151's penalty acted above 2 km while the excess is at the surface: the mechanism was not located before the experiment.
14. L5 planned a data route (ARCO point extraction) that is physically impractical (whole-globe chunks): check data layout and size before planning.
15. I described the IFS-ensemble NaN months wrongly and suggested a rerun that could not help (read the notebook notes first).
16. **HRRR evidence is contaminated (found at the first checklist run, see D1):** the stations used as truth (ASOS TCS and MAF) are most likely assimilated by HRRR, so HRRR's 10 m score at those points is optimistic for a pad with no nearby station. Meanwhile ERA5, behind the tool's past mode, does not assimilate those winds. The "-35 %" is an upper bound until tested at independent stations.

17. We tried four fixes on the network (loss weights, masks, smoothing, penalties, convolutions) for an excess that is added AFTER the network by calibration and shuffle; the stage audit (L14b) found it. Lesson: locate the stage before designing the fix.

18. A cause was named from one seed (calibration "creates" surface jumps, 2.7x ERA5): on seeds 1 and 2 the calibrated row is only 1.1-1.2x ERA5 and the raw network is too smooth. Always read a physics row on at least two seeds before designing a fix (L14a, found before building).

19. A vehicle-dependent number (apogee error of three flights) was the yardstick for an input that is a small part of it (the atmosphere). Report the input-level error (atmosphere against observations) and the end-to-end error side by side; never conclude from the end-to-end number alone (flight-sim rerun, 2026-11-08).

20. A 5-year median difference (tool for one year's date against a multi-year ASOS median) was read as a model artifact (noisy trend slopes). Comparing like with like year by year showed it was mostly monthly weather and ENSO noise; the test of the supposed fix (year clamp) was neutral. Before naming a cause from a mean difference, compare the same period, one year at a time, and size the noise of the reference (V1 follow-up, 2026-11-08).

21. A ratio conditioned on a noisy denominator (80 m speed given the 10 m class) was read as a shape error: station and balloon 10 m winds are noisy, reanalysis ones are not, so the conditional ratio falls with wind for noisy sources and rises for smooth ones even when the means agree. Compare ratios of means, or regress with the noise in mind, before calling a profile wrong (V2, 2026-11-08).

22. Queue scripts looked for result files under names they never get (`_cal2122_`, a stage listing with a wrong stem), so the automatic comparison step skipped silently. After writing a script, list the real output names of one finished run and compare with the names in the script before relying on its verdict (found twice on 2026-11-08, `docs/AUDIT_2026-11-08.md` M7).

## C. The check (after every 3 trials; answer for each of the last three)
- Truth: did any compared source see the truth (A1)? Fit years separate from test years (A2)? Dev-test use counted (A3)?
- Size: effect larger than seed noise or bootstrap interval (A4)? One change at a time (A5)? Strongest baseline, same rows (A6)?
- Detail: every band, regime and tail looked at (A7)? Metric matches the question (A8)?
- Honesty: every fallback loud (A9)? Units and signs checked by hand once (A10)? Claim says what was and was not tested (A11, A14)?
- Real path: new code run once on the live path, not only a fake (A13)? Data counted for NaN and duplicates (A17)?
- Hygiene: `git diff` read, only named files staged, no data or models committed (A18).

## D. Check log (newest last)
- **D5, 2026-11-08, trials IL-161 (failed), IL-162 first run, IL-162 confirmation:** IL-162 was first judged on one seed, then confirmed on two more day seeds and night with the same fitted map and the same rows as the base (A4, A6); fit years 2021-23, scoring 2024-25 (A2); every physics row looked at, shear unchanged and jump only slightly improved, so no claim beyond the superadiabatic row (A7, A11); the target is ERA5, a reanalysis, not balloons: the lapse map matches ERA5 statistics, which is what the physics rows measure, and balloon lapse rates were not checked (A8, new open item); the map is fitted and scored on the same pilot box (A19: no claim for Denver or other regions); 2024-25 now used for about 28 decisions (A3). IL-161 was a clean falsification and is logged as a failure.
- **D4, 2026-11-08, trials IL-155, L26, IL-160:** IL-155 fit/test separate and claim limited to one model and one seed (A2, A4). L26 one change, same rows, baseline files identical to L11 (A5, A6), physics rows read, not only the headline (A7); flag stays off, the build was a refinement not the planned replacement and the verdict says so (A11). IL-160 same seed and same samples at each stage so the stages are comparable (A16); the script's own final listing looked for a wrongly named file (stage B) - found on reading, the numbers were taken from the real file (a script naming bug, not a result); stage E (shuffle without shear map) is a diagnostic, not a pipeline state, and is labelled so. The development window 2024-25 has now served about 24 decisions (A3). New mistake class B17: an effect was blamed on the model while it was added by later stages; fixed by measuring each stage.
- **D3, 2026-11-08, trials L12a (done above, D2), L12b (sidelined), IL-76:** IL-76 changes two things at once, the windows and the training years (A5): stated in the verdict, so no claim that the skill drop is caused by the split itself; single seed (A4) but the coverage result is identical to four digits, which is the claim made; same rows and the same baseline files (A6); rh2m skill moved 0.0127 -> 0.0024 (A7), looked at, consistent with less data, not claimed as a split effect; sources: no new data. L12b: not a result, a blocked source; no claim made. Two failures in the ledger (IL-158, L12b) toward the next idea.
- **D2, 2026-11-08, L12a (one trial so far, run early because it reuses L1 data):** fit years and test years separate (A2); bootstrap interval excludes zero but in the WRONG direction (A4: regime fit is worse than the fixed anchor, so no claim); fitted weights near 1.0 everywhere is consistent with truth contamination (A1/B16), so the result does not support or refute HRRR at a remote pad. L28 (gradient-boosted head) now carries the same warning: it only makes sense after L12b gives an independent reference.
- **D1, 2026-11-08, trials L8, L11, L12 (HRRR):** found B16 (HRRR truth contamination): trust line, `hrrr.py` docstring and the plan now say "tested at HRRR-assimilated airport stations; an independent-station check is queued (L12b)". L8 attribution caveat (B12) and L11 mechanism (B13) already recorded. Real path for `observe_hrrr` was run live once (archive path). Fit years (2021-23) and test years (2024-25) are separate; the 2024-25 set has been used for many decisions (A3: count about 20, treat as optimistic).
