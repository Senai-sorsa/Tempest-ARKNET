# Triage of the external review `global-fixes.md` (2026-11-06)

Each claim was checked against the code and the data on disk. Verdicts: **wrong** = the check shows it does not happen;
**done** = already handled; **to-do** = real, scheduled (`To-do-Concise.md`); **skip** = not worth it now, with the reason.

## Checked and wrong
| Item | Claim | Check |
|---|---|---|
| 2.1 | terrain weight is sin(lat), kills the Southern Hemisphere | `np.cos(np.radians(90 - i*0.25))` is cos(lat) because 90 - i*0.25 *is* the latitude: factor 0 / 1 / 0 at i = 0 / 360 / 720. Terrain points N/S = 1031/474 (land and mountains are mostly northern); 172 southern terrain points above 1.5 km |
| 11.2 | grid indices may be off by half a cell | store `latitude[ilat]`, `longitude[ilon]` equal the point coordinates for all 7,483 points |
| 11.3 | `arccos` distance is unstable below 1 deg | in float64 the error near 1 deg is ~1e-8 deg; irrelevant for a 1 deg radius |
| 12.4 / 3.1 / 3.3 | the 24-day hour cycle aliases with the calendar | 1991-2025 steps per (month, UTC hour): 40-47, near uniform; 0 steps in 2026 |
| 10.1 | station/ASOS lookups hard-code the pilot | `calibrate/station.py` reads `region.load()` (since the region refactor) |
| 6.7 | sp int16 range may not cover Earth | 14.5-145.5 kPa covers every surface (Everest ~33 kPa); encode raises, so a miss could not be silent |
| 4.2 | longitude distance breaks at +-180 | `gc_deg` uses cos(lon1 - lon2), periodic |

## Done
- 1.2 / 1.3 / 11.5: ERA5 invariants incl. **z_sfc**, lsm, sdor, slor, anor, isor fetched (`tempest/ingest/fetch_statics.py`, `data/raw/era5_static/era5_invariants.npz`, same grid as the point indices, Denver checked at 1,723 m).
- 8.6: the fetch runs under a retry loop (`scripts/fetch_global.sh`) and is resumable per month.
- 2.5: 987 IGRA cells against 6,000 lattice capacity (fine now; the loader asserts the counts, below).

## To-do (in `To-do-Concise.md`)
- 1.1 / 3.5 / 6.5 / 8.2 / 8.5 / 12.5 **Global loader** (`tempest/geo/global_store.py`, G0): decode int16 → physical, merge months, pressure → 44 heights above the ERA5 z_sfc with a below-ground support mask (no dropped mountain rows), a completeness report (months, points, variables) that refuses to label a partial store 1991-2025, and conversion to one chunked file for training.
- 1.6 / 12.3 / 2.9: the loader checks `points.npz` against the current holdout file (hash) and records point counts by type and hemisphere.
- 12.1 / 5.1 / 5.2: **one holdout + date guard** in that loader (holdout places within radius and dates >= 2026-01-01 refused); calibration and scoring of global data go through it. The 2026 guard at the pilot already exists (E3).
- 1.2: static join by point index from the invariants file (+ distance to coast, TPI) in `tempest/geo/statics.py`.
- 6.6: int16 tail check: 99.9th shear on Denver float vs int16-rounded profiles (cheap, CPU).
- 10.3: `output/atmosphere.py` `BOX` gate → the DI/AOA flag (G3, already in the plan).
- 3.2: the diurnal-cycled store is training data only, never an exact-hour past lookup (already the plan's use; stated here).

## Skip (reason)
- 11.4 / 11.5 terrain-point choice with a proxy elevation and a grid-space window: it only decides *which* points are fetched (now frozen, half downloaded); the points are good (median 1,085 m vs 0 m for the lattice). The training inputs use the real orography.
- 2.3 / 2.4 refill after holdout removal: the count is recorded; a few dozen fewer points near 11 holdouts does not bias anything measurable.
- 2.6 / 2.7 WMO region by id block: holdouts are a fixed, written list; "one per region" is a spread device, not a claim. IDs exist (the fetch resolved all of them).
- 5.5 signed unlock artefact, 7.x statistical framework: the gates, block CV and seed tolerance are already in `docs/plans/GLOBAL_PLAN.md`; confidence intervals by block bootstrap are added when G3/G4 scoring is written.
- 8.4 memory: measured, the monthly fetch runs at ~2-7 GB.
