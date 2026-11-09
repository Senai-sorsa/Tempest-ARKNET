# Error fixes (concise) — as of 2026-11-08

One line per error. Three lists: **1. To fix**, **2. Fixed**, **3. Checked, not a bug** (so they are not raised again). Improvement experiments are in `Improvements-Concise.md`; next steps in `To-do-Concise.md`.
Sources: `docs/plans/fixing issues.md` (sections A-G), the external review triage files (`docs/reviews/triage/`), `docs/logs/AUTOPILOT.md` (F-n review fixes), `docs/results/APPLIED_STATUS.md`, `docs/plans/GLOBAL_PLAN.md` §7 and the git log.
`IL-n` = backlog row in `docs/logs/AUTOPILOT.md`. Status 2026-11-07 22:00: the items marked **[code done]** below have opt-in code (off by default) with tests in `tests/test_gemini_fixes.py` / `tests/test_gate_fixes.py`; they are NOT switched on until a verification run (3 seeds) says so.

Tags: **[C]** confirmed in the code. **[P]** plausible, not reproduced. **[?]** conditional or unclear. **High / Med / Low** = my priority.

---

## 1. TO FIX

**Confirmed bugs in `tempest_weather` (Gemini review, checked in the code)**
1. IL-129 [code done] [C] High — `_cdf`/`_ppf` clamp at the pool min/max, so an out-of-range observation makes a shear spike (IL-129).
2. IL-133 [code done] [C] High — `atmosphere_sequence` / `downrange` never update the vertical wind `w` after reordering (IL-133).
3. IL-134 [not started: needs a fit from ERA5/ASOS] [C] High — surface pressure has zero spread in past and forecast modes, so density is under-dispersed (IL-134).
4. IL-130 [code done] [C] Med — Dryden potential temperature is linearised: N² and Ri are 31 % low at 10 km, 45 % at 18 km (IL-130).
5. IL-130 [code done] [C] Med — boundary-layer factor floors at 0.05, so surface turbulence leaks to 18 km (IL-130).
6. IL-130 [code done] [C] Med — resolved vertical wind is dropped from `w_total` (IL-130).
7. IL-131 [code done] [C] Med — the reader clamps to the 10 m node, so the pad (0 m) gets 10 m values (IL-131).
8. IL-132 [code done; default decision needs the pad-elevation check] [C] Med — `site_shift` fade changes dT/dz by 2.17 K/km at dz = 500 m (IL-132).
9. IL-135 [code done] [C] Med — Dryden uses fixed `h_pbl` 1200 m, `ell_cat` 20 m and a uniform gust peak (IL-135).
10. [C] Med — repeated noise across batches: `seed + 31`, `seed + 47`, `turbulence_seed = 0` (spec F1).
11. [C] Med — results depend on batch size and `n`: no prefix property (spec F2).
12. [C] Med — readers need `height_asl`, producers give `z` and `elevation_m` (spec F3).
13. [C] Med — Dryden Euler sub-steps and 4 km burn-in: slow and inexact (spec S1).
14. IL-131 [code done] [C] Low — geometric vs geopotential altitude: 51 m at 18 km (IL-131).
15. IL-136 [code done] [C] Low — acoustic ray tracer uses dry temperature and the trapezoid rule near turning points (IL-136).
16. IL-136 [measured: <= 0.25 % from -20 to 30 C, 1-4 % at -40..-60 C where e < 0.2 hPa; formulas kept] [C] Low — three saturation-vapour formulas (es_liquid, Buck, Bolton) (IL-136).
17. IL-138 [code done] [C] Low — `inflate = 1.5` is one scalar for all unobserved eigenvalues (IL-138).
18. IL-137 [code done] [C] Low — `SMOOTH = 9` heights is 1.24 km low but 4.5 km aloft (IL-137).

**Plausible or conditional (test first)**
19. [P] High — Gaussian-copula rebuild in `sample_sobol` may smooth tail shear and inversions (IL-128).
20. IL-143 [code done; rescore waits for GPU] [P] High — L3-43 `fill_mask` judged against filled (isothermal) truth; verdict may be wrong (IL-143).
21. IL-141 [code done; refit waits for GPU] [P] Med — trust-blend weights are a step across bands: seams at 1, 5, 12 km (IL-141).
22. IL-142 [code done; refit waits for GPU] [P] Med — debias shifts RH in physical space and collapses the lower tail (IL-142).
23. IL-140 [code done] [?] Med — `pit_apply` returns members sorted; harmful if no shuffle follows (IL-140).
24. IL-139 [code done] [?] Med — `M_CAL = 199` block slicing `[:n]` can take a biased slice (IL-139).

**Gates and measurement**
25. IL-109 [code done; 3-seed rerun waits for GPU] High — the 0.0006 "within seed tolerance" gate is below the seed noise of 0.0025 (IL-109).
26. IL-110 [code done] High — tail gates may rest on few independent events (IL-110).
27. IL-111 [code done] Med — "CRPSS > 0 vs climatology" is too weak (IL-111).
28. Med — the 12 % shear-vs-IGRA gate was picked, not derived (IL-112).
29. High — headline is optimistic: 2024-25 used for 17+ decisions; 2026 test already spent (IL-113).
30. Med — balloon check is not independent of ERA5 (sondes are assimilated) (IL-114).
31. Med — fixed climatology baseline rewards capturing warming (IL-115).
32. Med — layers above 18 km are fills, not skill (IL-116).
33. Med — validation and calibration windows overlap (2021-23) (IL-76).

**Data**
34. High — ARCO and CDS humidity differ by 12-19 %RH under the terrain; check every `era5_cds` consumer masks below-ground rows (IL-117).
35. Med — the CDS downloader still requests months ARCO now covers (stop it or `--last 1997`).
36. Low — the IGRA refresh scope is unclear (`igra_2026` holds 2 entries); check.
37. Low — 44 months exist as both grib and nc; keep until item 34 is closed.

**Machine and process**
38. High — models and data exist only on this disk (the code is now on GitHub); no off-machine backup of `models/`, `data/train`, `data/raw` (ASK_LATER 13).
39. Med — disk: about 150 GB free; the fetch chain still adds about 57 GB.

**Known weak points still open**
40. Med — sp has no error data in Mode F rows (zero spread flagged, not modelled).
41. Low — `l3_overlay` slope has no cos(lat), in m per grid step; the global `statics.py` will use metric slopes.
42. Low — gust model uses UTC hour and a hard-coded station flag; global fit needs local solar hour.
43. Med — Denver inversion error belongs to the model; the IGRA jump head (L3-27) is the planned fix.
44. Med — superadiabatic and shear overshoot after the trust blend and shear map (0.338 vs ERA5 0.219; shear 1.7x) (IL-104).
45. Low — evaluation flaws E6-E10 (wind speed error, worst-month print, hour-binned Gaussian baseline, range map fitted on known drivers, dropped balloons): fixes planned in `PLAN.md`; completion not recorded in the logs I read.
46. Low — the F-15 item in the Gemini review (`m_final = 8`) was cut off; the rest was not received.

---

## 2. FIXED

**Review bug fixes (F-n; all with tests, in the code by default)**
1. F-1 `api.values` filtered a wind-direction literal, so u/v were evaluated twice.
2. F-2 `couple(..., gaussian_copula)` now refuses `wind_dir@z` (0-360 is not linear).
3. F-3 `to_heights` imported dask/xarray at module top; now lazy.
4. F-4 `load_npz` / `Sampler` changed module-level globals; each Sampler re-applies its own.
5. F-5 near-term ensemble never applied `liquid_rh`; now applied.
6. F-6 the tool snapped to the nearest grid point (stair steps); now bilinear block allocation.
7. F-18 gust model hour and station flag fixed (UTC hour, nearest ASOS).
8. F-21 vertical-wind head was fed site-adjusted values; now sampled before the shift.
9. F-22 `to_site` shifted t2m and sp but not the 10 m temperature; shift now fades with height.
10. F-28 index forecaster: standardised targets, positive-definite covariance, QBO phase terms.
11. F-30 NaN validation could save a checkpoint with no state; now raises. Block split uses true day numbers.
12. F-31 feature activation now requires the exact feature list in order.
13. F-32 gust and soak read columns by position; now by name plus a count check.
14. F-33 router, mix and scenario weights are validated; driver horizon cap 12 → 60 months.
15. F-34 shape diagnostics default to unknown drivers; pre-clip rate reported.
16. F-35 dataset now keeps row ids, source masks and correction version (sidecar).

**Training and data fixes**
17. P-9 early stopping used changing validation noise; now fixed noise.
18. P-19 station correction was fitted on validation years; now 1991-2020 only (leak fix).
19. F-19 NaN in the humidity loss run fixed before the retrain.
20. F-20 first station-blend dataset was invalid (rename bug); rebuilt.
21. L3-25 Denver mountain columns lost the top heights (23 % of rows dropped); `--fill-top` keeps them.
22. L3-35 shuffle `cell_keys` assumed 29 longitudes per row; now uses the real grid.
23. L3-30 / `noise_t` clip value shadowed the `c` tensor, breaking every Student-t model; renamed.
24. `model.py` shadowing bug behind the second L3-30 failure fixed.
25. `mc.py` "filled" check: filled = above 20.5 km MSL (was a wrong criterion).
26. Pitfall check 1b fixed for block validation; duplicate flag fixed.
27. Loop runner fixes: recursive resume helper, wait deadlock.

**Review fixes of 2026-11-07 (commit d997f62, 8 items)**
28. Export guards and a solar-hour manifest.
29. Shuffle columns taken from the grid.
30. Mode F hour and point handling.
31. Dissimilarity index computed on the sphere.
32. Region longitude check.
33. Flight w and gust use the Sobol draws.
34. `fill_top` index stored; opt-in `fill_mask` loss.

**Global review (done)**
35. ERA5 invariants including `z_sfc` fetched (`era5_invariants.npz`).
36. Global fetch runs under a retry loop and resumes per month.
37. Store completeness checked: 420 of 420 months, 7,483 points, steps and hours right, no saturated int16.

**Data and Colab guides**
38. IFS ensemble first pull had NaN holes; refetched as `tempest_wb2_ifs_ens_v2` (delivery pending, about 10 h from 2026-11-08).
39. ARCO fill: the 336 `.nc` months placed in `era5_cds`, nothing overwritten.
40. IFS extended-range guide: humidity is empty at 10, 50, 100 hPa; `Q_MIN_LEVEL = 200` and the check updated (2026-11-08).
41. Weekly-average meaning of the extended-range stores confirmed against ERA5 (168 h window from 12 h before day k).

**This review session**
42. Shear gate split: int16 parity 1 %, vs ERA5 5 %, vs balloons 10 % (`LAUNCH_PLAN.md` A3).

---

## 3. CHECKED, NOT A BUG

**Gemini model review (2026-11-06)**
1. `Sampler._activate` skipping `set_active` for overlay checkpoints: deliberate.
2. "SIREN without w0 is quasi-linear": overstated (it passed NM/TX and shape).
3. "`clim_u_d5000` is a step difference": wrong, it is the absolute 5 km wind.
4. The w head running before `to_site`: correct, it was trained on grid-elevation profiles.
5. "Zero residual guarantees skill15 = 0": wrong, a point forecast has worse CRPS than the climatology ensemble.

**Global review (2026-11-06)**
6. Terrain weight "sin(lat) kills the Southern Hemisphere": it is cos(lat), factor 1 at the equator.
7. Grid indices off by half a cell: stored coordinates equal the point coordinates for all 7,483 points.
8. `arccos` distance unstable below 1°: error ~1e-8 deg in float64.
9. The 24-step hour cycle aliasing with the calendar: 40-47 steps per (month, hour), near uniform.
10. Station/ASOS lookups hard-coding the pilot: they read `region.load()`.
11. sp int16 range too small: 14.5-145.5 kPa covers every surface; encode raises on a miss.
12. Longitude distance breaks at ±180: `gc_deg` is periodic.

**Other**
13. `site_elev - grid_elev` is zero in training rows: not a bug (box elevation collinear in one box); the `to_site` inversion is tested at G2 (Salt Lake).
14. "Bottom-up running sum is unchecked": the loss scores the rebuilt profiles.
15. Old DI numbers (L3-28) changed with the sphere metric: DI is diagnostic only, no verdict moves.
