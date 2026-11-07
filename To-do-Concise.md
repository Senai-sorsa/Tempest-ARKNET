# To-do (concise) — updated every check-in; done items are deleted

## You
- Confirm G1-a → G2 go: Denver beats climatology everywhere with a local fit, not zero-shot (see GLOBAL_PLAN §7). Default if you say nothing: go, with SAMOS targets in G2.
- Colab: WB2 HRES pull (ASK_LATER 9) — needed for global Mode F only, not urgent.
- Watch ISP data cap: ~2.5 TB more to transfer by ~Nov 7 evening.
- Optional: read `docs/reviews/triage/GLOBAL_REVIEW_TRIAGE.md` (external review: 7 claims wrong, rest scheduled below).
- Optional: read `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md` (Gemini review: 3 fixes applied; idea 1 tested and rejected; idea 3 waits for IGRA; idea 2 removed).
- Create a free NASA Earthdata login (for MERRA-2, the 48-80 km layer of A1) and tell me when done.
- Docs index: `docs/README.md` (plans, external reviews, triage, logs, results, data, Colab steps).

## Automatic — running
- Global store 7,483 pts (`data/global_fetch.log`): 2011-2025 **done 20:45 Nov 6** (usable now); it continues with 2001-2010 then 1991-2000 (~3.5 min/month), done ~11:00 Nov 7.
- Chain after the **whole** global store (`data/fetch_chain.log`, waits for 1991 too): extras (~5 h) → IGRA 987 stns (~1 h, ~25 GB) → 6 G2 boxes (~4 h, ~32 GB) → **~21:00 Nov 7** (corrected; earlier ETA assumed 2011-2025 only).
- Loop 3 lean queue: **done, nothing to stack.** Rejected: w768, terrain, ctxsep, sirenw15, studt (Gemini idea 1: shape FAIL). studt is transfer-only (Denver fill -0.173 vs -0.192, better coverage, no tropopause loss): try it in the global model. Results in `docs/logs/LOOP3.md`.
- **G9 follow-up block** (LOOP3 L3-28..33): DI and trust blend done (Denver -0.19 → +0.01, but physics worse; L3-33 adds the shuffle). Raw-p2f diagnosis done (calibration makes the surface jumps; the Denver inversion error comes from the model → IGRA jump head). L3-33 done: Denver **+0.0100, every band beats climatology**, physics close to ERA5 with the shuffle; but that needs the local ERA5 fit (not zero-shot). Running: studt clip 3 (L3-30) → L3-34 debias (remove the Denver mean bias) + L3-35 shuffle grid fix → data-needs queue.
- Recovered reaped job: the data-needs queue (`scripts/ap_l3_data.sh`: fewer years/points/hours tests) was killed before it ran; now chained after L3-34/35 in `scripts/ap_l3_debias.sh` (≥ 6 GB RAM free). The other reaped jobs (global fetch, loop-3 resume) had already been recovered.

## Automatic — next
- Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md.
- Stack the winners of the lean queue (if any) and rescore Denver with the fill-top data.
- Global loader + holdout/2026 guard + completeness check + below-ground masks (G0).
- Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI; slopes with cos(lat)) → model inputs.
- IGRA plain files → 44 heights, delete raw zips; then run the jump idea (L3-27, `configs/generator_l3_jump_igra.toml`: head only, base frozen, BLH / tropopause centre priors).
- int16 tail check (Denver 99.9th shear).
- G2 training (8 boxes, leave-one-box-out), then G3/G4.
- Launch plan (`docs/plans/LAUNCH_PLAN.md`), after the G9 block: A2 launch-day correction from any readings → A1 extension to 80 km (no retrain) → A3 wind/shear tails → tracer-drift check + runtime.
- Test #3 future climate.
