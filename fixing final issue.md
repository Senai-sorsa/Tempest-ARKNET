# Fixing final issues

Written 2026-11-14. The three issues we judge most important to resolve, each with its sub-issues. Source: the progress review of this date, built from `docs/results/FINAL_REPORT.md`, `Useful results.md` and `To-do-Concise.md`. Nothing was run to write this file; every number is copied from those documents. Each item is a problem statement, not a plan or a verdict.

---

## Issue A. Specific holes in the forecast and climate products

1. **Temperature at 12-18 km has negative skill against recent climatology.**
   - 2026 January-June: -0.030 on ERA5-type targets and -0.039 on balloons, for the shipped model and for E12 alike.
   - Known cause: the tropopause-region target changed around 2020 (IL-67).
   - It is also one of the cells where the tool is not better than the Gaussian baseline.
2. **Humidity at 12-18 km has weak coverage.**
   - Balloon RH 12-18 km 99 % range holds 0.958 of outcomes, the weakest cell in the 2026 test.
   - It is the RH 12-18 km failure that the cov99 clause kept stopping (AV2, NEST, AV30).
   - Seen-noise check (AU-5): 90 % coverage of RH and winds above 12 km can move up to 0.02.
3. **Tail-rate error is 3-4 times the nominal rate.**
   - Goal is 0.2 of the nominal rate; the final report calls it "probably unattainable at these sample sizes".
   - On 2026 the error was 3.9 against E12's 2.1, driven by RH at 12-18 km.
4. **Climate-mode skill beyond about 15 days is near climatology by nature.**
   - Not a fault to fix. The value there is honest, coherent profiles, not accuracy.
   - Open point: say this plainly wherever skill numbers are quoted for long leads.
5. **99 % coverage shortfall in forecast mode** (related, from `Useful results.md`).
   - SIGMA and NEST sit at 0.976-0.984 with the PIT step and about 0.99 without it.
   - The shipped-style binned model covers 0.958-0.963 at 7 days in the PIT column.
   - Open check: whether the shipped tool uses the PIT column or the no-PIT column (`scripts/il6_modeF.py:211`, `tempest/export_tool.py:208`).
   - Proposed fix (TAILCAL): a table of tail factors by variable, lead day and side, tried first on the shipped binned model. No training, about 1 h CPU.

---

## Issue B. Wind: the weak variable, and the one that matters most for rockets

1. **Wind only ties the Gaussian (Earth-GRAM-style) baseline.**
   - ERA5 u 1-5 km is -3 % against it on both truths.
   - Cells not better than the baseline: ERA5 u 1-5 km, u 5-12 km, v 5-12 km, v 12-18 km; balloons u 0-1, 1-5, 5-12 km and v 5-12, 12-18 km.
2. **Near-ground wind has a known bias.**
   - Climate-mode 10 m wind is windier than ERA5 u10: speeds under 5 m/s are lower by 0.06-0.14, and the per-hour gap is 0.12-0.19.
   - Code read 2026-11-13: not an intended widening; `launch.widen_near_surface` is past mode only and off by default. So it is an unexplained bias that needs a measured check.
   - This is the floor behind the STRAND miss, and it is larger than the link error (0.04-0.09).
3. **Past-mode coverage at 47-200 m was only 0.51-0.60** (tower check).
   - IL-207 found the Santa Teresa fault was bias, not spread.
   - Per-site factor IL-207b (PASS) and the map-first station work help, but the shipped station map still needs the refit (launch tolerance 30 m drops 914 Santa Teresa soundings launched 60 m off).
4. **ERA5 is a poor proxy for gusts and calm spells.**
   - Real air is calm 17.3 % of the time, ERA5 11.0 %.
   - Independent hours understate 3 h calm windows: 10 m wind under 5 m/s for 3 h is 0.41 against a real 0.64 (STRAND stage 0).
   - The shipped sequence under-links at 5 m/s and over-links at 8-10 m/s.
5. **Strong-wind under-prediction in forecast mode.**
   - AV9 cut it by 15-27 % but narrowed the spread too far (TCS coverage 0.89 to 0.84 / 0.85), so the centre is right and the spread is not.
   - Past-mode coverage at airports is 0.71-0.82, and widening hurts at some, so the fault there is the centre.
6. **Not enough real wind truth.**
   - Two balloon stations are the only independent truth; 3 of 9 airports are outside the trained box.
   - No flight-pad weather has been compared against the tool yet (`scripts/atmosphere_check.py` is ready for it).

---

## Issue C. Verdict rules that fight the data

1. **Rules the shipped baseline cannot pass.**
   - "cov99 within 0.003 of binned" cannot be met when binned itself covers 0.96 at 7 days. This clause killed AV2, NEST and AV30.
   - Proposed rule (a rule change, so the user's call): cov99 within 0.005 of 0.99 at every lead, CRPS not worse by more than 0.2 %.
2. **The CRPS-only rule (ASK_LATER 28).**
   - C6 / AV4 / AV25: PIT worsened while CRPS improved (-0.33 to -0.48 %), so the calibration line was closed.
   - Open: whether CRPS alone may decide.
3. **The looser multi-year rule (ASK_LATER 29).**
   - AV24 / AV26: the mix is better at every lead, 14 of 16 intervals below 0, but no clean third test year, so it is logged as MISS.
   - Open: accept pooled years, or demand a clean year.
4. **Real improvements logged as misses; wording is re-argued.**
   - Several misses were sample size: AV28 MISS then AV29 PASS on 2021 + 2022; O1 FAIL at 200 h then AV7 PASS at 600 h; AV8 MISS then AV31 PASS.
   - A pass rule should state the sample size that can resolve the expected gain before the run.
5. **The column choice is not fixed in the verdict scripts.**
   - Verdicts scored `network + PIT recal + range map + Schaake shuffle`; the tool may ship the no-PIT column.
   - Switching columns after seeing numbers is a forking path. Proposal (new idea 7, shipped-column ledger): write the shipped column into the verdict scripts once, re-score past verdicts only as a report, and take the clean word from UR15 (2023-24).
   - Step 0 first: load the shipped forecast pack, push 100 test rows through `tempest` and through the eval column, and demand identical members (about 10 minutes, CPU).
6. **The 2024-25 development years are used up.**
   - They carry dozens of accept/reject decisions; the 2026 January-June test is spent. A fresh one-time window (proposal 2026 July-October) waits for the user (ASK_LATER 14).

---

## Suggested order (my reading, not a decision)

1. C5 step 0: shipped-pack identity check (decides what A5 and C1 even mean).
2. C1-C3: the user settles the rule changes, so verdicts stop turning on wording.
3. B2: a measured check of the climate-mode 10 m wind bias.
4. A5: TAILCAL on the shipped binned model, then SIGMA, then NEST.
5. B6 and C6: real pad weather if any exists, and open the fresh test window.
