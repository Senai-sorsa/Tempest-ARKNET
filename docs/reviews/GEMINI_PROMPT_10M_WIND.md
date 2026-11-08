# Prompt for Gemini: improving the 10 m (ground) wind in a probabilistic launch-weather generator

Copy everything below the line into Gemini (a deep-research / thinking mode if available). Paste Gemini's answer back to Claude, which will fuse the ideas into the work loop.

---

You are a senior atmospheric scientist and machine-learning researcher (boundary-layer meteorology, statistical post-processing, probabilistic forecasting, generative models, wind engineering). Please do **real research** (papers, operational systems, public datasets) and give **specific, innovative, testable solutions**, not generic advice. Cite sources with links where you can. Where you are unsure, say so.

## 1. The system and the problem

We are building **Tempest-ARKNET**, a probabilistic atmosphere generator for amateur and collegiate rocket launches (Spaceport America, New Mexico, and Midland, Texas first). Given a place and a time (climate mode: a planned date, unknown weather; past mode: a past date; forecast mode: 1-7 days ahead), it returns an **ensemble of physically coherent vertical profiles**: wind (u, v), temperature, humidity at 44 heights above ground (10, 50, 100, 150, 200, 300, 500, 750, 1000 m ... 18 km), plus 2 m temperature, surface pressure, a gust model and vertical wind. A flight simulator then flies a rocket through each profile (Monte Carlo of apogee, rail-exit conditions, drift, landing dispersion).

**How it works today**
- Generator: a conditional neural network (residual MLP, 512 wide, 4 blocks, about 2.8 M parameters, 4 members, 32 noise inputs) trained with CRPS (almost-fair, alpha 0.95), an energy score on the joint profile, a loss on height-to-height wind steps (shear), a tail loss and EMA weights. Inputs: place, date, hour, ENSO/QBO-type slow indices and (in past mode) ERA5 profiles; output: the profile residual relative to ERA5, sampled with noise.
- Training truth: **ERA5 0.25 degree hourly**, corrected towards **radiosonde (IGRA) and ASOS station data** with a station-correction map. Train 1991-2020, calibrate 2021-2023, development test 2024-2025, 2026 H1 reserved for one final test (never touched).
- Post-processing: range calibration (a learned spread map), a "trust layer" that blends towards the 15-year station climatology where the model has no skill, a rank-preserving shear-space quantile map, a Schaake-style shuffle of members with real ERA5 templates (restores vertical coherence), optional PIT recalibration.
- Launch-day observation mode: a Gaussian-copula Schur-complement update on a pool of about 1000 atmospheres, conditioned on measured 10 m wind and direction, 2 m temperature and pad pressure. Not yet validated.
- Domain: NM/TX box (31-34 N, 108-101 W) and a Denver box. Heights near the ground come from ERA5 u10/v10 (10 m), u100/v100 (100 m) and the lowest pressure levels, **interpolated** (50 m is interpolated; nothing finer exists below 100 m). A 21-level boundary-layer fill (975-750 hPa) recently improved 0-1 km temperature by +0.018 CRPS skill.

## 2. The 10 m wind problem, with evidence

For a rocket on a rail, the wind in the **lowest 200 m** controls rail-exit weathercocking, early trajectory and apogee. We tested the generator against a flight simulator with a real 14 kg rocket (5 m rail):
- Calm air below 200 m: apogee error moves from +8.8 % to +10.6 %. Doubling the wind below 200 m: +7.2 %. **Removing all wind above 200 m changed nothing** (+8.9 %). So the ground wind is the one atmospheric input that matters as much as air density for apogee (about 2 % for a 3 m/s change), and it dominates rail exit, drift and recovery.
- Against **balloon soundings** (Santa Teresa NM, late June 00 UTC, 236 soundings): the real u falls inside the tool's 5-95 % range only **80-86 %** of the time (ideal 90 %); the tool's standard deviation is **15-25 % too small** (u at 0-1 km: 4.46 against 5.56 m/s); wind speed is **1.0-1.5 m/s too low** in the lowest 3 km. Temperature coverage is fine (85-94 %).
- ERA5 smooths wind (we measured spreads running low, most for wind). The model learns ERA5-like variability plus a station correction at two stations only.
- Launch-day conditioning on a **distant ASOS** (78 m higher than the pad, tens of km away, one hourly report) pinned the 10 m wind to 0.9 m/s against a climatological 3.2 m/s and moved apogee 2.3 %: representativeness error is large and unmodelled.
- Hourly ASOS at Truth or Consequences (TCS, 1479 m) and Midland (MAF, 872 m), 2000-2025: speed (kt), gust, direction, temperature at about :53 each hour. IGRA balloons, ERA5 and ARCO-ERA5 are on disk. No on-site pad anemometer data yet.

## 3. Candidate fixes we already listed (go beyond these)

(a) recalibrate the wind spread against station winds instead of ERA5; (b) within-hour gust and turbulence variability on top of the hourly mean; (c) persistence/assimilation of the latest observation with lag correlation; (d) blend with the station's own month-hour wind climatology; (e) log-law / Monin-Obukhov height scaling below 10 m using site roughness; (f) finer near-surface vertical levels (2, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300 m) from ERA5 model levels; (g) a pad-specific correction learned from any local logs; (h) a representativeness-error model for observations by distance, elevation difference, terrain and age; (i) training the 10 m wind directly on station observations. We are benchmarking (a)-(d) now against ASOS.

## 4. What we want from you

1. **Literature and operational survey**: how is 10 m wind post-processed, downscaled and calibrated today (EMOS/NGR, quantile mapping, MOS, analog ensembles, gradient-boosted and neural post-processing, graph and transformer models, diffusion/flow-matching downscaling, stochastic subgrid parametrizations, RTMA/URMA/HRRR analyses, wind-energy and aviation-turbulence practice, wildfire and urban-wind emulators)? What reaches the lowest 10-200 m with real skill? Which public datasets give **near-surface wind truth** for the US Southwest at better than ERA5 resolution (RTMA/URMA 2.5 km, mesonets, NM Mesonet, tower/sodar/lidar, Spaceport America and IREC weather stations, UAS profiles)?
2. **Innovative solutions** for a model that must output a *calibrated joint distribution* of wind in the lowest 200 m (and its time variability), from hourly 0.25 degree inputs. Think beyond the list above: for example, observation-conditioned generative training (the network sees the last station reports), learned subgrid-variability models, heteroscedastic or mixture/vector heads for u and v with circular direction, copulas across the lowest levels, stability- and terrain-regime-dependent calibration, conformal prediction for wind, multi-model forecast blending (HRRR, GFS, ICON, IFS ensemble) with lead-dependent calibration, data assimilation of the latest METAR with proper error models, transfer from other deserts and plateaus.
3. For each idea: **why it should work (mechanism and evidence)**, **expected gain** (which metric, how big), **data needed and where to get it** (free, US, small downloads), **implementation sketch** in a PyTorch/numpy pipeline, a **test design** (metrics: CRPS and coverage of u and v at 10-200 m against ASOS and balloons, spread/skill ratio, rail-exit wind distribution, effect on simulated apogee), and **risks and failure modes**.
4. **Rank** the ideas by expected gain per effort, and give a **minimal experiment** for the top five that one person with a laptop GPU (RTX 5070, 12 GB), 31 GB RAM and a few GB of downloads could run in a day each.
5. A short list of **traps** (leakage, hourly-versus-instantaneous obs mismatch, station siting, calm-wind direction undefined, vector versus speed scoring, etc.).

## 5. Constraints
Local Windows laptop (thermal limits, one GPU job at a time), a supercomputer later for global training, a home data cap (small point downloads only), no use of 2026 data for training or tuning, every new behaviour behind an off-by-default flag until verified on held-out years. Python/numpy/PyTorch only.

Please answer with: (1) a one-page summary of the best strategy, (2) the ranked idea list with the fields above, (3) the top-five minimal experiments, (4) the reading list with links.
