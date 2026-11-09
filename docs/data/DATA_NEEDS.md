# What data the system needs, and how much (living document, updated by the loop-3 check-ins)

Goal: the **smallest realistic data set** that keeps the model working, at each stage of `docs/plans/GLOBAL_PLAN.md`.
Every number below is marked **measured** (from files on disk or a run) or **estimate** (to be replaced by a measurement).
The data-needs runs D1-D7 (`scripts/ap_l3_data.sh`) **finished 2026-11-07 01:00**. Verdict: keep **all 1991-2025 years, hourly**; skill still rises with years (13 / 23 / 33 yrs: +0.005 / +0.022 / +0.028 at NM/TX) and one hour per day keeps only 64 % (NM/TX) / 43 % (Denver) of the skill, one hour in 4 keeps 96 %. The only free saving is space: a 0.5° lattice (D2) loses nothing, but not combined with thin hours (D5).

## 1. Where we stand (measured 2026-11-06)
| Item | Size | Note |
|---|---|---|
| `data/raw` (counts toward the **200 GB** cap, raised 2026-11-06) | **81 GB** (+ global store growing: 33/420 months, ~12 GB at the end) | ~107 GB left after the global store. **Time, not disk, is now the constraint** |
| ERA5 NM/TX store `era5_em80` (377 points, hourly) + `era5_em` (older, 18 variables) | 32 + 30 GB | together 3/4 of the cap |
| ERA5 Denver 1991-2025 hourly, 81 points, 13 levels + surface | **5.3 GB** = 212 B per point-hour (zarr, compressed) | per variable: r 1.1, v 1.0, u 1.0, t 0.94, z 0.86 GB |
| Denver night heights (UTC 05-11, L3-40) | 4.9 GB, built from the same raw store (no download) | needed: the all-hours Denver stack gains night skill (+0.0088 → +0.0102); keep every hour |
| IGRA derived files, 2 stations | 279 MB = **~140 MB per station** | the full derived archive would not fit (see 3) |
| `data/train/*.npz` (outside the cap) | 59 GB, of which ~10 near-identical 5.8 GB pilot copies | only `pilot80_dpd`, its `_l3x` overlay and `denver_full_dpd` are used by loop 3 |

## 2. What the model needs (known)
- **Variables**: u, v, T, RH on 13 pressure levels → 44 heights to 18 km (above 18 km dropped), plus t2m, sp, rh2m, 10/100 m wind. z can be rebuilt hydrostatically from T, RH and sp (saves ~16 % of a store; only worth doing for the global store).
- **Hours**: all 24 for the global store (night hours are R-8; the pilot only has solar hours 06-21). L3-38 (`scripts/ap_l3_hours.sh`) adds the pilot nights from the raw hourly store (no download, ~30 GB derived) and measures whether all 24 h at the same row count costs day skill.
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
| D2 | Is a 0.5° lattice enough (unseen points between)? | `pts2` | ~25 % | **neutral = enough** (22:28; with fewer rows than yrs2011 and no loss, so D1 fails on climate variety, not row count): skill15 +0.0276 vs +0.0277 (inside the 0.0006 seed tolerance), no band worse, cov99 PASS. A 0.5° lattice loses nothing at unseen points between |
| D3 | **One hour per day**, cycling through the hours (the global store design) | `hcyc16` | 6 % | **FAIL** (22:55): skill15 +0.0176 vs +0.0277 (36 % of the skill lost), no band worse, cov99 PASS. One hour per day is too thin at a fixed number of years: the global store (one hour per day) needs D4 or more years per box before G2 relies on it |
| D4 | One hour in 4, cycling (fallback if D3 loses) | `hcyc4` | 25 % | **small loss** (23:19): skill15 +0.0266 vs +0.0277 (-0.0011, ~2x the seed tolerance, 4 % of the skill), no band worse, cov99 PASS. One hour in 4 keeps ~96 % of the skill vs D3's 64 %: for G2, one hour in 4 is the thinnest safe choice (or one hour per day with ~2x the years/boxes) |
| D5 | 0.5° lattice + one hour per day | `pts2hcyc16` | ~1.5 % | **FAIL** (23:46): skill15 +0.0125 vs +0.0277, five low-level wind/RH bands worse than climatology, cov99 PASS. Worse than D3 alone (+0.0176): halving the points costs nothing at full hours (D2) but compounds when hours are thin. Do not thin both |
| D6 | Are 23 years (2001-2023) enough? (matters only if D1 fails) | `yrs2001` | 70 % | **FAIL** (00:12): skill15 +0.0221 vs +0.0277 (80 % of the skill), no band worse, cov99 PASS. Skill still rises with years (13 yrs +0.0050, 23 yrs +0.0221, 33 yrs +0.0277): keep all of 1991-2025. P3-5 found no gain from 1980-90 on an older model; worth one recheck on p2f only if a box is short of years |
| D7a | New region: 13 years of a box (vs B-local) | `den_yrs2011` | 39 % | **FAIL** (00:36): skill15 -0.0115 vs B-local +0.0162 (below climatology), 11 bands worse, worst u 12-18 km. At a new region years matter even more than at NM/TX (D1 kept +0.0050) |
| D7b | New region: one hour per day (vs B-local) | `den_hcyc16` | 6 % | **FAIL** (01:00): skill15 +0.0069 vs +0.0162 (43 % of the skill), only RH 1-5 km cov flagged. Same pattern as D3 (NM/TX 64 %): one hour per day too thin, worse at the new box |
| D8 | How much does a box that was never seen cost? | loop 3 B-raw vs B-local, and the best L3 variant zero-shot | 0 % | B-raw skill15 **-0.176** vs B-local **+0.016** (2026-11-06): a never-seen box with new terrain is far worse than climatology. Spatial coverage of terrain types is the first data need; years and hours come second. Rest pending (loop-3 variants) |

How to read them: a "PASS"/within-tolerance result means that slice of data can be dropped from the global store; a band that gets worse names what the thinning costs (e.g. 0-1 km at unseen hours = the diurnal cycle needs every hour).

## 5. Decisions so far
| Date | Decision | Evidence |
|---|---|---|
| 2026-11-06 | Keep 1991 as the earliest year; no pre-1991 data | P3-5 |
| 2026-11-06 | IGRA kept as processed profiles at our heights only, raw derived files deleted after conversion (for new stations; the 2 existing stay) | 140 MB/station measured |
| 2026-11-06 | **User approved the 16 GB global store.** Fetch from the Earthmover *spatial* group (`fetch_global.py`): 7,483 points (987 IGRA, ~5,000 Fibonacci lattice, **1,505 terrain points** added after L3-0b, chosen by local relief and weighted by area), one step per day (UTC hour cycles), int16 ≈ **11.8 GB** (28 MB and 174 s per month measured for 7,483 points), ~1.9 TB transferred, 2011-2025 first | the temporal group would need ~18 TB for scattered points (Denver: 4 tiles in 39 min) |
| 2026-11-06 | G2 boxes: fetch diurnal-cycled **if D3 holds**, else every 4th hour (D4, ~14 GB); hourly (56 GB) now fits the disk but costs ~5× the training time | 212 B/point-hour measured |
| 2026-11-06 | **G2 boxes stay hourly** (the fetch chain already fetches them hourly); thin to one hour in 4 at training only if 8 hourly boxes do not fit in RAM. D4's loss sits at the surface and 0-1 km (v 0-1 km -0.004, u/t2m/sp -0.003; upper levels unchanged): the diurnal cycle wants every hour. Training runs a fixed 6000 steps (15.2-15.5 min for D2/D3/D4 alike), so more rows cost RAM, not GPU time; the "~5× training time" in the G2 row above does not apply | D3, D4 train logs |
| 2026-11-06 | **Extra downloads (user request)**: ERA5 invariants incl. z_sfc (**7 MB, done**, `fetch_statics.py`); global extras w/fg10/blh/cape/tcc/tp on the same points (~3 GB est., ~5 h, `fetch_global_extra.py`); IGRA plain data files for the 987 store stations (~25 GB est. raw, Denver's is 77 MB; converted to 44 heights then deleted); 200 worldwide ASOS gust stations 2016-25 (~2 GB est., `fetch_asos_global.py`, running); 6 G2 boxes 2°×2° hourly like Denver (6 × 5.3 GB = **32 GB**, `configs/region_g2_*.toml`). Chain: `scripts/fetch_chain.sh` after the global store. data/raw ≈ **155 GB** at the end (est.) | user, 200 GB cap |
| 2026-11-06 | Cap raised to 200 GB by the user: "The larger concern is time." Data choices are now made for download and GPU time; pruning old stores (ASK_LATER 12) is no longer needed for G2-G4 | user |
| 2026-11-07 | **Actions v2 data budget (user: up to 5 GB if needed)**: only A1 (18-80 km extension) needs new data, ~1.7 GB kept + ~3 GB transient: ERA5 pressure levels 70-1 hPa (T/u/v/z, 0.5°, 3-hourly, 1991-2025, ~0.9 GB), ERA5 model levels above 1 hPa only (T/u/v, 1°, 3-hourly, 2011-2025, ~0.2 GB), MERRA-2 and MLS/SABER server-side subsets (~0.3 GB each), a one-year 0.25° hourly resolution check first (~0.5 GB, deleted). A2/A3/A5/A7 use existing data. **The IGRA converter (not written yet) must keep 19-30 km as well as our 44 heights** before deleting the raw files, for A1's balloon validation (+~27 % per station). Plan: `~/Downloads/GEMINI_REVIEW_ACTIONS_v2.md` |
| 2026-11-07 | **MERRA-2 access ready**: NASA Earthdata token (user account) tested on GES DISC (M2I3NVASM 1991-01-01, HTTP 206). Kept in `~/.earthdata_token` (never in the repo), sent as `Authorization: Bearer`; expires 2027-01-06. The A1 MERRA-2 subset (~0.3 GB, above) can be fetched when A1 starts; nothing downloaded yet. |
| 2026-11-07 | **IGRA converted once, to 80 km grid** (user: don't do the IGRA step twice): `tempest/ingest/igra_to_heights.py` puts every plain sounding (all launch hours, 1991-2025) on the 44 heights **plus** 19-30 km every 1 km and 32-80 km every 2 km (`EXT_HEIGHTS`, 81); balloons reach ~30-35 km, the rest stays NaN for ERA5 levels. u/v/T/RH/ln p int16, ~7 GB for 987 stations (est. 18 M soundings); raw zips deleted per station after its npz is written. Checked vs the NCEI derived file for Santa Teresa: T within 0.05 K, 1985 winds within 0.03 m/s (heights from the hypsometric fill are right); 2023 winds differ 0.4 m/s mean because the plain file keeps wind-only levels the derived file drops; RH 1-2 % mid-troposphere (reported RH vs derived CALCRH). `scripts/igra_convert.sh` starts it when `fetch_chain.sh` logs its IGRA step done. Output `data/igra_heights/<ID>.npz`, `load()` decodes. |
| 2026-11-07 | **Arrived (user, 18:30)**: (1) **ERA5 boundary-layer fill** `data/raw/era5_cds` complete, 420/420 months 1991-2025 (128 CDS grib + 292 ARCO nc, 17 GB), checked against the pilot grid: exact match, no gaps → 21-level rebuild L3-44. `fetch_cds` (grib duplicates of nc months) **stopped 18:45 by the user**; resume it only after all other Wi-Fi work ends (To-do item 17). (2) **Global HRES 2016-2022** `data/raw/wb2_hres_global` (ASK_LATER 9): 84/84 months, 8,499 cases, leads 6-240 h, 6.5 GB, points identical to the ERA5 global store, lead/valid times consistent, T in range → global Mode F (GLOBAL_PLAN §7.2 idea 6) once G0's loader exists. |
| 2026-11-07 | **IGRA arrived and converted (22:11)**: 986/987 stations in `data/igra_heights` (4.1 GB npz; raw zips deleted). XXM00084629 is a permanent 404 on NOAA, so it is skipped. G2 boxes: vandenberg, canaveral and fairbanks done by 22:19; saltlake, lamont and hilo are downloading. | unblocks IL-112 and L3-27 |
| 2026-11-07 | **New need: Denver boundary-layer fill (975-750 hPa, 8 levels, 1991-2025)**. L3-44 (23:04): the NM/TX fill gives the biggest boundary-layer gain so far (night +0.0236 → +0.0292, all in 0-1 km), but Denver's truth is still 13 levels, so the 21-level model scores worse there zero-shot (-0.175 → -0.219). Same request as `data/raw/era5_cds` for the Denver box (81 points, ~17 GB like NM/TX, ARCO route faster than CDS). Not started: Wi-Fi order is the user's (To-do 17); the Denver stack stays on all24 until it arrives |
| 2026-11-07 | **Long-range download budget (user): up to 5 GB total** for IL-118 to IL-127 (`ifs_extended_range` weekly anomalies, MJO/PNA indices, soil moisture and SST at the sites, optional GraphCast/Pangu trial). One exception to the no-extra-downloads rule, only for these ideas. Track the total; ask before exceeding. | user |


## 6. Needs found on 2026-11-08 (from the validation and assumption checks)
| Need | Why | Size | Status |
|---|---|---|---|
| A non-airport 10 m wind record near Spaceport America (West Texas Mesonet, NMSU Climate Center, RAWS, Jornada LTER station, or the Cup's own station) | the HRRR 10 m evidence is measured at airport stations HRRR very likely assimilates (checklist B16); this is the independent test (plan L12b) | under 1 GB | NOT AVAILABLE through any public script route found (IEM has none, WTM has no API, ZiaMet no download API, Jornada's data service returned 403 to a plain request); a manual export into `data/raw/indep_wind/` would unblock it |
| Pad weather observations (wind, temperature, pressure) for the three launch hours: Prometheus 2022-06-24 09:17, Juno III 2023-06-23 ~17:00, Heart of Steel 2017-06-22 | the missing pad truth for the flight-sim test, the observation weights and V1 / V2 (plan V9) | a few KB | to look up in the event reports; not downloaded |
| ERA5 profiles for IGRA stations outside the NM/TX box (Albuquerque, Amarillo, Del Rio, Tucson) | an unseen-station balloon test (plan V3; ERA5 assimilates radiosondes, so balloon skill is partly non-independent) | about 2-5 GB per station region | belongs to the G stages |
| ERA5 MODEL-level fields (0-300 m) at the pilot / Denver points | C2 real near-surface profile (plan L5): the public ARCO store is chunked in whole-globe fields (hundreds of GB per month) so it is not usable from here | 1-3 GB via a CDS / MARS request, but a multi-day queue and no `.cdsapirc` key on this machine | deferred to L24 with the CDS fetch |
| Pressure in the ASOS files | station pressure check against the tool (plan V6) | the existing IEM request without the pressure column: about +20 MB | not yet pulled (download ledger `data/download_ledger.txt`, budget 50 GB, 0 used) |
