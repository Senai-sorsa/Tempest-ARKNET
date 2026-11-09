# Fixing issues (found 2026-11-07, one review session)

**Status: nothing here has been applied to code.** This file is the list. Backlog rows (`IL-n`) are in `docs/logs/AUTOPILOT.md`; the backup item is `docs/agent/ASK_LATER.md` 13. "Measured" means I ran it on this PC; everything else comes from reading the plan files and code and has not been tested.

## A. Gates that look more precise than the data (change what counts as a pass)

| # | Issue | Evidence | Fix | Tracked |
|---|---|---|---|---|
| A1 | The shear gate "99.9th percentile within 5 %" mixes three different questions | float vs int16 should cost almost nothing; ERA5 itself understates real shear (balloon shear 2.5-3x wider, Houchi 2010) | Split: float vs int16 within **1 %**; model vs ERA5 within 5 % per band; model vs held-out balloons within 10 % | done in text, `docs/plans/LAUNCH_PLAN.md` A3 item 4 |
| A2 | The "within seed tolerance 0.0006" no-regression gate is below the noise | L3-37: the choice of the 5,000 held-out rows alone spans 0.0025 in skill15 | Paired 3-seed comparison, tolerance computed from those seeds, at ERA5 and balloons | IL-109 (NOW) |
| A3 | Tail gates may rest on few independent events | `shear_map._band_values` pools every layer of a band (rows x layers), but neighbouring layers of one row are correlated, so independent extreme events are far fewer than the count | Report the effective count and a date-block bootstrap interval (IL-87) for every tail number | IL-110 (NOW) |
| A4 | "CRPSS > 0 vs climatology" is too weak | Denver +0.0100 is mostly local climatology (blend weight 0 in several bands) | Also require a margin over climatology and a win over the Gaussian/GRAM-style baseline, per band | IL-111 (NOW) |
| A5 | One gate was picked, not derived | GLOBAL_PLAN G2: the 12 % shear-vs-IGRA gate is "not reachable"; 15 % is used "as an assumption" | Derive it from the station-to-station scatter of the 987 stations once `data/igra_heights` exists | IL-112 (NOW, blocked on IGRA convert) |

## B. Wind and shear tails (model weakness, ideas to try)

Measured: the plain model **under**-produces shear (NM/TX 99.99th: 0.0024 vs ERA5 0.0078); the shipped stack **over**shoots (0.0134, 1.7x ERA5) and the Denver inversion step is the worst band.

| # | Idea | Tracked |
|---|---|---|
| B1 | Fit the tail on balloons (IGRA), not ERA5 | IL-103 |
| B2 | Cap the shear overshoot with a balloon-based quantile ceiling | IL-104 |
| B3 | Calibrate shear as its own target after the shuffle | IL-105 |
| B4 | Regime-conditioned tail scale (jet proximity, stability, hour, terrain) | IL-106 |
| B5 | Tail-weighted scores (upper 1 %, exceedance) in `diagnose.py` | IL-107 |
| B6 | Validate upper-level shear 12-35 km with the extended IGRA heights | IL-108 |

## C. Results that could be overturned (how the numbers are measured)

| # | Issue | Evidence | Fix | Tracked |
|---|---|---|---|---|
| C1 | The headline (+0.0277) is optimistic: 2024-25 was used for 17+ decisions, and the one-time 2026 H1 test is already spent on the pilot | hard rules; `docs/final_test/` ran 2026-11-06 | Add a second untouched confirmation window and report both | IL-113 |
| C2 | Balloon verification is not fully independent | ERA5 assimilates radiosondes; station maps are fitted on IGRA | Score seen vs unseen stations separately; add one source ERA5 does not assimilate | IL-114 |
| C3 | The climatology baseline may flatter the model | fixed 1991-2020 climatology rewards capturing warming (2024-25 is warmer); not checked whether the baseline has a trend | Add a trend-aware baseline and report skill vs both | IL-115 |
| C4 | Layers above 18 km (and the 80 km claim) are fills, not skill | most heights have no real truth | Label "filled, not skilled"; score only where balloons (~30-35 km) or MERRA-2 give truth; keep out of the headline | IL-116 |
| C5 | The "works worldwide" claim is unproven | a never-seen box (B-raw) scored -0.176 vs climatology; home box +0.016 | Leave-one-box-out and 1,000 km block CV decide it; treat global as unproven until then | GLOBAL_PLAN gates |
| C6 | Most keep/drop verdicts are decided at the +-0.001 level, which is noise | seed spread 0.0025 (L3-37), gain over climatology only about +0.03 | Use A2 first, then re-read verdicts decided on a single seed | IL-109 |

## D. Data issues

| # | Issue | Evidence | Fix | Tracked |
|---|---|---|---|---|
| D1 | **Humidity differs between the two `era5_cds` sources below the terrain** | Measured on 199801 (ARCO `.nc` vs CDS `.grib`, same 8 levels): t/u/v/z match; RH above ground matches (mean -0.1..-0.4 %RH, rms 1-2); RH **below ground differs by -12 to -19 %RH** at 975/950/900 hPa (T >= 280 K). 336 of 420 months are ARCO, 128 are CDS | Confirm every consumer of `era5_cds` masks below-ground rows with z_sfc; repeat the comparison on 5 of the 44 overlap months | IL-117 (NOW) |
| D2 | The CDS downloader still asks for months ARCO now covers | `fetch_cds` only looks for `.grib` (Colab ARCO fill guide, step 4) | Stop it, or restart with `--last 1997`, once the ARCO portions are done | not logged elsewhere; to do |
| D3 | 44 months exist as both grib and nc (1998-01 to 2001-08) | the guide says the grib is used | Harmless extras; keep until D1 is closed (they are the comparison material) | n/a |
| D4 | The IGRA refresh scope is unclear | `data/raw/igra_2026` holds 2 entries (279 MB) | Check whether it covers all stations or only Denver and the pilot station | to check |
| D5 | The five-month spread of D1 is a single month so far | one month measured | See D1 fix | IL-117 |

## E. Risks to the machine and the work

| # | Issue | Evidence | Fix | Tracked |
|---|---|---|---|---|
| E1 | **No off-machine backup of anything** | 14 local commits not on `origin/main` (your never-push rule); `models/` 6.7 GB, `data/train` 85 GB, `data/raw` 115 GB on one disk; the Colab zips in Downloads are the only second copy of the global HRES, refetch and ARCO data | Your decision: copy `models/` and small configs to an external or cloud folder after each phase, and/or push to a private repo; keep the Colab zips until the stores are verified | ASK_LATER 13 |
| E2 | Disk will get tighter | about 150 GB free; the fetch chain still adds about 57 GB (IGRA, G2 boxes), taking `data/raw` to about 172 GB of the 200 GB cap | Watch free space; prune only with your approval | n/a |

## G. Gemini review of `tempest_weather` and the calibration experiments (added 2026-11-08)

**Status: nothing applied to code.** I checked every claim I could against the current files (read the code, or recomputed the maths). "Confirmed" means the code does what is claimed. Numbers Gemini quotes from its own tests (for example "-43 % shear") were **not** reproduced. The pasted text ended in the middle of the F-15 item (see G22), so anything after that point was not reviewed.

### G-A. Code issues in `tempest_weather` (Gemini 1.1-1.10)

| # | Claim | Verdict after checking | Priority | Fix (from Gemini, with my changes) | Tracked |
|---|---|---|---|---|---|
| G1 | Gaussian-copula rebuild in `sample_sobol` smooths tail shear and inversions | **Plausible, not reproduced.** The code does map each height back through its own `_ppf` (no tail dependence). The "-43 %" is from Gemini's synthetic test | High | When unconditioned, pick whole profiles from the pool by stratified Sobol (like `WholeSample.draw`); when conditioned, apply the Schur update as a residual on whole members. First reproduce the loss on the real pool (99th/99.9th shear before vs after `sample_sobol`) | IL-128 |
| G2 | `_cdf`/`_ppf` clamp at the pool min/max, so an out-of-range observation makes a shear spike | **Confirmed** (`engine.py` lines 59-63: clip at 1e-6, interpolation inside the pool) | High | Linear tail extrapolation from the outer 5 % slope. Use the **same** tail method as IL-103/F4, not a second one | IL-129 |
| G3 | Dryden potential temperature is linearised (`theta = T + 0.0098 z`), so N^2 and Ri are too low aloft | **Confirmed** (`dryden.py` line 26). My recomputation: N^2 is low by about **31 % at 10 km and 45 % at 18 km** (Gemini says 40 % / 58 %), same direction | Medium | `N^2 = (g/T)(dT/dz + g/cp)`, `Ri = N^2 / max(shear^2, 1e-6)` | IL-130 |
| G4 | Boundary-layer factor floors at 0.05, so surface turbulence leaks to 18 km | **Confirmed** (`np.clip(..., 0.05, 1.0) ** 0.75` leaves 0.106, so sigma_w keeps 0.137 u* at all heights) | Medium | Floor 0.0 plus a small physical background (about 0.05 m/s) independent of u* | IL-130 |
| G5 | `w_total` drops the synoptic vertical wind | **Confirmed** (`synthesize` has no `w` input and returns `w_total=wg`) | Medium | Add `w=None`, interpolate to the fine grid, return `wf + wg`; pass `batch.get("w")` | IL-130 |
| G6 | Reader clamps to the 10 m node, so the pad (0 m) gets the 10 m values | **Confirmed** (`flight_sim_readers.py` lines 54, 77, 95 clamp to `z[0]`); a code comment calls it intended. Gemini's pressure and temperature errors are plausible, not measured | Medium | Add a 0 m AGL node (t2m, sp, rh2m, reduced wind); test that `conditions(site)` equals (t2m, sp, rh2m) | IL-131 |
| G7 | Geometric vs geopotential altitude mismatch (`_Tail` uses constant g and US76 bases as geometric; baro altitude is geopotential) | **Confirmed**, and the file's own comment calls it an accepted approximation. My number: **51 m at 18 km** (Gemini 57.4 m); about 0.8 % in density | Low | Convert with `H = R z / (R + z)` in the two places | IL-131 |
| G8 | `site_shift` adds an artificial lapse-rate change | **Confirmed in size, sign mis-stated.** The fade term changes dT/dz by `LAPSE * dz / 1500` = **2.17 K/km for dz = 500 m** (a warming-with-height perturbation, not a "subtraction") | Medium | Test two options against the pad-elevation check (A1): per-sample boundary-layer lapse, or constant shift to the mixed-layer top then fade. Keep the current fade unless one wins | IL-132 |
| G9 | `atmosphere_sequence`/`downrange` never update `w` after reordering, so `w[j]` belongs to a different profile | **Confirmed** (`api.py` lines 403-410 reassign u, v, T, RH, t2m, sp, rh2m and recompute p, rho, a, but not `w`) | High | Include the 44 `w` columns in the coherence step, or re-sample the `w` head after it | IL-133 |
| G10 | Surface pressure has zero spread in past/forecast modes | **Confirmed** (`api.py` lines 207 and 256: `np.full((n, 1), ...["sp"])` unless the optional asset is loaded) | High | Add a lead-dependent sigma for sp, fitted from the ERA5/ASOS data on disk (Gemini's 50-250 Pa is a guess), correlated with t2m or wind | IL-134 |

### G-B. Assumptions and optimisation (Gemini section 2)

| # | Claim | Verdict | Action | Tracked |
|---|---|---|---|---|
| G11 | Dryden Euler sub-steps and the 4 km burn-in are slow and inexact | **Confirmed, already planned** (S1, Section 1 of `docs/plans/SECTIONS_PLAN.md`). The closed-form matrices are still unverified: test variance and spectrum against the current output | Do with S1 | S1 |
| G12 | `h_pbl = 1200 m`, `ell_cat = 20 m` and the uniform 3-15 m/s gust peak are arbitrary | **Confirmed** (defaults in `dryden.py`). Fair point for deep desert afternoons vs shallow winter nights | Per-sample `h_pbl` from the profile; draw the gust peak from the sample's own `gust_mu`/`gust_beta`. Goes with R1 (roughness) in 2A | IL-135 |
| G13 | Acoustic ray tracer uses dry temperature, integrates downward only, and uses the trapezoid rule near a singular integrand | **Confirmed for dry T and trapezoid** (`acoustics.py` lines 19, 48-50). The module is peripheral | Low: use the moist sound speed `atm["a"]`; mid-point or substitution near turning points | IL-136 |
| G14 | `SMOOTH = 9` heights is a different physical length at different heights | **Confirmed** (9 levels span 1.24 km low, 4.5 km mid and upper) | Experiment: smooth in metres (about 2 km Gaussian), opt-in flag, 3 seeds | IL-137 |
| G15 | One scalar `inflate = 1.5` for every unobserved eigenvalue | **Confirmed** (`engine.py` line 66; the docstring says it came from one check). The paste cuts off the formula Gemini proposed | Experiment: inflation that decays with correlation distance from the observed heights | IL-138 |
| G16 | Three saturation-vapour formulas (`es_liquid`, Buck in `avionics.py`, Bolton in `igra_to_heights.py`) | **Confirmed.** The dewpoint-depression clip (147 K) and the `/25.0` RH scaling are arbitrary but harmless | Low: unify on `es_liquid`; measure the round-trip difference first | IL-136 |
| G17 | `M_CAL = 199` block slicing `[:n]` can take a biased slice of the last block | **Conditional.** The last partial block is cut from the front. That is harmless when members are in random order, but biased if they come out sorted (opt-in PIT with no shuffle template for the bin) or from one grid point (climate mode) | Permute within each block before slicing, or generate exact counts (matches S5 in the plan) | IL-139 |

### G-C. Flaws Gemini found in earlier experiments (Gemini section 3)

| # | Claim | Verdict | Action | Tracked |
|---|---|---|---|---|
| G18 | `pit_apply` / `pit_recal.apply` return samples sorted along the member axis, so the result is comonotonic if no shuffle follows (this confounded IL-86) | **Confirmed in code** (the docstring itself says "sorted along m"). In the shipped path a shuffle follows, and an empty template bin leaves the order sorted, which is the risk | Restore the input member order (`take_along_axis` with the input ranks) as an opt-in; recheck IL-86 | IL-140 |
| G19 | Trust-blend weights are a step function across bands, creating seams at 1, 5 and 12 km | **Plausible, fits the L3-29 numbers** (superadiabatic 0.283 to 0.474; weight 0 below 1 km, 0.05-0.35 above). Not tested | Smooth the weight across heights (Whittaker smoother already in `station.py`), then rerun L3-29 and L3-33 | IL-141 |
| G20 | Debias shifts RH in physical space after range calibration, collapsing the lower tail at 0 % | **Plausible, fits L3-34** (humidity coverage ruined). `debias.py` subtracts the mean error, then clips, and states it shifts only the mean | Debias in the transformed coordinate (log dewpoint depression or logit), before conversion to physical | IL-142 |
| G21 | L3-43 `fill_mask` looked neutral only because scoring still uses the filled (isothermal) truth | **Plausible and important.** `score.py` has no fill masking (only `mc.py` has the `filled` / `real_12_18km` split), and 23.7 % of Denver rows were filled | Mask `score.py` by `fill_top_idx` (or use the `mc.py` real-height subset) and rerun L3-43, mask off vs on. Ties to C4 (filled heights are not skill) | IL-143 |
| G22 | F-15 (`m_final = 8`) degraded vertical correlation because of loss weighting | **Cannot assess:** the pasted text ends mid-sentence | Send the rest | none |

### Gemini recommendations: which I used

- **Used as given:** G2, G3, G4, G5, G6, G7, G9, G12, G14, G16 (low priority), G17, G18, G20, G21.
- **Used with changes:** G1 (reproduce the loss first, then fix with whole-profile selection), G8 (test two options, keep the current fade unless one wins), G10 (fit sigma from data instead of Gemini's guess), G19 (smooth the weights, then recheck), G15 (experiment; formula incomplete).
- **Not used:** none rejected outright. The numbers I could not reproduce (G1's -43 %, G3's 40 % / 58 %, G7's 57.4 m) are flagged and not relied on.
