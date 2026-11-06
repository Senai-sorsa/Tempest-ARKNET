# What data the system needs, and how much (living document, updated by the loop-3 check-ins)

Goal: the **smallest realistic data set** that keeps the model working, at each stage of `docs/GLOBAL_PLAN.md`.
Every number below is marked **measured** (from files on disk or a run) or **estimate** (to be replaced by a measurement).
The data-needs runs D1-D7 (`scripts/ap_l3_data.sh`, after the loop-3 queue) answer the open questions.

## 1. Where we stand (measured 2026-11-06)
| Item | Size | Note |
|---|---|---|
| `data/raw` (counts toward the 100 GB cap) | **80 GB** | the global plan assumed 66 GB; 20 GB left |
| ERA5 NM/TX store `era5_em80` (377 points, hourly) + `era5_em` (older, 18 variables) | 32 + 30 GB | together 3/4 of the cap |
| ERA5 Denver 1991-2025 hourly, 81 points, 13 levels + surface | **5.3 GB** = 212 B per point-hour (zarr, compressed) | per variable: r 1.1, v 1.0, u 1.0, t 0.94, z 0.86 GB |
| IGRA derived files, 2 stations | 279 MB = **~140 MB per station** | the full derived archive would not fit (see 3) |
| `data/train/*.npz` (outside the cap) | 59 GB, of which ~10 near-identical 5.8 GB pilot copies | only `pilot80_dpd`, its `_l3x` overlay and `denver_full_dpd` are used by loop 3 |

## 2. What the model needs (known)
- **Variables**: u, v, T, RH on 13 pressure levels → 44 heights to 18 km (above 18 km dropped), plus t2m, sp, rh2m, 10/100 m wind. z can be rebuilt hydrostatically from T, RH and sp (saves ~16 % of a store; only worth doing for the global store).
- **Hours**: all 24 for the global store (night hours are R-8; the pilot only has solar hours 06-21).
- **Years**: 1991-2025 is enough. P3-5 tested 1980-2023 against 1991-2023: **no skill gain** (`docs/PLAN.md` P3-5). Whether *fewer* years are enough is D1/D2.
- **Test and lock**: 2026 and the holdout places (`docs/GLOBAL_PLAN.md` §3.1) are never fetched into training stores.
- **Statics**: ERA5 invariants (z, lsm, sdor, slor, anor, isor) are one 2-D field each, < 100 MB worldwide.

## 3. What each stage needs (realistic sizes)
Point-hour cost 212 B (measured, Denver). "Diurnal-cycled" = one hour per day, cycling through the 24 hours, ~12,800 steps over 35 years.

| Stage | Data | Estimate | Fits the cap? |
|---|---|---|---|
| G1 (now) | Denver ERA5 (done, 5.3 GB) + ~15 western-US IGRA stations | IGRA: **use the plain IGRA2 data files, not the derived ones**, convert to our 44 heights on arrival and keep only that (≈ 2 soundings/day × 35 y × 176 values × 2 B ≈ **9 MB per station** instead of 140 MB) → ~0.15 GB | yes |
| G2 | 6 more boxes, 3°×3° (~144 points each), hourly 1991-2025 | 6 × 144 × 308k h × 212 B ≈ **56 GB hourly**; diurnal-cycled → **2.3 GB** | only if thinned in time |
| G3 | N. America lattice ~1,600 points + ~180 IGRA | diurnal-cycled: 1,600 × 12.8k × 212 B ≈ **4.3 GB** + IGRA ~1.6 GB | yes |
| G4 | global ~6,000 points + ~700 IGRA | diurnal-cycled **16 GB** (1991-2025); **7 GB** if 2011-2025 suffices (D1) + IGRA ~6 GB at 9 MB per station | **only with** time thinning and either fewer years or pruning old stores (needs the user, ASK_LATER 12) |
| G6 | 2026-07 → latest ERA5 at the holdouts | < 1 GB | yes |

The big decisions are therefore: **(a) how thin in time** (D3/D4/D5), **(b) how many years** (D1/D6), **(c) how dense in space** (D2, plus the Denver zero-shot tests of loop 3), **(d) IGRA as processed profiles only**.

## 4. Open questions and the runs that answer them
All on the p2f config, calibrated and scored on the **full** data 2024-25, compared with the full-data model by `compare_headline` (seed tolerance skill15 0.0006 NM/TX).

| ID | Question | Run | Data share | Result |
|---|---|---|---|---|
| D1 | Are 13 training years (2011-2023) enough? | `yrs2011` | 39 % | pending |
| D2 | Is a 0.5° lattice enough (unseen points between)? | `pts2` | ~25 % | pending |
| D3 | **One hour per day**, cycling through the hours (the global store design) | `hcyc16` | 6 % | pending |
| D4 | One hour in 4, cycling (fallback if D3 loses) | `hcyc4` | 25 % | pending |
| D5 | 0.5° lattice + one hour per day | `pts2hcyc16` | ~1.5 % | pending |
| D6 | Are 23 years (2001-2023) enough? (matters only if D1 fails) | `yrs2001` | 70 % | pending |
| D7a | New region: 13 years of a box (vs B-local) | `den_yrs2011` | 39 % | pending |
| D7b | New region: one hour per day (vs B-local) | `den_hcyc16` | 6 % | pending |
| D8 | How much does a box that was never seen cost? | loop 3 B-raw vs B-local, and the best L3 variant zero-shot | 0 % | pending (loop 3) |

How to read them: a "PASS"/within-tolerance result means that slice of data can be dropped from the global store; a band that gets worse names what the thinning costs (e.g. 0-1 km at unseen hours = the diurnal cycle needs every hour).

## 5. Decisions so far
| Date | Decision | Evidence |
|---|---|---|
| 2026-11-06 | Keep 1991 as the earliest year; no pre-1991 data | P3-5 |
| 2026-11-06 | IGRA kept as processed profiles at our heights only, raw derived files deleted after conversion (for new stations; the 2 existing stay) | 140 MB/station measured |
| 2026-11-06 | G2 boxes: hourly does not fit (56 GB); fetch diurnal-cycled **if D3 holds**, else every 4th hour (D4, ~14 GB) | 212 B/point-hour measured |
