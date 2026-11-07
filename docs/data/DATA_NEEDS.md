# What data the system needs, and how much (living document, updated by the loop-3 check-ins)

Goal: the **smallest realistic data set** that keeps the model working, at each stage of `docs/plans/GLOBAL_PLAN.md`.
Every number below is marked **measured** (from files on disk or a run) or **estimate** (to be replaced by a measurement).
The data-needs runs D1-D7 (`scripts/ap_l3_data.sh`) would answer the open questions; sidelined, then reaped, **running since 2026-11-06 21:35** (D1 `yrs2011` first, one GPU job at a time, then the rest in order). Until they run, keep the defaults below: all 1991-2025 years, hourly, full space.

## 1. Where we stand (measured 2026-11-06)
| Item | Size | Note |
|---|---|---|
| `data/raw` (counts toward the **200 GB** cap, raised 2026-11-06) | **81 GB** (+ global store growing: 33/420 months, ~12 GB at the end) | ~107 GB left after the global store. **Time, not disk, is now the constraint** |
| ERA5 NM/TX store `era5_em80` (377 points, hourly) + `era5_em` (older, 18 variables) | 32 + 30 GB | together 3/4 of the cap |
| ERA5 Denver 1991-2025 hourly, 81 points, 13 levels + surface | **5.3 GB** = 212 B per point-hour (zarr, compressed) | per variable: r 1.1, v 1.0, u 1.0, t 0.94, z 0.86 GB |
| IGRA derived files, 2 stations | 279 MB = **~140 MB per station** | the full derived archive would not fit (see 3) |
| `data/train/*.npz` (outside the cap) | 59 GB, of which ~10 near-identical 5.8 GB pilot copies | only `pilot80_dpd`, its `_l3x` overlay and `denver_full_dpd` are used by loop 3 |

## 2. What the model needs (known)
- **Variables**: u, v, T, RH on 13 pressure levels → 44 heights to 18 km (above 18 km dropped), plus t2m, sp, rh2m, 10/100 m wind. z can be rebuilt hydrostatically from T, RH and sp (saves ~16 % of a store; only worth doing for the global store).
- **Hours**: all 24 for the global store (night hours are R-8; the pilot only has solar hours 06-21).
- **Years**: 1991-2025 is enough. P3-5 tested 1980-2023 against 1991-2023: **no skill gain** (`docs/plans/PLAN.md` P3-5). Whether *fewer* years are enough is D1/D2.
- **Test and lock**: 2026 and the holdout places (`docs/plans/GLOBAL_PLAN.md` §3.1) are never fetched into training stores.
- **Statics**: ERA5 invariants (z, lsm, sdor, slor, anor, isor) are one 2-D field each, < 100 MB worldwide.

## 3. What each stage needs (realistic sizes)
Point-hour cost 212 B (measured, Denver). "Diurnal-cycled" = one hour per day, cycling through the 24 hours, ~12,800 steps over 35 years.

| Stage | Data | Estimate | Fits the cap? |
|---|---|---|---|
| G1 (now) | Denver ERA5 (done, 5.3 GB) + ~15 western-US IGRA stations | IGRA: **use the plain IGRA2 data files, not the derived ones**, convert to our 44 heights on arrival and keep only that (≈ 2 soundings/day × 35 y × 176 values × 2 B ≈ **9 MB per station** instead of 140 MB) → ~0.15 GB | yes |
| G2 | 6 more boxes, 3°×3° (~144 points each), hourly 1991-2025 | 6 × 144 × 308k h × 212 B ≈ **56 GB hourly** (temporal group: ~1 tile per box, ~4 h download at the Denver rate); diurnal-cycled → **2.3 GB** | yes, both. Hourly costs GPU time (~5× the rows), so D3 still decides |
| G3 | N. America lattice ~1,600 points + ~180 IGRA | diurnal-cycled: 1,600 × 12.8k × 212 B ≈ **4.3 GB** + IGRA ~1.6 GB | yes |
| G4 | global 7,483 points incl. 987 IGRA columns (fetch running) | diurnal-cycled **16 GB** (1991-2025); **7 GB** if 2011-2025 suffices (D1) + IGRA ~6 GB at 9 MB per station | yes (cap 200 GB) |
| G6 | 2026-07 → latest ERA5 at the holdouts | < 1 GB | yes |

The big decisions are therefore: **(a) how thin in time** (D3/D4/D5), **(b) how many years** (D1/D6), **(c) how dense in space** (D2, plus the Denver zero-shot tests of loop 3), **(d) IGRA as processed profiles only**.

## 4. Open questions and the runs that answer them
All on the p2f config, calibrated and scored on the **full** data 2024-25, compared with the full-data model by `compare_headline` (seed tolerance skill15 0.0006 NM/TX).

| ID | Question | Run | Data share | Result |
|---|---|---|---|---|
| D1 | Are 13 training years (2011-2023) enough? | `yrs2011` | 39 % | **FAIL** (22:02): skill15 +0.0050 vs +0.0277, every band lower, v/RH worse than climatology; cov99 fine. 13 years are not enough: keep 1991-2025, D6 (23 yrs) now decides |
| D2 | Is a 0.5° lattice enough (unseen points between)? | `pts2` | ~25 % | **neutral = enough** (22:28): skill15 +0.0276 vs +0.0277 (inside the 0.0006 seed tolerance), no band worse, cov99 PASS. A 0.5° lattice loses nothing at unseen points between |
| D3 | **One hour per day**, cycling through the hours (the global store design) | `hcyc16` | 6 % | pending |
| D4 | One hour in 4, cycling (fallback if D3 loses) | `hcyc4` | 25 % | pending |
| D5 | 0.5° lattice + one hour per day | `pts2hcyc16` | ~1.5 % | pending |
| D6 | Are 23 years (2001-2023) enough? (matters only if D1 fails) | `yrs2001` | 70 % | pending |
| D7a | New region: 13 years of a box (vs B-local) | `den_yrs2011` | 39 % | pending |
| D7b | New region: one hour per day (vs B-local) | `den_hcyc16` | 6 % | pending |
| D8 | How much does a box that was never seen cost? | loop 3 B-raw vs B-local, and the best L3 variant zero-shot | 0 % | B-raw skill15 **-0.176** vs B-local **+0.016** (2026-11-06): a never-seen box with new terrain is far worse than climatology. Spatial coverage of terrain types is the first data need; years and hours come second. Rest pending (loop-3 variants) |

How to read them: a "PASS"/within-tolerance result means that slice of data can be dropped from the global store; a band that gets worse names what the thinning costs (e.g. 0-1 km at unseen hours = the diurnal cycle needs every hour).

## 5. Decisions so far
| Date | Decision | Evidence |
|---|---|---|
| 2026-11-06 | Keep 1991 as the earliest year; no pre-1991 data | P3-5 |
| 2026-11-06 | IGRA kept as processed profiles at our heights only, raw derived files deleted after conversion (for new stations; the 2 existing stay) | 140 MB/station measured |
| 2026-11-06 | **User approved the 16 GB global store.** Fetch from the Earthmover *spatial* group (`fetch_global.py`): 7,483 points (987 IGRA, ~5,000 Fibonacci lattice, **1,505 terrain points** added after L3-0b, chosen by local relief and weighted by area), one step per day (UTC hour cycles), int16 ≈ **11.8 GB** (28 MB and 174 s per month measured for 7,483 points), ~1.9 TB transferred, 2011-2025 first | the temporal group would need ~18 TB for scattered points (Denver: 4 tiles in 39 min) |
| 2026-11-06 | G2 boxes: fetch diurnal-cycled **if D3 holds**, else every 4th hour (D4, ~14 GB); hourly (56 GB) now fits the disk but costs ~5× the training time | 212 B/point-hour measured |
| 2026-11-06 | **Extra downloads (user request)**: ERA5 invariants incl. z_sfc (**7 MB, done**, `fetch_statics.py`); global extras w/fg10/blh/cape/tcc/tp on the same points (~3 GB est., ~5 h, `fetch_global_extra.py`); IGRA plain data files for the 987 store stations (~25 GB est. raw, Denver's is 77 MB; converted to 44 heights then deleted); 200 worldwide ASOS gust stations 2016-25 (~2 GB est., `fetch_asos_global.py`, running); 6 G2 boxes 2°×2° hourly like Denver (6 × 5.3 GB = **32 GB**, `configs/region_g2_*.toml`). Chain: `scripts/fetch_chain.sh` after the global store. data/raw ≈ **155 GB** at the end (est.) | user, 200 GB cap |
| 2026-11-06 | Cap raised to 200 GB by the user: "The larger concern is time." Data choices are now made for download and GPU time; pruning old stores (ASK_LATER 12) is no longer needed for G2-G4 | user |
