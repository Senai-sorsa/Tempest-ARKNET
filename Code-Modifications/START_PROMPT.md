You are taking over the Tempest-ARKNET project (C:\Users\Senai\Tempest-ARKNET) from another Claude session. You have none of its memory, so the files are your only context.

STEP 0: GET CONTEXT (do this before anything else)
1. Read Code-Modifications/HANDOVER.md in full. It covers the rules, the machine limits, current state and past results.
2. Then read Code-Modifications/PHASED_PLAN.md and docs/PLAN.md. Read the other files they point to as needed.
3. Run the "first 15 minutes" checklist in HANDOVER.md section 1:
   - running jobs;
   - the pipeline;
   - the heat limiter;
   - CDS download progress.
   Restart anything that died, as that file describes.
4. Save HANDOVER.md sections 2-4 as memory notes, so the rules survive context resets.

THE GOALS (what "done" means)
Tempest is a probabilistic atmosphere-profile generator for the pilot box (31-34 N, 108-101 W): wind u/v, temperature and RH at 44 heights, plus t2m, surface pressure and rh2m. The only inputs at query time are location, time and date, plus public climate indices known at that time.

Not yours: Phase 4 (forecast and past-date correction, Code-Modifications/PHASE4_FORECAST.md) is a separate system. It is on hold until Phases 1-3 are done; the user starts it later.
- Skip TOOL_PLAN steps T2, T3 and T4/T4b.
- Don't edit Phase 4's files (its section 3).
- Share the GPU: one job on the machine at a time.

Goal 1. Past-weather identification. For any past date, give the most likely profile plus a calibrated distribution.
- The 99 % range must contain the real value about 99 % of the time in every variable and height band. Target: mean |cov99 - 0.99| <= 0.003, with no band below 0.98.
- The most likely value must be as close as possible to the truth: report and reduce MAE/RMSE of the median against ERA5 AND balloons.
- The user's own words: "if the model says 2C and the real data was 2.1C, then our model measures that as error".

Goal 2. Month-ahead and future draws. Distributions that are calibrated (same coverage targets) and beat climatology.
- Measure: CRPS skill vs the recent 15-year climatology (skill15) above 0 in as many bands as possible.
- Fix the known weak spots:
  - rh2m and RH 0-1 km skill15 below 0;
  - T 5-12 km too narrow;
  - extreme wind shear 16-22 % too weak.

Goal 3. Beat the E12 baseline (HANDOVER section 6, PHASED_PLAN §0.2) on the honest protocol:
- train ≤2020;
- validate and calibrate on 2021-23;
- development test 2024-25;
- one final test on 2026 Jan-Jun, run only at the very end.
- Use the phase-end pass rule in PHASED_PLAN §0.3.

Goal 4. Finish every item in PHASED_PLAN.md:
- Phases 1, 2 and 3;
- §4: tool T1-T5, operations O2-O8, flight-sim C3-C6;
- §5: all leftovers.
Then build the query tool in docs/TOOL_PLAN.md, so the user has a usable values()/distribution() tool.

Goal 5. Honest numbers.
- Every claim comes with intervals and states which years it was tested on. Call 2024-25 "development".
- Report results to the user in plain language. They are not an ML expert.
- Don't promise skill that physics doesn't allow: month-ahead skill is close to climatology by nature.

HOW TO WORK
Phase A. Planning (the only phase where you talk to me first).
1. Turn PHASED_PLAN.md into a concrete implementation plan:
   - order of work;
   - files touched;
   - the flag for each change (off by default);
   - tests;
   - time and GPU estimates;
   - what is risky.
2. Show me the plan once, and ask any questions you truly need answered, all at once in one message:
   - the A2 go/no-go thresholds;
   - whether to commit or push at milestones.
3. Wait for my approval.

Phase B. After I approve: work fully on your own until the very end. Then keep optimizing for as long as there are improvements to find.
- Never stop to ask a question or for approval again. If something breaks, diagnose it, fix it and keep going: low-memory kills, crashes, bad results, slow downloads.
- Test only at the end of each phase, as PHASED_PLAN says. Keep a change only if it verifiably improves held-out accuracy. If a phase fails, switch off half of its flags, retest and find the culprit.
- Log every experiment as a numbered row in docs/PLAN.md:
  - what changed;
  - what it was tested on;
  - the numbers with intervals;
  - kept or rejected.
- Risky or dangerous items: think them through and test them safely first, on a copy or behind a flag.
  - If one is clearly very beneficial and the test shows it is safe, use it.
  - If it is really risky, don't do it. Put it in Code-Modifications/ASK_LATER.md with the reason, the evidence and the exact command or change. Then carry on with everything else.
  - "Really risky" covers: deleting data or models, rewriting git history, anything that could destroy work, spending money.
- When the plan is finished, run a full double-check:
  - pytest;
  - rescore the final files;
  - check that the calibration and model hashes match;
  - check that no test-year leak exists.
  Fix any mistake found, even if that means retraining everything.
- Then run the single 2026 H1 final test and report it.
- After that, go into an improvement loop:
  - read the diagnostics;
  - find the weakest coverage or skill or point-error cells;
  - research and try one improvement at a time, verify it, log it.
  - Stop only when several honest attempts in a row give no real gain, then report.

HARD RULES (they override autonomy; full list in HANDOVER section 3)
- "Dont break anything". New behaviour goes behind a flag, off until verified. Failed items are switched off, not deleted.
- Never print or repeat the CDS key (~/.ecmwfdatastoresrc).
- Never commit data/ or models/.
- Commit or push only if I have said yes. Never add a "Co-Authored-By: Claude" line or any Claude attribution.
- Git history rewrites and force-pushes are mine to run. Put them in ASK_LATER.md.
- Machine limits (HANDOVER section 4):
  - RTX 5070 Laptop, 12 GB; 31 GB RAM; the laptop overheats.
  - One GPU or training job at a time.
  - CPU affinity 4095, BelowNormal priority, OMP_NUM_THREADS=12.
  - Never stop running jobs because of heat.
  - Kill stopped jobs by the whole process tree, and check for orphans.
  - Never edit a bash script while it runs.
  - Never run pytest while scoring.
- Keep each training run at about 15 min or less unless a verified gain justifies more.
- Touch 2026 Jan-Jun only once, at the very end.

Start now with Step 0, then Phase A.
