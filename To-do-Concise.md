# To-do (concise) — updated every check-in; done items are deleted

## You
- Colab: WB2 HRES pull (ASK_LATER 9) — needed for global Mode F only, not urgent.
- Watch ISP data cap: ~2.5 TB more to transfer by ~Nov 7 evening.
- Optional: read `docs/reviews/triage/GLOBAL_REVIEW_TRIAGE.md` (external review: 7 claims wrong, rest scheduled below).
- Optional: read `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md` (Gemini review: 3 fixes + idea 1 being tested; idea 3 waits for IGRA; idea 2 removed).
- Docs index: `docs/README.md` (plans, external reviews, triage, logs, results, data, Colab steps).

## Automatic — running
- Global store 7,483 pts (`data/global_fetch.log`) → ~Nov 7 06:00.
- Global ASOS gusts, 200 stations 2016-25 (`data/asos_global.log`) → ~Nov 7 morning.
- Chain after global store (`data/fetch_chain.log`): extras w/gust/BLH/CAPE/cloud/precip (~5 h) → IGRA plain files 987 stns (~1 h, ~25 GB) → 6 G2 boxes hourly (~4 h, ~32 GB) → ~Nov 7 evening.
- Loop 3 lean queue (`scripts/ap_l3_lean.sh`): (w768 and terrain rejected; terrain Denver fill -0.207 vs p2f -0.192) → ctxsep (rejected: NM/TX +0.0250, shape FAIL; Denver on the fill set) → sirenw15 (rejected: NM/TX +0.0288 but shape FAIL, Denver worse than siren) → studt (Gemini idea 1, improved; first run NaN from unbounded t draws; clamped, recalibrate + rescore retry `scripts/ap_l3_fill_studt.sh` after the fill rescore). Fill-top Denver so far: siren -0.156 vs p2f -0.192 (but T 12-18 km much worse), w768 -0.215, terrain -0.207. Everything else in loop 3 is sidelined (`docs/logs/SIDELINED.md`). Then `scripts/ap_l3_fill.sh` rescores the candidates on the fill-top Denver set (L3-25: p2f zero-shot -0.18 → -0.19 with mountain rows kept; old Denver numbers were optimistic).
- GLOBAL_PLAN §9 Monte Carlo checks (`scripts/ap_g9.sh`, running, waits for loop 3 + fill rescore, GPU idle, >= 9 GB RAM): results in `data/g9_verdicts.txt`; then record them in GLOBAL_PLAN §7.

## Automatic — next
- Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md.
- Stack the winners of the lean queue (if any) and rescore Denver with the fill-top data.
- Global loader + holdout/2026 guard + completeness check + below-ground masks (G0).
- Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI; slopes with cos(lat)) → model inputs.
- IGRA plain files → 44 heights, delete raw zips; then run the jump idea (L3-27, `configs/generator_l3_jump_igra.toml`: head only, base frozen, BLH / tropopause centre priors).
- int16 tail check (Denver 99.9th shear).
- G2 training (8 boxes, leave-one-box-out), then G3/G4.
- Stage 6 IL-33/G; test #3 future climate.
