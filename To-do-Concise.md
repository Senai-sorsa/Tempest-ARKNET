# To-do (concise) — updated every check-in; done items are deleted

## You
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
- **G9 follow-up block** (LOOP3 L3-28..33): DI and trust blend done (Denver -0.19 → +0.01, but physics worse; L3-33 adds the shuffle). Raw-p2f diagnosis done (calibration makes the surface jumps; the Denver inversion error comes from the model → IGRA jump head). L3-33 done: Denver **+0.0100, every band beats climatology**, physics close to ERA5 with the shuffle; but that needs the local ERA5 fit (not zero-shot). studt clip 3 (L3-30) rejected: no better than studt, wind-shear tails still too wide. Shuffle grid fix (L3-35) done: no change, kept. **Debias (L3-34) takes Denver from -0.19 to -0.03 with no retraining**, but it ruins the humidity spread. Debias on top of the local fit adds nothing, so the local fit (+0.0100) stays the Denver best.

## Left to check — numbered, in run order
L3-36 done 01:24: debias DROP (redundant once trust is on; stack stays +0.0100). L3-37 done 02:20: Sobol noise DROP (neutral, -0.0002 over 3 seeds). pytest 205 passed (02:40).
Queued tests (one GPU job at a time, ~30 min per data run, ~5-10 min per score):
1. L3-38 — **all solar hours** (`scripts/ap_l3_hours.sh`, started 02:31): night store (~2-3 h CPU) → builds → p2f on all 24 h at the same 8 M rows (~25 min) → day vs p2f, night vs p2f. If day skill drops > 0.0006: more rows (x) and a separate night model (split). ~5-7 h after L3-37.
2. Stack the winners and rescore NM/TX + Denver with 3 seeds (`--seed 0/1/2`): the seed's choice of the 5,000 held-out rows alone spans 0.0025 in skill15 (L3-37), so a single-seed headline is only good to about ±0.001.

Processes to finish and check:
7. Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md, this list.
8. Global store finishes 2001-2010 and 1991-2000 (~11:00 Nov 7); completeness check.
9. Fetch chain: extras → IGRA 987 stations → 6 G2 boxes (~21:00 Nov 7).
10. G0: global loader + holdout/2026 guard + completeness check + below-ground masks.
11. Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI; slopes with cos(lat)) → model inputs.
12. IGRA plain files → 44 heights, delete raw zips; then the jump idea (L3-27, `configs/generator_l3_jump_igra.toml`).
13. int16 tail check (Denver 99.9th shear).
14. G2 training (8 boxes, leave-one-box-out, SAMOS targets L3-8 as the zero-shot candidate; hour density from D4), then G3/G4.
15. Launch plan (`docs/plans/LAUNCH_PLAN.md`): A2 launch-day correction → A1 extension to 80 km (needs your NASA Earthdata login) → A3 wind/shear tails → tracer-drift check + runtime.
16. Test #3 future climate.
