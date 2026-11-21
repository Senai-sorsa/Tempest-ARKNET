# Tempest-ARKNET research paper: the complete guide

Written 2026-11-14 for a future session that writes the paper alone. It covers what to claim, how each section is built, which figure shows each metric, where every number lives in the repo, and what the AI-weather, verification and aerospace papers do that this paper should copy. Part 0 is the briefing; read it in full before you open anything else.

How this guide was made. I read the project docs (README, `docs/HANDOVER_2026-11-14.md` section 17, `docs/results/FINAL_REPORT.md`, `docs/final_test/tables.md`, `Useful results.md`, `Beat Earth-GRAM.md`, `New_Plan.md` sections 9 and 15, `FlightSIM&Validation with Tempest-ARKNET.md`, the key `docs/results/logs/*.log`, and the module docstrings). For outside work I read GenCast, FGN (WeatherNext 2) and AIFS-CRPS through their arXiv HTML (partly verbatim, partly summarised by the fetch tool), the Earth-GRAM 2026 User Guide (NASA/TM-20260004497) as full text, and search summaries for the rest. Numbers from outside papers that I could not check against the full text say so. **Every project number below must be re-checked against its source file before it goes into the manuscript.** Part 8 lists each source file.

---

## Contents

- Part 0. Briefing: rules, the state of the evidence, decisions to settle first
- Part 1. What the literature does (AI weather, verification science, aerospace atmospheres)
- Part 2. The paper's thesis, claims, and claims you must not make
- Part 3. Venue, format and mandatory statements
- Part 4. Title, abstract, significance statement, key points
- Part 5. Section by section: what to write, what data to show, what details to include
- Part 6. The figure plan (every main and supplementary figure, fully specified)
- Part 7. Metric-to-graphic map (every metric the project computes, and how to show it)
- Part 8. The numbers ledger (every headline number, its source file and its caveat)
- Part 9. Statistics and fairness rules for the paper
- Part 10. Figure and writing style
- Part 11. Production plan: files, scripts, order of work, checks
- Part 12. Reviewer questions to answer before they are asked
- Part 13. References (with links)
- Part 14. Questions for the user before submission

---

# Part 0. Briefing

## 0.1 Rules that apply to the paper work (from the project's standing rules)

1. **Do not use any 2026 data for anything new.** The 2026 January-June final test was run once on 2026-11-06 (`data/FINAL_TEST_DONE`). Its results exist as files (`docs/final_test/`), and you may **plot and quote those files**. You may **not** re-score, re-sample or otherwise read the 2026 rows again, not even "just to make a figure". If a figure needs a statistic those files don't hold, take it from the development window (2024-25) and label it as development data.
2. **The fresh final test (2026 July-October) runs only when the user says "the model is final".** Its pipeline is `scripts/final_test_2026h2.sh` (CONFIRM_FINAL=yes, lock file). Never start it for the paper. If the user approves it, it is the best main result the paper can have (see 0.3).
3. Train ≤ 2020 (shipped generators ≤ 2023, as documented), calibrate 2021-23, develop on 2024-25. The paper must state this protocol and that 2024-25 was used for many decisions (about 30+; say "development set, reused" every time a 2024-25 number appears).
4. Machine rules: one GPU job at a time, at most 16 CPU threads at low priority (`source scripts/cap_cpu.sh`), more than 2 GB RAM free, no new job on battery or at GPU ≥ 85 °C. Figure scripts are light CPU work; any re-scoring is a GPU or scoring job and follows the same rules as every trial.
5. No commits unless the user asks. No Claude or Co-Authored-By attribution in commits. Never push.
6. Library questions (matplotlib, cartopy, scoringrules, LaTeX classes) go through Context7 first (`C:\Users\Senai\.claude\rules\context7.md`).
7. New code goes in new files under `paper/` (see Part 11). Do not change scoring code to make a figure. If a figure needs an output the scorer doesn't save, add an **opt-in flag** (off by default, byte-identical when off, with a test), the way every other change in this repo is made.

## 0.2 What the system is (the one-paragraph version for the paper)

Tempest-ARKNET is a probabilistic generator of vertically coherent atmospheric profiles for rocket-launch Monte Carlo. For a place inside a trained box, a date (past, near-term or years ahead) and an hour, it returns N profiles of u, v, T and RH at 44 fixed heights from 10 m to 18 km above ground, plus 2 m temperature, surface pressure and 2 m humidity. Derived outputs are pressure, density, speed of sound, vertical wind, gusts and turbulence parameters. The core is an **Engression** generator (Shen & Meinshausen; noise enters the network): a residual MLP whose layer norms are modulated by one 32-dimensional noise vector, the same design as ECMWF AIFS-CRPS and DeepMind FGN. It is trained on an almost-fair CRPS (α = 0.95) with an energy-score term, a CRPS on height-to-height steps (shear) and a shear-tail weight, on ERA5 profiles corrected toward radiosondes. A post-processing stack then makes the output honest:
- a monotone **range map**, so p % ranges hold p % of outcomes;
- a **Schaake shuffle** with real templates per 2° block × month × hour bin;
- a **shear quantile map** and a **lapse-rate quantile map**, both rank-preserving.

Lead time picks the source:
- **forecast mode F**: the HRES/IFS forecast turned into a distribution by a residual network, about 0.75-7.5 days;
- **climate mode**: the generator, for any date;
- **past mode P**: ERA5 for that hour plus a residual network learned against balloons.

Observation conditioning (`Launch.observe`, `observe_radar`) updates the whole profile from launch-day measurements. Boxes: NM/TX (31-34 N, 108-101 W: Spaceport America, Midland) and Denver (38-40 N, 106-104 W). Since 2026-11-10 all 24 hours are served.

## 0.3 The state of the evidence (what the paper can stand on today)

| Evidence | Model | Window | Clean? |
|---|---|---|---|
| Final test, ERA5 targets + 2 balloon stations, vs E12, clim15, Gaussian | the "final system" of 2026-11-06 (p2f-era stack) | 2026 Jan-Jun | **Yes, held out**, run once. But this is not the model shipped today. |
| Shipped stack `l3_c4w` (21-level ERA5, all hours, C4w loss, lapse map) headline | shipped | 2024-25 | development, reused |
| Fair-baseline rescore (AU-1) | shipped | 2024-25 | development; shows the plain baseline overstated skill by about 0.013 |
| Earth-GRAM kit: tool vs `gaussfull` vs measured-profile `bank`, 800 balloons | shipped | 2024-25 | development; neither side blind at these stations |
| Forecast mode F skill by lead | mode F v3 | 2022 (test year) | held out from training, but the only test year (the HRES archive ends 2022-12) |
| Radar conditioning (`observe_radar`) | tool | 2021-23, 120 days | bootstrap intervals; one radar and one balloon site |
| Apogee sensitivity by height band (P6) | tool + real simulator | one rocket, one day | illustration |
| Flight-sim check, 3 in-box flights | tool + simulator | 2017, 2022, 2023 | n = 3: a feasibility result only |

**Decision the user must make first (Part 14, Q1).** Option A: wait for "the model is final", run the 2026 July-October test once on the shipped model, and make that the main table. This is the strongest paper. Option B: write it now. The 2026 H1 test (earlier system) becomes the held-out result, and the shipped model's development numbers are shown as later improvements, clearly labelled. Write the draft so the numbers sit in **one generated file** (`paper/numbers.tex`, Part 11). Switching from B to A then means re-running the scripts, not rewriting text.

**Second decision: real Earth-GRAM (Part 14, Q2).** Every comparison so far uses an Earth-GRAM-*style* Gaussian, not the program itself. The Earth-GRAM 2026 guide shows a **2019 Range Reference Atmosphere for White Sands Missile Range (code `wsm`, 32.94 N, -106.42 E, 1.219 km, WMO 722690)**, which lies inside the NM/TX box. A run of real Earth-GRAM 2026 (GRAM Suite, NASA Software Catalog) at the two balloon stations, with the MERRA-2 option and with the WSMR RRA, would turn "Earth-GRAM-style" into "Earth-GRAM". The comparison kit already takes external output (`new_plan_kit/b9_gram_compare.py --extra gram=FILE.npz`, `--cases-out` writes the list of runs to make, `--from-csv` converts a table). GRAM builds on Linux (WSL on this machine) and is requested from NASA, so this needs the user. Aerospace reviewers will ask for it. Without it, the paper must say "Earth-GRAM-style" every time, and say why the stand-in is a **ceiling** for any Gaussian method (Part 2.3).

---

# Part 1. What the literature does

## 1.1 AI weather and generative-model papers: their anatomy

| Paper | Main-text figures | How results are shown | What to copy |
|---|---|---|---|
| **GenCast** (Price et al., arXiv 2312.15796; Nature 2025) | 5 figures, no main-text tables. Fig 1 schematic; Fig 2 skill (line plots relative to ENS for one variable each + **scorecards** for RMSE / CRPS / Brier of extremes); Fig 3 maps of samples vs truth vs ensemble mean (sharpness vs blur); Fig 4 power spectra + derived wind-speed CRPS and bias; Fig 5 **spread/skill ratio** + **rank histograms** at 3 leads | Scorecard colours: blue = better, red = worse, white = equal, saturating at ±30 %. Headline as a win fraction ("better on 96-97 % of 1320 targets") | One schematic; one scorecard per score; a "physical realism" figure separate from skill; a reliability figure (spread/skill + rank histograms) of its own; derived quantities (wind speed) as a joint-structure test |
| **FGN / WeatherNext 2** (Alet et al., arXiv 2506.10772) | Fig 2 CRPS scorecard vs GenCast with **hatched cells where the difference is not significant (p ≥ 0.05)**; spread-skill curves; REV curves for extremes. Fig 3 joint structure: **average- and max-pooled CRPS**, CRPS of derived quantities (10 m wind speed, z300-z500 thickness), spectra. Fig 4 cyclone tracks | Joint structure shown indirectly: "minimising marginal CRPS is not sufficient for pooled CRPS", so pooled and derived scores test dependence | **Closest relative of our generator**: one 32-dim noise vector into conditional layer norms, marginal CRPS training, 4 independently trained seeds pooled as a deep ensemble. Cite it as the design precedent. Copy the hatching convention and the "derived quantity" test (our wind speed, shear, density, Richardson number) |
| **AIFS-CRPS** (Lang et al., arXiv 2412.15832) | Tables of grids, variables, training settings; schematic; sample maps; spectra; CRPS vs lead; scorecards with **light/dark shading = 95 % / 99.7 % significance**; verification against analyses **and against radiosondes and SYNOP** | States the loss exactly: afCRPS_α = α·fCRPS + (1−α)·CRPS, α = 0.95, 4 members in training | Our loss is the same (`crps_alpha = 0.95`, `m = 4`). Cite it and write the loss in the same notation. Copy the double verification (against reanalysis and against observations) |
| **WeatherBench 2** (Rasp et al., arXiv 2308.15560) | Headline scorecards relative to IFS ENS; metric definitions (RMSE, ACC, CRPS with fair estimator, spread/skill, rank histograms, spectra) | Warns that RMSE rewards blur, that scoring against a model's own analysis vs ERA5 vs observations changes rankings, and that spread/skill = 1 is necessary, not sufficient | Copy the vocabulary and the warnings. Our "truths" are ERA5 *and* balloons, as WB2 recommends |
| **CorrDiff** (Mardani et al., Commun. Earth Environ. 2025; arXiv 2309.15214) | Regression-then-diffusion; shows **PDFs and power spectra of generated fields vs target**, case studies; limitations: "calibration remains challenging", no guaranteed temporal coherence | Distribution-shape plots (PDF on log y for tails) beside skill | Copy the PDF/CCDF-on-log-axis figure for tails (our shear, lapse rate) and the honest limitations style |

Patterns that hold across all of them (follow these):
1. **Figure 1 is a schematic** of the method or the generation loop.
2. **Skill is shown relative to the strongest operational baseline** (ENS, HRES), as a ratio or skill score, in a **scorecard**: rows are variables and levels, columns are lead times, a diverging colour scale, and non-significant cells marked.
3. **Calibration gets its own figure**: spread/skill and rank histograms (or PIT).
4. **Physical realism gets its own figure**: spectra, derived quantities, sample maps. "Good CRPS" is never the only evidence for a generative model.
5. **Limitations are explicit**: resolution, dependence on an analysis, a single test year, the evaluation conventions that favour one side (GenCast notes that scoring against an analysis "unduly rewards under-dispersion at short lead times").
6. **Training, validation and test years are stated exactly.** The test year stays frozen until the end (GenCast trains to 2017, validates on 2018, then retrains to 2018 and tests on 2019).
7. **Main text is short; the supplement is long**: per-variable figures, every ablation, hyperparameter tables.

## 1.2 Verification science: the methods the paper must cite and use

| Topic | Reference | What it says / why we need it |
|---|---|---|
| Proper scoring, "sharpness subject to calibration" | Gneiting & Raftery 2007 (JASA); Gneiting, Balabdaoui & Raftery 2007 (JRSS B) | The guiding principle for the whole evaluation; CRPS is proper |
| Fair CRPS for finite ensembles | Ferro 2014 (QJRMS); Zamo & Naveau 2018 | The AU-1 fix: the plain estimator punishes a thin climatology pool; the fair estimator spreads over m(m−1). **The paper must use fair CRPS for all baselines** (Part 9) |
| Rank histograms | Hamill 2001 (MWR) | Flat is necessary, not sufficient; read the shape (U = too narrow, dome = too wide, slope = bias) |
| PIT and calibration | Dawid 1984; Gneiting et al. 2007 | PIT histograms per variable and height band |
| Variogram score, p = 0.5 | Scheuerer & Hamill 2015 (MWR) | More sensitive to dependence errors than the energy score (Pinson & Tastu 2013 showed the energy score is weak on correlation). Our scorer uses p = 0.5 |
| Energy score | Gneiting et al. 2008 (Test) | Joint score; report it but rely on VS for structure |
| Schaake shuffle / ECC | Clark et al. 2004 (J. Hydrometeor.); Schefzik, Thorarinsdottir & Gneiting 2013 (Stat. Sci.) | Our template reordering. Lerch et al. 2020 (NPG) found the Schaake shuffle "difficult to outperform", which matches our failed re-ordering trials |
| Tail calibration | Allen, Koh, Segers & Ziegel, arXiv 2407.03167 | Calibration overall does not imply calibration in the tails. Supports showing coverage at 99 % and tail-rate errors separately |
| Forecaster's dilemma / extremes evaluation | Lerch et al. 2017 (Stat. Sci.) | Do not evaluate only on cases selected by the outcome; use weighted scores (threshold-weighted CRPS) for tails |
| Weighted multivariate scores | Allen et al. (arXiv 2209.04872, 2202.12732) | Optional: threshold-weighted CRPS for strong-wind tails |
| Block bootstrap for serially correlated scores | Künsch 1989; Wilks 1997 (J. Climate) | The project's AU-4 finding: one-day blocks are too narrow; use 21-day blocks (skill autocorrelation up to 19 days in the 12-18 km band) |
| Engression | Shen & Meinshausen, JRSS B (DOI 10.1093/jrsssb/qkae108; online 2024, print 2025) | The generator family; check the year format against the journal page |
| Software | scoringrules (Python, PyPI 0.11.0 as of 2026-11-04 per `docs/research/research-notes.md`) | Cite the version you use for any independent recomputation |

## 1.3 Aerospace atmospheres: what Earth-GRAM is, and what NASA uses instead for winds

From the Earth-GRAM 2026 User Guide (P. W. White, NASA/TM-20260004497, MSFC, May 2026; read in full text):
- **Lower atmosphere (surface to 0.1 mb): MERRA-2 monthly means and standard deviations**, 0.5° × 0.625°, for 8 UTC hours (00, 03, ..., 21) plus an all-hours average, at the surface and 42 pressure levels, **period of record 1999-2018**. Variables: height, pressure, temperature, density, u, v, wind speed, **u-v correlation**, dew point, RH, vapour pressure. The NCEP Reanalysis-1 option remains (2.5°, 4 UTC hours, 1997-2015). Above that: MAP data (20-120 km) and thermosphere models (now including NRLMSIS 2.1).
- **Range Reference Atmospheres (RRA)** for 1983, 2006, 2013 and 2019 replace the mean and standard deviation near a site. **White Sands Missile Range has 1983, 2006, 2013 and 2019 RRAs**; the 2019 set's top is 30 km. 2026 adds Brownsville, TX.
- **Perturbation model.** Total variance is split into a **large-scale, wave-like part** (a cosine in horizontal wavenumber, vertical wavelength and time, with a random amplitude factor A_Q = 0.4808 + 0.96·Q that allows exceedances beyond √2 σ) and a **small-scale part**: a first-order autoregressive (Markov) process with **Gaussian** innovations and exponential correlation in horizontal distance, height and time, r = exp(−δh/L_h)·exp(−δz/L_z)·exp(−δt/τ). The small-scale part has a Dryden power spectrum. An optional "patchy severe turbulence" mode multiplies the variance. Cross-correlations come from Buell relations: pressure-density, temperature from the gas law, winds correlated with density.
- **Scale knobs**: RandomPerturbationScale (density, temperature, pressure) and HorizontalWindPerturbationScale (0.1-2.0, nominal 1.0). The sample input file shows 1.6.
- **Validation shown by NASA**: monthly mean profiles of MERRA-2 against the Cape Canaveral RRA (density, temperature, dew point, u, v; Figs 2-6). **CorrMonte** (hourly dispersions) compared with **Jimsphere balloon wind pairs, MERRA-2 pairs and NASA LSP pairs from the 50-MHz and 915-MHz Doppler radar wind profilers**, as standard deviations of 3-hour wind change, January and October at Cape Canaveral (Figs 8-11). Sample output: 1000 Monte Carlo u dispersions with mean and ±3σ (Fig 13), and a **cumulative-probability plot with a Gaussian fit to show the dispersions are approximately Gaussian** (Fig 14).
- **What this means for the paper.** (1) Earth-GRAM's spread is by design approximately Gaussian, from monthly statistics, and its fine vertical structure comes from an exponential-correlation Markov process. Our three advantages to test are non-Gaussian shape, real-profile vertical structure and date-specific information. (2) NASA itself validates against **measured wind databases and wind pairs**, so our measured-profile `bank` bar (E5) is the comparison an aerospace reader trusts. (3) Show our version of NASA's Fig 13 (spaghetti + mean ± 3σ) and Fig 14 (CDF with Gaussian fit) **side by side with the balloons**. Our distributions are not Gaussian where the air isn't, and that is visible at a glance.
- **Wind pairs and profiler databases**: Decker & Barbré (NASA/TM-2013-217924; AMS ARAM 2014 paper on temporal variability of upper-level winds at the Eastern Range, Western Range and Wallops) build wind-pair databases at 0.75, 1.5, 2, 3 and 4 h from the KSC 50-MHz (about 2.5-18.5 km) and 915-MHz profilers, used for commit-to-launch decisions. Barbré 2013 (JTECH) covers profiler QC. Cite these when you discuss launch-day wind change (observation conditioning, report age).

## 1.4 Gaps the paper fills (state them in the Introduction)

The searches found **no published generative ML model that produces calibrated, vertically coherent multi-variable profiles for launch-range Monte Carlo** (search of 2026-11-14; say "to our knowledge", and re-run a literature search before submission). Near relatives:
- ML reconstruction of boundary-layer wind profiles from IGRA (arXiv 2611.13359). Supervised, not generative.
- Generative downscaling (CorrDiff). Gridded fields, not columns for Monte Carlo.
- AI ensembles (GenCast, FGN, AIFS-CRPS). Global medium range, not site columns with climate-to-forecast blending.
- Earth-GRAM and RRA. Gaussian monthly statistics.
- Measured-profile databases (Jimsphere, profiler). Real structure, but no date-specific skill and limited sites.

---

# Part 2. Thesis, claims, and claims you must not make

## 2.1 One-sentence thesis (draft)

"A noise-injected neural generator trained with proper scores on radiosonde-corrected reanalysis, followed by a small rank-preserving calibration stack, produces launch-site atmospheric profiles whose ranges are calibrated against independent radiosondes and which beat an Earth-GRAM-style Gaussian dispersion for temperature and surface fields, tie it for wind in climate mode, and reproduce real-air vertical structure better than a Gaussian in most measures. The same machinery turns forecasts and launch-day observations into calibrated profile ensembles."

## 2.2 The claims, with their evidence and their limits

Write each claim in the Results with these three parts: the number, the interval, the limit.

| # | Claim | Evidence (Part 8 has the files) | Limit you must state |
|---|---|---|---|
| C1 | Calibrated ranges against independent truth | 2026 H1: mean \|cov99 − 0.99\| = 0.0049 (ERA5), 0.0064 (balloons); 99 % ranges hold | Looser than development (0.0032 / 0.0038). Weakest: balloons RH 12-18 km 0.958, v 12-18 km 0.977 |
| C2 | Beats the Earth-GRAM-style Gaussian on temperature and surface | 2026 H1 CRPS vs Gaussian: T 0-12 km +13 to +16 % (ERA5), +9.7 to +13.8 % (balloons); t2m +25 % / +9.5 %; mean +5.6 % / +2.2 %; better in 13 / 12 of 19 cells | Gaussian is a stand-in, not Earth-GRAM; wind not better (u 1-5 km −3 %) |
| C3 | Ties the Gaussian and the measured-profile bank for wind in climate mode, which is close to the ceiling of what a date alone can tell | Kit (800 balloons 2024-25): CRPS v tie (gaussfull − tool +0.0192 [−0.0250, +0.0645], +0.4 %), u tool better 3.0 %, T 8.1 %; vs bank: u +3.0 %, v tie (−0.1 %), T +6.1 % | Development window; neither side blind |
| C4 | Real-air vertical structure better than a Gaussian in most shape measures, and the stack is why | Shape-stack ablation on 2026 H1 (shear distance 0.0333 → 0.0274, vertical-correlation error 0.0697 → 0.0606); VS u and T better than `gaussfull` and `bank` | Vertical-correlation error is **worse** than both Gaussian and bank (0.061 vs 0.040 / 0.038); shear p99 still 0.70-0.91 of balloons; Ri<1 at 12-18 km 0.068 vs 0.149 |
| C5 | Skill over recent climatology is small but positive | 2026 H1 skill15 +0.0209 (ERA5), +0.0187 (balloons); fair-baseline shipped stack ≈ +0.017 to +0.019 (ERA5, 2024-25) | AU-1: the plain estimator overstated by ≈ 0.013. **Quote fair-baseline numbers only** (Part 9). T 12-18 km is negative (−0.030 / −0.039) |
| C6 | Forecast mode adds skill at 1-7 days and stays calibrated | 2022: tool CRPS skill vs short-record climatology 0.691 / 0.539 / 0.350 / 0.209 at 1 / 3 / 5 / 7 d vs raw HRES 0.57 / 0.34 / 0.08 / −0.21 | One test year; the climatology there is short-record (state its pool) |
| C7 | Launch-day observations sharpen the whole profile | Radar 0.5-2 km winds → CRPS +31.3 % [+25.0, +37.5] at 2.5-5 km, +15.2 % [+9.4, +20.9] at 5-12 km, +6.4 % [+2.7, +10.0] at 12-18 km | One radar, one balloon site, 2021-23, radar one hour before the balloon |
| C8 | For a small rocket, near-ground wind dominates apogee dispersion, so a site's 0-300 m wind is what matters | P6: 87 % of wind-driven apogee variance from 0-300 m, 53 % from 50-150 m; landing also depends on 3-5 km (43 %) | One rocket (Sol Invictus), one day, one site |
| C9 | Physical consistency of derived variables | Density within 0.5 % of 149 balloons at 0-10 km vs 6.4 % for the 1976 standard atmosphere at the pad; hydrostatic gap 0.064 % vs balloons 0.026 % (kit) | Development window |

## 2.3 How to frame the Gaussian baseline honestly

- In the scorer (`tempest/scoring/score.py`), `gauss` is the monthly mean plus a correlated bell-curve spread per grid point × month × 2-hour bin (month only where a bin has fewer than 600 rows), built the way Earth-GRAM and the RRAs build dispersions. At balloon stations, `gaussfull` uses the **station's own 1991-2020 balloon mean and full covariance**.
- Argue: real Earth-GRAM uses coarser MERRA-2 monthly statistics (1999-2018) and an exponential-correlation perturbation model, so at a balloon station it **cannot beat a Gaussian fitted to that station's own balloons with the full covariance**. `gaussfull` is therefore a **ceiling** for Earth-GRAM-type methods. Say clearly that this is an argument, not a measurement. The measurement waits for a real Earth-GRAM run (Q2).
- AU-7: the margin over the Gaussian mixes shape and warming trend (`--gauss15`: the margin is about 92 % shape, 8 % trend). Report the recent-15-year Gaussian beside the 1991-2020 one, so the reader sees that the gain is not only "a newer mean".

## 2.4 Claims you must NOT make

- "Beats Earth-GRAM." Only "beats an Earth-GRAM-style Gaussian" until real GRAM output is scored.
- "Improves apogee prediction." The 3-flight check went 5.21 % → 5.81 % mean absolute error. The simulator's own bias (5-8 %) dominates. You may say the atmosphere inputs became physically right (pad 26-37 °C vs standard 6 °C; real air raises apogee by 1.5-3.1 %, real wind lowers it by about 2 %).
- "The shipped model is better than E12 on held-out data." All 38 cells were ties on 2026 H1.
- Any 2024-25 number described as a "test" result. It is development data.
- Any single-seed effect below the noise yardstick (training seed moves mean skill15 by about 0.0005, single bands by up to 0.003, rh2m 0.005).
- "Calibrated at every height and variable." Name the cells that are not.
- "Generalises to new regions." Denver zero-shot made temperature worse; Denver has its own model.
- Forecast-mode results presented as 2026 results (its test year is 2022).

---

# Part 3. Venue, format, mandatory statements

## 3.1 Venue (recommendation first)

1. **AMS *Artificial Intelligence for the Earth Systems* (AIES)** (recommended). The paper is an AI method judged by atmospheric verification standards, and AIES reviewers expect both. AMS manuscript components apply: abstract, an optional **significance statement** (AMS templates give ≤ 120 words), and an **Availability Statement right after the Acknowledgments**. Check the current AIES author page for the abstract limit and article types (there is a "Lessons Learned" short format; the negative results could fill one later).
2. *Journal of Applied Meteorology and Climatology* (AMS): if the paper leans to applied climatology and range meteorology.
3. *Geoscientific Model Development* (EGU): if it is written as a model description paper (code and data availability are mandatory, with versioned archives such as Zenodo). This is a good fit for the tool itself.
4. *Journal of Spacecraft and Rockets* (AIAA) or AIAA SciTech: if the Monte Carlo and apogee side becomes the core, which needs more flights. Not now.

Write for AIES. A GMD or AIAA version is a re-framing, not a rewrite.

## 3.2 Length and shape (AIES-style article; verify current limits)

- About 7,000-9,000 words of main text, 10-12 figures, 3-5 tables; the rest in the supplement.
- Use the AMS LaTeX template (Overleaf "American Meteorological Society (AMS) LaTeX" v5 or newer; ask Context7 or the AMS site for the current class).
- SI units, with heights **above ground level (AGL)** every time. The 44 heights are AGL; ERA5 levels are pressure. Say how the conversion is done (`tempest/profiles/to_heights.py`).

## 3.3 Mandatory statements

- **Availability Statement** (after the Acknowledgments). Give the data sources with access terms and credits (copy from `ATTRIBUTION.md`):
  - ERA5: Copernicus Climate Change Service / CDS, and the Earthmover Icechunk ERA5 copy, CC-BY-4.0;
  - IGRA v2.2 radiosondes: NOAA NCEI;
  - WeatherBench 2 IFS HRES;
  - ECMWF open data and ensemble products via Open-Meteo;
  - ASOS one-minute data: Iowa Environmental Mesonet;
  - NEXRAD Level II: NOAA;
  - CPC climate indices.
  Code: the repo, with a frozen tag and a Zenodo DOI. Models: the shipped assets. Say which data cannot be redistributed and how to rebuild it (the README's run commands).
- **AI-tool disclosure.** AMS policy requires that substantive use of AI tools in data collection and analysis be disclosed: which tool and how it was used, in the methods or acknowledgments. Much of this project's code, experiments and documentation was produced with an AI coding assistant working under the user's direction. The user decides the exact wording (Q4). AI tools cannot be listed as authors.
- **Competing interests / funding**: ask the user.

---

# Part 4. Title, abstract, significance statement, key points

## 4.1 Title options

1. "Calibrated, vertically coherent atmospheric profiles for launch Monte Carlo from a noise-injected neural generator"
2. "Beyond Gaussian dispersions: a generative model of launch-site atmospheric profiles verified against radiosondes"
3. "Tempest-ARKNET: probabilistic launch-site atmospheres from climate to launch day"

Option 1 suits AIES best. Avoid "Earth-GRAM" in the title unless real GRAM output is scored.

## 4.2 Abstract skeleton (≤ 250 words; one sentence per line below)

1. Problem: launch-vehicle Monte Carlo needs many physically coherent atmospheres for a site and date. Standard tools draw Gaussian dispersions from monthly statistics.
2. Gap: these miss non-Gaussian shapes, sharp vertical structure and any date-specific information. Measured databases have structure but no skill.
3. Method: an Engression generator (noise-modulated residual network) trained with proper scores on radiosonde-corrected ERA5, plus a rank-preserving calibration stack; forecast, past and observation-conditioned modes.
4. Data and test: NM/TX box, 44 heights to 18 km; trained 1991-2020 (shipped to 2023), calibrated 2021-23, tested once on held-out 2026 data against ERA5 and two radiosonde stations.
5. Result 1 (calibration): 99 % ranges hold to within 0.005-0.006 on average.
6. Result 2 (vs Gaussian): CRPS better by 5.6 % (ERA5) / 2.2 % (balloons), up to 25 % for near-surface temperature; tie for wind.
7. Result 3 (structure): profile-shape scores and shear distributions closer to radiosondes than the Gaussian; vertical-correlation error remains larger.
8. Result 4 (modes): forecast mode skill 0.69 → 0.21 from 1 to 7 days; radar winds improve the profile above by 6-31 %.
9. Application: for a small rocket, 87 % of wind-driven apogee spread comes from the lowest 300 m.
10. Take-home: what to use it for and what limits it (two stations, one box, wind climate ceiling).

Fill every number from `paper/numbers.tex`. Re-check after the Option A/B decision.

## 4.3 Significance statement (≤ 120 words, plain language)

Draft: "Rockets are tested in thousands of simulated flights, each needing a believable atmosphere. Today these atmospheres usually come from monthly averages with bell-shaped random changes. We built a machine-learning system that produces whole, realistic profiles of wind, temperature and humidity for a given site and date, and checked them against weather balloons that the system never saw. Its ranges hold as often as they should, it is more accurate than the bell-curve approach for temperature, and it is as good for wind. It can also use forecasts and launch-day measurements. This helps engineers judge launch risk with atmospheres that look like the real air."

## 4.4 Key points (if the journal asks; 3 × ≤ 140 characters)

- A noise-injected neural generator gives calibrated, coherent launch-site profiles to 18 km, verified on held-out radiosondes
- It beats an Earth-GRAM-style Gaussian for temperature and ties it for wind; profile shape is closer to real air
- One framework covers climate, forecast, past and launch-day modes; near-ground wind dominates small-rocket apogee spread

---

# Part 5. Section by section

Proposed outline (AIES):

1 Introduction · 2 Background and related work · 3 Data · 4 Method (4.1 problem and representation, 4.2 generator, 4.3 training objective, 4.4 calibration stack, 4.5 operating modes, 4.6 observation conditioning, 4.7 derived outputs) · 5 Experimental design (5.1 splits, 5.2 truths, 5.3 baselines, 5.4 metrics, 5.5 significance) · 6 Results (6.1 skill and calibration on the held-out test, 6.2 against Earth-GRAM-style and measured-profile bars, 6.3 distribution shape and vertical structure, 6.4 ablations, 6.5 forecast and past modes, 6.6 launch-day observations, 6.7 Monte Carlo application) · 7 Discussion (7.1 what worked and why, 7.2 negative results, 7.3 limitations) · 8 Conclusions · Acknowledgments · Availability · References · Appendices A-F + Supplement.

## 5.1 Introduction (≈ 900-1100 words, 5-6 paragraphs)

1. **Why launch atmospheres matter.** Monte Carlo dispersion analysis of trajectories, loads, landing zones and range safety. Wind (especially low-level shear) and density drive apogee, drift and loads. One sentence with the project's own finding (C8) as motivation, cited forward to 6.7.
2. **How it is done today.** Standard atmospheres; reference atmospheres (Earth-GRAM with MERRA-2 monthly statistics and RRAs; the perturbation model is approximately Gaussian with Markov small-scale structure); measured-profile databases (Jimsphere, 50-MHz profiler) and wind pairs for launch-day change. Each has strengths: simple statistics, coverage, physical consistency, review-board acceptance. Each has gaps: no date information, Gaussian shape, smooth profiles, hour-of-day detail.
3. **What ML weather brought.** CRPS-trained ensembles (AIFS-CRPS, FGN) and diffusion ensembles (GenCast) are calibrated and sharp. The FGN result that a low-dimensional noise vector plus marginal CRPS training gives realistic joint structure suggests the same works for columns. Engression gives the statistical footing. Give the gap: these are global grid models, not site columns that blend climate, forecast and observations; and their verification is mostly against analyses, not radiosondes.
4. **This paper.** The system in two sentences; the questions it answers: (i) are the ranges honest against independent balloons? (ii) does it beat a Gaussian dispersion and a measured-profile bank, and where? (iii) does it reproduce real-air structure? (iv) do forecasts and observations add value? (v) which heights matter for a rocket?
5. **Contributions** (bulleted, 4-5). Generator + calibration stack; a verification protocol for profile generators (multi-truth, fair baselines, structure metrics, 21-day block bootstrap); held-out results with intervals; an honest list of what failed; open code.
6. Roadmap sentence.

## 5.2 Background and related work (≈ 700-900 words)

Four short subsections:
- **Reference atmospheres**: Earth-GRAM (2026 guide facts from 1.3; describe the perturbation equations in words, cite the guide), RRA 2019 incl. WSMR, the 1976 standard atmosphere.
- **Measured-profile methods**: Jimsphere and profiler databases, wind pairs (Decker & Barbré).
- **Probabilistic ML weather**: GenCast, FGN, AIFS-CRPS, NeuralGCM (briefly), WeatherBench 2 verification. Generative downscaling (CorrDiff).
- **Statistical post-processing and dependence**: EMOS and quantile mapping in brief; ECC and the Schaake shuffle (Clark 2004, Schefzik 2013, Lerch 2020); tail calibration (Allen et al.).

End with a 3-row table, or one paragraph: "Gaussian reference | measured bank | ML ensembles | this work", against six properties (date skill, non-Gaussian shape, real vertical structure, calibrated vs observations, coverage of all lead times, physical derived outputs). Use ✓/partial/✗ only where you can cite it.

## 5.3 Data (≈ 800-1000 words + Table 1 + Fig 2 map + Fig 3 timeline)

Include, with exact numbers checked from code or configs:
- **Domain**: NM/TX box 31-34 N, 108-101 W at 0.25° (`configs/region.toml`). Give the number of grid points used and how they are sampled (`build_dataset.py`: random (point, hour) rows; check the "80" in `pilot80` and say what it means). Denver box only in the supplement.
- **ERA5**: 21 pressure levels for the shipped l3 model (CDS); 13-level Earthmover copy for the earlier models; hourly; surface fields. The vertical interpolation to 44 AGL heights: list the heights. 10, 50, 100, 150, 200, 300, 500, 750, 1000, 1250, 1500, 2000 m, then every 500 m from 2500 to 18000 m. 10 m and 100 m winds come from single-level fields.
- **Radiosondes**: IGRA v2.2, Santa Teresa NM (USM00072364, 1254 m) and Midland TX (USM00072265, 874 m), 00Z (about 17 h local solar) and 12Z (about 05 h). Counts per window. QC: the AU-6 complete-sounding rule, the launch-tolerance rule, the 2023 sonde-type change (IL-194: it inflates the 0-1 km shear tail after 2023).
- **Radiosonde correction of training targets** (`tempest/calibrate/station.py`): a linear fit per station × season × launch hour × variable × height on 1991-2020, then whole-profile leftovers. Mention that quantile mapping of each height step alone was tried first and inflated the whole-profile spread by 20-140 %.
- **Climate drivers**: ONI, WWV, QBO 30/50 hPa, global mean temperature (`tempest/ingest/fetch_indices`). In climate mode the drivers are "unknown" and drawn from earlier rows (state this; it is the honest setting).
- **Forecast data**: WeatherBench 2 IFS HRES 2016-2022, 00 UTC (+12 UTC in v3), leads 1/3/5/7 d; IFS ensemble via Open-Meteo for the live tool.
- **Surface stations**: ASOS one-minute data (TCS, MAF, ELP) for gusts; USCRN Monahans.
- **Radar**: NEXRAD VAD (El Paso KEPZ, Holloman KHDX), MetPy decode.
- **Table 1**: source | variables | period | resolution | use (train / calibrate / truth / input) | licence.

## 5.4 Method (≈ 1500-2000 words + Fig 1 schematic + Table 2 hyperparameters)

### 4.1 Problem and representation
- Output vector: per variable u, v, T and humidity, the surface value plus 43 height differences (`tempest/profiles/diff.py`), then t2m, sp and rh2m. Humidity is learned as dew-point depression, ln(T − Td + 1 K), so RH ≤ 100 % by construction. Give the target dimension (count it from `target_names()`).
- Inputs: lat, lon, site and grid elevation, day of year (sin/cos), hour (sin/cos), climate drivers and trend (gmst in the p2 feature set). List the shipped model's exact feature set from its config or checkpoint, not from this guide.

### 4.2 Generator
- Engression / FGN-style network: input embedding → depth-4 residual MLP, width 512 (about 2.8 M parameters in p2f; **recount for l3_c4w**), SiLU. Each block is a pre-norm whose scale and shift come from a 32-dim noise embedding (conditional layer norm, zero-initialised so it starts as a plain norm). **4 members** are trained independently and pooled at sampling time (deep ensemble, as in FGN). EMA of weights (0.999).
- Equation block: x̂ = G_θ(c, ε), ε ~ N(0, I_32).

### 4.3 Training objective
- Loss = afCRPS_α over all output values (α = 0.95, m = 4 samples per row; AIFS-CRPS notation), + 0.1 × energy score on the joint vector, + 0.5 × CRPS on height-to-height steps (shear), + shear-tail weight (q = 0.9), + the C4w near-ground vector-wind term (`configs/generator_c4w.toml`; read its exact form there).
- Optimiser: AdamW, lr 1e-3, cosine to 0, weight decay 1e-4, batch 4096, 6000 steps, early stopping on validation CRPS (patience 10, every 500 steps). About 13 min for 4 members on an RTX 5070 Laptop GPU (p2f; recheck for l3). The small compute is a selling point: say it.
- Splits inside training: the last 3 training years for validation.

### 4.4 Calibration stack (all rank-preserving; order matters)
1. **Range map** (`spread.py`): per output column, standardise samples by the row median and 5-95 % half-width, then map the quantiles of z onto those of the truth's u on a held-out calibration year, separately for the low and high sides. Monotone, so ranks and joint shape are kept (ECC-like).
2. **Schaake shuffle** (`shuffle.py`): reorder samples to the rank structure of real profiles from the same 2° block × month × hour bin (templates from the training years). Marginals are unchanged.
3. **Shear quantile map** (`shear_map.py`): a gain on each layer's vector shear, a function of the shear itself and the height band, equal to 1 up to the median. Then a high-pass so the medians and the large-scale wind change are kept.
4. **Lapse-rate map** (`lapse_map.py`): the temperature twin, acting only above the band median.

Say that each step was accepted by a pre-set rule on development data (Part 9) and that the stack is ablated in 6.4.

### 4.5 Operating modes and router
Forecast mode F (residual network on the HRES profile; lead, season and place as inputs; range map; Schaake shuffle by lead; tool mix of network and ridge 50:50). Climate mode. Past mode P (ERA5 hour + residual network trained on ~40,000 balloon-ERA5 pairs). The lead-time routing rules (`tempest/forecast/router.py`); all 24 hours; Denver sets.

### 4.6 Observation conditioning
`Launch.observe`: a Gaussian-conditional (Schur-complement) update of the pool on 10 m wind, direction and 2 m temperature, using the learned vertical correlations. `observe_radar`: per-(variable, height) sensor errors. The Student-t widening option is opt-in; mention it only in the supplement.

### 4.7 Derived outputs
Pressure by hypsometric integration, density, speed of sound, vertical wind head, gust law fitted on ASOS one-minute peaks (gust factor ≈ 1.4), Dryden turbulence parameters, export to Monte Carlo formats. Keep this short; the details go in an appendix.

**Table 2**: hyperparameters of the shipped generator, mode F and mode P networks (read from configs and checkpoints).

## 5.5 Experimental design (≈ 900-1200 words + Table 3 baselines)

- **5.1 Splits**: Fig 3 timeline. Train 1991-2020 (shipped to 2023), validate the last 3 years of training, calibrate 2021-23, develop 2024-25 (reused for decisions; say so), held-out test 2026 H1 (once; earlier system), and if Option A, 2026 Jul-Oct (shipped). Mode F: train 2016-2020, range map 2021, test 2022.
- **5.2 Truths**: (a) ERA5-type targets of the dataset (balloon-corrected; their noise pool overlaps what the model saw, AU-5); (b) **radiosondes as independent truth**, at the nearest grid point, with surface T and p moved to the station elevation. Explain why both are needed: ERA5 is smooth and partly assimilates the balloons; balloons are points with instrument noise of about 0.5 m/s in wind.
- **5.3 Baselines (Table 3)**: clim (all training years, same point × month × 2-h bin), **clim15** (the 15 years before the test, so warming is in the bar), **gauss** (Earth-GRAM-style; 2.3), **gaussfull** and **bank** (balloon stations), E12 (earlier adopted model), raw HRES (mode F), raw ERA5 (mode P), persistence (observe). For each: the pool size R (fair CRPS) and how it is sampled.
- **5.4 Metrics**: define each one formally in Appendix B (the Part 7 table gives the list). The main text names the headline set: fair CRPS and skill vs clim15; CRPS ratio vs Gaussian; coverage at 90 / 99 %; PIT; variogram score p = 0.5; energy score; vertical- and cross-variable correlation errors; shear and lapse-rate distribution distances; tail rates.
- **5.5 Aggregation and significance**: 19 cells (u, v, T, RH × 0-1, 1-5, 5-12, 12-18 km + t2m, sp, rh2m). Paired differences per case. **21-day block bootstrap** 95 % intervals (AU-4). Ties are called when the interval spans 0. Multiple testing: report the count of better/worse/tie cells and note that about 1 in 20 ties will look significant by chance (or apply a Holm or false-discovery-rate correction in the supplement). Seeds: 3 score seeds and ≥ 2 training seeds for model-vs-model claims; the noise yardstick.
- **Pre-registration-style rules**: the project wrote PASS / KILL / MISS rules into each verdict script's header before running it (`new_plan_kit/bNN_*.py`). This is rare and worth a paragraph. It defends against forking paths, and the negative-results table (7.2) proves it was used.

## 5.6 Results (≈ 2500-3500 words, the figures carry it)

Order each subsection as: the question → the figure → the numbers with intervals → the limit.
- **6.1 Held-out skill and calibration**: Fig 5 (scorecard), Fig 6 (skill vs height), Fig 7 (calibration), Table 4 (headline). Cells not better than the Gaussian, named. T 12-18 km negative and why (tropopause changes around 2020, IL-67; E4 idea).
- **6.2 Against Earth-GRAM-style and measured-profile bars**: Table 5 (the kit: tool / gaussfull / bank, accuracy, coupling, shape). Fig 8 (paired differences with intervals as a forest plot). Explain "the v-wind tie is the climate ceiling": all three tie.
- **6.3 Distribution shape and structure**: Fig 4 (example spaghetti vs balloons and Gaussian, NASA Fig 13/14 analogue), Fig 9 (shear and lapse CCDFs on a log axis), Fig 10 (vertical correlation matrices and their error), plus PIT/skew/kurtosis in the supplement.
- **6.4 Ablations**: Fig 11 (stack ablation: plain → +range map → +shuffle → +shear map → +lapse map; and training-loss ablations: no step-CRPS, no energy score, no balloon correction, if the logs hold them). Use only ablations that have logs; mark "development years" on them.
- **6.5 Forecast and past modes**: Fig 12 (mode F skill vs lead with raw HRES and climatology; the vertical-correlation error with and without the shuffle; coverage by lead). Past mode: median error 6 % below raw ERA5, CRPS 5.5 % below the station correction (README; find the log).
- **6.6 Launch-day observations**: Fig 13 (radar gain by height band with bootstrap intervals; El Paso co-located, Holloman at about 145 km). `observe` against persistence at 10 m (TCS tie, MAF 3.9 % worse; be honest).
- **6.7 Monte Carlo application**: Fig 14 (apogee and landing variance share by height band, P6), plus the IL-201 test (flattening 100-300 m structure changes apogee by 0.9 % of its spread), plus a short paragraph on the 3 flights (Table S-x), framed as feasibility.

## 5.7 Discussion (≈ 1200-1500 words)

- **7.1 What worked and why** (from `Useful results.md` part 0): measured tables beside the network beat new network bodies; more information in (radar, ensemble features); learning the leftover around a climate centre; more test rows turn near misses into passes; network capacity where there is signal.
- **7.2 Negative results**: Table 6, about 10-15 rows with one-line reasons:
  - re-ordering members (ECC variants, STRAND templates over-link: lift 3.51 vs 2.35);
  - trackers that follow recent errors;
  - uniform stretching of tails (RH 12-18 km cov99 0.948 → 0.991 but CRPS +5.9 %);
  - changing the noise shape to fix coverage (AV30: no effect);
  - run disagreement as a spread signal;
  - guessing a site from descriptors;
  - Weibull wind head (the calm gap is in ERA5 itself: calm 1.2 % vs stations 6.1 %);
  - token generator too slow;
  - driver interactions far worse.
  AIES values "lessons learned"; this is a strength.
- **7.3 Limitations**:
  - two balloon stations;
  - one box (plus Denver);
  - development-set reuse;
  - real Earth-GRAM not run;
  - the ERA5 truth is smooth and saw the balloons;
  - the 2023 sonde change;
  - wind skill at the climate ceiling;
  - vertical-correlation error larger than the Gaussian;
  - shear tails short (0.70-0.91 of balloons) and too few unstable layers aloft;
  - T 12-18 km;
  - mode F has one test year;
  - the near-ground wind at a site without a record is the main remaining error, and pad data are needed (one month of pad data gave −25 % in tests);
  - apogee accuracy is bounded by the rocket model.
- **7.4 Use guidance**: when to use which mode; that `trust` lines and refusals exist (outside the box, missing stores).

## 5.8 Conclusions (≈ 300-400 words)

Three findings, one limitation, one next step: the global extension, real Earth-GRAM, pad measurements, aircraft profiles (E2) as all-hours truth.

## 5.9 Appendices / supplement

- A. Heights, variables, units, the target transform.
- B. Metric definitions with formulas (Part 7) and estimators (fair CRPS, VS p = 0.5, PIT, coverage, correlation errors, shear and lapse definitions, Richardson number, co-extremes, hydrostatic gap).
- C. Calibration-stack algorithms (pseudo-code from the docstrings).
- D. Full per-cell tables (ERA5 and balloons) for each test window.
- E. Denver box and all-hours results.
- F. Software: package layout, tests (count, e.g. 431 passing on 2026-11-13; re-run before quoting), the reproducibility commands.
- Supplement: every figure per variable, rank histograms, PIT per band, seasonal and hour breakdowns, gusts, density, mode F per lead, the list of all trials with verdicts (machine-generated from `New_Plan.md` section 9 and `docs/logs/AUTOPILOT.md`).

---

# Part 6. The figure plan

Conventions for all figures: the Part 10 palette (one fixed colour per source); heights on the **vertical axis** in km AGL (atmospheric convention), with the near-ground part stretched (a split axis or square-root scale, because 0-2 km holds 12 of 44 heights); 95 % intervals as ribbons or error bars from the 21-day block bootstrap; "development (2024-25)" or "held-out (2026 Jan-Jun)" written into every panel title or caption.

| Fig | Content | Chart type and encoding | Data source | Caption must say |
|---|---|---|---|---|
| **1** | System schematic: inputs (place, date, hour, drivers, forecast, observations) → router by lead → generator / mode F / mode P → calibration stack (range map → shuffle → shear map → lapse map) → derived outputs → Monte Carlo files | Block diagram, left to right; the generator shown as noise ε → conditional LayerNorm blocks; colour per mode | code structure (Part 5.4) | which parts are learned and which are fitted tables |
| **2** | Domain map: NM/TX box with the 0.25° grid, terrain shading, balloon stations (Santa Teresa, Midland), Spaceport America, ASOS sites, NEXRAD (KEPZ, KHDX), WSMR RRA site; inset of the US with both boxes | Map (cartopy, PlateCarree), terrain from ERA5 orography or a DEM; markers by type | `configs/region.toml`, `configs/sites.toml` | box edges; that only these boxes are served |
| **3** | Data timeline: ERA5 1991-2025, train / validate / calibrate / develop / test bars; IGRA, HRES 2016-22, ASOS, radar periods; the two final-test windows | Gantt-style horizontal bars | Part 5.5 | that 2024-25 was reused for decisions |
| **4** | Example atmospheres: one case (a held-out 2026 H1 00Z balloon day from existing files, or a development day). Panels u, v, T, RH vs height: 100 tool members (thin lines), the median, the 5-95 % band, the balloon (black), and the Gaussian's 100 members in a second column. Bottom row: CDF at 3 heights, tool vs Gaussian vs the balloon climatology (the analogue of Earth-GRAM Fig 14) | Spaghetti + band; small-multiple CDFs | tool via `tempest_weather_v2.Launch` on a development date; balloons from IGRA | that it is one case and is illustrative; pick it by a rule (e.g. the median-CRPS case), not by beauty |
| **5** | **Headline scorecard**, 2 truths × 2 references: rows = 19 cells; columns = ERA5 vs clim15, ERA5 vs Gaussian, balloons vs clim15, balloons vs Gaussian. Cell colour = skill or % CRPS change (diverging, symmetric, blue = tool better); hatched = interval spans 0; the number printed in each cell | Heatmap scorecard (GenCast/FGN style) | `docs/final_test/tables.md` (2026 H1) or the Option A run; development: `models/l3_c4wl_s0_cal2021_smap_shufc8_lmap_fair_headline.csv` | estimator (fair), block length, pool sizes |
| **6** | Skill vs height: CRPS skill vs Gaussian (and vs clim15) for u, v, T, RH at all 44 heights, 95 % ribbons, zero line | 4 panels, x = skill, y = height (log or split axis) | the per-column `*.score.csv` of the score and sonde runs | which truth; that the band means of Fig 5 come from these |
| **7** | Calibration: (a) coverage of central intervals at nominal 10…99 % vs nominal (reliability curve) for tool, Gaussian, clim15, with binomial intervals; (b) PIT histograms per variable (pooled heights) for ERA5 and balloons; (c) cov99 per cell as a dot plot with the 0.99 line and ±2σ binomial band | Reliability line plot; histograms with a uniform reference line; dot plot | score / sonde outputs (`--extras` coverage at all levels, `final_shape.csv`) | which cells miss and by how much |
| **8** | The kit's paired comparisons (tool vs gaussfull, tool vs bank): forest plot of % difference with 95 % intervals for CRPS u/v/T, VS u/v/T, VSx, vertical-correlation error, cross-variable correlation error, co-extremes | Forest plot (dot + interval), zero line, labels "tool better" / "baseline better" | `docs/results/logs/kit_b9_gram_compare.log` (2026-11-14 block) | 800 balloons, development window, neither blind; gaussfull is not Earth-GRAM |
| **9** | Shear and lapse-rate distributions: CCDF (1 − F) of layer vector shear in 4 bands for balloons, tool, gaussfull, bank, on a log y-axis; inset of p50 and p99 ratios; a panel of the Ri < 1 share by band | Log-scale CCDF lines (CorrDiff-style PDF/tail figure); bar or dot inset | kit log SHAPE block; `il103_*`, `il194_shear_2021_22.log` | the 2023 sonde change inflates the post-2023 balloon tails; use 2021-22 balloons as a second reference |
| **10** | Vertical structure: correlation matrices across the 44 heights for u (and T): balloons, tool, Gaussian; then difference maps (tool − balloons, Gaussian − balloons) | 3 + 2 heatmaps, diverging colour for differences | needs a small new script reading pools (development data only) | the vertical-correlation error is larger for the tool: say it plainly |
| **11** | Ablations: (a) stack ablation on the held-out 2026 rows (plain p2f → +shuffle → +shear map), metrics shear distance, vertical-correlation error, event-coverage gap, skill; (b) training-loss ablations from development logs | Grouped dot plot or slope chart per metric | `docs/final_test/shape_stack_vs_plain.txt`, `shape_*.log`; PLAN.md Phase 2 results | (a) is descriptive (not used for any choice) |
| **12** | Forecast mode: (a) CRPS skill vs lead (1/3/5/7 d) for raw HRES, network, tool blend, climate mode; (b) cov99 by lead (shipped column, without PIT; see Part 8 note); (c) vertical-correlation error with and without the shuffle | Line plots vs lead with markers; reference lines at 0 / 0.99 | FINAL_REPORT section 5; `models/modeF_*_eval.csv` | test year 2022 only; the climatology's pool |
| **13** | Launch-day radar: CRPS gain by height band (2.5-5, 5-12, 12-18 km) with 95 % intervals, El Paso radar (co-located with the balloon) vs Holloman (≈ 145 km from the balloon site, ≈ 80 km from the pad); day vs night | Dot + interval per band, two colours | `docs/results/logs/il198_bootstrap.log`, O2 logs | one radar pair, one balloon site |
| **14** | Monte Carlo relevance: (a) share of apogee and landing variance by height band (bars: 0-50, 50-150, 150-300, ... 3000-5000 m); (b) apogee per m/s of wind by band; (c) optional landing-dispersion scatter with tool vs Gaussian ellipses | Horizontal bar charts with height on the y-axis; scatter + ellipses | `docs/results/logs/p6_apogee_sensitivity.log`; `il201_shear_apogee.log` | one rocket, one day, one site |

Supplementary figures (S1-S20 or so): training curves (`report.training_curves`); per-height CRPS in physical units; rank histograms per variable and band (`report.rank_histograms`); PIT per band; coverage at all levels per band; seasonal and hour-of-day skill (from score CSVs grouped by month and hour); skill by year (the T 12-18 km drift); the RH 12-18 km drift against balloons (AU-5); variogram skill (`report.variogram_skill`); surface fields; gust CRPS (W8d); density vs 149 balloons; superadiabatic share (33.8 % → 23.6 % vs ERA5 21.9 %); the Denver box; all-hours results; the mode F ensemble-feature candidate; the observation-conditioning replays (AV7, AV31) if the user wants them included; the full trial list.

Tables (main): **T1** data sources; **T2** hyperparameters; **T3** baselines (definition, pool, estimator); **T4** headline held-out results (Part 8 numbers, with intervals); **T5** Earth-GRAM kit (tool / gaussfull / bank; accuracy, coupling, shape); **T6** negative results.

---

# Part 7. Metric-to-graphic map

Every metric the project computes, what it measures, its definition, and how to show it.

| Metric | Measures | Definition (estimator) | Where computed | Show as |
|---|---|---|---|---|
| CRPS | accuracy + spread, per value | fair: (1/m)Σ\|x_i − y\| − 1/(2m(m−1)) ΣΣ\|x_i − x_j\| | `scoring/score.py`, `sonde.py` (`--fair-baseline`) | physical units vs height (Supp); in scorecards as skill or ratio |
| skill15 (CRPSS vs clim15) | gain over recent climate | 1 − CRPS / CRPS_clim15 (fair for both) | same | Fig 5, Fig 6 |
| % vs Gaussian | gain over the Earth-GRAM-style bar | (CRPS_gauss − CRPS)/CRPS_gauss | same | Fig 5, Fig 8 |
| Median error (MAE of the median) | best-guess accuracy | \|median − y\| | same (headline) | Table 4 column (user wants it next to CRPS) |
| cov90, cov99 | range honesty | share of truths inside the central 90 / 99 % | same | Fig 7c dot plot with binomial band |
| Coverage at all levels / mean \|cov − nominal\| | calibration curve | per nominal level | `--extras`, `compare_shape.py` | Fig 7a reliability curve |
| PIT and PIT distance | calibration shape | rank of the truth among the members; total-variation distance from uniform | `diag.py`, `final_shape.csv` (pit_tv) | Fig 7b histograms |
| Rank histogram | spread vs error | counts of the truth's rank | `report.rank_histograms` | Supp |
| Skew / kurtosis difference | non-Gaussian shape | sample moments, model − truth | `final_shape.csv` | Supp dot plot |
| Tail-rate error | extreme frequency | observed rate beyond model quantiles (0.5 %, 99.5 %) ÷ nominal | `final_shape.csv` | Supp bar; say the goal (0.2) is probably not reachable at these sample sizes |
| Event-conditional coverage | calibration on hard days | coverage in the top-decile wind/shear cases | shape scripts | Supp; mention the forecaster's dilemma |
| Variogram score (p = 0.5) | profile shape and dependence | Σ w_ij (\|y_i − y_j\|^p − E\|X_i − X_j\|^p)² | `score.py`, kit | Fig 8 (paired %) and Supp skill |
| VSx (cross-variable VS) | coupling of u, v, T at one height | VS over variables | kit | Fig 8 |
| Energy score | joint accuracy | E‖X − y‖ − ½E‖X − X′‖ | training and scoring | Supp only (weak on dependence) |
| Vertical-correlation error | structure in height | mean \|corr_model − corr_truth\| over height pairs | kit, `diag.py` | Fig 10, Fig 8 |
| Cross-variable correlation error | structure across variables | same over variable pairs | kit | Fig 8 |
| Shear distribution: p50 / p99 ratio, KS / quantile distance | sharpness of layers | layer vector shear \|ΔV\|/Δz per band, model quantiles ÷ balloon quantiles | kit, `shear_map.py`, IL-60 logs | Fig 9 CCDF + ratio inset |
| Ri < 1 share | dynamic instability layers | bulk Richardson number per layer from T and shear | kit | Fig 9 panel |
| Superadiabatic share | thermal realism | share of layers with lapse > 9.8 K/km | lapse-map logs | Supp |
| Co-extremes | joint extremes (shear + wind) | rate of simultaneous top-tail events vs balloons | kit, G3B logs | Fig 8 row; note it rests on about 5 % of cases |
| Depth deviation | profile-level spread fidelity | as defined in the kit (read `b9_gram_compare.py`) | kit | Table 5 only |
| Hydrostatic gap % | physical consistency | relative mismatch of p, T, z against hydrostatics | kit | Table 5 / text |
| Density error vs balloons | derived-variable accuracy | % error 0-10 km | V6 log | text + Supp |
| Mode F CRPS skill by lead | forecast value | as above, vs a short-record climatology | `scripts/il6_modeF.py` evals | Fig 12 |
| Radar / observe CRPS gain | value of observations | paired % change, bootstrap over days | `il198_bootstrap.log`, `a1_bootstrap.log` | Fig 13 |
| Apogee / landing variance share | MC relevance | first-order sensitivity per band × wind variance | `p6_apogee_sensitivity.log` | Fig 14 |
| Gust CRPS | surface extremes | CRPS of the 5-s gust vs ASOS one-minute peaks | W8d logs | Supp |

---

# Part 8. The numbers ledger

Every number in the paper must trace to one of these files. Before use: open the file, confirm the number, and record the file path in a comment in `paper/numbers.tex`.

## 8.1 Held-out test 2026 Jan-Jun (earlier "final system"; source: `docs/final_test/tables.md`, `docs/results/FINAL_REPORT.md` sections 2-4, `docs/final_test/*.txt|*.csv|*.log`)

- ERA5 (85,734 rows): mean skill15 +0.0209 (E12 +0.0204; development +0.0278); mean \|cov99 − 0.99\| 0.0049 (E12 0.0047; development 0.0032); CRPS vs Gaussian +5.6 %, better in 13 of 19 cells.
- Balloons (about 290 Santa Teresa + 264 Midland soundings with an ERA5 pair): skill15 +0.0187; \|cov99 − 0.99\| 0.0064; vs Gaussian +2.2 %, better in 12 of 19.
- Per-cell values and intervals: `tables.md` (copy the whole tables into Appendix D).
- All 38 cells tie with E12.
- T 12-18 km: −0.0300 [−0.0514, −0.0067] (ERA5), −0.0385 [−0.0591, −0.0176] (balloons).
- Weakest coverage: balloons RH 12-18 km 0.9583; v 12-18 km 0.9766; ERA5 T 0-1 km 0.9783.
- Shape stack vs plain on 2026: shear distance 0.0333 → 0.0274; vertical-correlation error 0.0697 → 0.0606.
- **Caveat.** These skill15 numbers use the **plain** estimator (before AU-1). FINAL_REPORT / 15.4 says the 2026 test gets "a caveat only (fair baseline + 21-day blocks when run)". Two ways to handle it: present the plain-estimator numbers and state the measured bias (≈ 0.013 on ERA5 and ≈ 0.003 on balloons, measured on 2024-25), or ask the user whether the stored 2026 sample arrays can be re-scored with the fair estimator **without reading the 2026 data again**. Check whether any `docs/final_test/` file stores per-row CRPS of each source; if not, it cannot be done without touching 2026 data, which is forbidden. Model-vs-model and model-vs-Gaussian differences are much less affected (the bonus cancels; the margin over the Gaussian barely moves, +0.080 → +0.081).

## 8.2 Shipped stack l3_c4w, development 2024-25 (sources: `New_Plan.md` section 9 rows AU-1 step 5, AU-6; `models/l3_c4wl_s{0,1,2}_cal2021_smap_shufc8_lmap[_fair]_headline.csv`; balloons `models/l3_c4wl_s0_sonde_cal2021_smap_headline.csv`)

- Fair baseline, ERA5 seed 0: skill15_unknown +0.017 (plain +0.030); seed 1 +0.018; skill_known (all-years clim) +0.026; balloons skill15_unknown +0.007 (plain +0.010).
- Fair skill15_known per band: interval above 0 in 9 of 19 (all T bands +0.035 to +0.058, t2m +0.054, u 1-18 km +0.016 to +0.047); point below 0 in u 0-1 km, RH 5-12 km, rh2m.
- Margin over the Gaussian (unknown drivers) ≈ +0.08 in skill units, unchanged by the fair estimator.
- **Seed noise**: training seed ≈ 0.0005 mean skill15, ≤ 0.003 per band (rh2m 0.005); score seed ≈ 0.0002 on the shift and ≈ 0.002 on the level.

## 8.3 Earth-GRAM kit, 800 balloons, El Paso + Midland, 00Z + 12Z, 2024-25, 100 members (source: `docs/results/logs/kit_b9_gram_compare.log`, block of 2026-11-14 11:31)

- CRPS u/v/T: tool 4.400 / 4.373 / 1.962; gaussfull 4.533 / 4.392 / 2.120; bank 4.530 / 4.368 / 2.082.
- Paired gaussfull − tool: u +3.0 % [interval > 0], v +0.4 % (tie), T +8.1 %. bank − tool: u +3.0 %, v −0.1 % (tie), T +6.1 %.
- VS u/v/T: tool 1.330 / 1.134 / 0.209; gaussfull 1.379 / 1.142 / 0.215; bank 1.373 / 1.135 / 0.215.
- Vertical-correlation error: tool 0.061, gaussfull 0.040, bank 0.038 (**both better than the tool**, intervals exclude 0).
- Shear p99 ratio to balloons (4 bands): tool 0.70 / 0.91 / 0.75 / 0.77; gaussfull 0.65 / 0.84 / 0.81 / 0.74; bank 0.68 / 0.92 / 0.88 / 0.85.
- Ri < 1 share: balloons 0.738 / 0.351 / 0.199 / 0.149; tool 0.649 / 0.301 / 0.190 / 0.068; gaussfull 0.599 / 0.296 / 0.257 / 0.090.
- cov90 u/v/T: tool 0.878 / 0.871 / 0.891 (all a little narrow against real air, as are both bars).
- Hydrostatic gap: balloons 0.026 %, tool 0.064 %.
- Copy the exact intervals from the log; the log prints them.

## 8.4 Forecast mode (source: FINAL_REPORT sections 5 and 11; `models/modeF_*_eval.csv`; `Useful results.md` update of 11-14)

- 2022, CRPS skill vs short-record climatology at 1 / 3 / 5 / 7 d: raw HRES 0.57 / 0.34 / 0.08 / −0.21; network 0.69 / 0.54 / 0.35 / 0.20; tool (50:50 network/ridge) 0.691 / 0.539 / 0.350 / 0.209.
- Vertical-correlation error 0.3-0.5 → 0.05-0.12 with the shuffle.
- Denver mode F 0.68 / 0.57 / 0.43 / 0.26.
- **Coverage-column caveat**: verdict tables scored a column with a PIT step; the tool appears to export the range map fitted **without** PIT (`scripts/il6_modeF.py:211`, `tempest/export_tool.py:208`; a code reading in `Useful results.md`, not verified). Before quoting any mode F cov99, verify which column the shipped tool uses (the "SHIPPED-COLUMN LEDGER step 0" in `Useful results.md`, new idea 7), and quote that column.

## 8.5 Observation and site results (sources: FINAL_REPORT section 12; logs named there)

- Radar: +31.3 % [+25.0, +37.5] (2.5-5 km), +15.2 % [+9.4, +20.9] (5-12 km), +6.4 % [+2.7, +10.0] (12-18 km); 120 days 2021-23 (`il198_bootstrap.log`). Holloman keeps the gain: 2.5-5 km +27.6 % vs +29.1 %.
- `observe` vs persistence at 10 m: TCS −0.011 m/s [−0.046, +0.026] (tie); MAF +0.037 [+0.007, +0.067] (tool 3.9 % worse) (`a1_bootstrap.log`).
- 0-1 km shear tail vs balloons: −32 % vs 2024-25 balloons, −9 % vs 2021-22 balloons (before the sonde change) (`il194_shear_2021_22.log`).

## 8.6 Monte Carlo and physics (sources: `p6_apogee_sensitivity.log`, `il201_shear_apogee.log`, FINAL_REPORT section 10, `FlightSIM&Validation with Tempest-ARKNET.md`)

- Apogee variance share by band: 0-50 m 18.9 %, 50-150 m 53.1 %, 150-300 m 15.4 %, 300-600 m 5.0 %, ... ; landing variance 3000-5000 m 43.3 %. Base apogee 3720.7 m AGL (Sol Invictus model, mode ai, one date).
- Flattening 100-300 m structure: apogee change 0.9 % of its sd, landing 2.0 %.
- Density within 0.5 % of 149 balloons (0-10 km); 1976 standard atmosphere 6.4 % off at the pad.
- Superadiabatic layers 33.8 % → 23.6 % with the lapse map (ERA5 21.9 %).
- Gusts: CRPS 1.73 → 0.61 after a measured wind; 1.34 → 1.06 for model winds; gust factor ≈ 1.4.
- 3 flights: mean absolute error 5.21 % (as filed) vs 5.81 % (past mode) vs 6.15 % (standard air at the true pad) vs 7.37 % (climate mode).

## 8.7 Numbers you still need to compute or look up (none needs 2026 data)

1. Grid-point count, training row count, balloon counts per window, number of parameters of l3_c4w (from the data files and checkpoint).
2. Per-height skill and coverage arrays for Fig 6 / 7 (from `*.score.csv`; check what the 2026 H1 run saved under `docs/final_test/`).
3. Correlation matrices for Fig 10 (development pools; a new script).
4. The recent-15-year `gaussfull` (AU-7; a one-line option in the kit, listed as open in `Beat Earth-GRAM.md` section 5) so the Gaussian bar is shown in both forms.
5. Ablation numbers from logs for Fig 11b (find them in `docs/plans/PLAN.md` Phase 2 results and `docs/logs/AUTOPILOT.md`; quote only those with seeds and intervals).
6. If Q1 = Option A: the whole of 8.1 again from the 2026 July-October run.

---

# Part 9. Statistics and fairness rules for the paper

1. **Fair CRPS everywhere.** All baselines and the model use the fair estimator, with climatology drawn from the whole pool without replacement (`--fair-baseline`). Report the pool size R of each baseline. If a number in the paper uses the plain estimator (the 2026 H1 tables), say so in its caption and give the measured bias.
2. **Intervals**: paired, 21-day block bootstrap, 95 %; at least 1000 resamples; resample days (not rows) so all heights and variables of one day move together.
3. **Calling a result**: "better" only if the paired interval excludes 0; otherwise "tie". Give counts of better / tie / worse cells. Do not rank models on point estimates inside the noise yardstick.
4. **Seeds**: model-vs-model claims need ≥ 2 training seeds (paired against a base retrained with the same seed) and 3 score seeds. Report the seed spread as a separate line in Table 4.
5. **Development reuse**: write "development years (2024-25), reused for model selection" on every such number. Prefer held-out numbers in the main text and development numbers in sections that explain choices.
6. **Truth limits**: ERA5 assimilates the balloons and is smooth; balloons carry instrument noise and the 2023 sonde change. Where the two truths disagree, report both and let the balloons referee (the project rule).
7. **Multiple comparisons**: 19 cells × 2 truths × several references. In the supplement, give a false-discovery-rate-adjusted version of the scorecard (Benjamini-Hochberg). In the main text, add one sentence on expected false positives.
8. **No outcome-selected cases** for scores (forecaster's dilemma). Example cases (Fig 4) are picked by a stated rule.
9. **Pre-set rules**: say that every trial had PASS / KILL / MISS rules written before it ran, cite the verdict-script convention, and give the count of trials and verdicts (from `New_Plan.md` section 9 and AUTOPILOT; count them, don't guess).

---

# Part 10. Figure and writing style

## 10.1 Figure style

- Load the `dataviz` skill before writing any plotting code. Use matplotlib with a project style file (`paper/figs/tempest.mplstyle`). Export **vector PDF** (and PNG at 300 dpi for preview). Embed fonts. Check the AMS figure widths (about 8 cm single column, 16-17 cm double) in the current author guide and set `figsize` to them.
- **One colour per source, used in every figure** (Okabe-Ito, colour-blind safe):
  - Tempest tool: blue #0072B2
  - Gaussian / Earth-GRAM-style: vermillion #D55E00
  - Measured bank: bluish green #009E73
  - clim15: grey #7F7F7F
  - E12: sky blue #56B4E9, dashed
  - raw HRES / raw ERA5: orange #E69F00
  - truth: black (balloons solid, ERA5 dashed)
- Line styles separate truths: solid = balloons, dashed = ERA5.
- Scorecards: diverging blue (tool better) to red (tool worse), symmetric limits (e.g. ±20 % or ±0.05 skill), white at 0, hatching for ties, numbers printed in cells, rows grouped by variable with thin separators.
- Height axis: km AGL on y; split or square-root scale for 0-2 km; tick labels at the actual band edges (1, 5, 12, 18 km).
- Units everywhere (m s⁻¹, K, %, m s⁻¹ km⁻¹ for shear). No chart junk; light grid. Panel letters (a), (b), ... in bold at the top-left.
- Write each caption as a sentence that states the finding, then the details: what is plotted, the truth, the window, the interval method, n.
- Accessibility: never rely on colour alone. Add markers or line styles, and check every figure in greyscale.

## 10.2 Writing style

- AMS style: past tense for what was done, present tense for what the figures show; SI units; "AGL" with heights; UTC and local solar time stated.
- Every number with its interval and window ("+5.6 % (13 of 19 cells better; 2026 Jan-Jun, ERA5)").
- Use one name per concept and keep it. The project's internal labels (AV17, IL-198, `l3_c4w`, skill15) must be translated:
  - shipped generator / the generator
  - "recent-15-year climatology (clim15)"
  - "Earth-GRAM-style Gaussian"
  - "measured-profile bank"
  - "range map"
  - "shear map"
  
  Keep a glossary in Appendix A. Never put an internal trial ID in the main text. Put them only in the supplement's trial list.
- Hedge exactly as much as the evidence demands; no "significantly" without a test.

---

# Part 11. Production plan

## 11.1 Files to create (all new; nothing existing changes)

```
paper/
  README.md               how to rebuild the paper and every figure
  manuscript/main.tex     AMS template; \input{../numbers.tex}
  manuscript/sections/*.tex
  manuscript/refs.bib
  numbers.tex             GENERATED: \newcommand{\skillERAtest}{+0.0209} ... with source comments
  figs/tempest.mplstyle
  figs/f01_schematic.(svg|tex)    drawn by hand (TikZ or an SVG editor)
  figs/f02_map.py ... f14_mc.py   one script per figure; each reads only files listed in its header
  figs/out/*.pdf
  tables/t4_headline.py ... -> tables/out/*.tex
  scripts/make_numbers.py  parses tables.md, headline CSVs, kit logs -> numbers.tex
  scripts/check_numbers.py asserts every \newcommand appears in the manuscript and every number in the
                           manuscript text comes from numbers.tex (no hand-typed numbers)
tests/test_paper_numbers.py  parser tests on small fixtures (no data needed)
```

## 11.2 Order of work

1. Ask the user Q1-Q5 (Part 14). Without answers, take Option B, "Earth-GRAM-style" wording and AIES, and say so.
2. `make_numbers.py` + test: the ledger (Part 8) becomes machine-readable. Run it; diff against Part 8 by eye.
3. Figures in this order: 5, 7, 8 and 9 (existing files only), then 2 and 3 (no data needed), then 4, 6 and 10 (some new extraction from development pools: CPU, light, within machine rules), then 11-14.
4. Tables T1-T6.
5. Write Methods and Data first (they are facts), then Results (follow the figures), then Discussion, then Introduction, then Abstract last.
6. Supplement: generate the per-cell tables and the trial list by script.
7. Checks (11.3), then hand the draft to the user. Do not submit anything anywhere.

## 11.3 Checks before calling the draft done

- `check_numbers.py` passes: no hand-typed number in the `.tex`.
- Every figure script runs from a clean shell and reads only the files in its header; none reads 2026 data (grep each script for `2026`, `final_test_2026h2`, `era5_2026h2`; only `docs/final_test/` result files may appear).
- Every 2024-25 number carries "development" in text or caption.
- The words "Earth-GRAM" never appear without "-style" unless real GRAM output was scored.
- Every claim in Part 2.2 has its limit sentence in the text.
- The full test suite still passes (`OMP_NUM_THREADS=16 .venv/Scripts/python -m pytest tempest_weather_v2/tests tests -q -p no:cacheprovider --ignore=tests/test_flight_sim_readers.py`), never while a GPU score runs.
- Compile the PDF; check fonts embedded; check each figure in greyscale.
- Re-run a literature search for 2026 work on generative profile models before finalising "to our knowledge".

---

# Part 12. Reviewer questions to answer before they are asked

1. *"Why not run real Earth-GRAM?"* Answer with the run, or with the ceiling argument (2.3) and the RRA plan.
2. *"Two balloon stations is thin."* Give the counts and the day-block intervals. Point to the 197-station real-air gap result (RA stage 1a, 90 % coverage 0.83-0.90 → 0.90-0.92) as evidence beyond the two stations. Name the global extension.
3. *"The development set was reused 30+ times."* Answer with the held-out windows, the pre-set rules, and the seed noise yardstick.
4. *"ERA5 truth saw the balloons."* Answer with the two truths; balloons referee.
5. *"Your skill over climatology is tiny."* Agreed; climate-mode skill is bounded by what a date can tell (the v-wind ceiling with the bank). The value is calibration and structure. Forecast and observation modes add the skill.
6. *"Is the calibration stack overfitting?"* Fit on 2021-23, judged on 2024-25 and 2026; monotone maps; the ablation shows each step on held-out rows.
7. *"Why an MLP and not a diffusion model or transformer?"* The column is 179-dimensional, so FGN-style conditional-norm noise is enough. A token generator was tried and was too slow. Compute is minutes on a laptop GPU.
8. *"Vertical correlation is worse than the Gaussian."* Say it in the abstract or results; the shuffle and shear map trade correlation error against shear realism; future work.
9. *"Does it matter for a real rocket?"* P6 and IL-201; the 3-flight check shows the rocket model's error dominates. Name the plan for pad measurements and more flights.
10. *"Reproducibility?"* Repo tag, Zenodo DOI, commands, tests, licence (MIT), data access.
11. *"Statistical significance across 19 cells?"* Hatching, counts, FDR in the supplement.
12. *"Why AGL heights, not pressure levels?"* Monte Carlo users fly in height above the pad; the conversion method and its error.

---

# Part 13. References (verify every entry's details before citing)

AI weather and generative models
- Price, I. et al. GenCast: diffusion-based ensemble forecasting for medium-range weather. arXiv:2312.15796; Nature (2025). https://arxiv.org/abs/2312.15796
- Alet, F. et al. Skillful joint probabilistic weather forecasting from marginals (FGN; WeatherNext 2). arXiv:2506.10772. https://arxiv.org/html/2506.10772v1 (one source gives 2506.14285; check the abstract page)
- Lang, S. et al. AIFS-CRPS: ensemble forecasting using a model trained with a loss function based on the continuous ranked probability score. arXiv:2412.15832. https://arxiv.org/abs/2412.15832
- Rasp, S. et al. WeatherBench 2. arXiv:2308.15560 (J. Adv. Model. Earth Syst. 2024). https://arxiv.org/abs/2308.15560
- Mardani, M. et al. Residual corrective diffusion modeling for km-scale atmospheric downscaling (CorrDiff). Commun. Earth Environ. (2025), doi:10.1038/s43247-025-02042-5; arXiv:2309.15214
- Kochkov, D. et al. Neural general circulation models for weather and climate (NeuralGCM). Nature (2024)
- Shen, X. & Meinshausen, N. Engression: extrapolation through the lens of distributional regression. JRSS B, doi:10.1093/jrsssb/qkae108. https://arxiv.org/abs/2307.00835

Verification and post-processing
- Gneiting, T. & Raftery, A. E. (2007) Strictly proper scoring rules, prediction, and estimation. JASA 102.
- Gneiting, T., Balabdaoui, F. & Raftery, A. E. (2007) Probabilistic forecasts, calibration and sharpness. JRSS B 69.
- Ferro, C. A. T. (2014) Fair scores for ensemble forecasts. QJRMS 140.
- Hamill, T. M. (2001) Interpretation of rank histograms for verifying ensemble forecasts. MWR 129.
- Scheuerer, M. & Hamill, T. M. (2015) Variogram-based proper scoring rules for probabilistic forecasts of multivariate quantities. MWR 143.
- Pinson, P. & Tastu, J. (2013) Discrimination ability of the energy score. DTU technical report.
- Clark, M. et al. (2004) The Schaake shuffle. J. Hydrometeor. 5.
- Schefzik, R., Thorarinsdottir, T. L. & Gneiting, T. (2013) Uncertainty quantification in complex simulation models using ensemble copula coupling. Stat. Sci. 28.
- Lerch, S. et al. (2020) Simulation-based comparison of multivariate ensemble post-processing methods. NPG 27, 349. https://npg.copernicus.org/articles/27/349/2020/
- Lerch, S. et al. (2017) Forecaster's dilemma: extreme events and forecast evaluation. Stat. Sci. 32.
- Allen, S., Koh, J., Segers, J. & Ziegel, J. Tail calibration of probabilistic forecasts. arXiv:2407.03167. https://arxiv.org/abs/2407.03167
- Allen, S. et al. Weighted verification tools for high-impact events. arXiv:2209.04872; Evaluating forecasts for high-impact events using transformed kernel scores. arXiv:2202.12732
- Wilks, D. S. (1997) Resampling hypothesis tests for autocorrelated fields. J. Climate 10; Künsch (1989) The jackknife and the bootstrap for general stationary observations. Ann. Stat. 17.
- ECMWF Tech. Memo 865 (representativeness error added before scoring against stations). https://www.ecmwf.int/node/19544

Aerospace atmospheres and launch winds
- White, P. W. (2026) Earth Global Reference Atmospheric Model (Earth-GRAM) 2026: User Guide. NASA/TM-20260004497, MSFC, doi:10.64631/GQWW9238. https://ntrs.nasa.gov/citations/20260004497
- Earth-GRAM User Guide 2023. https://ntrs.nasa.gov/api/citations/20230014404/downloads/Earth-GRAM%20User%20Guide%202023.pdf
- Justus, C. G. et al. GRAM-95 and earlier reports (cited in the 2026 guide as the perturbation-model source).
- Decker, R. & Barbré, R. Wind pair databases (NASA/TM-2013-217924); Temporal variability of upper-level winds at the Eastern Range, Western Range and Wallops Flight Facility (AMS ARAM 2014). https://ams.confex.com/ams/94Annual/webprogram/Manuscript/Paper231761/2014%20ARAM%20LSP%20Wind%20Pairs_Paper.pdf
- Barbré, R. (2013) Quality control algorithms for the KSC 50-MHz wind profiler database. JTECH. https://ntrs.nasa.gov/citations/20150002878
- NASA MSFC wind-pair and Jimsphere database reports: https://ntrs.nasa.gov/api/citations/20050092294/downloads/20050092294.pdf
- U.S. Standard Atmosphere 1976.
- Ceotto, G. et al. (2021) RocketPy: six degree-of-freedom rocket trajectory simulator. J. Aerosp. Eng. 34. https://ascelibrary.com/doi/10.1061/%28ASCE%29AS.1943-5525.0001331

Data
- Hersbach, H. et al. (2020) The ERA5 global reanalysis. QJRMS 146.
- Durre, I. et al. IGRA v2 (NOAA NCEI).
- Gelaro, R. et al. (2017) MERRA-2. J. Climate 30 (the data behind Earth-GRAM's lower atmosphere).
- Also: Open-Meteo, WeatherBench 2 data, IEM ASOS, NEXRAD, CPC indices (`ATTRIBUTION.md` has the credit lines).

Journal practice
- AMS Availability Statement examples. https://ametsoc.org/ams/publications/author-information/formatting-and-manuscript-components/availability-statement-examples
- AIES journal page. https://ametsoc.org/ams/publications/journals/artificial-intelligence-for-the-earth-systems
- AMS LaTeX template (Overleaf). https://www.overleaf.com/latex/templates/a-sample-american-meteorological-society-ams-latex-document/xvjwqqtdwjzh

---

# Part 14. Questions for the user (ask before the draft is final)

1. **Main held-out result.** Wait for "the model is final" and the one-time 2026 July-October test of the shipped model (Option A), or write now with the 2026 January-June test of the earlier system (Option B)?
2. **Real Earth-GRAM.** Can you request the GRAM Suite from NASA (and allow a WSL build), so the paper can score real Earth-GRAM 2026 output (MERRA-2 option and the White Sands 2019 RRA) at the two balloon stations? Until then the paper says "Earth-GRAM-style".
3. **Fair-baseline default (ASK_LATER 27).** The paper will quote fair-baseline skill (about +1.7 to +1.8 % on ERA5 for the shipped model instead of the README's +2.8 %). Agree?
4. **AI-assistance disclosure and authorship.** Which wording do you want for the AMS AI-tool disclosure? Who are the authors and affiliations? Funding? Competing interests?
5. **Venue.** AIES (recommended), JAMC, GMD, or an AIAA venue?
6. **Scope.** Include the Denver box and the observation-conditioning replays (AV7, AV31) in the supplement, or leave them for a second paper?
7. **Code release.** May the repo be tagged and archived on Zenodo at submission, and which assets can be published?
