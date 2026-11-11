# ASK_LATER: items for the user to decide or run

Each entry has the reason, the evidence and the exact command or change.

## 1. Make the forecast logger survive reboots (Windows Task Scheduler)

- **Reason:** the logger (`tempest.ops.logger`) currently runs as a background loop (`--loop 12`) started by Claude.
  It stops when the machine reboots or the session's processes are cleaned up. Days not logged are lost for good,
  because Open-Meteo does not keep past ensemble members.
- **Why not done by Claude:** creating a scheduled task is persistent system configuration, which the permission
  check blocked.
- **Evidence:** `data/ops/logger.log` (one line per request), files in `data/ops/raw/<site>/<model>/`.
- **Command (run in PowerShell; twice a day, low priority, safe to run any time because stored slots are skipped):**
  ```
  schtasks /Create /TN "TempestForecastLogger" /TR "C:\Users\Senai\Tempest-ARKNET\scripts\run_logger.cmd" /SC DAILY /ST 03:15 /RI 720 /DU 24:00 /F
  ```
  Remove with `schtasks /Delete /TN "TempestForecastLogger" /F`.

## 2. History split and force-push (from HANDOVER section 9)

**Status (2026-11-05):** the history is rebuilt locally as 75 small commits with the same final tree (backup branch `backup-pre-rewrite` keeps the old one). Only the push is left, because the auto-mode classifier blocks force-pushes: run `git push --force-with-lease=main:ba2e2df origin main` yourself (type `! git push --force-with-lease=main:ba2e2df origin main` in the prompt). The old `update-ref` command below is no longer needed.


```
git update-ref refs/heads/main split-main ba2e2df && git push --force-with-lease=main:ba2e2df origin main && git worktree remove <old scratchpad>/splitwt && git branch -D split-main
```
The scratchpad of the old session is gone; if the worktree folder has vanished run `git worktree prune` first.
Local commits made by Claude would sit on top of `ba2e2df`; rebase them onto `split-main` before pushing.

## 3. A2 go/no-go limits (P(scrub), PHASED_PLAN 3.9)

Not built: needs the wind, shear, temperature and RH limits per vehicle or launch from the user. Send them and
3.9 plus any go/no-go output get built.

## 4. Real NASA Earth-GRAM for the comparison (PHASED_PLAN section 8)

- **Reason:** the user wants the final system shown to beat Earth-GRAM. A statistical stand-in ("gauss", built the same way)
  is scored already; the real program needs the NASA GRAM Suite, which must be requested from NASA (software catalog).
- **Not done by Claude:** getting software that needs an account/agreement with an external party.
- **Evidence:** E12 vs gauss table in PHASED_PLAN section 8.
- **What to do:** obtain the GRAM Suite (Linux/WSL, has a Python API), tell Claude where it is installed; Claude then runs
  it at Spaceport America and Midland for the 2024-25 test hours and scores it with the existing code.

## 5. Data for the thermals check (PHASED_PLAN 3.3): sshf and high-resolution soundings

- **Reason:** `tempest/output/thermals.py` (convective boundary-layer scaling) needs the surface sensible heat flux H.
  ERA5's `sshf` is not in the Earthmover store (checked: `single/temporal` has blh, fg10, ssrd, ssr, slhf but no sshf). It
  has to come from the Copernicus CDS (`reanalysis-era5-single-levels`, variable `surface_sensible_heat_flux`, box
  31-34 N, 108-101 W, 1991-2025, hourly). The check of the coefficients needs NWS 1-second radiosonde data (balloon rise
  rates) at Santa Teresa and Midland, which is not yet downloaded.
- **Why not done:** the one CDS downloader (`fetch_cds`, 420 monthly requests, 33 done after a day) already fills the
  user's queue; a second job would compete with it and break the "one downloader" rule in HANDOVER section 1.
- **Evidence:** thermals module and its 4 physics unit tests exist; no data check yet. The module is off everywhere.
- **What to do after `fetch_cds` finishes:** run a one-year-per-request pull of `surface_sensible_heat_flux` (35 requests,
  small), then `tempest.profiles.surface_hourly` gets `sshf`, then compare `w_sigma` with rise-rate variance.

## 6. Chronos-2 and CPC/IRI/NMME in the index-forecast bake-off (PHASED_PLAN 3.7)

- Not run: needs a model download (Chronos-2 weights from Hugging Face) or archives of the other forecasts. The run that
  was done (persistence, climatology, ridge regression, analog draw) already shows regression beating the analog draw.
  Chronos-2 is a candidate for the improvement loop. Command idea: `pip install chronos-forecasting` into the venv, then add a
  method in `scripts/index_bakeoff.py`.

## 7. Two Colab notebooks to run when you are at the computer (optional, each saves hours or days)

Both extract a small box from Google's public archives inside Google's network, so nothing large comes to your machine.
- `notebooks/arco_fill_colab.md`: the 8 boundary-layer ERA5 levels (975-750 hPa) from ARCO-ERA5, as `<yyyymm>.nc`, run newest month first. Speeds up or replaces the CDS download.
- `notebooks/wb2_colab.md`: IFS HRES forecasts 2016-2022 at 1/3/5/7 days (a few MB per year). Needed for the calibrated forecast modes (IL-6).
Copy the outputs to `data/raw/era5_cds/` and `data/raw/wb2_hres/`, then tell Claude.

## 8. Optional: second forecast-archive pull with the whole diurnal cycle (needed to use mode F at every hour)
**User 2026-11-10: wait until the end for the Colab run; continue with the data we have.** Correction: the 00Z + 12Z refetch (`data/raw/wb2_hres_v2*`, valid 00 / 12 / 18 UTC = about 17 / 05 / 11 h solar) is on disk since 2026-11-06 but was never used (plan F-V2); only 06 UTC (about 23 h solar, night) is missing.
The archived HRES cases are 00 UTC starts at whole-day leads, so every valid time is 00 UTC (about 17:00 local solar time in the box). Mode F is therefore only trained for the late afternoon; the tool uses it only between 14 and 20 solar hours and falls back to the climate generator otherwise (flagged).
To cover 06-21 h: in `notebooks/wb2_colab.md` change `--leads` to `30 36 42 54 60 66 78 84 90 102 108 114 126 132 138 150 156 162` (valid times 06, 12, 18 UTC) and rerun the cell with `--out .../tempest_wb2_diurnal`; copy the files to `data/raw/wb2_hres_diurnal/` (about 100 MB). Then mode F can be trained with the hour of day as an input.

## 9. Needs the user, asked at the very end: North America (docs/plans/REGION_PLAN.md, R-6)
Serving places outside the pilot box needs new training data over the target region. The unattended part (region file, many-station correction, a small portability dry run) is done or queued; the data pulls for a continental lattice need Colab runs (ARCO-ERA5 in Google's network, about 25 TB read for 6-hourly 1991-2025) and the choice of the region and lattice spacing (1 or 2 degrees). Decision for the user: how far (CONUS only, or Canada and Mexico), what spacing, and whether to run the Colab pulls.

## 10. Stage 6 (tools for the flight simulator only, no changes to the weather model): RESOLVED 2026-11-06, the user said to start it without asking once all tasks are complete
Plan file: C:\Users\Senai\Downloads\tempest_arknet_flight_sim_expansion_blueprint.md (not read yet by design). Starts only after the user approves, after the final model is built.

## 11. Needs the user: GitHub
Nothing is pushed since commit 5864545 (user rule 2026-11-05: push only after approval or at the very end). Local commits continue. Ask at the end: push all.
- (loop 2) IL-79: if you want forecasts at 2/4/6 days, the IL-75 Colab notebook needs rerunning with those leads.
- (loop 2) Turn on the H1b post-processing (half-strength PIT map + RH seasonal widths above 1 km) in `scripts/export_final.sh`? It passes shape (4 better, none worse) and the ERA5 headline (skill15 +0.0209 to +0.0276, 99 % coverage error 0.0049 to 0.0020), balloons neutral; judged on 2024-25 only, not on the already-used 2026 test.

## 12. Loop 3 / global scaling (docs/plans/GLOBAL_PLAN.md)
- G4 global data needs more than the 100 GB `data/raw` cap (estimate in GLOBAL_PLAN G4): approve a higher cap or an external drive?
- `data/train` holds 56 GB of npz copies of older variants; OK to prune the ones no adopted model uses?
- G3 needs a WeatherBench-2 HRES pull for the new region (Colab, same notebook as before).

### 12b. Data-cap headroom (2026-11-06, `docs/data/DATA_NEEDS.md`)
`data/raw` is 80 GB of the 100 GB cap. Nothing is deleted unattended. Candidates, if you approve:
- `data/raw/era5_em_denver` (1.3 GB, Denver 2016-23). `era5_em_denver_full` (1991-2025) supersedes it.
- `data/raw/era5_em` (30 GB, the older 18-variable NM/TX store) vs `era5_em80` (32 GB): which one the current datasets are built from has to be checked before pruning.
- New IGRA stations will be kept as converted profiles only (~9 MB per station), not as derived text files (~140 MB).

## 13. Off-machine backup (added 2026-11-07, risk found in the audit)
Git has 14 local commits that origin/main does not (your rule: never push), and `data/` and `models/` are never in git. `models/` is 6.7 GB (2015 files), `data/train` is 85 GB and `data/raw` is 115 GB on one disk, with no copy anywhere else (the Colab zips in Downloads are the only second copy of the global HRES, ARCO fill and refetch data). One disk failure loses the trained models and days of downloads. Options if you approve: (a) copy `models/` plus the small configs to an external drive or cloud folder after each phase, (b) push the commits to a private repo, (c) keep the Colab zips until the stores are verified. Nothing done.

## 14. Needs the user: the final test window (added 2026-11-09, new session)
The one-time 2026 January-June test was already run on 2026-11-06 01:31-01:49 on the pilot model (`data/FINAL_TEST_DONE`, `FINAL_REPORT.md`). The 2026-11-09 handover still listed it as a future step; that is corrected. Running it again on the current system would reuse a seen test set. Options:
- (a) Report the existing 2026 H1 result as it is (pilot model) and judge the current system only on 2024-25 (used for about 30 decisions, so optimistic).
- (b) Open a NEW one-time window: 2026 July-October (ERA5 is published with about 5 days' delay; ASOS and IGRA for 2026 are partly on disk already in `data/asos_2026`, `data/igra_2026`). Download, lock file, run once at the very end. Recommended.
- (c) Both: (a) for continuity, (b) as the real final test.
Until you answer: no 2026 data is used for anything; the plan's Group E waits for this choice.

## 15. Needs the user: pad truth (added 2026-11-09, plan item P5)
- A wind record from the pad itself (anemometer, even one month, 10 m if possible; `docs/templates/pad_observations.csv` has the format). One month cut the median wind error by about 25 % in tests.
- The raw flight logs (GPS track, especially the descent under the parachute) of the validation rockets in the flight_sim branch: the drift is a wind profile at the exact pad and hour, the pad truth several checks are waiting for.

## 16. Needs the user: a package install for radar winds (added 2026-11-09, plan item P3)
NEXRAD VAD wind profiles (the radar's wind every 300 m up to about 10 km, every few minutes, free; El Paso KEPZ stands next to the EPZ balloon site) come as NWS Level III NVW files, which need a decoder: MetPy (`pip install metpy` into the project venv, pure Python, BSD licence) is the usual one. Installing packages is your call, so P3 waits. With it: compare VAD winds with EPZ balloons, then feed them to the existing conditioning (500-2000 m data gave +15-17 % aloft).
Also (P7, optional): `rasterio` would let the site model use the NLCD land-cover roughness map; without it P7 uses terrain only.

## 17. Needs the user: decisions taken autonomously on 2026-11-09 that change what the tool reports (confirm or ask to revert; each has an off switch)
- `tempest_weather.api.GUST_PHYSICAL = True`: gusts are the PHYSICAL 5-second peak (one-minute ASOS data: about 1.4 x the wind at every speed) instead of the METAR convention (gust = wind in most light-wind hours). Gust CRPS -65 % (measured wind) / -21 % (model wind) on 2021-23, confirmed at unseen El Paso (0.70 vs 1.76). Effect: higher light-wind gusts and an OpenRocket turbulence estimate that is no longer about 0.
- `tempest_weather_v2.launch.MEASURED_GUST_LAW = True`: after observe(wind_10m=...) the gust uses the law fitted on measured winds (storm gusts about 1.35 x instead of 2.4-4.8 x).
- `Launch(past_era5_anchor=True)`: past mode centres the near-ground wind on ERA5 10 m (gain at four sites, -3 to -20 %).
- Gust draws in `ranking.py` / `registry.py` clipped at the 10 m wind (by definition gust >= wind).
- **ANSWERED 2026-11-09 23:50 (user): keep all four.**

## 18. Needs the user: open decisions (2026-11-09 late)
- **Final test 2026 July-October:** data being downloaded and prepared; runs only when you say the model is final (`CONFIRM_FINAL=yes bash scripts/final_test_2026h2.sh`).
- **Denver tool model:** the Denver-trained C4w passes on two training seeds (+0.0007 / +0.0004 mean skill15, t2m +0.004); re-exporting the Denver assets (now from the lighter generator_denver.pt) needs your OK.
- **MetPy in pyproject:** installed with `uv pip` into the venv but not added to pyproject.toml; a `uv sync` would remove it (radar winds need it). Add it as a dependency?
- **ANSWERED 2026-11-09 23:50 (user):** final test waits for "model is final" (the user will say when; report when the data is ready); Denver export with the Denver-trained C4w: YES (back up first); MetPy: add as an OPTIONAL extra (`radar`) in pyproject.toml.
- Empty folder `tempest_weather/assets_c4w_staging` and three empty one-minute files (`data/raw/asos1min/LRU_*, ALM_*, PEQ_*`, 52 bytes, those stations have no one-minute data) can be removed by you (the rm guard blocks me).

## 19. Needs the user: defaults changed autonomously on 2026-11-10 (confirm or ask to revert)
- `tempest_weather.api.FORECAST_SOLAR` (14, 20) -> **(2, 20)** h solar: forecast mode now answers mornings and midday. Evidence (`scripts/fv2_eval.py`, `docs/results/logs/fv2_eval.log`, the shipped mode F on the 00Z + 12Z refetch, test year 2022 that mode F never saw, against an hour-aware climatology): CRPS skill at 1 day 0.67 (05 h) / 0.74 (11 h) / 0.71 (17 h, served before), at 7 days 0.19 / 0.21 / 0.24, better than the raw forecast everywhere. Before, those hours fell back to the climate model. 23 h solar (night, 06 UTC) is untested (needs the Colab run at the end). The lead limit stays 7.5 days (at 8-10 days the gain is small).
- Asset choice by hour (`api.region_assets(..., solar_hour=)`): when a place has a day set and an all-hours set, the day set answers by day and the all-hours set at night. No effect until an all-hours set is installed (A24).
- Sequences / downrange for a region without its own correlation tables (Denver) used the NM/TX tables silently; they still do, now with a flag in `quality`.
- **Installed 2026-11-10 01:50 for the 24-hour goal (your instruction of 2026-11-10: all data should cover the entire day):** the NM/TX tool model is now the all-hours stack (day neutral on balloons +0.0099 -> +0.0102, night 12Z balloons -0.021 -> +0.016); Denver keeps its day model by day and uses a new all-hours set at night (night -0.068 -> +0.015). Backups: `models/assets_backup_2026-11-10_day/`, `models/assets_denver_backup_2026-11-10/`. Say if you want either reverted.
- **Installed 2026-11-10 02:15:** Denver forecast mode (Denver had none; forecasts fell back to climate): skill 0.68 / 0.57 / 0.43 / 0.26 at 1 / 3 / 5 / 7 days on the 2022 test year. In both Denver sets.
- **Installed 2026-11-10 04:50:** NM/TX forecast mode v3 (trained on all three valid hours; morning skill +0.04..+0.06) and the all-hours vertical-wind head (night w -1.6 % CRPS at 0-1 km, day equal). With these the NM/TX tool has no day-only component left; Denver has no w head and borrows NM/TX's time / distance correlation tables (flagged).
- **Installed 2026-11-10 06:55-07:10 (Denver parity):** Denver now has a vertical-wind head (calibrated: 99 % coverage 0.99), its own time / distance correlation tables (sequences no longer borrow NM/TX's) and its own physical gust law (DEN + APA one-minute data; better than the NM/TX law in strong wind, slightly worse below 5 m/s). Still missing for Denver: past mode (needs Denver balloons, which end in 2022).

## 20. Needs the user: low-level wind data that needs a login (2026-11-10)
- **DOE Wind Data Hub (A2e / OpenEI):** TTU SWiFT 200 m tower (10 levels, inside the NM/TX box) and the WFIP1 sodars (30-200 m every 10 m, West Texas 2011-12). The user is registering. Put the files in `data/raw/a2e/` (one folder per dataset) or give an API token.
- **EDI (Jornada Basin LTER CSIS met stations, wind at 0.37 / 0.75 / 1.5 / 3 m, 5-minute, 2013 onward, about 80 km from Spaceport):** since 2026 the EDI API, its portal and the LTER DataONE node refuse unauthenticated downloads (checked 2026-11-10; metadata probes only, nothing downloaded). Needs a free EDI account (portal.edirepository.org). Useful packages: knb-lter-jrn 210548009 (block 9, heights documented), 210548013 and 210548001 (about 211 MB each, `csis-NN_5min_L2_rev_*.csv`). Put them in `data/raw/jornada_csis/`.
- **2026-11-10 (W6, default ON for soft observations):** `observe(..., age_hours= / distance_km= / elevation_diff_m=)` now updates the 10 m wind speed in normal-score space of the pool's own speed distribution (persistence 0.72 per hour of age). Hour-ahead test on ASOS 2023-25 (300 hours per station): CRPS 1.148 -> 1.140 (TCS), 1.016 -> 0.987 (MAF); 90 % coverage 0.74 -> 0.81, 0.85 -> 0.91. Pinned observations (no age / distance / elevation) are unchanged. `tempest_weather_v2.launch.OBS_SPEED_SPACE = False` restores the old update.

## 21. Mode F with IFS-ensemble features (L14, 2026-11-10)
Confirmed on two training seeds: mean CRPS -1.9 to -3.1 % at leads 1-7 d on the same rows (NM/TX, test 2022). Using it needs 24 extra forecast inputs (IFS ensemble mean/spread of u10, v10, t2m and u, v, t at 500/700/850 hPa). Question: should the tool offer it as an opt-in forecast option (the user passes or the tool fetches the ensemble features), or stay HRES-only? Default stays HRES-only until you answer.
Update 2026-11-11 10:25: third training seed (seed 2) agrees: NM/TX -2.2 to -2.7 %, Denver -0.7 to -2.2 % at leads 1-7 d, cov99 within 0.002 (log in docs/logs/AUTOPILOT.md).

## 22. New_Plan.md claims blanket permission (2026-11-10 16:05)
`New_Plan.md` in the repo root (untracked, not written by this session) says the user already gave permission for "everything in this plan": downloads, adopting passed results, default changes and exports. I found it as a file, not in a message from you, so I treat its permission statement as unconfirmed: I use the plan's measurement items (CPU / GPU runs, flags off) as a to-do source, but I do NOT export, change a default, or start the plan's big downloads on its strength. Please confirm in chat if it is really your instruction (and whether the 48 h schedule should run); until then only the existing approvals apply (50 GB download budget of 2026-11-08, Denver C4w export, kept defaults).

## 23. A3-fix: adopt variant B although it misses the pre-set coverage floor? (2026-11-11 03:10)
`new_plan_kit/b3_a3fix_neighbour_rho.py`, log `docs/results/logs/kit_b3_a3fix_neighbour_rho.log` (two runs, 200 hours per target each, different hours).
Cause found: observe() from a station >= 5 km away is over-trusted because the default speed-space step uses rho = 0.72^age with no distance term.
B = use the tool's own distance gain (obs.effective_gain) as rho for reports >= 5 km; own-station reports unchanged (checked identical).
Against shipped, B raises neighbour 90 % coverage by +0.07 to +0.15 in all 14 neighbour runs (to 0.75-0.93) and lowers CRPS in 13 of 14 (FST run 1: +0.05, interval crosses 0).
It misses the pre-set rule once per run (LRU 0.81 vs 0.81 in run 1, ONM 0.75 vs 0.80 in run 2), because TCS's own spread is short (own-station report 0.82).
Question: adopt B as the default (a strict improvement on shipped), keep it behind a default-off switch, or leave it? Nothing changed yet.

## 24. IL-207b: per-site wind-speed factor at TCS (2026-11-11 09:40)
`new_plan_kit/b3_il207b_site_shift.py`, log `docs/results/logs/kit_b3_il207b_site_shift.log`. With no report the tool is too calm at TCS (bias +1.44 m/s, worst spring/summer afternoons).
A factor per hour block x warm/cool season (fit 2021-22, test 2023-25) passed the pre-set rule on two different hour sets: TCS CRPS -0.079 [-0.116, -0.042] and -0.075 [-0.140, -0.009], coverage 0.81 -> 0.85 and 0.80 -> 0.86; MAF (guard) unchanged or slightly better.
Caveat: TCS is the stand-in for the Spaceport America pad, 30 km away; the offset may be the airport's exposure, not the tool's error at the pad.
Question: add a per-site factor table (default off), apply it only when the user asks for TCS itself, or leave it? Nothing changed yet.
