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
