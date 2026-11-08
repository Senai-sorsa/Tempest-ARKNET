# To-do (concise) — updated every check-in; done items are deleted

## You
- **Long-range data (IL-118): DONE 2026-11-08.** `data/raw/wb2_ifs_extended/` is in place and checked (84 months x pilot/denver x fc/rf = 336 files, 646 MB, no bad files). Long-range download budget used: 0.65 of 5 GB (IL-118 to IL-127). Weekly-average meaning confirmed (lead k = 168 h window starting 12 h before day k, forward week).
- **Waiting on you:** the IFS ensemble refetch (`Colab IFS ENS fetch.md`, `tempest_wb2_ifs_ens_v2`) arrives in about 10 h; unzip into `data/raw/wb2_ifs_ens\` (pilot) and `data/raw/wb2_ifs_ens_denver\` (denver) and tell Claude.
- Watch ISP data cap: ~2.5 TB more to transfer by ~Nov 7 evening.
- Optional: read `docs/reviews/triage/GLOBAL_REVIEW_TRIAGE.md` (external review: 7 claims wrong, rest scheduled below).
- Optional: read `docs/reviews/triage/GEMINI_REVIEW_TRIAGE.md` (Gemini review: 3 fixes applied; idea 1 tested and rejected; idea 3 waits for IGRA; idea 2 removed).
- Done: NASA Earthdata token works for MERRA-2 (GES DISC approved 2026-11-07; token in `~/.earthdata_token`, outside the repo, expires 2027-01-06 — renew before then). Used by A1 (48-80 km layer).
- Docs index: `docs/README.md` (plans, external reviews, triage, logs, results, data, Colab steps).

## Automatic — running
- Global store 7,483 pts (`data/global_fetch.log`): 2011-2025 **done 20:45 Nov 6** (usable now); now in 1991-2000 (at 1995-10, 62 months left). **Slowed 06:00 Nov 7**: ~3 → ~18 min/month, network-bound (fetch CPU idle, Wi-Fi ~2.5 MB/s shared with fetch_cds) → still ~21 min/month at 07:00 (1995-12, 60 left) → **sped up ~10:30 Nov 7** to ~3 min/month since 13:45 → **whole store DONE 14:48 Nov 7** (1991-2025); the chain ETAs below move with it.
- Chain after the **whole** global store (`data/fetch_chain.log`, waits for 1991 too): extras (~5 h) → IGRA 987 stns (~1 h, ~25 GB) → 6 G2 boxes (~4 h, ~32 GB) → **~01:00 Nov 8** (extras started 14:48, ~48 s/month, **extras done 20:39** (420/420, no errors); IGRA started 20:39: 986/987 stns by 21:29 (22 GB), 1 permanent 404 (XXM00084629, not on server; harmless, chain retries then goes on to G2)).
- Loop 3 lean queue: **done, nothing to stack.** Rejected: w768, terrain, ctxsep, sirenw15, studt (Gemini idea 1: shape FAIL). studt is transfer-only (Denver fill -0.173 vs -0.192, better coverage, no tropopause loss): try it in the global model. Results in `docs/logs/LOOP3.md`.
- **G9 follow-up block** (LOOP3 L3-28..33): DI and trust blend done (Denver -0.19 → +0.01, but physics worse; L3-33 adds the shuffle). Raw-p2f diagnosis done (calibration makes the surface jumps; the Denver inversion error comes from the model → IGRA jump head). L3-33 done: Denver **+0.0100, every band beats climatology**, physics close to ERA5 with the shuffle; but that needs the local ERA5 fit (not zero-shot). studt clip 3 (L3-30) rejected: no better than studt, wind-shear tails still too wide. Shuffle grid fix (L3-35) done: no change, kept. **Debias (L3-34) takes Denver from -0.19 to -0.03 with no retraining**, but it ruins the humidity spread. Debias on top of the local fit adds nothing, so the local fit (+0.0100) stays the Denver best.

## Left to check — numbered, in run order
L3-36 done 01:24: debias DROP (redundant once trust is on; stack stays +0.0100). L3-38 03:29: all-hours KEEP (day +0.0278 = +0.0277, night -0.0072 → +0.0274; `l3_h_all24` is the new NM/TX base). L3-37 done 02:20: Sobol noise DROP (neutral, -0.0002 over 3 seeds). pytest 208 passed (11:40, after review fixes d997f62).
**FIXES FIRST (user 2026-11-07: all fixes before any new idea is tested).** Rule: every fix is code behind an opt-in flag, off by default; tests in `tests/test_gate_fixes.py` and `tests/test_gemini_fixes.py`. "Code done" = written, tested, committed, NOT yet switched on; the verification run decides that.
- **Code done 22:00 Nov 7:** IL-110 (tail support + day-block CI), IL-111 (Gaussian margin columns), IL-109 (`--tol`), IL-129 (tail extrapolation), IL-130 + IL-135 (Dryden: exact N2, PBL floor, resolved w, PBL depth, gust law; one switch `dryden_fixes`), IL-131 (pad node, geopotential), IL-132 (site_shift const/pbl), IL-133 (`fix_w`), IL-136 (acoustics; saturation formulas measured: <= 0.25 % from -20 to 30 C, kept), IL-137 (`smooth_m`), IL-138 (`inflate_decay_m`), IL-139 (`OPTIONS["permute_blocks"]`), IL-140 (`keep_order`), IL-141 (`--smooth-w-m`), IL-142 (`--rh-logit`), IL-143 (`--mask-filled`).
- **Next, CPU only (no data needed):** IL-128 (does the copula rebuild smooth tail shear? test on a real pool), spec F1-F3 + S1 (noise seeds, prefix property, `height_asl`, Dryden sub-steps), IL-134 (sp spread: fit from ERA5/ASOS on disk), IL-116 (mark fills above 18 km), IL-117 (check every `era5_cds` consumer).
- **Needs the GPU (after L3-44, one job at a time):** IL-109 3-seed rerun that sets `--tol`; IL-143 L3-43 rescore with `--mask-filled`; IL-141 refit trust with `--smooth-w-m` then L3-29/L3-33; IL-142 refit debias with `--rh-logit`, rerun L3-34; flip decisions for every flag above (3 seeds each).
- **Needs data:** IL-112 (`igra_heights`), IL-114 (balloons vs ERA5 independence), IL-113 (fresh confirmation window).
**New-idea tests wait until the fixes above are verified** (the list below). Queued tests (one GPU job at a time, ~30 min per data run, ~5-10 min per score):
**L3-44 running (18:42)**: 21-level NM/TX rebuild + retrain (`scripts/ap_l3_lev21.sh`): day file built 20:31 (6.81 M rows, 5.2 GB, 0 rows dropped; store deleted), night store 10/36 blocks at 21:37 (~6.5 min/block, slowed by the IGRA download) → night build + concat + train → verdict ~03:00 Nov 8; global HRES (84 months) arrived, waits for G0's loader.
1. Base for both stacks is now `l3_h_all24` (L3-42 NM/TX KEEP: day -0.0001 over 3 seeds, night +0.0274; L3-40/41 Denver KEEP). Known costs: Denver day t2m -0.005 (fallback: p2f stack by day), night rh2m cov99 0.9976 over-cover. GPU idle until IGRA/global data arrive (L3-27).
2. Any further winners stacked on all24 and rescored with 3 seeds (`--seed 0/1/2`): the seed's choice of the 5,000 held-out rows alone spans 0.0025 in skill15 (L3-37), so a single-seed headline is only good to about ±0.001.

3. Review fixes 2026-11-07 done (8 bugs, GLOBAL_PLAN §7). Pending from it: `fill_mask` Denver test L3-43 **done 13:55: DROP (neutral, +0.0154 = +0.0154)**; still pending: the 2021-22 / 2023 validation-calibration split test. 7 candidate ideas logged in GLOBAL_PLAN §7.2, not run.

Processes to finish and check:
7. Verdicts each check-in → LOOP3.md, AUTOPILOT.md, DATA_NEEDS.md, this list.
9. Fetch chain: extras → IGRA 987 stations → 6 G2 boxes (~21:00 Nov 7).
10. G0: global loader + holdout/2026 guard + below-ground masks (store completeness checked 15:37 Nov 7: 420/420 months 1991-2025, steps/hours right, no .part/2026, no saturated int16, 11 GB, 7,483 pts).
11. Statics join (z_sfc, lsm, sdor, slor, anor, isor, coast distance, TPI; slopes with cos(lat)) → model inputs.
12. IGRA plain files → `data/igra_heights` (44 + A1 heights to 80 km, raw zips deleted): automatic via `scripts/igra_convert.sh` after the chain's IGRA download; then the jump idea (L3-27, `configs/generator_l3_jump_igra.toml`).
13. int16 tail check (Denver 99.9th shear).
14. G2 training (8 boxes, leave-one-box-out, SAMOS targets L3-8 as the zero-shot candidate; hour density from D4), then G3/G4.
15. Launch plan (`docs/plans/LAUNCH_PLAN.md`): A2 launch-day correction → A1 extension to 80 km (needs your NASA Earthdata login) → A3 wind/shear tails → tracer-drift check + runtime.
16. Test #3 future climate.
17. **Last, after ALL other Wi-Fi work** (fetch chain extras → IGRA → G2, MERRA-2 for A1, any other downloads): resume the CDS grib download, `nohup .venv/Scripts/python -W ignore -u -m tempest.ingest.fetch_cds >> data/cds.log 2>&1 &` (stopped 18:45 Nov 7 by the user's choice; relaunched 19:20 by the other session's stale Nov-4 `pipeline4.sh` watchdog, which waits for 420 `.grib` and ignores the nc fill; the user stopped both ~19:40. Don't restart `pipeline4.sh`: L3-44 replaces its 13-level profiles_bl/generator_pilot steps; the ledger resumes it; ~290 grib copies of months the ARCO nc fill already covers, so nothing waits on it).
