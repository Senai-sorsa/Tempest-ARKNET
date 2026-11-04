# Research notes for plan v2

How the Argon report *Tempest-ARKNET Probabilistic Weather Architecture* was used, and the facts checked
while writing [PLAN.md](PLAN.md). Checked 2026-11-03.

## Kept from the report

| Idea | Where in the plan |
|---|---|
| Vertical coherence is required: independent per-height sampling creates fake shear | Product = whole profiles; energy/variogram score in acceptance criteria |
| Heights above ground, not pressure levels | Vertical grid |
| Temperature and RH profiles, not just wind | Variables (kept) |
| No CMIP6/LOCA2 for 1–3 years; empirical trend instead. LOCA2 has no upper-air winds | Long-range predictors |
| QBO as the long-lead predictor for upper winds | Analog shift, step 3 |
| Lead-time regimes (days / weeks / months / years) | Router, simplified to fixed rules |
| Honest skill: CRPSS beyond ~6 months is ~0–0.08, ~0 for low-level wind/RH | Acceptance criteria, risks |
| Walk-forward backtest with embargo, spatial blocks, refit preprocessing inside each fold | Acceptance criteria |
| PIT, spread-skill, CRPS, energy score, variogram score | Acceptance criteria |
| IGRA radiosondes as truth; ERA5 under-dispersion | Phase 6 |
| NASA Earth-GRAM as benchmark | Phase 9 |
| One-step generator (engression / FGN) trained on CRPS + energy + variogram | Phase 9, gated |

## Cut or deferred, and why

| Report item | Decision | Reason |
|---|---|---|
| Neural trunk–branch generator as the core | Deferred to phase 9 | Analogs give real profiles with no training; a network must beat them first |
| HNET/SIREN trunks, GNNs, sCM distillation, TensorRT | Cut | Solve speed/resolution problems the analog design does not have |
| HRRR fine-tuning stage, MBCn harmonisation | Cut | HRRR covers 2014+ only and adds a dataset seam; MBCn is needed only when mixing sources |
| MERRA-2, NARR, JRA-3Q, AMDAR, VAD | Cut | One reanalysis + radiosondes is enough to calibrate; JRA-3Q terms also restrict commercial use |
| 6.96 TB / 11-source lakehouse, ~1,200 A100 h | Cut | Plan needs ~0.1–0.8 TB and no GPU until phase 9 |
| Learned forecast router / gate | Cut | Fixed lead-time rules plus a linear blend over days 10–15; nothing to learn |
| CopulaCPTS + AgACI conformal layers | Replaced | Per (variable, height, lead) spread inflation fitted on the backtest |
| Coupled EOFs + Dryden shear filter | Partly kept | EOFs only for storage at CONUS scale; analogs already carry real shear, so no synthetic filter |
| 40 levels to 20 km | Adjusted | 44 levels to 18 km: covers the 13.7 km Sol Invictus apogee with margin and stays under ERA5's 50 hPa level |

## Facts checked

- **Open-Meteo ensemble** (curl test): `models=ecmwf_ifs025` returns 51 members with pressure-level wind
  (e.g. `wind_speed_850hPa`, `wind_speed_250hPa`), ~14.6 days of data. `gfs025` returns no pressure-level wind.
  The archive API has no pressure-level wind; the historical-forecast API does. This closes v1 open question 3.
- **ECMWF open data**: whole real-time catalogue CC-BY-4.0 from 1 Oct 2025. Free tier is coarser; full
  resolution / real-time extended range have service charges.
- **ARCO-ERA5 (Google)**: `gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3`, 37 levels,
  one global map per chunk, so point time series are very costly to read.
- **Earthmover Icechunk ERA5 (AWS)**: `s3://earthmover-icechunk-era5/icechunkV2`, us-east-1, anonymous,
  CC-BY-4.0, quarterly updates, spatial and temporal layouts, 13 pressure levels × 8 variables +
  35 single-level variables. Opened directly: data run 1940-01-01 to 2026-06-30; `pressure/temporal` has
  u, v, t, r, q, z, w, pv; temporal chunks are 8,736 h × 1 level × 12 × 12 points; codec `pcodec`
  (needs `numcodecs[pcodec]`); ~3–5 s per chunk from this machine.

## Facts from the `dynamics` repo and the launch context

- `aero_modeling/PRELIM_JARVIS/sims/sol_invictus_*.toml`: Sol Invictus, flown to impact from
  `sites/spaceport_america.toml` (32.99 N, 4,595 ft), atmosphere `StandardAtmosphere1976`, wind `UniformWind`.
- Apogee targets in the repo's tools: 45,000 ft (13.7 km), with 35–44k ft variants.
- `tools/weather/Weather_to_JARVIS_inputs.py monte-carlo` writes one mean/std TOML per campaign, so one
  weather query per campaign.
- IREC (the old Spaceport America Cup) moved to Midland, TX in 2025 (9–14 June), 2026 (15–20 June), and
  AIAA says it returns there in 2027; 2027 dates not published yet.
- Active IGRA stations near the pilot sites: Santa Teresa NM `USM00072364`, Midland TX `USM00072265`,
  Albuquerque `USM00072365`, Amarillo `USM00072363`. 201 active IGRA stations inside the CONUS box.
- QBO forecasts: multi-model ensembles stay reliable to at least a year ahead; one study reports correlation
  > 0.7 at 12 months.
- No study found that gives a clean ERA5-vs-radiosonde wind error for the US boundary layer; reported RMSDs
  elsewhere are ~2–3 m/s. The plan's starting error values are placeholders that phase 6 replaces.
- **CDS**: server-side area cut; 2026 forum reports of pressure-level queues of hours to > 24 h. New CDS
  ERA5 time-series dataset on pressure levels exists (6-hourly, 13 levels).
- **Earth-GRAM**: part of NASA GRAM Suite (catalogue MFS-33888-1); GRAMpy Python API since v2.0 (Oct 2023);
  builds on Linux/GCC, so Windows needs WSL.
- **IGRA v2.2**: free from NCEI, per-station derived files, updated daily.
- **engression**: `pip install engression` (v0.1.11), repo xwshen51/engression.

- **Predictor persistence** (CPC indices, 2026-11-04; lagged regression, tested on the last 30 % of the
  record): ONI correlation 0.78 at 3 months, ~0 from 8 months. QBO u30 from (u30, u50): 0.74 at 8 months,
  0.66 at 12, 0.53 at 20, ~0 at 32. The latest ONI (ASO 2026) is +2.46. CPC QBO data run through Oct 2026.
- **No machine-readable IRI ENSO plume** was found (the guessed data URLs return 404). It is not needed;
  see the line above.
- **Package versions (PyPI, 2026-11-04):** icechunk 2.3.1 (Python ≥ 3.12, Windows wheel), scoringrules
  0.11.0 (≥ 3.12), ecmwf-datastores-client 0.5.3, cfgrib 0.9.15.1, eccodes 2.50.0 (Windows wheels).
- **IGRA v2.2 derived format:** fixed-width header and level columns, listed in PHASE1.md §4. Derived files:
  Santa Teresa 143 MB, Midland 148 MB.
- **Open-Meteo historical-forecast API:** pressure levels from about 2021–22. Runs are stitched, so it suits
  single past dates after the ERA5 store ends, not long series.

## AI-model research (2026-11-04, Chrome + arXiv API)

- **WeatherNext 2 on Open-Meteo** (curl test at Midland): `/v1/ensemble?models=google_weathernext2_ensemble`
  returns 64 members at 0.25°, 6-hourly (`temporal_resolution=native`), 15 days, built from the 00Z and 12Z runs.
  Pressure levels 1000–50 hPa (13) carry T, RH, wind, geopotential height and vertical velocity; 10 m and 100 m
  wind are included too. One request counts as about 6.4 API calls. The model is an FGN: noise goes into
  the network's weights, and it is trained on CRPS.
- **AIFS ENS on Open-Meteo:** `ecmwf_aifs025_ensemble`, 51 members, pressure levels. It has been operational at
  ECMWF since 2025-07-01 and is up to ~20 % better than IFS ENS for surface temperature.
- **No long member archive on Open-Meteo:** the ensemble API keeps past members only from 2026-08-03. The
  historical-forecast API returns the member series, but every value is null.
- **WeatherNext 2 archive:** Earth Engine `projects/gcp-public-data-weathernext/assets/weathernext_2_0_0`,
  2022-01-01 to 2026-11-03, filtered by `ensemble_member` and `forecast_hour`. It has 27.8 km pixels and the same 13 levels
  (u, v, T, q, z, w), plus 10 m and 100 m wind, t2m, msl and 6 h precipitation. Historic data is CC-BY-4.0; real-time
  data comes under the GDM forecast terms. Earth Engine is free for research, education and non-profit use. It is also on BigQuery.
- **EC46 / SEAS5 on Open-Meteo** (`seasonal-api.open-meteo.com/v1/seasonal`): 51 members, 46 days or 7 months,
  near-surface only (850 hPa came back null); members are kept for 1 month.
- **Papers:**
  - 2610.42130: adding AI ensembles to a multi-model blend improves CRPS only when the models' errors
    differ. Calibrate each source, then the blend.
  - 2610.25545: AI ensembles beat IFS ENS on heat and cold records, but the wind gains shrink in the deep
    tails and at long leads.
  - 2506.14022: a learned weight mask for analog selection beats plain analogs on S2S, including upper winds.
  - 2412.15832: AIFS-CRPS.
  - 2607.05100: AIFS-SUBS, weeks 2–6.

## 2025–2026 AI research pass (2026-11-04)

Searched arXiv for papers submitted 2025-01 to 2026-11, plus Hugging Face and PyPI for availability.

| Finding | Adopted where | Why |
|---|---|---|
| Online conformal prediction gives guaranteed coverage for GenCast, NeuralGCM and AIFS-ENS, extremes included (2606.19642) | Phase 6 | Our main acceptance test is coverage; conformal guarantees it cheaply for any source |
| Warm water volume extends ENSO skill (the recharge oscillator; a 2025 diffusion ENSO model, 2511.01214, finds it learns this mechanism). Measured here: r at 9 months 0.07 → 0.37, at 12 months 0.04 → 0.27 | Phase 1 fetch, phase 4 | Measured gain from one extra index; 2025 deep-learning ENSO models (CTEFNet, 20 months, 2503.19502) need ocean fields we do not store |
| AI weather/climate models trained on history produce climates 15–30 years old (2509.22359); climate emulation is an out-of-distribution task (2605.22248) | Phase 5 bias on recent years; confirms the explicit trend term | Analogs + tested trend shift handle this; a pure AI generator would not |
| Probabilistic bias correction (PBC) doubles AIFS subseasonal skill and won ECMWF's 2025 S2S competition (2604.16238) | Phase 9, weeks 3–6 | Weeks 3–6 are currently pure analogs; this adds the known skill |
| Wind vectors need a joint (u, v) calibration; a normal × spline correction improves energy and variogram scores (2610.35137) | Phase 6 | Separate u and v inflation misses non-normal wind |
| Huge ACE2 ensembles + extreme value theory estimate very rare quantiles (2510.08893) | Phase 6 Pareto tails | Fixes the "analogs cap the tails" risk without a network |
| Simple backbones match GenCast and IFS ENS when given MAE pre-training then a short CRPS fine-tune (U-Cast 2604.09041; 2601.18111) | Phase 9 generator recipe | No bespoke architecture needed |
| Synthetic pre-training on 10,000 emulated years beats ERA5-only training at S2S, even for a linear model (2512.22814) | Phase 9 generator, learned analog mask | 35 ERA5 years is too few to train a long-lead network |
| ML model-analogs with a learned mask match initialized climate models at 1–10 years (2502.17583) | Phase 9 | Direct upgrade path for the analog core |
| Chronos-2 (2510.15821; `chronos-forecasting` 2.3.2, Apache-2.0 weights) | Phase 4 contender | Zero-shot time-series foundation model; cheap to test against the regression |

Looked at and not adopted:
- **AIFS ENS v2 open weights** (HF `ecmwf/aifs-ens-2.0`, CC-BY-4.0, May 2026). Self-made reforecasts would
  fall inside its 1979–2022 training years, so they would overstate skill.
- **km-scale diffusion downscaling** (Apeliotes 2607.17037, HiRO-ACE 2512.18224). Only needed if phase 8's
  spatial CV shows terrain error.
- **Diffusion/flow models** (Tyche, LaDCast, OmniCast, Swift). They solve global-field generation speed;
  we sample per point.
- **TabPFN-3.5.** Code is Apache-2.0, but the weight terms were not checked; Chronos-2 covers the same test.

## Cross-domain inspiration pass (2026-11-04)

The search covered fields other than weather, using the arXiv API for 2024–2026. Argon gets the
domain-free prompt in [argon-prompt-general.md](argon-prompt-general.md). The goal is to borrow
mechanisms, not to copy models. The "Our version" column is the adaptation.

| Field → mechanism | Our version | Verdict |
|---|---|---|
| Retrieval-augmented forecasting: similarity-only retrieval is redundant, so retrieval balances relevance against diversity (SARAF, 2606.04135) | Choose analog draws with a cap of draws per year (or max-marginal-relevance across years), so 1,000 samples do not come from 3 look-alike years. Report the effective number of years | **Adopt, phase 3**: tiny |
| Multi-series probabilistic forecasting: aggregate the marginals first, then rebuild the dependence with a copula (WIRED, 2608.12998) | After per-element calibration in phase 6, reorder each element's calibrated values to the rank order of the raw analog draws. Calibration then cannot break the joint shape | **Adopt, phase 6**: tiny, protects the energy and variogram scores |
| Hierarchical Bayes forecasting: share strength across levels instead of fitting each level alone (2606.23009) | Partial pooling of the trend, ENSO and QBO coefficients across neighbouring heights and grid points, shrinking towards a smooth profile, instead of a hard keep/drop at \|t\| ≥ 2 per point | **Adopt as phase 4 contender** |
| Multivariate extremes: spectral bootstrap draws a new radius from a GPD and keeps an observed angular "shape" (2509.26451) | Make the new extreme profiles by scaling the shape of real extreme shear events with a radius drawn from the GPD. Joint shape stays real while magnitudes go past the historical maximum | **Adopt, phase 6**: extends the GPD step |
| Test-time adaptation: adapt only on matured ground truth, i.e. outcomes whose time has passed (2605.17250) | Rule for online conformal and the logger: an update uses only verifications whose target time is in the past | **Adopt as protocol rule** |
| Forecast combination: under kernel scores, the linear pool helps most when members disagree (2412.09430). Bandit-style online weights for epidemic ensembles (2606.18575) | Phase 5 pool weights per lead band, updated online (exponential weights on CRPS). Log WN2 versus IFS disagreement as a diagnostic | Consider in phase 5. The archive is short, so start with fixed weights |
| Sample-cloud conformal ellipsoids: joint regions from the covariance of the current samples (SPACE, 2608.17333; kernel score, 2604.21595) | Check joint coverage of the whole shear vector in EOF space of the current sample set, as a phase 6 *diagnostic* | Diagnostic only |
| Engression: generator Y = f(X, ε) trained with the energy score. Pre-additive noise gives principled extrapolation (Shen & Meinshausen 2024; 2607.27723) | If the phase 9 ML generator is built: a small MLP trained with the energy score, with trend and driver inputs placed before the noise so it can extrapolate past the training range. Sampling is fast | Phase 9 option, replaces the diffusion-style recipe |
| Decision-aware training: energy score plus a downstream cost term, still proper (2607.01171) | Weight the energy score towards the heights and shear that matter most for the vehicle in `dynamics` | Phase 9 option |
| Robot movement primitives / functional flow matching: generate coefficients of a smooth basis, not raw points (FODMP 2603.24806, SFM 2508.13831) | The generator outputs EOF or B-spline coefficients, so smoothness and channel relations hold by construction | Phase 9 option |
| Finance curve scenarios: semiparametric bootstrap = structural model + resampled residuals (2606.11859) | Confirms the current design: shifted analogs are already that | Keep as is |
| Prior-fitted networks / one-shot world models trained on a synthetic prior (2409.14084, 2603.29475) | — | Skip: 35 independent years and an interpretability requirement favour the analog core |

## Argon cross-domain report (2026-11-04)

Input: *Cross-Domain Probabilistic Curve Prediction* (Argon, from `argon-prompt-general.md`). It gives 10
principles (P1 rank-copula coupling; P2 work in difference or spectral space; P3 Engression-style
extrapolation; P4 GPD tails on neighbour differences; P5 multi-fidelity distribution matching; P6 retrieve
then correct; P7 linear pool with shrunk weights; P8 stratified driver draws; P9 MinT reconciliation; P10
whole-cloud conformal scaling) and 5 hybrids, ranked SCAT-RCT > HRQC-LRLM > SCV-FOBT > MF-HPOSF > SP-ICFA.
What went into the plan: SCAT-RCT, adapted, becomes *Optimal structure* S0–S7 in PLAN.md. The other hybrids
become options 2B, 2C, 3B and 3D. Engression (3A) and multi-fidelity station transfer (3C) are my own
additions.

Checked on the arXiv API, all exist and match what the report says they do: 2609.25980 (training-free
coupling of marginals), 2606.30821 (mean-residual downscaling is biased and too narrow), 2610.33482 (CD-FFM),
2608.13886 (forecast combination = reconciliation), 2607.12730 (input-uncertainty propagation),
2509.04203 (Gibbs-posterior stacking), 2610.42130 (AI ensembles in a multi-model blend),
2606.19412 (spectral retrieval), 2608.19849 (DExtrI), 2602.10182 (CSig-MMD), 2510.13763 (PriorGuide),
2611.01849 (FADE), 2604.25008 (EVT generative), 2607.27160 (low-rank EOF state-space).

Caveats: the report's latencies are estimates from FLOP counts, not measurements. Its falsification
thresholds (3 % variogram score, 15 % tail error, 5 % mode loss, 2 % codebook loss) are its own proposals. Most
sources are 2026 preprints, and their gains come from other domains. The extracted text had `[span_xx]`
artifacts, so a few citations could not be matched.

## Could not verify

- The report's "Earth-GRAM 2026" technical memo and catalogue number MFS-32780-2.
- Several 2026 arXiv IDs cited for FGN/sCM/CopulaCPTS variants. Treat their numbers as unconfirmed.
- Argon cross-domain report: performance numbers quoted from its sources, and its latency estimates.

## Sources

- https://github.com/google-research/arco-era5
- https://registry.opendata.aws/earthmover-era5/
- https://open-meteo.com/en/docs/ensemble-api
- https://sciencebusiness.net/network-updates/ecmwf-makes-its-entire-real-time-catalogue-open-all
- https://forum.ecmwf.int/t/what-does-fully-open-data-status-in-2025-mean/12777
- https://forum.ecmwf.int/t/severe-and-persistent-queue-delays-for-era5-hourly-data-pressure-levels-via-cds-api/14836
- https://forum.ecmwf.int/t/new-dataset-published-in-cds-era5-time-series-data-on-pressure-levels-from-1940-to-present/15220
- https://ntrs.nasa.gov/api/citations/20230015519/downloads/GRAM%20Suite%20Presentation%202023%20GRAM%20Virtual%20Workshop.pdf
- https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive
- https://pypi.org/project/engression/
- https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/doc/igra2-station-list.txt
- https://aiaa.org/events/2026-international-rocket-engineering-competition-irec/
- https://aiaa.org/events/2025-international-rocket-engineering-competition-irec/
- https://www.yahoo.com/news/spaceport-america-cup-moving-midland-010203838.html
- https://www.climate.ox.ac.uk/node/2613651
- https://forum.ecmwf.int/t/what-is-the-number-of-items-limit/1369
- https://arxiv.org/pdf/2604.19023
- https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
- https://www.cpc.ncep.noaa.gov/data/indices/qbo.u30.index
- https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/doc/igra2-derived-format.txt
- https://scoringrules.readthedocs.io/en/latest/
- https://open-meteo.com/en/docs/historical-forecast-api
- https://open-meteo.com/en/docs/google-weathernext-api
- https://open-meteo.com/en/docs/seasonal-forecast-api
- https://developers.google.com/earth-engine/datasets/catalog/projects_gcp-public-data-weathernext_assets_weathernext_2_0_0
- https://arxiv.org/abs/2610.42130
- https://arxiv.org/abs/2610.25545
- https://arxiv.org/abs/2506.14022
- https://arxiv.org/abs/2412.15832
- https://arxiv.org/abs/2607.05100
- https://www.pmel.noaa.gov/tao/wwv/data/wwv.dat
- https://huggingface.co/ecmwf/aifs-ens-2.0
- https://huggingface.co/amazon/chronos-2
- https://huggingface.co/allenai/ACE2-ERA5
- arXiv 2606.19642, 2604.16238, 2610.35137, 2510.08893, 2509.22359, 2605.22248, 2512.22814, 2604.09041,
  2601.18111, 2502.17583, 2503.19502, 2511.01214, 2510.15821, 2607.17037, 2512.18224
- Cross-domain pass: arXiv 2606.04135, 2608.12998, 2606.23009, 2509.26451, 2605.17250, 2412.09430,
  2606.18575, 2608.17333, 2604.21595, 2607.27723, 2607.01171, 2603.24806, 2508.13831, 2606.11859, 2409.14084
- Argon cross-domain report: arXiv 2609.25980, 2606.30821, 2610.33482, 2608.13886, 2607.12730, 2509.04203, 2610.42130, 2606.19412, 2608.19849, 2602.10182, 2510.13763, 2611.01849, 2604.25008, 2607.27160, 2307.00835, 2410.12557, 2507.00514
