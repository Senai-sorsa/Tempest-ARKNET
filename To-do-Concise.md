# To-do (concise) — updated every check-in; done items are deleted

## You
- Colab: WB2 HRES pull (ASK_LATER 9) — needed for global Mode F only, not urgent.
- Watch ISP data cap: ~2.5 TB more to transfer by ~Nov 7 evening.
- Optional: read `docs/reviews/triage/GLOBAL_REVIEW_TRIAGE.md` (external review: 7 claims wrong, rest scheduled below).
- Optional: read `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md` (Gemini review: 3 fixes applied; idea 1 tested and rejected; idea 3 waits for IGRA; idea 2 removed).
- Decide: adopt **siren** (L3-4) over p2f? NM/TX +0.0278 (PASS), shape PASS, Denver fill-top -0.156 vs p2f -0.192, but T 12-18 km at Denver -0.02 → -0.33. G9 evidence (18:05): the T 12-18 km loss is on real heights, not fill-top copies, and siren's members make t2m/10 m jumps 12x as often as ERA5. Recommendation: keep p2f; revisit after the IGRA tropopause fix (L3-27).
- Docs index: `docs/README.md` (plans, external reviews, triage, logs, results, data, Colab steps).

## Automatic — running
- Global store 7,483 pts (`data/global_fetch.log`) → ~Nov 7 06:00.
- Global ASOS gusts, 200 stations 2016-25 (`data/asos_global.log`) → ~Nov 7 morning.
- Chain after global store (`data/fetch_chain.log`): extras w/gust/BLH/CAPE/cloud/precip (~5 h) → IGRA plain files 987 stns (~1 h, ~25 GB) → 6 G2 boxes hourly (~4 h, ~32 GB) → ~Nov 7 evening.
- Loop 3 lean queue: **done, nothing to stack.** Rejected: w768, terrain, ctxsep, sirenw15, studt (Gemini idea 1: shape FAIL). studt is transfer-only (Denver fill -0.173 vs -0.192, better coverage, no tropopause loss): try it in the global model. Results in `docs/logs/LOOP3.md`.
- GLOBAL_PLAN §9 Monte Carlo checks (`scripts/ap_g9.sh`, running: all done but studt (scoring now), then `ap_g9_refill.sh` rescores p2f Denver): results in `data/g9_verdicts.txt`; then record them in GLOBAL_PLAN §7. `scripts/ap_g9_refill.sh` then rescores p2f Denver with the fixed filled check. Siren evidence is in: its Denver T 12-18 km loss is on real heights (-0.31), so it does not transfer cleanly; adoption is the user's call. Next design step from the first results: DI-gated climatology blend (§9.3), and check siren's t2m/10 m jump excess.

## Automatic — next
- Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md.
- Stack the winners of the lean queue (if any) and rescore Denver with the fill-top data.
- Global loader + holdout/2026 guard + completeness check + below-ground masks (G0).
- Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI; slopes with cos(lat)) → model inputs.
- IGRA plain files → 44 heights, delete raw zips; then run the jump idea (L3-27, `configs/generator_l3_jump_igra.toml`: head only, base frozen, BLH / tropopause centre priors).
- int16 tail check (Denver 99.9th shear).
- G2 training (8 boxes, leave-one-box-out), then G3/G4.
- Stage 6 IL-33/G; test #3 future climate.
