# To-do (concise) — updated every check-in; done items are deleted

## You
- Colab: WB2 HRES pull (ASK_LATER 9) — needed for global Mode F only, not urgent.
- Watch ISP data cap: ~2.5 TB more to transfer by ~Nov 7 evening.
- Optional: read `docs/GLOBAL_REVIEW_TRIAGE.md` (external review: 7 claims wrong, rest scheduled below).

## Automatic — running
- Global store 7,483 pts (`data/global_fetch.log`) → ~Nov 7 06:00.
- Global ASOS gusts, 200 stations 2016-25 (`data/asos_global.log`) → ~Nov 7 morning.
- Chain after global store (`data/fetch_chain.log`): extras w/gust/BLH/CAPE/cloud/precip (~5 h) → IGRA plain files 987 stns (~1 h, ~25 GB) → 6 G2 boxes hourly (~4 h, ~32 GB) → ~Nov 7 evening.
- Loop 3 GPU queue: siren → sh10ctx → w768 → terrain → clocks → clim → ctxall → thead; then D1-D7 data runs.

## Automatic — next
- Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md.
- L3-15..20 (variogram, calibration rows, DI, stack) when evidence supports; stack winners.
- Global loader + holdout/2026 guard + completeness check + below-ground masks (G0).
- Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI) → model inputs.
- IGRA plain files → 44 heights, delete raw zips.
- int16 tail check (Denver 99.9th shear).
- G2 training (8 boxes, leave-one-box-out), then G3/G4.
- Stage 6 IL-33/G; test #3 future climate.
